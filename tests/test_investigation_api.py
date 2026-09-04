from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.db_models import Base
from app.db import session as session_module
from app.main import app


def test_investigation_endpoints_execute_and_retrieve_a_report(tmp_path: Path, monkeypatch) -> None:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    monkeypatch.setattr(session_module, "SessionLocal", sessionmaker(bind=engine, expire_on_commit=False))
    path = tmp_path / "invoices.csv"
    pd.DataFrame(
        [{"invoice_id": "invoice-1", "status": "open", "amount": 100, "paid_amount": 0}]
    ).to_csv(path, index=False)
    payload = {
        "investigation_id": "PF-API",
        "datasets": [
            {
                "dataset_id": "invoices",
                "dataset_type": "invoices",
                "path": str(path),
                "row_count": 1,
                "columns": ["invoice_id", "status", "amount", "paid_amount"],
            }
        ],
    }

    client = TestClient(app)
    created = client.post("/investigations", json=payload)
    listed = client.get("/investigations")
    retrieved = client.get("/investigations/PF-API")

    assert created.status_code == 201
    assert created.json()["status"] == "completed"
    assert listed.status_code == 200
    assert listed.json()[0]["investigation_id"] == "PF-API"
    assert retrieved.status_code == 200
    assert retrieved.json()["case_files"][0]["title"] == "Revenue collection opportunities detected"
    assert retrieved.json()["datasets"] == created.json()["datasets"]
    assert retrieved.json()["investigation_plan"][0]["investigator"] == "revenue_opportunity"

    duplicate = client.post("/investigations", json=payload)
    assert duplicate.status_code == 409

    assert client.post("/investigations", json={"datasets": []}).status_code == 422
    assert client.get("/investigations/missing").status_code == 404
