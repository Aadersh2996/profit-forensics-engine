"""Typed LangGraph runtime state for one investigation case."""

from operator import add
from typing import Annotated, TypedDict

from app.models.schemas import (
    CaseFile,
    DatasetMetadata,
    Evidence,
    ExecutiveSummary,
    InvestigationPlanItem,
    InvestigationStatus,
    InvestigatorName,
    Recommendation,
    TimelineEvent,
)


def merge_case_files(existing: list[CaseFile], updates: list[CaseFile]) -> list[CaseFile]:
    """Append new case files and replace revisions by stable case-file ID."""

    merged = list(existing)
    positions = {case_file.id: index for index, case_file in enumerate(merged)}
    for case_file in updates:
        if case_file.id in positions:
            merged[positions[case_file.id]] = case_file
        else:
            positions[case_file.id] = len(merged)
            merged.append(case_file)
    return merged


class CaseState(TypedDict, total=False):
    """Serializable runtime state; pandas DataFrames never belong here."""

    investigation_id: str
    status: InvestigationStatus
    current_stage: str
    current_hypothesis: str | None
    confidence: float
    investigation_plan: list[InvestigationPlanItem]
    completed_investigations: Annotated[list[InvestigatorName], add]
    datasets: list[DatasetMetadata]
    evidence: Annotated[list[Evidence], add]
    case_files: Annotated[list[CaseFile], merge_case_files]
    recommendations: Annotated[list[Recommendation], add]
    executive_summary: ExecutiveSummary | None
    timeline: Annotated[list[TimelineEvent], add]
    estimated_monthly_loss: float
    estimated_annual_loss: float
    retry_count: int
    max_retry_count: int
    requires_more_evidence: bool
