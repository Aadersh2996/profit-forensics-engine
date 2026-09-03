"""Investigation execution and retrieval endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.db_models import CaseFileORM, Investigation, RecommendationORM, TimelineEventORM
from app.db.session import get_db
from app.graph.builder import build_investigation_graph
from app.graph.state import CaseState
from app.models.schemas import (
    CaseFile,
    DatasetMetadata,
    ExecutiveSummary,
    InvestigationReport,
    InvestigationRequest,
    InvestigationStatus,
    Recommendation,
    TimelineEvent,
)


router = APIRouter(prefix="/investigations", tags=["investigations"])


def _report_from_state(state: CaseState) -> InvestigationReport:
    return InvestigationReport(
        investigation_id=state["investigation_id"],
        status=state["status"],
        current_hypothesis=state.get("current_hypothesis"),
        confidence=state.get("confidence", 0.0),
        estimated_monthly_loss=state.get("estimated_monthly_loss", 0.0),
        estimated_annual_loss=state.get("estimated_annual_loss", 0.0),
        investigation_plan=state.get("investigation_plan", []),
        datasets=state.get("datasets", []),
        case_files=state.get("case_files", []),
        recommendations=state.get("recommendations", []),
        executive_summary=state.get("executive_summary"),
        timeline=state.get("timeline", []),
    )


def _persist_report(db: Session, report: InvestigationReport) -> None:
    """Persist the graph result using the existing normalized ORM relationships."""

    investigation = Investigation(
        id=report.investigation_id,
        status=report.status.value,
        confidence=report.confidence,
        current_hypothesis=report.current_hypothesis,
        estimated_monthly_loss=report.estimated_monthly_loss,
        estimated_annual_loss=report.estimated_annual_loss,
        executive_summary=(
            report.executive_summary.model_dump(mode="json")
            if report.executive_summary is not None
            else None
        ),
    )
    investigation.case_files = [
        CaseFileORM(
            id=case_file.id,
            title=case_file.title,
            status=case_file.status.value,
            confidence=case_file.confidence,
            evidence=[evidence.model_dump(mode="json") for evidence in case_file.evidence],
            root_cause=case_file.root_cause,
            estimated_monthly_loss=case_file.estimated_monthly_loss,
            estimated_annual_loss=case_file.estimated_annual_loss,
            recommendation=case_file.recommendation,
            priority=case_file.priority,
        )
        for case_file in report.case_files
    ]
    investigation.timeline_events = [
        TimelineEventORM(
            id=event.id,
            title=event.title,
            description=event.description,
            stage=event.stage,
            progress=event.progress,
            created_at=event.created_at,
        )
        for event in report.timeline
    ]
    investigation.recommendations = [
        RecommendationORM(
            id=recommendation.id,
            title=recommendation.title,
            description=recommendation.description,
            priority=recommendation.priority,
            expected_monthly_impact=recommendation.expected_monthly_impact,
            related_case_file_ids=recommendation.related_case_file_ids,
        )
        for recommendation in report.recommendations
    ]
    db.add(investigation)
    db.commit()


def _report_from_persisted(investigation: Investigation) -> InvestigationReport:
    """Rebuild the public report from persisted normalized records."""

    return InvestigationReport(
        investigation_id=investigation.id,
        status=InvestigationStatus(investigation.status),
        current_hypothesis=investigation.current_hypothesis,
        confidence=investigation.confidence,
        estimated_monthly_loss=investigation.estimated_monthly_loss,
        estimated_annual_loss=investigation.estimated_annual_loss,
        case_files=[
            CaseFile(
                id=case_file.id,
                investigation_id=investigation.id,
                title=case_file.title,
                status=case_file.status,
                confidence=case_file.confidence,
                evidence=case_file.evidence,
                root_cause=case_file.root_cause,
                estimated_monthly_loss=case_file.estimated_monthly_loss,
                estimated_annual_loss=case_file.estimated_annual_loss,
                recommendation=case_file.recommendation,
                priority=case_file.priority,
            )
            for case_file in investigation.case_files
        ],
        recommendations=[
            Recommendation(
                id=recommendation.id,
                title=recommendation.title,
                description=recommendation.description,
                priority=recommendation.priority,
                expected_monthly_impact=recommendation.expected_monthly_impact,
                related_case_file_ids=recommendation.related_case_file_ids,
            )
            for recommendation in investigation.recommendations
        ],
        executive_summary=(
            ExecutiveSummary.model_validate(investigation.executive_summary)
            if investigation.executive_summary is not None
            else None
        ),
        timeline=[
            TimelineEvent(
                id=event.id,
                title=event.title,
                description=event.description,
                stage=event.stage,
                progress=event.progress,
                created_at=event.created_at,
            )
            for event in investigation.timeline_events
        ],
    )


@router.post("", response_model=InvestigationReport, status_code=status.HTTP_201_CREATED)
def create_investigation(
    request: InvestigationRequest, db: Session = Depends(get_db)
) -> InvestigationReport:
    """Execute and persist a complete investigation over supplied dataset references."""

    state = build_investigation_graph().invoke(
        {"investigation_id": request.investigation_id, "datasets": request.datasets}
    )
    report = _report_from_state(state)
    if db.get(Investigation, report.investigation_id) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An investigation with this identifier already exists.",
        )
    _persist_report(db, report)
    return report


@router.get("/{investigation_id}", response_model=InvestigationReport)
def get_investigation(investigation_id: str, db: Session = Depends(get_db)) -> InvestigationReport:
    """Return a persisted investigation report by its stable investigation identifier."""

    investigation = db.get(Investigation, investigation_id)
    if investigation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investigation not found.")
    return _report_from_persisted(investigation)
