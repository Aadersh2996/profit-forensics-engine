from pathlib import Path

import pandas as pd

from app.graph.nodes.case_manager import case_manager_node
from app.graph.nodes.planner import planner_node
from app.graph.nodes.subscription_investigator import subscription_investigator_node
from app.models.schemas import DatasetMetadata


def test_subscription_recovery_signals(tmp_path: Path) -> None:
    path = tmp_path / "subscriptions.csv"
    pd.DataFrame([
        {"subscription_id": "s1", "customer_id": "repeat", "status": "renewal_failed", "amount": 100},
        {"subscription_id": "s2", "customer_id": "repeat", "status": "renewal_failed", "amount": 100},
        {"subscription_id": "s3", "customer_id": "other", "status": "cancelled", "amount": 200},
    ]).to_csv(path, index=False)
    dataset = DatasetMetadata(dataset_id="subscriptions", dataset_type="subscriptions", path=str(path), row_count=3, columns=["subscription_id", "customer_id", "status", "amount"])
    state = case_manager_node({"investigation_id": "PF-SUB", "datasets": [dataset]})
    state["investigation_plan"] = planner_node(state)["investigation_plan"]

    result = subscription_investigator_node(state)

    assert {item.rule for item in result["evidence"]} == {"renewal_failures", "cancellation_behavior", "repeated_renewal_failures"}
    assert result["case_files"][0].estimated_monthly_loss == 400
