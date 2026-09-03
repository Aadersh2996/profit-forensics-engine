"""LLM-backed recommendation wording with deterministic impact and linkage."""

from __future__ import annotations

import json

from openai import OpenAI

from app.config import settings
from app.graph.state import CaseState
from app.models.schemas import CaseFile, InvestigationStatus, Recommendation
from app.services.investigators.base import build_timeline_event


def _recommendation_context(case_file: CaseFile) -> str:
    return "\n".join(
        f"- {evidence.rule}: {evidence.summary}" for evidence in case_file.evidence
    )


def generate_recommendation_content(case_file: CaseFile) -> tuple[str, str] | None:
    """Generate an operational recommendation from evidence already in the case file."""

    if not settings.openai_api_key or not case_file.evidence:
        return None
    prompt = (
        "Create one financial-operations recommendation grounded only in the supplied "
        "case evidence and root-cause hypothesis. Do not calculate money, invent facts, "
        "or claim certainty. Return a JSON object with exactly `title` and `description` "
        "string fields. The description must be concise and actionable.\n\n"
        f"Case: {case_file.title}\n"
        f"Root-cause hypothesis: {case_file.root_cause or 'Not available'}\n"
        f"Evidence:\n{_recommendation_context(case_file)}"
    )
    try:
        response = OpenAI(api_key=settings.openai_api_key).responses.create(
            model=settings.openai_model,
            input=prompt,
        )
        content = json.loads(response.output_text)
    except (Exception, json.JSONDecodeError):
        return None
    title = content.get("title") if isinstance(content, dict) else None
    description = content.get("description") if isinstance(content, dict) else None
    if not isinstance(title, str) or not isinstance(description, str):
        return None
    title, description = title.strip(), description.strip()
    return (title, description) if title and description else None


def recommendation_generator_node(state: CaseState) -> dict:
    """Create linked recommendations without allowing the LLM to set financial values."""

    recommendations: list[Recommendation] = []
    revised_case_files: list[CaseFile] = []
    for case_file in state.get("case_files", []):
        content = generate_recommendation_content(case_file)
        if content is None:
            continue
        title, description = content
        recommendation = Recommendation(
            title=title,
            description=description,
            priority=case_file.priority,
            expected_monthly_impact=case_file.estimated_monthly_loss,
            related_case_file_ids=[case_file.id],
        )
        recommendations.append(recommendation)
        revised_case_files.append(case_file.model_copy(update={"recommendation": description}))

    return {
        "status": InvestigationStatus.SYNTHESIZING,
        "current_stage": "recommendation_generation",
        "case_files": revised_case_files,
        "recommendations": recommendations,
        "timeline": [
            build_timeline_event(
                title=(
                    "Recommendations Generated" if recommendations else "Recommendation Generation Deferred"
                ),
                description=(
                    f"Created {len(recommendations)} evidence-linked recommendation(s)."
                    if recommendations
                    else "No LLM-generated recommendations are available without configured credentials."
                ),
                stage="recommendation_generation",
                progress=0.75,
            )
        ],
    }
