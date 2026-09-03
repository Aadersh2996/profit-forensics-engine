from app.graph.nodes.evidence_refinement import evidence_refinement_node
from app.graph.routers import route_after_refinement
from app.models.schemas import InvestigationPlanItem, InvestigatorName, PlanItemStatus


def test_refinement_marks_only_the_highest_priority_running_item_for_one_retry() -> None:
    state = {
        "requires_more_evidence": True,
        "retry_count": 0,
        "max_retry_count": 1,
        "investigation_plan": [
            InvestigationPlanItem(
                investigator=InvestigatorName.REFUND,
                status=PlanItemStatus.RUNNING,
                priority=2,
            ),
            InvestigationPlanItem(
                investigator=InvestigatorName.PAYMENT_RECOVERY,
                status=PlanItemStatus.RUNNING,
                priority=1,
            ),
        ],
    }

    result = evidence_refinement_node(state)

    assert result["retry_count"] == 1
    assert result["requires_more_evidence"] is False
    assert route_after_refinement(result) == "payment_recovery"
    statuses = {item.investigator: item.status for item in result["investigation_plan"]}
    assert statuses[InvestigatorName.PAYMENT_RECOVERY] == PlanItemStatus.RETRYING
    assert statuses[InvestigatorName.REFUND] == PlanItemStatus.RUNNING


def test_refinement_does_not_exceed_the_global_retry_limit() -> None:
    state = {
        "requires_more_evidence": True,
        "retry_count": 1,
        "max_retry_count": 1,
        "investigation_plan": [
            InvestigationPlanItem(
                investigator=InvestigatorName.REFUND,
                status=PlanItemStatus.RUNNING,
                priority=1,
            )
        ],
    }

    result = evidence_refinement_node(state)

    assert "retry_count" not in result
    assert "investigation_plan" not in result
    assert result["requires_more_evidence"] is False
