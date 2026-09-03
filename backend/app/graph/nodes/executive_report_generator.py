"""Executive report synthesis from completed, traceable investigation artifacts."""

from __future__ import annotations

import json

from openai import OpenAI

from app.config import settings
from app.graph.state import CaseState
from app.models.schemas import ExecutiveSummary, InvestigationStatus
from app.services.investigators.base import build_timeline_event


def _report_context(state: CaseState) -> str:
    cases = "\n".join(
        f"- {case_file.title}: root cause={case_file.root_cause or 'not synthesized'}"
        for case_file in state.get("case_files", [])
    )
    recommendations = "\n".join(
        f"- {recommendation.title}: {recommendation.description}"
        for recommendation in state.get("recommendations", [])
    )
    return (
        f"Case files:\n{cases or '- None'}\n\n"
        f"Recommendations:\n{recommendations or '- None'}"
    )


def generate_executive_summary(state: CaseState) -> ExecutiveSummary | None:
    """Generate a narrative-only executive summary from the finalized case artifacts."""

    if not settings.openai_api_key:
        return None
    prompt = (
        "Create an executive financial-investigation summary using only the supplied "
        "case files and recommendations. Do not calculate, introduce monetary figures, "
        "invent facts, or state hypotheses as certain. Return JSON with exactly the "
        "fields headline, summary, primary_root_causes, highest_priority_actions, and "
        "limitations. All list fields must contain strings.\n\n"
        f"{_report_context(state)}"
    )
    try:
        response = OpenAI(api_key=settings.openai_api_key).responses.create(
            model=settings.openai_model,
            input=prompt,
        )
        return ExecutiveSummary.model_validate(json.loads(response.output_text))
    except Exception:
        return None


def _deterministic_summary(state: CaseState) -> ExecutiveSummary:
    """Provide a transparent report when optional LLM synthesis is unavailable."""

    case_files = state.get("case_files", [])
    recommendations = state.get("recommendations", [])
    root_causes = [case_file.root_cause for case_file in case_files if case_file.root_cause]
    return ExecutiveSummary(
        headline=f"Investigation completed with {len(case_files)} case file(s).",
        summary=(
            "This report is a deterministic consolidation of the completed investigation "
            "artifacts; review the linked evidence before acting on each finding."
        ),
        primary_root_causes=root_causes,
        highest_priority_actions=[recommendation.title for recommendation in recommendations],
        limitations=[
            "Findings are limited to the datasets supplied to this investigation.",
            "LLM executive synthesis was unavailable; this summary contains no added narrative inference.",
        ],
    )


def executive_report_generator_node(state: CaseState) -> dict:
    """Finalize the investigation report with a synthesized or transparent fallback summary."""

    executive_summary = generate_executive_summary(state) or _deterministic_summary(state)
    return {
        "status": InvestigationStatus.COMPLETED,
        "current_stage": "executive_report_generation",
        "executive_summary": executive_summary,
        "timeline": [
            build_timeline_event(
                title="Executive Report Generated",
                description="The investigation has been consolidated into its final executive report.",
                stage="executive_report_generation",
                progress=1.0,
            )
        ],
    }
