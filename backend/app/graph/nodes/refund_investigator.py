"""Deterministic investigator for evidence-supported refund leakage patterns."""

from __future__ import annotations

from math import ceil

import pandas as pd

from app.config import settings
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
    normalize_timestamp_column,
    update_plan_item_status,
)

HIGH_REFUND_RATE = 0.10
ROBUST_OUTLIER_Z_SCORE = 3.5


def _resolve_column(df: pd.DataFrame, aliases: tuple[str, ...]) -> str | None:
    normalized = {str(column).strip().lower(): str(column) for column in df.columns}
    return next((normalized[alias] for alias in aliases if alias in normalized), None)


def _load_refund_frames(state: CaseState) -> tuple[pd.DataFrame | None, list[str], list[str]]:
    frames: list[pd.DataFrame] = []
    dataset_ids: list[str] = []
    errors: list[str] = []
    for dataset in find_datasets(state, ("refund",)):
        try:
            frame = load_csv_dataset(dataset).copy()
        except DatasetLoadError as exc:
            errors.append(str(exc))
            continue
        frame["_source_dataset_id"] = dataset.dataset_id
        frame["_source_row"] = frame.index.astype(str)
        frames.append(frame)
        dataset_ids.append(dataset.dataset_id)

    if not frames:
        return None, dataset_ids, errors
    return pd.concat(frames, ignore_index=True, sort=False), dataset_ids, errors


def _record_keys(df: pd.DataFrame, identifier_column: str | None) -> pd.Series:
    fallback = df["_source_dataset_id"].astype(str) + ":" + df["_source_row"].astype(str)
    if identifier_column is None:
        return fallback
    identifiers = df[identifier_column].astype("string")
    return identifiers.where(identifiers.notna() & (identifiers.str.strip() != ""), fallback).astype(str)


def _robust_outlier_mask(amounts: pd.Series) -> tuple[pd.Series, float]:
    if len(amounts) < 4:
        return pd.Series(False, index=amounts.index), 0.0

    median = amounts.median()
    median_absolute_deviation = (amounts - median).abs().median()
    if median_absolute_deviation > 0:
        modified_z_score = 0.6745 * (amounts - median).abs() / median_absolute_deviation
        return modified_z_score > ROBUST_OUTLIER_Z_SCORE, float(modified_z_score.max())

    lower_quartile, upper_quartile = amounts.quantile([0.25, 0.75])
    interquartile_range = upper_quartile - lower_quartile
    if interquartile_range <= 0:
        return pd.Series(False, index=amounts.index), 0.0
    threshold = upper_quartile + 1.5 * interquartile_range
    return amounts > threshold, float((amounts.max() / threshold) if threshold else 0.0)


def _spike_mask(
    df: pd.DataFrame, timestamps: pd.Series, amounts: pd.Series
) -> tuple[pd.Series, float, dict[str, float] | None]:
    valid_timestamps = timestamps.notna()
    if valid_timestamps.sum() < 4:
        return pd.Series(False, index=df.index), 0.0, None

    daily = pd.DataFrame(
        {
            "day": timestamps[valid_timestamps].dt.floor("D"),
            "amount": amounts[valid_timestamps],
        }
    ).groupby("day").agg(refund_count=("amount", "size"), refund_amount=("amount", "sum"))
    if len(daily) < 4:
        return pd.Series(False, index=df.index), 0.0, None

    def upper_control_limit(values: pd.Series) -> float:
        median = values.median()
        mad = (values - median).abs().median()
        if mad > 0:
            return float(median + 3 * 1.4826 * mad)
        return float(values.quantile(0.75) + 1.5 * (values.quantile(0.75) - values.quantile(0.25)))

    amount_limit = upper_control_limit(daily["refund_amount"])
    count_limit = upper_control_limit(daily["refund_count"])
    spike_days = daily.index[
        (daily["refund_amount"] > amount_limit) | (daily["refund_count"] > count_limit)
    ]
    if spike_days.empty:
        return pd.Series(False, index=df.index), 0.0, None

    mask = timestamps.dt.floor("D").isin(spike_days).fillna(False)
    peak_amount_ratio = float(daily.loc[spike_days, "refund_amount"].max() / max(amount_limit, 1))
    peak_count_ratio = float(daily.loc[spike_days, "refund_count"].max() / max(count_limit, 1))
    return (
        mask,
        min(1.0, max(peak_amount_ratio, peak_count_ratio)),
        {
            "spike_day_count": float(len(spike_days)),
            "amount_control_limit": round(amount_limit, 2),
            "count_control_limit": round(count_limit, 2),
        },
    )


