from pathlib import Path

import pandas as pd

from app.graph.nodes.case_manager import case_manager_node
from app.graph.nodes.planner import planner_node
from app.graph.nodes.refund_investigator import refund_investigator_node
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


def _state(datasets: list[DatasetMetadata], *, retry_count: int = 0) -> dict:
    state = case_manager_node({"investigation_id": "PF-REFUND-TEST", "datasets": datasets})
    state["investigation_plan"] = planner_node(state)["investigation_plan"]
    state["retry_count"] = retry_count
    return state


def _rules(result: dict) -> set[str]:
    return {evidence.rule for evidence in result["evidence"]}


def test_normal_refunds_produce_no_leakage_finding(tmp_path: Path) -> None:
    refunds = [
        {
            "refund_id": f"r-{index}",
            "customer_id": f"c-{index}",
            "order_id": f"o-{index}",
            "amount": 100,
            "created_at": f"2026-01-{index + 1:02d}T10:00:00Z",
        }
        for index in range(20)
    ]
    result = refund_investigator_node(_state([_dataset(tmp_path, "refunds.csv", "refunds", refunds)]))

    assert result["evidence"] == []
    assert result["case_files"] == []
    assert result["investigation_plan"][0].status == PlanItemStatus.COMPLETED
    assert any(event.title == "No Meaningful Refund Leakage Detected" for event in result["timeline"])


def test_high_refund_rate_uses_successful_payment_denominator(tmp_path: Path) -> None:
    refunds = [{"refund_id": f"r-{index}", "amount": 100} for index in range(10)]
    payments = [
        {"payment_id": f"p-{index}", "amount": 500, "status": "captured"}
        for index in range(10)
    ]
    result = refund_investigator_node(
        _state(
            [
                _dataset(tmp_path, "refunds.csv", "refunds", refunds),
                _dataset(tmp_path, "payments.csv", "payments", payments),
            ],
            retry_count=1,
        )
    )

    assert "high_refund_rate" in _rules(result)
    high_rate = next(item for item in result["evidence"] if item.rule == "high_refund_rate")
    assert high_rate.metrics["refund_rate"] == 0.2
    assert result["investigation_plan"][1].status == PlanItemStatus.COMPLETED


def test_repeat_customer_refunds_are_dataset_relative(tmp_path: Path) -> None:
    refunds = [
        {"refund_id": f"a-{index}", "customer_id": "repeat", "amount": 100}
        for index in range(5)
    ] + [
        {"refund_id": f"single-{index}", "customer_id": f"single-{index}", "amount": 100}
        for index in range(12)
    ]
    result = refund_investigator_node(_state([_dataset(tmp_path, "refunds.csv", "refunds", refunds)]))

    assert "repeat_customer_refunds" in _rules(result)


def test_refund_amount_outliers_use_robust_statistics(tmp_path: Path) -> None:
    refunds = [
        {"refund_id": f"r-{index}", "amount": 90 + (index % 3) * 10}
        for index in range(20)
    ] + [{"refund_id": "large", "amount": 2_000}]
    result = refund_investigator_node(_state([_dataset(tmp_path, "refunds.csv", "refunds", refunds)]))

    assert "refund_amount_outliers" in _rules(result)


def test_repeated_order_refunds_are_detected(tmp_path: Path) -> None:
    refunds = [
        {"refund_id": "r-1", "order_id": "repeat-order", "amount": 100},
        {"refund_id": "r-2", "order_id": "repeat-order", "amount": 100},
        {"refund_id": "r-3", "order_id": "unique", "amount": 100},
    ]
    result = refund_investigator_node(_state([_dataset(tmp_path, "refunds.csv", "refunds", refunds)]))

    assert "repeated_order_refunds" in _rules(result)


def test_refund_spikes_use_dataset_timestamps(tmp_path: Path) -> None:
    refunds = [
        {
            "refund_id": f"normal-{day}",
            "amount": 100,
            "created_at": f"2026-01-{day:02d}T10:00:00Z",
        }
        for day in range(1, 11)
    ] + [
        {
            "refund_id": f"spike-{index}",
            "amount": 100,
            "created_at": "2026-01-11T10:00:00Z",
        }
        for index in range(5)
    ]
    result = refund_investigator_node(_state([_dataset(tmp_path, "refunds.csv", "refunds", refunds)]))

    assert "refund_spike" in _rules(result)


def test_missing_amount_column_is_insufficient_evidence(tmp_path: Path) -> None:
    result = refund_investigator_node(
        _state([_dataset(tmp_path, "refunds.csv", "refunds", [{"refund_id": "r-1"}])])
    )

    assert result["confidence"] == 0.0
    assert result["evidence"] == []
    assert any(event.title == "Insufficient Refund Evidence" for event in result["timeline"])


def test_empty_refund_data_is_insufficient_evidence(tmp_path: Path) -> None:
    path = tmp_path / "refunds.csv"
    path.write_text("refund_id,amount\n", encoding="utf-8")
    dataset = DatasetMetadata(
        dataset_id="refunds.csv",
        dataset_type="refunds",
        path=str(path),
        row_count=0,
        columns=["refund_id", "amount"],
    )
    result = refund_investigator_node(_state([dataset]))

    assert result["confidence"] == 0.0
    assert result["evidence"] == []


def test_refund_refinement_is_bounded_to_one_retry(tmp_path: Path) -> None:
    refunds = [{"refund_id": f"r-{index}", "amount": 100} for index in range(10)]
    payments = [
        {"payment_id": f"p-{index}", "amount": 500, "status": "captured"}
        for index in range(10)
    ]
    result = refund_investigator_node(
        _state(
            [
                _dataset(tmp_path, "refunds.csv", "refunds", refunds),
                _dataset(tmp_path, "payments.csv", "payments", payments),
            ],
            retry_count=1,
        )
    )

    assert result["requires_more_evidence"] is False
    refund_plan = next(
        item
        for item in result["investigation_plan"]
        if item.investigator == InvestigatorName.REFUND
    )
    assert refund_plan.status == PlanItemStatus.COMPLETED
