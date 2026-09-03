from app.graph.nodes.recommendation_generator import recommendation_generator_node
from app.models.schemas import CaseFile, Evidence, InvestigatorName


def test_recommendation_generator_keeps_impact_and_linkage_deterministic(monkeypatch) -> None:
    case_file = CaseFile(
        id="case-1",
        investigation_id="PF-RECOMMENDATION",
        title="Payment recovery",
        confidence=0.8,
        evidence=[
            Evidence(
                investigator=InvestigatorName.PAYMENT_RECOVERY,
                rule="stuck_pending_payments",
                summary="Pending payments have aged past the recovery window.",
                confidence=0.8,
                estimated_amount=100.0,
            )
        ],
        estimated_monthly_loss=120.0,
        priority=1,
    )
    monkeypatch.setattr(
        "app.graph.nodes.recommendation_generator.generate_recommendation_content",
        lambda _: ("Recover pending payments", "Trigger a controlled recovery workflow."),
    )

    result = recommendation_generator_node({"case_files": [case_file]})

    recommendation = result["recommendations"][0]
    assert recommendation.expected_monthly_impact == 120.0
    assert recommendation.related_case_file_ids == ["case-1"]
    assert result["case_files"][0].recommendation == "Trigger a controlled recovery workflow."