def _successful_payment_amount(state: CaseState) -> tuple[float | None, list[str]]:
    totals: list[float] = []
    dataset_ids: list[str] = []
    for dataset in find_datasets(state, ("payment", "transaction", "order")):
        try:
            frame = load_csv_dataset(dataset)
        except DatasetLoadError:
            continue
        amount_column = _resolve_column(frame, ("amount", "payment_amount", "transaction_amount"))
        if amount_column is None:
            continue
        amounts = normalize_numeric_column(frame, amount_column)
        status_column = _resolve_column(frame, ("status", "payment_status"))
        if status_column is not None:
            status = frame[status_column].astype("string").str.lower().str.strip()
            successful = status.isin({"captured", "success", "successful", "paid"})
            if not successful.any():
                continue
            amounts = amounts[successful]
        valid_amounts = amounts[amounts > 0]
        if not valid_amounts.empty:
            totals.append(float(valid_amounts.sum()))
            dataset_ids.append(dataset.dataset_id)
    return (sum(totals) if totals else None), dataset_ids


def _insufficient_evidence_update(
    state: CaseState, description: str, *, load_errors: list[str] | None = None
) -> dict:
    timeline = [
        build_timeline_event(
            title="Refund Investigation Started",
            description="Loading refund records for deterministic analysis.",
            stage="refund_investigation",
            progress=0.2,
        ),
        build_timeline_event(
            title="Insufficient Refund Evidence",
            description=description,
            stage="refund_investigation",
            progress=0.35,
        ),
    ]
    if load_errors:
        timeline.append(
            build_timeline_event(
                title="Refund Dataset Access Issue",
                description="; ".join(load_errors),
                stage="refund_investigation",
                progress=0.35,
            )
        )
    return {
        "status": InvestigationStatus.INVESTIGATING,
        "current_stage": "refund_investigation",
        "confidence": 0.0,
        "requires_more_evidence": False,
        "investigation_plan": update_plan_item_status(
            state, InvestigatorName.REFUND, PlanItemStatus.COMPLETED
        ),
        "completed_investigations": [InvestigatorName.REFUND],
        "evidence": [],
        "case_files": [],
        "timeline": timeline,
    }


