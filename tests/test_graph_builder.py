from pathlib import Path

import pandas as pd

from app.graph.builder import build_investigation_graph
from app.models.schemas import DatasetMetadata, InvestigationStatus


def test_compiled_graph_runs_an_invoice_investigation_end_to_end(tmp_path: Path) -> None:
    path = tmp_path / "invoices.csv"
    pd.DataFrame(
        [
            {
                "invoice_id": "invoice-1",
                "status": "open",
                "amount": 100,
                "paid_amount": 0,
            }
        ]
    ).to_csv(path, index=False)
    dataset = DatasetMetadata(
        dataset_id="invoices",
        dataset_type="invoices",
        path=str(path),
        row_count=1,
        columns=["invoice_id", "status", "amount", "paid_amount"],
    )

    state = build_investigation_graph().invoke({"investigation_id": "PF-GRAPH", "datasets": [dataset]})

    assert state["status"] == InvestigationStatus.COMPLETED
    assert state["case_files"][0].title == "Revenue collection opportunities detected"
    assert state["executive_summary"] is not None
    assert state["estimated_monthly_loss"] == 100.0
