"""Bounded deterministic refinement transition for an investigation plan item."""

from app.graph.state import CaseState
from app.models.schemas import InvestigationStatus, PlanItemStatus
from app.services.investigators.base import build_timeline_event


def evidence_refinement_node(state: CaseState) -> dict:
    """Mark the active investigator for its single permitted evidence rerun.

    Investigators decide whether supporting evidence warrants a refinement.
    This node deliberately performs no financial analysis and does not retain
    temporary tabular data: it only advances the global bounded retry state
    that ``route_after_refinement`` consumes.
    """

    retry_count = state.get("retry_count", 0)
    max_retry_count = state.get("max_retry_count", 1)
    running_items = [
        item
        for item in state.get("investigation_plan", [])
        if item.status == PlanItemStatus.RUNNING
    ]
    if not state.get("requires_more_evidence", False) or retry_count >= max_retry_count or not running_items:
        return {
            "status": InvestigationStatus.REFINING,
            "current_stage": "evidence_refinement_complete",
            "requires_more_evidence": False,
            "timeline": [
                build_timeline_event(
                    title="Evidence Refinement Not Required",
                    description="No eligible investigator requires the bounded refinement pass.",
                    stage="evidence_refinement_complete",
                    progress=0.45,
                )
            ],
        }

    selected = min(running_items, key=lambda item: item.priority)
    plan = [
        item.model_copy(update={"status": PlanItemStatus.RETRYING})
        if item.investigator == selected.investigator
        else item
        for item in state["investigation_plan"]
    ]
    return {
        "status": InvestigationStatus.REFINING,
        "current_stage": "evidence_refinement_complete",
        "investigation_plan": plan,
        "retry_count": retry_count + 1,
        "requires_more_evidence": False,
        "timeline": [
            build_timeline_event(
                title="Evidence Refinement Scheduled",
                description=(
                    f"{selected.investigator.value} is scheduled for the single permitted "
                    "rerun using its existing supporting datasets."
                ),
                stage="evidence_refinement_complete",
                progress=0.45,
            )
        ],
    }
