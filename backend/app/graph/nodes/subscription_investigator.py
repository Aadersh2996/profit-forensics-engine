"""Deterministic investigator for supported subscription leakage signals."""

from __future__ import annotations

import pandas as pd

from app.graph.state import CaseState
from app.models.schemas import Evidence, InvestigationStatus, InvestigatorName, PlanItemStatus
from app.services.investigators.base import (
    DatasetLoadError, build_case_file, build_timeline_event, calculate_confidence,
    evidence_metrics, find_datasets, load_csv_dataset, normalize_numeric_column,
    update_plan_item_status,
)


def _column(df: pd.DataFrame, aliases: tuple[str, ...]) -> str | None:
    values = {str(column).lower().strip(): str(column) for column in df.columns}
    return next((values[name] for name in aliases if name in values), None)


def subscription_investigator_node(state: CaseState) -> dict:
    """Detect repeated renewal failures and cancellation concentration from supplied records."""
    frames: list[pd.DataFrame] = []
    dataset_ids: list[str] = []
    for dataset in find_datasets(state, ("subscription",)):
        try:
            frame = load_csv_dataset(dataset).copy()
        except DatasetLoadError:
            continue
        frame["_dataset_id"], frame["_row"] = dataset.dataset_id, frame.index.astype(str)
        frames.append(frame)
        dataset_ids.append(dataset.dataset_id)

    def finish(confidence: float, evidence: list[Evidence], files: list, title: str, description: str) -> dict:
        return {"status": InvestigationStatus.INVESTIGATING, "current_stage": "subscription_investigation", "confidence": confidence, "investigation_plan": update_plan_item_status(state, InvestigatorName.SUBSCRIPTION, PlanItemStatus.COMPLETED), "completed_investigations": [InvestigatorName.SUBSCRIPTION], "evidence": evidence, "case_files": files, "requires_more_evidence": False, "timeline": [build_timeline_event(title="Subscription Investigation Started", description="Analyzing subscription states and renewal outcomes.", stage="subscription_investigation", progress=0.2), build_timeline_event(title=title, description=description, stage="subscription_investigation", progress=0.35), build_timeline_event(title=f"Subscription Confidence: {confidence:.0%}", description="Confidence reflects available state fields, sample adequacy, and corroborating signals.", stage="subscription_investigation", progress=0.4)]}

    if not frames:
        return finish(0.0, [], [], "Insufficient Subscription Evidence", "No readable subscription rows are available for analysis.")
    df = pd.concat(frames, ignore_index=True, sort=False)
    status_column = _column(df, ("status", "subscription_status", "renewal_status"))
    if status_column is None:
        return finish(0.0, [], [], "Insufficient Subscription Evidence", "Subscription status is required for leakage analysis.")
    amount_column = _column(df, ("amount", "plan_amount", "subscription_amount"))
    customer_column = _column(df, ("customer_id", "customer", "customerid"))
    id_column = _column(df, ("subscription_id", "id"))
    df["_status"] = df[status_column].astype("string").str.lower().str.strip()
    df["_amount"] = normalize_numeric_column(df, amount_column).fillna(0) if amount_column else 0.0
    fallback = df["_dataset_id"].astype(str) + ":" + df["_row"].astype(str)
    df["_record_key"] = df[id_column].astype("string").fillna("").str.strip() if id_column else fallback
    df.loc[df["_record_key"] == "", "_record_key"] = fallback
    evidence: list[Evidence] = []
    flagged: set[str] = set()
    strengths: list[float] = []

    def add(rule: str, summary: str, mask: pd.Series, **metrics: object) -> None:
        if not mask.any(): return
        keys = df.loc[mask, "_record_key"].tolist(); flagged.update(keys)
        evidence.append(Evidence(investigator=InvestigatorName.SUBSCRIPTION, rule=rule, summary=summary, dataset_ids=dataset_ids, record_ids=keys, metrics=evidence_metrics(affected_subscription_count=int(mask.sum()), **metrics), confidence=0.0, estimated_amount=float(df.loc[mask, "_amount"].clip(lower=0).sum())))
        strengths.append(min(1.0, float(mask.mean()) * 3))

    failure_mask = df["_status"].isin({"failed", "payment_failed", "renewal_failed"})
    add("renewal_failures", "Subscription renewals failed and are candidates for controlled recovery.", failure_mask)
    cancellation_mask = df["_status"].isin({"cancelled", "canceled"})
    add("cancellation_behavior", "Cancellation records represent measurable retention or recovery candidates.", cancellation_mask)
    if customer_column is not None:
        customers = df[customer_column].astype("string").str.strip()
        failed_counts = customers[failure_mask & customers.notna() & (customers != "")].value_counts()
        repeat_customers = failed_counts[failed_counts >= 2].index
        add("repeated_renewal_failures", "Some customers have repeated subscription renewal failures.", (failure_mask & customers.isin(repeat_customers)).fillna(False), affected_customer_count=len(repeat_customers))
    confidence = calculate_confidence(required_column_coverage=(1 + int(amount_column is not None) + int(customer_column is not None)) / 3, row_count=len(df), evidence_count=len(evidence), signal_strength=max(strengths, default=0.0))
    evidence = [item.model_copy(update={"confidence": confidence}) for item in evidence]
    if not evidence:
        return finish(confidence, [], [], "No Meaningful Subscription Leakage Detected", "Available subscription records did not trigger supported renewal or cancellation controls.")
    rows = df[df["_record_key"].isin(flagged)]
    file = build_case_file(investigation_id=state["investigation_id"], title="Subscription recovery signals detected", confidence=confidence, evidence=evidence, estimated_monthly_loss=float(rows["_amount"].clip(lower=0).sum()), priority=2, recommendation="Prioritize recovery outreach for failed renewals and investigate repeated failure cohorts before avoidable churn occurs.")
    return finish(confidence, evidence, [file], "Subscription Recovery Patterns Detected", f"{len(evidence)} measurable subscription signal(s) were identified.")
