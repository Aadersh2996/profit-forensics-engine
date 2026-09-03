"""LangGraph assembly for the complete Profit Forensics investigation lifecycle."""

from langgraph.graph import END, START, StateGraph

from app.graph.nodes.case_manager import case_manager_node
from app.graph.nodes.discount_investigator import discount_investigator_node
from app.graph.nodes.evidence_refinement import evidence_refinement_node
from app.graph.nodes.executive_report_generator import executive_report_generator_node
from app.graph.nodes.financial_impact_estimator import financial_impact_estimator_node
from app.graph.nodes.payment_recovery_investigator import payment_recovery_investigator_node
from app.graph.nodes.planner import planner_node
from app.graph.nodes.recommendation_generator import recommendation_generator_node
from app.graph.nodes.refund_investigator import refund_investigator_node
from app.graph.nodes.revenue_opportunity_investigator import revenue_opportunity_investigator_node
from app.graph.nodes.root_cause import root_cause_node
from app.graph.nodes.subscription_investigator import subscription_investigator_node
from app.graph.routers import (
    route_after_executive_report,
    route_after_investigator,
    route_after_planner,
    route_after_refinement,
)
from app.graph.state import CaseState


_INVESTIGATOR_NODES = {
    "refund": "refund",
    "payment_recovery": "payment_recovery",
    "discount": "discount",
    "subscription": "subscription",
    "revenue_opportunity": "revenue_opportunity",
}
_POST_INVESTIGATOR_ROUTES = {**_INVESTIGATOR_NODES, "evidence_refinement": "evidence_refinement", "root_cause": "root_cause"}
_POST_REFINEMENT_ROUTES = {**_INVESTIGATOR_NODES, "root_cause": "root_cause"}


def build_investigation_graph():
    """Compile the fixed, deterministic investigation workflow."""

    graph = StateGraph(CaseState)
    graph.add_node("case_manager", case_manager_node)
    graph.add_node("planner", planner_node)
    graph.add_node("refund", refund_investigator_node)
    graph.add_node("payment_recovery", payment_recovery_investigator_node)
    graph.add_node("discount", discount_investigator_node)
    graph.add_node("subscription", subscription_investigator_node)
    graph.add_node("revenue_opportunity", revenue_opportunity_investigator_node)
    graph.add_node("evidence_refinement", evidence_refinement_node)
    graph.add_node("root_cause", root_cause_node)
    graph.add_node("financial_impact_estimator", financial_impact_estimator_node)
    graph.add_node("recommendation_generator", recommendation_generator_node)
    graph.add_node("executive_report_generator", executive_report_generator_node)

    graph.add_edge(START, "case_manager")
    graph.add_edge("case_manager", "planner")
    graph.add_conditional_edges("planner", route_after_planner, _POST_REFINEMENT_ROUTES)
    for investigator_node in _INVESTIGATOR_NODES.values():
        graph.add_conditional_edges(
            investigator_node,
            route_after_investigator,
            _POST_INVESTIGATOR_ROUTES,
        )
    graph.add_conditional_edges(
        "evidence_refinement",
        route_after_refinement,
        _POST_REFINEMENT_ROUTES,
    )
    graph.add_edge("root_cause", "financial_impact_estimator")
    graph.add_edge("financial_impact_estimator", "recommendation_generator")
    graph.add_edge("recommendation_generator", "executive_report_generator")
    graph.add_conditional_edges(
        "executive_report_generator",
        route_after_executive_report,
        {"__end__": END},
    )
    return graph.compile()
