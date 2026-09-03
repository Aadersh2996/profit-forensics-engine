"""Deterministic investigator for recoverable payment operations."""

from __future__ import annotations

from datetime import timedelta

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

STALE_PAYMENT_AGE = timedelta(hours=24)
RECOVERABLE_FAILURE_TERMS = ("timeout", "network", "gateway", "technical", "temporary")


def _resolve_column(df: pd.DataFrame, aliases: tuple[str, ...]) -> str | None:
    columns = {str(column).strip().lower(): str(column) for column in df.columns}
    return next((columns[alias] for alias in aliases if alias in columns), None)


def _load_payment_frames(state: CaseState) -> tuple[pd.DataFrame | None, list[str], list[str]]:
    frames: list[pd.DataFrame] = []
    dataset_ids: list[str] = []
    errors: list[str] = []
    for dataset in find_datasets(state, ("payment", "transaction")):
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
    values = df[identifier_column].astype("string")
    return values.where(values.notna() & (values.str.strip() != ""), fallback).astype(str)


def _settled_payment_ids(state: CaseState) -> tuple[set[str], list[str]]:
    identifiers: set[str] = set()
    dataset_ids: list[str] = []
    for dataset in find_datasets(state, ("settlement",)):
        try:
            frame = load_csv_dataset(dataset)
        except DatasetLoadError:
            continue
        id_column = _resolve_column(frame, ("payment_id", "transaction_id", "id"))
        if id_column is None:
            continue
        identifiers.update(frame[id_column].dropna().astype(str).str.strip())
        dataset_ids.append(dataset.dataset_id)
    return identifiers, dataset_ids


def _insufficient_evidence_update(state: CaseState, description: str) -> dict:
    return {
        "status": InvestigationStatus.INVESTIGATING,
        "current_stage": "payment_recovery_investigation",
        "confidence": 0.0,
        "requires_more_evidence": False,
        "investigation_plan": update_plan_item_status(
            state, InvestigatorName.PAYMENT_RECOVERY, PlanItemStatus.COMPLETED
        ),
        "completed_investigations": [InvestigatorName.PAYMENT_RECOVERY],
        "evidence": [],
        "case_files": [],
        "timeline": [
            build_timeline_event(
                title="Payment Recovery Investigation Started",
                description="Loading payment records for deterministic state analysis.",
                stage="payment_recovery_investigation",
                progress=0.2,
            ),
            build_timeline_event(
                title="Insufficient Payment Evidence",
                description=description,
                stage="payment_recovery_investigation",
                progress=0.35,
            ),
        ],
    }


