"""Shared deterministic helpers used by specialized investigator nodes."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import pandas as pd

from app.graph.state import CaseState
from app.models.schemas import (
    CaseFile,
    DatasetMetadata,
    Evidence,
    InvestigatorName,
    PlanItemStatus,
    TimelineEvent,
)


class DatasetLoadError(ValueError):
    """Raised when a referenced CSV cannot be read as tabular evidence."""


def find_datasets(
    state: CaseState, dataset_type_keywords: Iterable[str]
) -> list[DatasetMetadata]:
    """Return lightweight dataset references whose type contains a supplied keyword."""

    keywords = tuple(keyword.lower() for keyword in dataset_type_keywords)
    return [
        dataset
        for dataset in state.get("datasets", [])
        if any(keyword in dataset.dataset_type.lower() for keyword in keywords)
    ]


def load_csv_dataset(dataset: DatasetMetadata) -> pd.DataFrame:
    """Load a referenced CSV only for the duration of an investigator execution."""

    try:
        return pd.read_csv(dataset.path)
    except (OSError, UnicodeDecodeError, pd.errors.ParserError) as exc:
        raise DatasetLoadError(f"Unable to load dataset '{dataset.dataset_id}': {exc}") from exc


def missing_required_columns(df: pd.DataFrame, required_columns: Iterable[str]) -> list[str]:
    """Return required columns that are not available in a loaded dataset."""

    available_columns = {str(column).strip().lower() for column in df.columns}
    return [
        column
        for column in required_columns
        if column.strip().lower() not in available_columns
    ]


def normalize_numeric_column(df: pd.DataFrame, column: str) -> pd.Series:
    """Return a numeric series with malformed values represented as ``NaN``."""

    return pd.to_numeric(df[column], errors="coerce")


def normalize_timestamp_column(df: pd.DataFrame, column: str) -> pd.Series:
    """Return UTC timestamps with malformed values represented as ``NaT``."""

    return pd.to_datetime(df[column], errors="coerce", utc=True)


def calculate_confidence(
    *,
    required_column_coverage: float,
    row_count: int,
    evidence_count: int,
    signal_strength: float,
    corroborating_dataset_count: int = 0,
) -> float:
    """Calculate explainable evidence confidence from bounded measurable inputs.

    The weighting is data completeness (30%), sample adequacy (20%), signal
    strength (30%), and independent corroboration (20%). Thirty rows are the
    smallest dataset treated as fully adequate for this MVP; two independent
    datasets fully satisfy corroboration.
    """

    def clamp(value: float) -> float:
        return max(0.0, min(1.0, value))

    data_completeness = clamp(required_column_coverage)
    sample_adequacy = clamp(row_count / 30)
    evidence_coverage = clamp(evidence_count / 3)
    strength = clamp(signal_strength)
    corroboration = clamp(corroborating_dataset_count / 2)

    # Evidence coverage moderates the measured rule strength: a single weak
    # finding cannot receive the same confidence as several supporting signals.
    supported_signal_strength = strength * (0.5 + 0.5 * evidence_coverage)
    return round(
        0.30 * data_completeness
        + 0.20 * sample_adequacy
        + 0.30 * supported_signal_strength
        + 0.20 * corroboration,
        4,
    )


def update_plan_item_status(
    state: CaseState, investigator: InvestigatorName, status: PlanItemStatus
) -> list:
    """Return a replacement plan with one investigator status changed safely."""

    plan = state.get("investigation_plan", [])
    if not any(item.investigator == investigator for item in plan):
        raise ValueError(f"Investigator '{investigator.value}' is not in the investigation plan")
    return [
        item.model_copy(update={"status": status})
        if item.investigator == investigator
        else item
        for item in plan
    ]


def build_case_file(
    *,
    investigation_id: str,
    case_file_id: str | None = None,
    title: str,
    confidence: float,
    evidence: list[Evidence],
    estimated_monthly_loss: float,
    priority: int,
    recommendation: str | None = None,
) -> CaseFile:
    """Build a financially traceable Case File from concrete evidence."""

    return CaseFile(
        **({"id": case_file_id} if case_file_id is not None else {}),
        investigation_id=investigation_id,
        title=title,
        confidence=confidence,
        evidence=evidence,
        estimated_monthly_loss=estimated_monthly_loss,
        estimated_annual_loss=estimated_monthly_loss * 12,
        priority=priority,
        recommendation=recommendation,
    )


def build_timeline_event(
    *, title: str, description: str | None, stage: str, progress: float
) -> TimelineEvent:
    """Build a validated first-class investigation timeline event."""

    return TimelineEvent(
        title=title,
        description=description,
        stage=stage,
        progress=progress,
    )


def evidence_metrics(**metrics: Any) -> dict[str, Any]:
    """Remove null metrics so stored evidence only contains observed values."""

    return {key: value for key, value in metrics.items() if value is not None}