def refund_investigator_node(state: CaseState) -> dict:
    """Detect supported refund leakage patterns using temporary pandas DataFrames."""

    refunds, refund_dataset_ids, load_errors = _load_refund_frames(state)
    if refunds is None or refunds.empty:
        return _insufficient_evidence_update(
            state,
            "No readable refund rows are available; refund leakage cannot be determined.",
            load_errors=load_errors,
        )

    amount_column = _resolve_column(refunds, ("amount", "refund_amount", "refund_value"))
    if amount_column is None:
        return _insufficient_evidence_update(
            state,
            "Refund records do not include an amount field required for financial analysis.",
            load_errors=load_errors,
        )

    identifier_column = _resolve_column(refunds, ("refund_id", "id"))
    customer_column = _resolve_column(refunds, ("customer_id", "customer", "customerid"))
    order_column = _resolve_column(refunds, ("order_id", "payment_id", "order", "payment"))
    timestamp_column = _resolve_column(
        refunds, ("created_at", "refund_date", "timestamp", "created")
    )

    refunds = refunds.copy()
    source_refund_row_count = len(refunds)
    refunds["_record_key"] = _record_keys(refunds, identifier_column)
    refunds["_amount"] = normalize_numeric_column(refunds, amount_column)
    refunds = refunds.loc[refunds["_amount"].notna() & (refunds["_amount"] >= 0)].copy()
    if refunds.empty:
        return _insufficient_evidence_update(
            state,
            "Refund amount values are malformed or unavailable after validation.",
            load_errors=load_errors,
        )

    evidence: list[Evidence] = []
    flagged_record_keys: set[str] = set()
    signal_strengths: list[float] = []
    payment_total, payment_dataset_ids = _successful_payment_amount(state)

    if payment_total and payment_total > 0:
        refund_total = float(refunds["_amount"].sum())
        refund_rate = refund_total / payment_total
        if refund_rate >= HIGH_REFUND_RATE:
            record_keys = refunds["_record_key"].tolist()
            flagged_record_keys.update(record_keys)
            signal_strengths.append(min(1.0, refund_rate / HIGH_REFUND_RATE))
            evidence.append(
                Evidence(
                    investigator=InvestigatorName.REFUND,
                    rule="high_refund_rate",
                    summary="Refund value is materially high relative to successful payment value.",
                    dataset_ids=refund_dataset_ids + payment_dataset_ids,
                    record_ids=record_keys,
                    metrics=evidence_metrics(
                        refund_total=round(refund_total, 2),
                        successful_payment_total=round(payment_total, 2),
                        refund_rate=round(refund_rate, 4),
                        materiality_threshold=HIGH_REFUND_RATE,
                    ),
                    confidence=0.0,
                    estimated_amount=refund_total,
                )
            )

    if customer_column is not None:
        customer_values = refunds[customer_column].astype("string").str.strip()
        usable_customers = customer_values.notna() & (customer_values != "")
        customer_counts = customer_values[usable_customers].value_counts()
        if customer_counts.size >= 2:
            lower_quartile, upper_quartile = customer_counts.quantile([0.25, 0.75])
            threshold = max(2, ceil(upper_quartile + 1.5 * (upper_quartile - lower_quartile)))
            repeat_customers = customer_counts[customer_counts >= threshold].index
            repeat_mask = customer_values.isin(repeat_customers).fillna(False)
            if repeat_mask.any():
                record_keys = refunds.loc[repeat_mask, "_record_key"].tolist()
                flagged_record_keys.update(record_keys)
                repeat_ratio = float(repeat_mask.mean())
                signal_strengths.append(min(1.0, repeat_ratio * 2))
                evidence.append(
                    Evidence(
                        investigator=InvestigatorName.REFUND,
                        rule="repeat_customer_refunds",
                        summary="A dataset-relative outlier group of customers has repeated refunds.",
                        dataset_ids=refund_dataset_ids,
                        record_ids=record_keys,
                        metrics=evidence_metrics(
                            affected_customer_count=int(len(repeat_customers)),
                            repeat_refund_threshold=threshold,
                            affected_refund_count=int(repeat_mask.sum()),
                        ),
                        confidence=0.0,
                        estimated_amount=float(refunds.loc[repeat_mask, "_amount"].sum()),
                    )
                )

    outlier_mask, max_outlier_score = _robust_outlier_mask(refunds["_amount"])
    if outlier_mask.any():
        record_keys = refunds.loc[outlier_mask, "_record_key"].tolist()
        flagged_record_keys.update(record_keys)
        signal_strengths.append(min(1.0, max_outlier_score / ROBUST_OUTLIER_Z_SCORE))
        evidence.append(
            Evidence(
                investigator=InvestigatorName.REFUND,
                rule="refund_amount_outliers",
                summary="Refund amounts include robust statistical outliers.",
                dataset_ids=refund_dataset_ids,
                record_ids=record_keys,
                metrics=evidence_metrics(
                    outlier_count=int(outlier_mask.sum()),
                    robust_outlier_score=round(max_outlier_score, 3),
                    threshold=ROBUST_OUTLIER_Z_SCORE,
                ),
                confidence=0.0,
                estimated_amount=float(refunds.loc[outlier_mask, "_amount"].sum()),
            )
        )

    if order_column is not None:
        order_values = refunds[order_column].astype("string").str.strip()
        usable_orders = order_values.notna() & (order_values != "")
        repeated_orders = order_values[usable_orders].value_counts()
        repeated_orders = repeated_orders[repeated_orders >= 2].index
        repeated_order_mask = order_values.isin(repeated_orders).fillna(False)
        if repeated_order_mask.any():
            record_keys = refunds.loc[repeated_order_mask, "_record_key"].tolist()
            flagged_record_keys.update(record_keys)
            repeated_order_ratio = float(repeated_order_mask.mean())
            signal_strengths.append(min(1.0, repeated_order_ratio * 2))
            evidence.append(
                Evidence(
                    investigator=InvestigatorName.REFUND,
                    rule="repeated_order_refunds",
                    summary="Multiple refunds are associated with the same order or payment reference.",
                    dataset_ids=refund_dataset_ids,
                    record_ids=record_keys,
                    metrics=evidence_metrics(
                        repeated_order_count=int(len(repeated_orders)),
                        affected_refund_count=int(repeated_order_mask.sum()),
                    ),
                    confidence=0.0,
                    estimated_amount=float(refunds.loc[repeated_order_mask, "_amount"].sum()),
                )
            )

    if timestamp_column is not None:
        timestamps = normalize_timestamp_column(refunds, timestamp_column)
        spike_mask, spike_strength, spike_metrics = _spike_mask(refunds, timestamps, refunds["_amount"])
        if spike_mask.any():
            record_keys = refunds.loc[spike_mask, "_record_key"].tolist()
            flagged_record_keys.update(record_keys)
            signal_strengths.append(spike_strength)
            evidence.append(
                Evidence(
                    investigator=InvestigatorName.REFUND,
                    rule="refund_spike",
                    summary="Refund activity exceeds a robust dataset-derived daily control limit.",
                    dataset_ids=refund_dataset_ids,
                    record_ids=record_keys,
                    metrics=spike_metrics or {},
                    confidence=0.0,
                    estimated_amount=float(refunds.loc[spike_mask, "_amount"].sum()),
                )
            )
    else:
        timestamps = pd.Series(pd.NaT, index=refunds.index, dtype="datetime64[ns, UTC]")

    amount_completeness = len(refunds) / max(1, source_refund_row_count)
    confidence = calculate_confidence(
        required_column_coverage=amount_completeness,
        row_count=len(refunds),
        evidence_count=len(evidence),
        signal_strength=max(signal_strengths, default=0.0),
        corroborating_dataset_count=(1 if payment_dataset_ids else 0),
    )
    evidence = [item.model_copy(update={"confidence": confidence}) for item in evidence]

    supporting_datasets = find_datasets(state, ("payment", "transaction", "order", "customer"))
    requires_refinement = bool(evidence) and (
        confidence < settings.confidence_threshold
        and state.get("retry_count", 0) < state.get("max_retry_count", 1)
        and bool(supporting_datasets)
    )
    final_plan_status = PlanItemStatus.RUNNING if requires_refinement else PlanItemStatus.COMPLETED

    timeline = [
        build_timeline_event(
            title="Refund Investigation Started",
            description="Analyzing refund records with deterministic financial controls.",
            stage="refund_investigation",
            progress=0.2,
        )
    ]
    case_files = []
    if evidence:
        flagged_rows = refunds[refunds["_record_key"].isin(flagged_record_keys)]
        flagged_total = float(flagged_rows["_amount"].sum())
        valid_flagged_timestamps = timestamps.loc[flagged_rows.index].dropna()
        if valid_flagged_timestamps.empty:
            monthly_loss = 0.0
        else:
            observed_days = max(
                1, (valid_flagged_timestamps.max() - valid_flagged_timestamps.min()).days + 1
            )
            monthly_loss = round(flagged_total * 30 / observed_days, 2)
        case_files = [
            build_case_file(
                investigation_id=state["investigation_id"],
                case_file_id=f"{state['investigation_id']}:refund",
                title="Refund leakage signals detected",
                confidence=confidence,
                evidence=evidence,
                estimated_monthly_loss=monthly_loss,
                priority=1,
                recommendation=(
                    "Review the flagged refund records and require approval controls for "
                    "repeat customers, repeated order references, and exceptional refund amounts."
                ),
            )
        ]
        timeline.append(
            build_timeline_event(
                title="Refund Patterns Detected",
                description=(
                    f"{len(evidence)} deterministic signal(s) identified across "
                    f"{len(flagged_rows)} traceable refund record(s)."
                ),
                stage="refund_investigation",
                progress=0.35,
            )
        )
    else:
        timeline.append(
            build_timeline_event(
                title="No Meaningful Refund Leakage Detected",
                description=(
                    "Available refund records did not trigger the configured "
                    "dataset-relative detection controls."
                ),
                stage="refund_investigation",
                progress=0.35,
            )
        )

    timeline.append(
        build_timeline_event(
            title=f"Refund Confidence: {confidence:.0%}",
            description="Confidence is calculated from data completeness, sample adequacy, signal strength, and corroboration.",
            stage="refund_investigation",
            progress=0.4,
        )
    )
    if requires_refinement:
        timeline.append(
            build_timeline_event(
                title="Additional Refund Evidence Required",
                description="A bounded refinement will use supporting datasets before one rerun.",
                stage="refund_refinement_required",
                progress=0.42,
            )
        )

    return {
        "status": InvestigationStatus.INVESTIGATING,
        "current_stage": "refund_investigation",
        "confidence": confidence,
        "investigation_plan": update_plan_item_status(
            state, InvestigatorName.REFUND, final_plan_status
        ),
        "completed_investigations": []
        if requires_refinement
        else [InvestigatorName.REFUND],
        "evidence": evidence,
        "case_files": case_files,
        "requires_more_evidence": requires_refinement,
        "timeline": timeline,
    }
