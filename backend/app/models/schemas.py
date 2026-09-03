"""Pydantic contracts for Profit Forensics Engine domain data and APIs."""

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DomainModel(BaseModel):
    """Shared validation behaviour for application contracts."""

    model_config = ConfigDict(extra="forbid")


class InvestigationStatus(StrEnum):
    CREATED = "created"
    PLANNING = "planning"
    INVESTIGATING = "investigating"
    REFINING = "refining"
    SYNTHESIZING = "synthesizing"
    COMPLETED = "completed"
    FAILED = "failed"


class PlanItemStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    RETRYING = "retrying"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


class InvestigatorName(StrEnum):
    REFUND = "refund"
    PAYMENT_RECOVERY = "payment_recovery"
    DISCOUNT = "discount"
    SUBSCRIPTION = "subscription"
    REVENUE_OPPORTUNITY = "revenue_opportunity"


class DatasetMetadata(DomainModel):
    """A lightweight dataset reference; tabular data is never stored in graph state."""

    dataset_id: str = Field(default_factory=lambda: str(uuid4()))
    dataset_type: str = Field(min_length=1, max_length=80)
    path: str = Field(min_length=1)
    row_count: int = Field(ge=0)
    columns: list[str] = Field(default_factory=list)
    source: str = Field(default="csv", min_length=1, max_length=40)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("columns")
    @classmethod
    def validate_columns(cls, columns: list[str]) -> list[str]:
        cleaned = [column.strip() for column in columns if column.strip()]
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("dataset columns must be unique")
        return cleaned


class UploadResponse(DomainModel):
    dataset: DatasetMetadata
    message: str = Field(min_length=1)


class InvestigationRequest(DomainModel):
    """Input required to execute a graph investigation over registered datasets."""

    investigation_id: str | None = Field(default=None, min_length=1, max_length=36)
    datasets: list[DatasetMetadata] = Field(default_factory=list)


class InvestigationPlanItem(DomainModel):
    investigator: InvestigatorName
    status: PlanItemStatus = PlanItemStatus.PENDING
    priority: int = Field(gt=0)


class TimelineEvent(DomainModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2_000)
    stage: str = Field(min_length=1, max_length=80)
    progress: float = Field(ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=_utc_now)


class Evidence(DomainModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    investigator: InvestigatorName
    rule: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=2_000)
    dataset_ids: list[str] = Field(default_factory=list)
    record_ids: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0)
    estimated_amount: float = Field(default=0.0, ge=0.0)


class CaseFileStatus(StrEnum):
    OPEN = "open"
    VALIDATED = "validated"
    CLOSED = "closed"


class CaseFile(DomainModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    investigation_id: str = Field(min_length=1)
    title: str = Field(min_length=1, max_length=200)
    status: CaseFileStatus = CaseFileStatus.OPEN
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[Evidence] = Field(default_factory=list)
    root_cause: str | None = Field(default=None, max_length=2_000)
    estimated_monthly_loss: float = Field(default=0.0, ge=0.0)
    estimated_annual_loss: float = Field(default=0.0, ge=0.0)
    recommendation: str | None = Field(default=None, max_length=2_000)
    priority: int = Field(gt=0)


class Recommendation(DomainModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2_000)
    priority: int = Field(gt=0)
    expected_monthly_impact: float = Field(default=0.0, ge=0.0)
    related_case_file_ids: list[str] = Field(default_factory=list)


class ExecutiveSummary(DomainModel):
    headline: str = Field(min_length=1, max_length=300)
    summary: str = Field(min_length=1, max_length=5_000)
    primary_root_causes: list[str] = Field(default_factory=list)
    highest_priority_actions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class InvestigationReport(DomainModel):
    investigation_id: str = Field(min_length=1)
    status: InvestigationStatus
    current_hypothesis: str | None = Field(default=None, max_length=2_000)
    confidence: float = Field(ge=0.0, le=1.0)
    estimated_monthly_loss: float = Field(default=0.0, ge=0.0)
    estimated_annual_loss: float = Field(default=0.0, ge=0.0)
    investigation_plan: list[InvestigationPlanItem] = Field(default_factory=list)
    datasets: list[DatasetMetadata] = Field(default_factory=list)
    case_files: list[CaseFile] = Field(default_factory=list)
    recommendations: list[Recommendation] = Field(default_factory=list)
    executive_summary: ExecutiveSummary | None = None
    timeline: list[TimelineEvent] = Field(default_factory=list)
