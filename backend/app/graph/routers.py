"""Pure deterministic routing functions for the investigation graph."""

from app.config import settings
from app.graph.state import CaseState
from app.models.schemas import PlanItemStatus


def _next_pending_investigator(state: CaseState) -> str | None:
    pending_items = sorted(
        (
            item
            for item in state.get("investigation_plan", [])
            if item.status == PlanItemStatus.PENDING
        ),
        key=lambda item: item.priority,
    )
    return pending_items[0].investigator.value if pending_items else None


def route_after_planner(state: CaseState) -> str:
    """Route to the highest-priority pending investigator, or synthesis if none exist."""

    return _next_pending_investigator(state) or "root_cause"


def route_after_investigator(state: CaseState) -> str:
    """Apply the confidence gate before advancing the structured plan."""

    can_refine = (
        state.get("requires_more_evidence", False)
        and state.get("confidence", 0.0) < settings.confidence_threshold
        and state.get("retry_count", 0) < state.get("max_retry_count", 1)
    )
    if can_refine:
        return "evidence_refinement"
    return _next_pending_investigator(state) or "root_cause"


def route_after_refinement(state: CaseState) -> str:
    """Rerun the single plan item marked retrying after a bounded refinement pass."""

    retrying_items = sorted(
        (
            item
            for item in state.get("investigation_plan", [])
            if item.status == PlanItemStatus.RETRYING
        ),
        key=lambda item: item.priority,
    )
    return retrying_items[0].investigator.value if retrying_items else "root_cause"


def route_after_executive_report(_: CaseState) -> str:
    """Finish the graph after the final report stage."""

    return "__end__"
