from pathlib import Path

import pandas as pd

from app.graph.builder import build_investigation_graph
from app.models.schemas import DatasetMetadata
from app.services.razorpay_ingestion import persist_normalized_razorpay_dataset
from app.services.razorpay_normalization import normalize_razorpay_payload


def _csv_dataset(path: Path, dataset_type: str) -> DatasetMetadata:
    frame = pd.read_csv(path)
    return DatasetMetadata(
        dataset_id=path.stem, dataset_type=dataset_type, path=str(path), row_count=len(frame),
        columns=frame.columns.tolist(), source="csv",
    )


def test_razorpay_and_equivalent_csv_data_produce_the_same_graph_result(tmp_path: Path) -> None:
    payment_rows = normalize_razorpay_payload("payments", [
        {"id": "pay_1", "status": "failed", "amount": 12500, "created_at": 1735689600,
         "error_description": "gateway timeout"}
    ])
    invoice_rows = normalize_razorpay_payload("invoices", [
        {"id": "inv_1", "status": "open", "amount": 5000, "amount_paid": 0,
         "amount_due": 5000, "created_at": 1735689600}
    ])
    csv_paths = []
    for resource, rows in (("payments", payment_rows), ("invoices", invoice_rows)):
        path = tmp_path / f"{resource}.csv"
        pd.DataFrame(rows).to_csv(path, index=False)
        csv_paths.append(_csv_dataset(path, resource))
    razorpay_datasets = [
        persist_normalized_razorpay_dataset(upload_dir=tmp_path / "razorpay", resource="payments", records=payment_rows),
        persist_normalized_razorpay_dataset(upload_dir=tmp_path / "razorpay", resource="invoices", records=invoice_rows),
    ]

    csv_state = build_investigation_graph().invoke({"investigation_id": "PF-CSV", "datasets": csv_paths})
    razorpay_state = build_investigation_graph().invoke({"investigation_id": "PF-RZP", "datasets": razorpay_datasets})

    assert [item.investigator for item in razorpay_state["investigation_plan"]] == [
        item.investigator for item in csv_state["investigation_plan"]
    ]
    assert razorpay_state["estimated_monthly_loss"] == csv_state["estimated_monthly_loss"]
    assert razorpay_state["estimated_annual_loss"] == csv_state["estimated_annual_loss"]
    assert [case.title for case in razorpay_state["case_files"]] == [case.title for case in csv_state["case_files"]]
