"""Deterministic selection of relevant investigators from dataset metadata."""

from app.graph.state import CaseState
from app.models.schemas import (
    InvestigationPlanItem,
    InvestigationStatus,
    InvestigatorName,
    TimelineEvent,
)


_INVESTIGATOR_PRIORITY: tuple[tuple[InvestigatorName, tuple[str, ...]], ...] = (
    (InvestigatorName.PAYMENT_RECOVERY, ("payment", "transaction", "order")),
    (InvestigatorName.REFUND, ("refund",)),
    (InvestigatorName.DISCOUNT, ("discount", "coupon", "promotion")),
    (InvestigatorName.SUBSCRIPTION, ("subscription",)),
)


def _has_dataset_type(dataset_types: set[str], keywords: tuple[str, ...]) -> bool:
    return any(keyword in dataset_type for dataset_type in dataset_types for keyword in keywords)


def _build_hypothesis(plan: list[InvestigationPlanItem]) -> str:
    if not plan:
        return "No supported financial datasets are available for investigation."

    labels = {
        InvestigatorName.PAYMENT_RECOVERY: "payment recovery opportunities",
        InvestigatorName.REFUND: "refund patterns and potential leakage",
        InvestigatorName.DISCOUNT: "discount concentration and potential leakage",
        InvestigatorName.SUBSCRIPTION: "subscription payment and renewal issues",
        InvestigatorName.REVENUE_OPPORTUNITY: "evidence-supported revenue opportunities",
    }
    investigation_targets = ", ".join(labels[item.investigator] for item in plan)
    return f"The engine will examine {investigation_targets}."


def planner_node(state: CaseState) -> dict:
    """Generate a structured, priority-ordered investigation plan without LLM use."""

    dataset_types = {dataset.dataset_type.strip().lower() for dataset in state.get("datasets", [])}
    plan: list[InvestigationPlanItem] = []

    for investigator, keywords in _INVESTIGATOR_PRIORITY:
        if _has_dataset_type(dataset_types, keywords):
            plan.append(
                InvestigationPlanItem(
                    investigator=investigator,
                    priority=len(plan) + 1,
                )
            )

    has_invoice_data = _has_dataset_type(dataset_types, ("invoice",))
    has_payment_data = _has_dataset_type(dataset_types, ("payment", "transaction", "order"))
    if has_invoice_data or (has_payment_data and _has_dataset_type(dataset_types, ("customer", "subscription"))):
        plan.append(
            InvestigationPlanItem(
                investigator=InvestigatorName.REVENUE_OPPORTUNITY,
                priority=len(plan) + 1,
            )
        )

    hypothesis = _build_hypothesis(plan)
    return {
        "status": InvestigationStatus.PLANNING,
        "current_stage": "planning_complete",
        "current_hypothesis": hypothesis,
        "investigation_plan": plan,
        "timeline": [
            TimelineEvent(
                title="Investigation Plan Generated",
                description=(
                    f"Selected {len(plan)} investigator(s) from "
                    f"{len(dataset_types)} dataset type(s)."
                ),
                stage="planning_complete",
                progress=0.1,
            )
        ],
    }