def payment_recovery_investigator_node(state: CaseState) -> dict:
    """Identify supported payment recovery opportunities from normalized CSV records."""

    payments, payment_dataset_ids, load_errors = _load_payment_frames(state)
    if payments is None or payments.empty:
        return _insufficient_evidence_update(
            state,
            "No readable payment rows are available; payment recovery cannot be determined.",
        )

    status_column = _resolve_column(payments, ("status", "payment_status"))
    if status_column is None:
        return _insufficient_evidence_update(
            state,
            "Payment status is required to distinguish pending, authorized, failed, and captured states.",
        )

    amount_column = _resolve_column(payments, ("amount", "payment_amount", "transaction_amount"))
    identifier_column = _resolve_column(payments, ("payment_id", "transaction_id", "id"))
    timestamp_column = _resolve_column(payments, ("created_at", "updated_at", "timestamp", "created"))
    error_column = _resolve_column(
        payments, ("error_reason", "failure_reason", "error", "failure_code")
    )

    payments = payments.copy()
    source_row_count = len(payments)
    payments["_record_key"] = _record_keys(payments, identifier_column)
    payments["_status"] = payments[status_column].astype("string").str.lower().str.strip()
    payments["_amount"] = (
        normalize_numeric_column(payments, amount_column)
        if amount_column is not None
        else 0.0
    )
    if timestamp_column is not None:
        payments["_timestamp"] = normalize_timestamp_column(payments, timestamp_column)
        reference_time = payments["_timestamp"].max()
    else:
        payments["_timestamp"] = pd.NaT
        reference_time = pd.NaT

    evidence: list[Evidence] = []
    flagged_keys: set[str] = set()
    signal_strengths: list[float] = []
    has_time_reference = pd.notna(reference_time)
    stale = (
        (reference_time - payments["_timestamp"] >= STALE_PAYMENT_AGE)
        if has_time_reference
        else pd.Series(False, index=payments.index)
    )

    def add_evidence(rule: str, summary: str, mask: pd.Series, **metrics: object) -> None:
        if not mask.any():
            return
        record_keys = payments.loc[mask, "_record_key"].tolist()
        flagged_keys.update(record_keys)
        affected_amount = float(payments.loc[mask, "_amount"].clip(lower=0).sum())
        evidence.append(
            Evidence(
                investigator=InvestigatorName.PAYMENT_RECOVERY,
                rule=rule,
                summary=summary,
                dataset_ids=payment_dataset_ids,
                record_ids=record_keys,
                metrics=evidence_metrics(affected_payment_count=int(mask.sum()), **metrics),
                confidence=0.0,
                estimated_amount=affected_amount,
            )
        )
        signal_strengths.append(min(1.0, float(mask.mean()) * 3))

    pending_mask = payments["_status"].isin({"pending", "processing"}) & stale
    add_evidence(
        "stuck_pending_payments",
        "Pending payment records have exceeded the dataset-derived 24-hour recovery window.",
        pending_mask,
        reference_timestamp=reference_time.isoformat() if has_time_reference else None,
        stale_after_hours=24,
    )

    authorized_mask = payments["_status"].isin({"authorized", "authorised"}) & stale
    add_evidence(
        "authorized_not_captured",
        "Authorized payments were not captured within the dataset-derived recovery window.",
        authorized_mask,
        reference_timestamp=reference_time.isoformat() if has_time_reference else None,
        stale_after_hours=24,
    )

    failed_mask = payments["_status"].isin({"failed", "failure", "declined"})
    if error_column is not None:
        error_text = payments[error_column].astype("string").str.lower().fillna("")
        recoverable_error = error_text.str.contains("|".join(RECOVERABLE_FAILURE_TERMS), regex=True)
        recoverable_mask = failed_mask & recoverable_error
        add_evidence(
            "recoverable_failed_payments",
            "Failed payments have technical failure reasons that support a controlled recovery attempt.",
            recoverable_mask,
        )

        timeout_mask = failed_mask & error_text.str.contains("timeout", regex=False)
        if int(timeout_mask.sum()) >= 2:
            add_evidence(
                "gateway_timeout_pattern",
                "Multiple failed payments share a timeout pattern requiring gateway follow-up.",
                timeout_mask,
                timeout_pattern_minimum=2,
            )

    abandoned_mask = payments["_status"].isin({"created", "initiated", "attempted"}) & stale
    add_evidence(
        "abandoned_payment_flows",
        "Unfinished payment flows have aged beyond the dataset-derived follow-up window.",
        abandoned_mask,
        reference_timestamp=reference_time.isoformat() if has_time_reference else None,
        stale_after_hours=24,
    )

    settled_ids, settlement_dataset_ids = _settled_payment_ids(state)
    if identifier_column is not None and settled_ids:
        captured_mask = payments["_status"].isin({"captured", "success", "successful", "paid"})
        payment_identifiers = payments[identifier_column].astype("string").str.strip()
        reconciliation_mask = captured_mask & ~payment_identifiers.isin(settled_ids)
        if reconciliation_mask.any():
            record_keys = payments.loc[reconciliation_mask, "_record_key"].tolist()
            flagged_keys.update(record_keys)
            affected_amount = float(payments.loc[reconciliation_mask, "_amount"].clip(lower=0).sum())
            evidence.append(
                Evidence(
                    investigator=InvestigatorName.PAYMENT_RECOVERY,
                    rule="reconciliation_mismatches",
                    summary="Captured payments are absent from the supplied settlement references.",
                    dataset_ids=payment_dataset_ids + settlement_dataset_ids,
                    record_ids=record_keys,
                    metrics=evidence_metrics(
                        affected_payment_count=int(reconciliation_mask.sum()),
                        settlement_reference_count=len(settled_ids),
                    ),
                    confidence=0.0,
                    estimated_amount=affected_amount,
                )
            )
            signal_strengths.append(min(1.0, float(reconciliation_mask.mean()) * 3))

    column_coverage = sum(
        column is not None for column in (status_column, amount_column, timestamp_column)
    ) / 3
    confidence = calculate_confidence(
        required_column_coverage=column_coverage,
        row_count=source_row_count,
        evidence_count=len(evidence),
        signal_strength=max(signal_strengths, default=0.0),
        corroborating_dataset_count=1 if settlement_dataset_ids else 0,
    )
    evidence = [item.model_copy(update={"confidence": confidence}) for item in evidence]

    supporting_datasets = find_datasets(state, ("settlement", "invoice", "customer", "order"))
    requires_refinement = bool(evidence) and (
        confidence < settings.confidence_threshold
        and state.get("retry_count", 0) < state.get("max_retry_count", 1)
        and bool(supporting_datasets)
    )
    plan_status = PlanItemStatus.RUNNING if requires_refinement else PlanItemStatus.COMPLETED

    timeline = [
        build_timeline_event(
            title="Payment Recovery Investigation Started",
            description="Analyzing payment states against the latest dataset timestamp.",
            stage="payment_recovery_investigation",
            progress=0.2,
        )
    ]
    case_files = []
    if evidence:
        flagged_rows = payments[payments["_record_key"].isin(flagged_keys)]
        flagged_total = float(flagged_rows["_amount"].clip(lower=0).sum())
        valid_timestamps = flagged_rows["_timestamp"].dropna()
        if valid_timestamps.empty:
            monthly_loss = 0.0
        else:
            observed_days = max(1, (valid_timestamps.max() - valid_timestamps.min()).days + 1)
            monthly_loss = round(flagged_total * 30 / observed_days, 2)
        case_files = [
            build_case_file(
                investigation_id=state["investigation_id"],
                case_file_id=f"{state['investigation_id']}:payment_recovery",
                title="Payment recovery opportunities detected",
                confidence=confidence,
                evidence=evidence,
                estimated_monthly_loss=monthly_loss,
                priority=1,
                recommendation=(
                    "Prioritize recovery outreach and reconciliation for the flagged payment records; "
                    "review authorization capture and gateway timeout controls."
                ),
            )
        ]
        timeline.append(
            build_timeline_event(
                title="Recoverable Payment Patterns Detected",
                description=f"{len(evidence)} deterministic payment-control signal(s) were identified.",
                stage="payment_recovery_investigation",
                progress=0.35,
            )
        )
    else:
        timeline.append(
            build_timeline_event(
                title="No Meaningful Payment Recovery Opportunity Detected",
                description="Available payment records did not trigger the supported deterministic recovery controls.",
                stage="payment_recovery_investigation",
                progress=0.35,
            )
        )
    timeline.append(
        build_timeline_event(
            title=f"Payment Recovery Confidence: {confidence:.0%}",
            description="Confidence is calculated from column coverage, sample adequacy, signal strength, and corroboration.",
            stage="payment_recovery_investigation",
            progress=0.4,
        )
    )
    if requires_refinement:
        timeline.append(
            build_timeline_event(
                title="Additional Payment Evidence Required",
                description="A bounded refinement will inspect supporting operational records before one rerun.",
                stage="payment_refinement_required",
                progress=0.42,
            )
        )

    return {
        "status": InvestigationStatus.INVESTIGATING,
        "current_stage": "payment_recovery_investigation",
        "confidence": confidence,
        "investigation_plan": update_plan_item_status(
            state, InvestigatorName.PAYMENT_RECOVERY, plan_status
        ),
        "completed_investigations": []
        if requires_refinement
        else [InvestigatorName.PAYMENT_RECOVERY],
        "evidence": evidence,
        "case_files": case_files,
        "requires_more_evidence": requires_refinement,
        "timeline": timeline,
    }
