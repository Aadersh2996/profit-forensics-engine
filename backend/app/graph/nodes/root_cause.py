"""LLM-backed, evidence-constrained root-cause synthesis node."""

from __future__ import annotations

from openai import OpenAI

from app.config import settings
from app.graph.state import CaseState
from app.models.schemas import CaseFile, InvestigationStatus
from app.services.investigators.base import build_timeline_event


def _evidence_context(case_file: CaseFile) -> str:
    """Serialize only traceable evidence fields for a bounded synthesis prompt."""

    return "\n".join(
        (
            f"- Rule: {evidence.rule}\n"
            f"  Summary: {evidence.summary}\n"
            f"  Metrics: {evidence.metrics}"
        )
        for evidence in case_file.evidence
    )


def generate_root_cause(case_file: CaseFile) -> str | None:
    """Ask the configured model for a concise cause hypothesis grounded in evidence only."""

    if not settings.openai_api_key or not case_file.evidence:
        return None

    prompt = (
        "You are synthesizing a financial investigation root-cause hypothesis. "
        "Use only the supplied deterministic evidence. Do not perform arithmetic, "
        "invent facts, name individuals, or state causation as certain. Return one "
        "concise paragraph that describes plausible operational causes and clearly "
        "labels them as hypotheses.\n\n"
        f"Case: {case_file.title}\n"
        f"Evidence:\n{_evidence_context(case_file)}"
    )
    try:
        response = OpenAI(api_key=settings.openai_api_key).responses.create(
            model=settings.openai_model,
            input=prompt,
        )
    except Exception:
        return None
    root_cause = response.output_text.strip()
    return root_cause or None


def root_cause_node(state: CaseState) -> dict:
    """Attach evidence-bounded root-cause hypotheses to the current case files."""

    revised_case_files: list[CaseFile] = []
    synthesized_count = 0
    for case_file in state.get("case_files", []):
        root_cause = generate_root_cause(case_file)
        if root_cause is None:
            continue
        revised_case_files.append(case_file.model_copy(update={"root_cause": root_cause}))
        synthesized_count += 1

    if settings.openai_api_key:
        title = "Root Cause Analysis Completed"
        description = f"Generated evidence-bounded hypotheses for {synthesized_count} case file(s)."
    else:
        title = "Root Cause Analysis Deferred"
        description = "No LLM credentials are configured; deterministic evidence remains available for review."
    return {
        "status": InvestigationStatus.SYNTHESIZING,
        "current_stage": "root_cause_analysis",
        "case_files": revised_case_files,
        "timeline": [
            build_timeline_event(
                title=title,
                description=description,
                stage="root_cause_analysis",
                progress=0.55,
            )
        ],
    }
