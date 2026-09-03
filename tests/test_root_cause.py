from app.graph.nodes.root_cause import root_cause_node
from app.graph.state import merge_case_files
from app.models.schemas import CaseFile, Evidence, InvestigatorName


def _case_file() -> CaseFile:
    evidence = Evidence(
        investigator=InvestigatorName.REFUND,
        rule="repeat_customer_refunds",
        summary="A repeat customer cohort has elevated refunds.",
        confidence=0.8,
        estimated_amount=100.0,
    )
    return CaseFile(
        id="case-1",
        investigation_id="PF-ROOT",
        title="Refund signals",
        confidence=0.8,
        evidence=[evidence],
        priority=1,
    )


def test_case_file_merge_replaces_a_revision_without_losing_other_cases() -> None:
    original = _case_file()
    revised = original.model_copy(update={"root_cause": "A supported hypothesis."})
    other = original.model_copy(update={"id": "case-2"})

    merged = merge_case_files([original, other], [revised])

    assert [case_file.id for case_file in merged] == ["case-1", "case-2"]
    assert merged[0].root_cause == "A supported hypothesis."


def test_root_cause_node_attaches_only_generated_hypotheses(monkeypatch) -> None:
    case_file = _case_file()
    monkeypatch.setattr(
        "app.graph.nodes.root_cause.generate_root_cause",
        lambda _: "The evidence supports a hypothesis of a missing refund control.",
    )

    result = root_cause_node({"case_files": [case_file]})

    assert result["case_files"][0].id == case_file.id
    assert result["case_files"][0].root_cause.startswith("The evidence supports")
