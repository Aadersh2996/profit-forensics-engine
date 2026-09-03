from pathlib import Path

import pandas as pd

from app.graph.nodes.case_manager import case_manager_node
from app.graph.nodes.payment_recovery_investigator import payment_recovery_investigator_node
from app.graph.nodes.planner import planner_node
from app.models.schemas import DatasetMetadata, InvestigatorName, PlanItemStatus


def _dataset(tmp_path: Path, name: str, dataset_type: str, rows: list[dict]) -> DatasetMetadata:
    path = tmp_path / name
    pd.DataFrame(rows).to_csv(path, index=False)
    frame = pd.read_csv(path)
    return DatasetMetadata(
        dataset_id=name,
        dataset_type=dataset_type,
        path=str(path),
        row_count=len(frame),
        columns=frame.columns.tolist(),
    )


def _state(datasets: list[DatasetMetadata]) -> dict:
    state = case_manager_node({"investigation_id": "PF-PAYMENT-TEST", "datasets": datasets})
    state["investigation_plan"] = planner_node(state)["investigation_plan"]
    return state


def _rules(result: dict) -> set[str]:
    return {item.rule for item in result["evidence"]}


def test_stale_pending_and_authorized_payments_use_dataset_reference_time(tmp_path: Path) -> None:
    payments = [
        {"payment_id": "pending", "status": "pending", "amount": 100, "created_at": "2025-01-01T00:00:00Z"},
        {"payment_id": "authorized", "status": "authorized", "amount": 200, "created_at": "2025-01-01T00:00:00Z"},
        {"payment_id": "latest", "status": "captured", "amount": 300, "created_at": "2025-01-03T00:00:00Z"},
    ]
    result = payment_recovery_investigator_node(
        _state([_dataset(tmp_path, "payments.csv", "payments", payments)])
    )

    assert {"stuck_pending_payments", "authorized_not_captured"} <= _rules(result)
    pending = next(item for item in result["evidence"] if item.rule == "stuck_pending_payments")
    assert pending.metrics["reference_timestamp"].startswith("2025-01-03")


def test_recoverable_failures_and_timeout_pattern_are_detected(tmp_path: Path) -> None:
    payments = [
        {"payment_id": f"p-{index}", "status": "failed", "amount": 100, "error_reason": "gateway timeout"}
        for index in range(2)
    ] + [{"payment_id": "declined", "status": "failed", "amount": 100, "error_reason": "card declined"}]
    result = payment_recovery_investigator_node(
        _state([_dataset(tmp_path, "payments.csv", "payments", payments)])
    )

    assert {"recoverable_failed_payments", "gateway_timeout_pattern"} <= _rules(result)


def test_stale_initiated_payments_are_abandoned_flows(tmp_path: Path) -> None:
    payments = [
        {"payment_id": "old", "status": "initiated", "amount": 100, "created_at": "2025-02-01T00:00:00Z"},
        {"payment_id": "latest", "status": "captured", "amount": 100, "created_at": "2025-02-03T00:00:00Z"},
    ]
    result = payment_recovery_investigator_node(
        _state([_dataset(tmp_path, "payments.csv", "payments", payments)])
    )

    assert "abandoned_payment_flows" in _rules(result)


def test_settlement_absence_identifies_reconciliation_mismatch(tmp_path: Path) -> None:
    payments = [
        {"payment_id": "settled", "status": "captured", "amount": 100},
        {"payment_id": "missing", "status": "captured", "amount": 200},
    ]
    settlements = [{"payment_id": "settled"}]
    result = payment_recovery_investigator_node(
        _state(
            [
                _dataset(tmp_path, "payments.csv", "payments", payments),
                _dataset(tmp_path, "settlements.csv", "settlements", settlements),
            ]
        )
    )

    assert "reconciliation_mismatches" in _rules(result)


def test_missing_status_is_insufficient_evidence(tmp_path: Path) -> None:
    result = payment_recovery_investigator_node(
        _state([_dataset(tmp_path, "payments.csv", "payments", [{"payment_id": "p-1", "amount": 100}])])
    )

    assert result["confidence"] == 0.0
    assert result["evidence"] == []
    payment_plan = next(
        item
        for item in result["investigation_plan"]
        if item.investigator == InvestigatorName.PAYMENT_RECOVERY
    )
    assert payment_plan.status == PlanItemStatus.COMPLETED
