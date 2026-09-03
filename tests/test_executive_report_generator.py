from app.graph.nodes.executive_report_generator import executive_report_generator_node
from app.models.schemas import CaseFile, ExecutiveSummary


def test_executive_report_uses_generated_summary_when_available(monkeypatch) -> None:
    summary = ExecutiveSummary(
        headline="Refund controls require review.",
        summary="The supplied evidence supports a focused controls review.",
        primary_root_causes=["A control gap is a hypothesis."],
        highest_priority_actions=["Review approval workflow"],
        limitations=["Dataset scope is limited."],
    )
    monkeypatch.setattr(
        "app.graph.nodes.executive_report_generator.generate_executive_summary",
        lambda _: summary,
    )

    result = executive_report_generator_node(
        {
            "case_files": [
                CaseFile(
                    investigation_id="PF-REPORT",
                    title="Refund leakage",
                    confidence=0.8,
                    priority=1,
                )
            ]
        }
    )

    assert result["executive_summary"] == summary
    assert result["status"] == "completed"


def test_executive_report_has_a_transparent_offline_fallback(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.graph.nodes.executive_report_generator.generate_executive_summary",
        lambda _: None,
    )

    result = executive_report_generator_node({"case_files": [], "recommendations": []})

    assert "deterministic" in result["executive_summary"].summary
