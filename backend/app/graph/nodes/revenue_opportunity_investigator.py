"""Deterministic investigator for evidence-supported revenue collection opportunities."""

from __future__ import annotations

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
    normalize_timestamp_column,
    update_plan_item_status,
)


COLLECTIBLE_INVOICE_STATUSES = {
    "open",
    "unpaid",
    "pending",
    "past_due",
    "overdue",
    "payment_due",
}
NON_COLLECTIBLE_INVOICE_STATUSES = {
    "paid",
    "settled",
    "captured",
    "void",
    "voided",
    "cancelled",
    "canceled",
    "draft",
}


def _resolve_column(df: pd.DataFrame, aliases: tuple[str, ...]) -> str | None:
    columns = {str(column).strip().lower(): str(column) for column in df.columns}
    return next((columns[alias] for alias in aliases if alias in columns), None)


def _load_invoice_frames(state: CaseState) -> tuple[pd.DataFrame | None, list[str], list[str]]:
    frames: list[pd.DataFrame] = []
    dataset_ids: list[str] = []
    errors: list[str] = []
    for dataset in find_datasets(state, ("invoice",)):
        try:
            frame = load_csv_dataset(dataset).copy()
        except DatasetLoadError as exc:
            errors.append(str(exc))
            continue
        frame["_source_dataset_id"] = dataset.dataset_id
        frame["_source_row"] = frame.index.astype(str)
        frames.append(frame)
        dataset_ids.append(dataset.dataset_id)
    return (pd.concat(frames, ignore_index=True, sort=False) if frames else None), dataset_ids, errors


def _record_keys(df: pd.DataFrame, identifier_column: str | None) -> pd.Series:
    fallback = df["_source_dataset_id"].astype(str) + ":" + df["_source_row"].astype(str)
    if identifier_column is None:
        return fallback
    identifiers = df[identifier_column].astype("string")
    return identifiers.where(identifiers.notna() & (identifiers.str.strip() != ""), fallback).astype(str)


def _insufficient_evidence_update(
    state: CaseState, description: str, *, load_errors: list[str] | None = None
) -> dict:
    timeline = [
        build_timeline_event(
            title="Revenue Opportunity Investigation Started",
            description="Loading invoice records for deterministic collection analysis.",
            stage="revenue_opportunity_investigation",
            progress=0.2,
        ),
        build_timeline_event(
            title="Insufficient Revenue Opportunity Evidence",
            description=description,
            stage="revenue_opportunity_investigation",
            progress=0.35,
        ),
    ]
    if load_errors:
        timeline.append(
            build_timeline_event(
                title="Invoice Dataset Access Issue",
                description="; ".join(load_errors),
                stage="revenue_opportunity_investigation",
                progress=0.35,
            )
        )
    return {
        "status": InvestigationStatus.INVESTIGATING,
        "current_stage": "revenue_opportunity_investigation",
        "confidence": 0.0,
        "requires_more_evidence": False,
        "investigation_plan": update_plan_item_status(
            state, InvestigatorName.REVENUE_OPPORTUNITY, PlanItemStatus.COMPLETED
        ),
        "completed_investigations": [InvestigatorName.REVENUE_OPPORTUNITY],
        "evidence": [],
        "case_files": [],
        "timeline": timeline,
    }


