from pathlib import Path

import pandas as pd

from app.graph.nodes.case_manager import case_manager_node
from app.graph.nodes.planner import planner_node
from app.graph.nodes.revenue_opportunity_investigator import revenue_opportunity_investigator_node
from app.models.schemas import DatasetMetadata, InvestigatorName, PlanItemStatus


def _state(tmp_path: Path, rows: list[dict]) -> dict:
    path = tmp_path / "invoices.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    frame = pd.read_csv(path)
    dataset = DatasetMetadata(
        dataset_id="invoices",
        dataset_type="invoices",
        path=str(path),
        row_count=len(frame),
        columns=frame.columns.tolist(),
    )
    state = case_manager_node({"investigation_id": "PF-REVENUE", "datasets": [dataset]})
    state["investigation_plan"] = planner_node(state)["investigation_plan"]
    return state


def test_outstanding_and_overdue_invoice_balances_use_dataset_reference_time(tmp_path: Path) -> None:
    result = revenue_opportunity_investigator_node(
        _state(
            tmp_path,
            [
                {
                    "invoice_id": "old",
                    "status": "open",
                    "amount": 100,
                    "paid_amount": 25,
                    "due_date": "2025-01-01T00:00:00Z",
                    "created_at": "2025-01-01T00:00:00Z",
                },
                {
                    "invoice_id": "latest",
                    "status": "open",
                    "amount": 50,
                    "paid_amount": 0,
                    "due_date": "2025-01-03T00:00:00Z",
                    "created_at": "2025-01-03T00:00:00Z",
                },
                {
                    "invoice_id": "paid-later",
                    "status": "paid",
                    "amount": 25,
                    "paid_amount": 25,
                    "due_date": "2025-01-05T00:00:00Z",
                    "created_at": "2025-01-05T00:00:00Z",
                },
            ],
        )
    )

    rules = {item.rule for item in result["evidence"]}
    assert {"outstanding_invoice_balances", "overdue_invoice_balances"} <= rules
    overdue = next(item for item in result["evidence"] if item.rule == "overdue_invoice_balances")
    assert overdue.metrics["reference_timestamp"].startswith("2025-01-05")
    assert result["case_files"][0].estimated_monthly_loss == 125


def test_explicit_balance_is_usable_without_paid_amount(tmp_path: Path) -> None:
    result = revenue_opportunity_investigator_node(
        _state(
            tmp_path,
            [{"invoice_id": "open", "balance_due": 125, "status": "open"}],
        )
    )

    finding = next(item for item in result["evidence"] if item.rule == "outstanding_invoice_balances")
    assert finding.estimated_amount == 125
    assert finding.record_ids == ["open"]


def test_invoice_without_collectible_balance_is_insufficient_evidence(tmp_path: Path) -> None:
    result = revenue_opportunity_investigator_node(
        _state(tmp_path, [{"invoice_id": "paid", "amount": 100}])
    )

    assert result["confidence"] == 0.0
    assert result["case_files"] == []
    plan_item = next(
        item
        for item in result["investigation_plan"]
        if item.investigator == InvestigatorName.REVENUE_OPPORTUNITY
    )
    assert plan_item.status == PlanItemStatus.COMPLETED
