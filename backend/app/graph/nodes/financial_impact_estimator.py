"""Deterministic aggregation of traceable case-file financial impact."""

from app.graph.state import CaseState
from app.models.schemas import InvestigationStatus
from app.services.investigators.base import build_timeline_event


def financial_impact_estimator_node(state: CaseState) -> dict:
    """Aggregate existing case-file monthly estimates without reinterpreting evidence.

    Each investigator establishes the amount and its dataset-relative cadence.
    This node intentionally performs only a transparent case-level sum so the
    report-wide amounts remain traceable to those already persisted estimates.
    """

    monthly_loss = round(
        sum(case_file.estimated_monthly_loss for case_file in state.get("case_files", [])),
        2,
    )
    annual_loss = round(monthly_loss * 12, 2)
    return {
        "status": InvestigationStatus.SYNTHESIZING,
        "current_stage": "financial_impact_estimation",
        "estimated_monthly_loss": monthly_loss,
        "estimated_annual_loss": annual_loss,
        "timeline": [
            build_timeline_event(
                title="Financial Impact Estimated",
                description=(
                    f"Aggregated {len(state.get('case_files', []))} traceable case-file "
                    "estimate(s) without cross-case extrapolation."
                ),
                stage="financial_impact_estimation",
                progress=0.65,
            )
        ],
    }
