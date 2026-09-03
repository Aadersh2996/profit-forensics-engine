from pathlib import Path

import pandas as pd

from app.graph.nodes.case_manager import case_manager_node
from app.graph.nodes.discount_investigator import discount_investigator_node
from app.graph.nodes.planner import planner_node
from app.models.schemas import DatasetMetadata


def _state(tmp_path: Path, rows: list[dict]) -> dict:
    path = tmp_path / "discounts.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    frame = pd.read_csv(path)
    dataset = DatasetMetadata(dataset_id="discounts", dataset_type="discounts", path=str(path), row_count=len(frame), columns=frame.columns.tolist())
    state = case_manager_node({"investigation_id": "PF-DISCOUNT", "datasets": [dataset]})
    state["investigation_plan"] = planner_node(state)["investigation_plan"]
    return state


def test_discount_outliers_and_customer_concentration_are_traceable(tmp_path: Path) -> None:
    rows = [{"id": f"normal-{i}", "customer_id": f"c-{i}", "discount_amount": 10} for i in range(10)]
    rows += [{"id": f"heavy-{i}", "customer_id": "heavy", "discount_amount": 200} for i in range(4)]
    result = discount_investigator_node(_state(tmp_path, rows))

    rules = {item.rule for item in result["evidence"]}
    assert "repeated_heavy_discount_usage" in rules
    assert "discount_concentration" in rules
    assert result["case_files"][0].estimated_monthly_loss > 0


def test_discount_data_without_amount_is_insufficient(tmp_path: Path) -> None:
    result = discount_investigator_node(_state(tmp_path, [{"id": "missing"}]))

    assert result["confidence"] == 0.0
    assert result["case_files"] == []
