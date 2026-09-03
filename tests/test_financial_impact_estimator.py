from app.graph.nodes.financial_impact_estimator import financial_impact_estimator_node
from app.models.schemas import CaseFile


def test_financial_impact_estimator_aggregates_case_level_amounts() -> None:
    case_files = [
        CaseFile(
            investigation_id="PF-IMPACT",
            title="Refund leakage",
            confidence=0.8,
            estimated_monthly_loss=125.25,
            priority=1,
        ),
        CaseFile(
            investigation_id="PF-IMPACT",
            title="Payment recovery",
            confidence=0.7,
            estimated_monthly_loss=74.75,
            priority=2,
        ),
    ]

    result = financial_impact_estimator_node({"case_files": case_files})

    assert result["estimated_monthly_loss"] == 200.0
    assert result["estimated_annual_loss"] == 2400.0
