from app.graph.nodes.case_manager import case_manager_node
from app.graph.nodes.planner import planner_node
from app.graph.routers import route_after_investigator, route_after_planner, route_after_refinement
from app.models.schemas import (
    DatasetMetadata,
    InvestigationPlanItem,
    InvestigatorName,
    PlanItemStatus,
)


def _datasets(*dataset_types: str) -> list[DatasetMetadata]:
    return [
        DatasetMetadata(
            dataset_id=f"dataset-{index}",
            dataset_type=dataset_type,
            path=f"C:/data/{dataset_type}.csv",
            row_count=10,
            columns=["id"],
        )
        for index, dataset_type in enumerate(dataset_types)
    ]


def test_planner_selects_only_supported_investigators_in_priority_order() -> None:
    initial = case_manager_node({"datasets": _datasets("refunds", "payments", "discounts")})
    result = planner_node(initial)

    assert [item.investigator for item in result["investigation_plan"]] == [
        InvestigatorName.PAYMENT_RECOVERY,
        InvestigatorName.REFUND,
        InvestigatorName.DISCOUNT,
    ]
    assert [item.priority for item in result["investigation_plan"]] == [1, 2, 3]
    assert "will examine" in result["current_hypothesis"]


def test_planner_does_not_invent_an_investigation_for_unknown_data() -> None:
    initial = case_manager_node({"datasets": _datasets("inventory")})
    result = planner_node(initial)

    assert result["investigation_plan"] == []
    assert result["current_hypothesis"] == "No supported financial datasets are available for investigation."


def test_router_uses_highest_priority_pending_investigator() -> None:
    state = {
        "investigation_plan": [
            InvestigationPlanItem(
                investigator=InvestigatorName.REFUND,
                priority=2,
            ),
            InvestigationPlanItem(
                investigator=InvestigatorName.PAYMENT_RECOVERY,
                priority=1,
            ),
        ]
    }

    assert route_after_planner(state) == "payment_recovery"


def test_router_allows_only_one_refinement_cycle() -> None:
    retry_state = {
        "confidence": 0.5,
        "requires_more_evidence": True,
        "retry_count": 0,
        "max_retry_count": 1,
    }
    exhausted_state = {**retry_state, "retry_count": 1}

    assert route_after_investigator(retry_state) == "evidence_refinement"
    assert route_after_investigator(exhausted_state) == "root_cause"


def test_refinement_router_reexecutes_only_the_retrying_investigator() -> None:
    state = {
        "investigation_plan": [
            InvestigationPlanItem(
                investigator=InvestigatorName.REFUND,
                status=PlanItemStatus.RETRYING,
                priority=2,
            ),
            InvestigationPlanItem(
                investigator=InvestigatorName.PAYMENT_RECOVERY,
                priority=1,
            ),
        ]
    }

    assert route_after_refinement(state) == "refund"
