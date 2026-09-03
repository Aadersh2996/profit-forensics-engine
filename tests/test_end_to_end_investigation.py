from pathlib import Path

import pandas as pd

from app.graph.builder import build_investigation_graph
from app.models.schemas import DatasetMetadata, InvestigationStatus, InvestigatorName


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


def test_full_investigation_lifecycle_preserves_traceable_case_impact(tmp_path: Path) -> None:
    datasets = [
        _dataset(
            tmp_path,
            "payments.csv",
            "payments",
            [
                {"payment_id": "pending", "status": "pending", "amount": 100, "created_at": "2025-01-01T00:00:00Z"},
                {"payment_id": "captured", "status": "captured", "amount": 100, "created_at": "2025-01-03T00:00:00Z"},
                {"payment_id": "failed", "status": "failed", "amount": 100, "error_reason": "gateway timeout"},
            ],
        ),
        _dataset(
            tmp_path,
            "refunds.csv",
            "refunds",
            [{"refund_id": "refund-1", "amount": 100, "customer_id": "customer-1"}],
        ),
        _dataset(
            tmp_path,
            "discounts.csv",
            "discounts",
            [{"id": "discount-1", "discount_amount": 10}],
        ),
        _dataset(
            tmp_path,
            "subscriptions.csv",
            "subscriptions",
            [
                {"subscription_id": "subscription-1", "status": "renewal_failed", "amount": 50},
                {"subscription_id": "subscription-2", "status": "cancelled", "amount": 50},
            ],
        ),
        _dataset(
            tmp_path,
            "invoices.csv",
            "invoices",
            [{"invoice_id": "invoice-1", "status": "open", "amount": 75, "paid_amount": 0}],
        ),
        _dataset(tmp_path, "settlements.csv", "settlements", [{"payment_id": "captured"}]),
    ]

    state = build_investigation_graph().invoke({"investigation_id": "PF-E2E", "datasets": datasets})

    assert state["status"] == InvestigationStatus.COMPLETED
    assert set(state["completed_investigations"]) == {
        InvestigatorName.PAYMENT_RECOVERY,
        InvestigatorName.REFUND,
        InvestigatorName.DISCOUNT,
        InvestigatorName.SUBSCRIPTION,
        InvestigatorName.REVENUE_OPPORTUNITY,
    }
    assert state["retry_count"] == 1
    assert len({case_file.id for case_file in state["case_files"]}) == len(state["case_files"])
    assert state["estimated_monthly_loss"] == round(
        sum(case_file.estimated_monthly_loss for case_file in state["case_files"]), 2
    )
    assert state["executive_summary"] is not None
    assert state["timeline"][-1].progress == 1.0
