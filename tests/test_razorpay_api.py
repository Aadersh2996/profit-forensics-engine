from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import razorpay as razorpay_api
from app.config import settings
from app.db import session as session_module
from app.db.db_models import Base
from app.main import app


class _FakeRazorpayClient:
    def close(self) -> None:
        pass

    def test_connection(self) -> None:
        pass

    def fetch_resource(self, resource: str, **_: object) -> list[dict[str, object]]:
        return {
            "payments": [
                {"id": "pay_1", "status": "failed", "amount": 12500, "created_at": 1735689600,
                 "error_description": "gateway timeout"}
            ],
            "invoices": [
                {"id": "inv_1", "status": "open", "amount": 5000, "amount_paid": 0,
                 "amount_due": 5000, "created_at": 1735689600}
            ],
        }[resource]


def test_razorpay_connection_and_sync_reuse_dataset_contract(tmp_path: Path, monkeypatch) -> None:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(session_module, "SessionLocal", sessionmaker(bind=engine, expire_on_commit=False))
    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    monkeypatch.setattr(razorpay_api, "_client", lambda _: _FakeRazorpayClient())
    client = TestClient(app)
    credentials = {"key_id": "rzp_test_key", "key_secret": "secret"}

    assert client.post("/razorpay/connect", json={"credentials": credentials}).status_code == 200
    response = client.post(
        "/razorpay/sync",
        json={"credentials": credentials, "resources": ["payments", "invoices"], "run_investigation": True, "investigation_id": "PF-RZP"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert [dataset["source"] for dataset in payload["datasets"]] == ["razorpay", "razorpay"]
    assert [dataset["dataset_type"] for dataset in payload["datasets"]] == ["payments", "invoices"]
    assert all(Path(dataset["path"]).is_file() for dataset in payload["datasets"])
    assert payload["investigation"]["status"] == "completed"
    assert {item["investigator"] for item in payload["investigation"]["investigation_plan"]} == {
        "payment_recovery", "revenue_opportunity"
    }


def test_razorpay_sync_requires_credentials_and_unique_resources(monkeypatch) -> None:
    monkeypatch.setattr(settings, "razorpay_key_id", None)
    monkeypatch.setattr(settings, "razorpay_key_secret", None)
    client = TestClient(app)
    assert client.post("/razorpay/sync", json={"resources": ["payments"]}).status_code == 503
    assert client.post(
        "/razorpay/sync",
        json={"credentials": {"key_id": "key", "key_secret": "secret"}, "resources": ["payments", "payments"]},
    ).status_code == 422


def test_razorpay_sync_rejects_an_all_empty_selection(monkeypatch) -> None:
    class _EmptyClient(_FakeRazorpayClient):
        def fetch_resource(self, resource: str, **_: object) -> list[dict[str, object]]:
            return []

    monkeypatch.setattr(razorpay_api, "_client", lambda _: _EmptyClient())
    response = TestClient(app).post(
        "/razorpay/sync",
        json={"credentials": {"key_id": "key", "key_secret": "secret"}, "resources": ["payments"]},
    )
    assert response.status_code == 422
