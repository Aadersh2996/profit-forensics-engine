"""Deterministic investigator for evidence-supported discount leakage."""

from __future__ import annotations

from math import ceil

import pandas as pd

from app.graph.state import CaseState
from app.models.schemas import Evidence, InvestigationStatus, InvestigatorName, PlanItemStatus
from app.services.investigators.base import (
    DatasetLoadError,
    build_case_file,
    build_timeline_event,
    calculate_confidence,
    evidence_metrics,
    find_datasets,
    load_csv_dataset,
    normalize_numeric_column,
    update_plan_item_status,
)


def _column(df: pd.DataFrame, aliases: tuple[str, ...]) -> str | None:
    columns = {str(column).lower().strip(): str(column) for column in df.columns}
    return next((columns[name] for name in aliases if name in columns), None)


def discount_investigator_node(state: CaseState) -> dict:
    """Detect unusual discount magnitude and concentration without claiming abuse."""

    datasets = find_datasets(state, ("discount", "coupon", "promotion"))
    frames: list[pd.DataFrame] = []
    dataset_ids: list[str] = []
    for dataset in datasets:
        try:
            frame = load_csv_dataset(dataset).copy()
        except DatasetLoadError:
            continue
        frame["_dataset_id"] = dataset.dataset_id
        frame["_row"] = frame.index.astype(str)
        frames.append(frame)
        dataset_ids.append(dataset.dataset_id)

    def insufficient(description: str) -> dict:
        return {
            "status": InvestigationStatus.INVESTIGATING,
            "current_stage": "discount_investigation",
            "confidence": 0.0,
            "requires_more_evidence": False,
            "investigation_plan": update_plan_item_status(
                state, InvestigatorName.DISCOUNT, PlanItemStatus.COMPLETED
            ),
            "completed_investigations": [InvestigatorName.DISCOUNT],
            "evidence": [],
            "case_files": [],
            "timeline": [
                build_timeline_event(title="Discount Investigation Started", description="Loading discount records.", stage="discount_investigation", progress=0.2),
                build_timeline_event(title="Insufficient Discount Evidence", description=description, stage="discount_investigation", progress=0.35),
            ],
        }

    if not frames:
        return insufficient("No readable discount rows are available for analysis.")
    df = pd.concat(frames, ignore_index=True, sort=False)
    amount_column = _column(df, ("discount_amount", "discount", "amount"))
    original_column = _column(df, ("original_amount", "list_price", "gross_amount"))
    final_column = _column(df, ("final_amount", "net_amount", "paid_amount"))
    if amount_column is not None:
        df["_discount"] = normalize_numeric_column(df, amount_column)
    elif original_column is not None and final_column is not None:
        df["_discount"] = normalize_numeric_column(df, original_column) - normalize_numeric_column(df, final_column)
    else:
        return insufficient("A discount amount or an original-and-final amount pair is required.")
    source_row_count = len(df)
    df = df.loc[df["_discount"].notna() & (df["_discount"] >= 0)].copy()
    if df.empty:
        return insufficient("Discount values are malformed or unavailable after validation.")
    id_column = _column(df, ("discount_id", "id", "order_id", "payment_id"))
    df["_record_key"] = (
        df[id_column].astype("string").fillna("").str.strip()
        if id_column is not None
        else ""
    )
    fallback = df["_dataset_id"].astype(str) + ":" + df["_row"].astype(str)
    df.loc[df["_record_key"] == "", "_record_key"] = fallback
    evidence: list[Evidence] = []
    flagged: set[str] = set()
    strengths: list[float] = []

    if len(df) >= 4:
        median = df["_discount"].median()
        mad = (df["_discount"] - median).abs().median()
        if mad > 0:
            score = 0.6745 * (df["_discount"] - median).abs() / mad
            outlier_mask = score > 3.5
            max_score = float(score.max())
        else:
            q1, q3 = df["_discount"].quantile([0.25, 0.75])
            threshold = q3 + 1.5 * (q3 - q1)
            outlier_mask = df["_discount"] > threshold
            max_score = float(df["_discount"].max() / max(threshold, 1))
        if outlier_mask.any():
            keys = df.loc[outlier_mask, "_record_key"].tolist()
            flagged.update(keys)
            strengths.append(min(1.0, max_score / 3.5))
            evidence.append(Evidence(investigator=InvestigatorName.DISCOUNT, rule="discount_amount_outliers", summary="Discount values include robust statistical outliers.", dataset_ids=dataset_ids, record_ids=keys, metrics=evidence_metrics(affected_discount_count=int(outlier_mask.sum()), robust_score=round(max_score, 3)), confidence=0.0, estimated_amount=float(df.loc[outlier_mask, "_discount"].sum())))

    customer_column = _column(df, ("customer_id", "customer", "customerid"))
    if customer_column is not None:
        customers = df[customer_column].astype("string").str.strip()
        counts = customers[customers.notna() & (customers != "")].value_counts()
        if len(counts) >= 2:
            q1, q3 = counts.quantile([0.25, 0.75])
            threshold = max(2, ceil(q3 + 1.5 * (q3 - q1)))
            heavy = counts[counts >= threshold].index
            mask = customers.isin(heavy).fillna(False)
            if mask.any():
                keys = df.loc[mask, "_record_key"].tolist()
                flagged.update(keys)
                strengths.append(min(1.0, float(mask.mean()) * 2))
                evidence.append(Evidence(investigator=InvestigatorName.DISCOUNT, rule="repeated_heavy_discount_usage", summary="A dataset-relative outlier group of customers repeatedly receives discounts.", dataset_ids=dataset_ids, record_ids=keys, metrics=evidence_metrics(affected_customer_count=len(heavy), repeat_usage_threshold=threshold), confidence=0.0, estimated_amount=float(df.loc[mask, "_discount"].sum())))
            customer_totals = df.assign(_customer=customers).groupby("_customer")["_discount"].sum()
            customer_totals = customer_totals[customer_totals.index.notna() & (customer_totals.index != "")]
            if len(customer_totals) >= 2 and customer_totals.sum() > 0:
                top_customer = customer_totals.idxmax()
                top_share = float(customer_totals.max() / customer_totals.sum())
                expected_share = 1 / len(customer_totals)
                if top_share >= 3 * expected_share:
                    mask = customers == top_customer
                    keys = df.loc[mask, "_record_key"].tolist()
                    flagged.update(keys)
                    strengths.append(min(1.0, top_share / min(1.0, 3 * expected_share)))
                    evidence.append(Evidence(investigator=InvestigatorName.DISCOUNT, rule="discount_concentration", summary="Discount value is materially concentrated in one customer relative to the dataset distribution.", dataset_ids=dataset_ids, record_ids=keys, metrics=evidence_metrics(top_customer_share=round(top_share, 4), expected_equal_share=round(expected_share, 4)), confidence=0.0, estimated_amount=float(df.loc[mask, "_discount"].sum())))

    confidence = calculate_confidence(required_column_coverage=len(df) / max(1, source_row_count), row_count=len(df), evidence_count=len(evidence), signal_strength=max(strengths, default=0.0))
    evidence = [item.model_copy(update={"confidence": confidence}) for item in evidence]
    timeline = [build_timeline_event(title="Discount Investigation Started", description="Analyzing discount records with deterministic distribution controls.", stage="discount_investigation", progress=0.2)]
    case_files = []
    if evidence:
        rows = df[df["_record_key"].isin(flagged)]
        loss = float(rows["_discount"].sum())
        case_files = [build_case_file(investigation_id=state["investigation_id"], title="Discount leakage signals detected", confidence=confidence, evidence=evidence, estimated_monthly_loss=loss, priority=2, recommendation="Review the flagged discount cohort and add eligibility, approval, or usage controls where the evidence supports intervention.")]
        timeline.append(build_timeline_event(title="Discount Patterns Detected", description=f"{len(evidence)} measurable discount signal(s) were identified.", stage="discount_investigation", progress=0.35))
    else:
        timeline.append(build_timeline_event(title="No Meaningful Discount Leakage Detected", description="Available discounts did not trigger the supported concentration or outlier controls.", stage="discount_investigation", progress=0.35))
    timeline.append(build_timeline_event(title=f"Discount Confidence: {confidence:.0%}", description="Confidence reflects data completeness, sample adequacy, and evidence strength.", stage="discount_investigation", progress=0.4))
    return {"status": InvestigationStatus.INVESTIGATING, "current_stage": "discount_investigation", "confidence": confidence, "investigation_plan": update_plan_item_status(state, InvestigatorName.DISCOUNT, PlanItemStatus.COMPLETED), "completed_investigations": [InvestigatorName.DISCOUNT], "evidence": evidence, "case_files": case_files, "requires_more_evidence": False, "timeline": timeline}
