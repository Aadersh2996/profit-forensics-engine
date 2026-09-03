"""Initialize a deterministic investigation case runtime state."""

from uuid import uuid4

from app.graph.state import CaseState
from app.models.schemas import InvestigationStatus, TimelineEvent


def case_manager_node(state: CaseState) -> dict:
    """Create the initial state update for one investigation case."""

    investigation_id = state.get("investigation_id") or f"PF-{uuid4().hex[:12].upper()}"
    datasets = state.get("datasets", [])

    return {
        "investigation_id": investigation_id,
        "status": InvestigationStatus.CREATED,
        "current_stage": "case_created",
        "current_hypothesis": None,
        "confidence": 0.0,
        "investigation_plan": [],
        "completed_investigations": [],
        "datasets": datasets,
        "evidence": [],
        "case_files": [],
        "recommendations": [],
        "executive_summary": None,
        "timeline": [
            TimelineEvent(
                title="Case Created",
                description=(
                    f"Investigation {investigation_id} created with "
                    f"{len(datasets)} available dataset(s)."
                ),
                stage="case_created",
                progress=0.0,
            )
        ],
        "estimated_monthly_loss": 0.0,
        "estimated_annual_loss": 0.0,
        "retry_count": 0,
        "max_retry_count": 1,
        "requires_more_evidence": False,
    }