def revenue_opportunity_investigator_node(state: CaseState) -> dict:
    """Identify outstanding and overdue invoice balances without speculative forecasting.

    An explicit outstanding balance is preferred.  When it is unavailable, the
    node derives one only from an invoice total and paid amount, or from an
    invoice total paired with a collectible invoice status.  This keeps every
    estimated amount traceable to an uncollected invoice record.
    """

    invoices, dataset_ids, load_errors = _load_invoice_frames(state)
    if invoices is None or invoices.empty:
        return _insufficient_evidence_update(
            state,
            "No readable invoice rows are available; revenue opportunities cannot be determined.",
            load_errors=load_errors,
        )

    balance_column = _resolve_column(
        invoices, ("balance_due", "amount_due", "outstanding_amount", "outstanding_balance")
    )
    amount_column = _resolve_column(
        invoices, ("invoice_amount", "total_amount", "amount", "gross_amount")
    )
    paid_column = _resolve_column(
        invoices, ("paid_amount", "amount_paid", "collected_amount", "payment_amount")
    )
    status_column = _resolve_column(invoices, ("status", "invoice_status", "payment_status"))
    due_date_column = _resolve_column(
        invoices, ("due_date", "due_at", "payment_due_date")
    )
    timestamp_column = _resolve_column(
        invoices, ("created_at", "issued_at", "updated_at", "timestamp", "created")
    )
    identifier_column = _resolve_column(invoices, ("invoice_id", "id", "order_id"))

    if balance_column is None and not (amount_column is not None and (paid_column or status_column)):
        return _insufficient_evidence_update(
            state,
            "An explicit invoice balance, or an invoice total paired with paid amount or status, is required.",
            load_errors=load_errors,
        )

    invoices = invoices.copy()
    source_row_count = len(invoices)
    invoices["_record_key"] = _record_keys(invoices, identifier_column)
    status = (
        invoices[status_column].astype("string").str.lower().str.strip()
        if status_column is not None
        else pd.Series(pd.NA, index=invoices.index, dtype="string")
    )
    total_amount = (
        normalize_numeric_column(invoices, amount_column)
        if amount_column is not None
        else pd.Series(float("nan"), index=invoices.index)
    )
    paid_amount = (
        normalize_numeric_column(invoices, paid_column)
        if paid_column is not None
        else pd.Series(float("nan"), index=invoices.index)
    )

    if balance_column is not None:
        outstanding_balance = normalize_numeric_column(invoices, balance_column)
    else:
        outstanding_balance = pd.Series(float("nan"), index=invoices.index)
    if amount_column is not None and paid_column is not None:
        outstanding_balance = outstanding_balance.fillna(total_amount - paid_amount)
    if amount_column is not None and status_column is not None:
        status_balance = total_amount.where(status.isin(COLLECTIBLE_INVOICE_STATUSES))
        outstanding_balance = outstanding_balance.fillna(status_balance)

    invoices["_outstanding_balance"] = outstanding_balance
    invoices["_due_date"] = (
        normalize_timestamp_column(invoices, due_date_column)
        if due_date_column is not None
        else pd.NaT
    )
    invoices["_timestamp"] = (
        normalize_timestamp_column(invoices, timestamp_column)
        if timestamp_column is not None
        else pd.NaT
    )
    reference_candidates = pd.concat(
        [invoices["_timestamp"].dropna(), invoices["_due_date"].dropna()], ignore_index=True
    )
    reference_time = reference_candidates.max() if not reference_candidates.empty else pd.NaT

    valid_balance = invoices["_outstanding_balance"].notna() & (invoices["_outstanding_balance"] > 0)
    if status_column is not None:
        valid_balance &= ~status.isin(NON_COLLECTIBLE_INVOICE_STATUSES).fillna(False)
    invoices = invoices.loc[valid_balance].copy()
    if invoices.empty:
        return _insufficient_evidence_update(
            state,
            "Invoice records do not contain a positive, collectible outstanding balance.",
            load_errors=load_errors,
        )

    evidence: list[Evidence] = []
    flagged_keys: set[str] = set()
    signal_strengths: list[float] = []

    def add_evidence(rule: str, summary: str, mask: pd.Series, **metrics: object) -> None:
        if not mask.any():
            return
        record_keys = invoices.loc[mask, "_record_key"].tolist()
        flagged_keys.update(record_keys)
        affected_amount = float(invoices.loc[mask, "_outstanding_balance"].sum())
        evidence.append(
            Evidence(
                investigator=InvestigatorName.REVENUE_OPPORTUNITY,
                rule=rule,
                summary=summary,
                dataset_ids=dataset_ids,
                record_ids=record_keys,
                metrics=evidence_metrics(
                    affected_invoice_count=int(mask.sum()),
                    **metrics,
                ),
                confidence=0.0,
                estimated_amount=affected_amount,
            )
        )
        signal_strengths.append(min(1.0, float(mask.mean()) * 3))

    outstanding_mask = pd.Series(True, index=invoices.index)
    add_evidence(
        "outstanding_invoice_balances",
        "Invoices have a positive, collectible balance that represents uncollected invoiced revenue.",
        outstanding_mask,
        outstanding_balance_total=round(float(invoices["_outstanding_balance"].sum()), 2),
    )

    has_reference_time = pd.notna(reference_time)
    overdue_mask = (
        invoices["_due_date"].notna() & (invoices["_due_date"] < reference_time)
        if has_reference_time
        else pd.Series(False, index=invoices.index)
    )
    add_evidence(
        "overdue_invoice_balances",
        "Outstanding invoices were due before the latest timestamp available in the supplied invoice data.",
        overdue_mask,
        reference_timestamp=reference_time.isoformat() if has_reference_time else None,
        overdue_balance_total=round(
            float(invoices.loc[overdue_mask, "_outstanding_balance"].sum()), 2
        )
        if overdue_mask.any()
        else None,
    )

    column_coverage = sum(
        column is not None
        for column in (balance_column or amount_column, paid_column or status_column, due_date_column)
    ) / 3
    confidence = calculate_confidence(
        required_column_coverage=column_coverage,
        row_count=source_row_count,
        evidence_count=len(evidence),
        signal_strength=max(signal_strengths, default=0.0),
    )
    evidence = [item.model_copy(update={"confidence": confidence}) for item in evidence]

    flagged_rows = invoices[invoices["_record_key"].isin(flagged_keys)]
    opportunity_amount = float(flagged_rows["_outstanding_balance"].sum())
    case_files = [
        build_case_file(
            investigation_id=state["investigation_id"],
            title="Revenue collection opportunities detected",
            confidence=confidence,
            evidence=evidence,
            estimated_monthly_loss=opportunity_amount,
            priority=1,
            recommendation=(
                "Prioritize collection and dispute resolution for the flagged invoice balances; "
                "separate amounts already in payment plans before escalation."
            ),
        )
    ]
    timeline = [
        build_timeline_event(
            title="Revenue Opportunity Investigation Started",
            description="Analyzing invoice balances using only supplied invoice timestamps.",
            stage="revenue_opportunity_investigation",
            progress=0.2,
        ),
        build_timeline_event(
            title="Revenue Collection Opportunities Detected",
            description=f"{len(evidence)} deterministic invoice-collection signal(s) were identified.",
            stage="revenue_opportunity_investigation",
            progress=0.35,
        ),
        build_timeline_event(
            title=f"Revenue Opportunity Confidence: {confidence:.0%}",
            description="Confidence reflects invoice-field coverage, sample adequacy, and signal strength.",
            stage="revenue_opportunity_investigation",
            progress=0.4,
        ),
    ]
    return {
        "status": InvestigationStatus.INVESTIGATING,
        "current_stage": "revenue_opportunity_investigation",
        "confidence": confidence,
        "investigation_plan": update_plan_item_status(
            state, InvestigatorName.REVENUE_OPPORTUNITY, PlanItemStatus.COMPLETED
        ),
        "completed_investigations": [InvestigatorName.REVENUE_OPPORTUNITY],
        "evidence": evidence,
        "case_files": case_files,
        "requires_more_evidence": False,
        "timeline": timeline,
    }
