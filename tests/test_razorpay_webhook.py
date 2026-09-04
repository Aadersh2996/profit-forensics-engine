import hashlib
import hmac
import json
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.db import session as session_module
from app.db.db_models import Base
from app.main import app
from app.services.razorpay_normalization import normalize_razorpay_payload


_SECRET = "webhook-test-secret"


def _client(tmp_path: Path, monkeypatch) -> TestClient:
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    monkeypatch.setattr(
        session_module, "SessionLocal", sessionmaker(bind=engine, expire_on_commit=False)
    )
    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    monkeypatch.setattr(settings, "razorpay_webhook_secret", _SECRET)
    return TestClient(app)


def _post(client: TestClient, payload: object, *, secret: str = _SECRET):
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    return client.post(
        "/razorpay/webhook",
        content=raw,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": signature},
    )


def _event(event: str, key: str, entity: dict[str, object]) -> dict[str, object]:
    return {"event": event, "payload": {key: {"entity": entity}}}


def test_webhook_rejects_invalid_signatures_and_malformed_payloads(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    payload = _event("payment.captured", "payment", {"id": "pay_1", "amount": 100})

    assert _post(client, payload, secret="wrong-secret").status_code == 401

    malformed = b"{"
    signature = hmac.new(_SECRET.encode(), malformed, hashlib.sha256).hexdigest()
    response = client.post("/razorpay/webhook", content=malformed, headers={"X-Razorpay-Signature": signature})
    assert response.status_code == 400


def test_unknown_verified_webhook_is_acknowledged_without_an_investigation(tmp_path: Path, monkeypatch) -> None:
    response = _post(_client(tmp_path, monkeypatch), {"event": "payout.processed", "payload": {}})

    assert response.status_code == 200
    assert response.json() == {
        "accepted": True,
        "event": "payout.processed",
        "message": "Webhook event is not supported and was ignored.",
        "dataset": None,
        "investigation": None,
    }


@pytest.mark.parametrize(
    ("event", "key", "entity", "resource", "investigator", "title"),
    [
        (
            "payment.captured", "payment",
            {"id": "pay_1", "status": "captured", "amount": 12345, "created_at": 1735689600},
            "payments", "payment_recovery", "Payment Captured",
        ),
        (
            "refund.processed", "refund",
            {"id": "rfnd_1", "payment_id": "pay_1", "status": "processed", "amount": 5000, "created_at": 1735689600},
            "refunds", "refund", "Refund Processed",
        ),
        (
            "subscription.cancelled", "subscription",
            {"id": "sub_1", "status": "cancelled", "created_at": 1735689600, "plan": {"item": {"amount": 9900}}},
            "subscriptions", "subscription", "Subscription Cancelled",
        ),
    ],
)
def test_supported_webhooks_normalize_and_reuse_the_planner(
    tmp_path: Path, monkeypatch, event: str, key: str, entity: dict[str, object], resource: str,
    investigator: str, title: str,
) -> None:
    client = _client(tmp_path, monkeypatch)
    response = _post(client, _event(event, key, entity))

    assert response.status_code == 200
    payload = response.json()
    assert payload["dataset"]["source"] == "razorpay"
    assert payload["dataset"]["dataset_type"] == resource
    assert [item["investigator"] for item in payload["investigation"]["investigation_plan"]] == [investigator]
    titles = [item["title"] for item in payload["investigation"]["timeline"]]
    assert "Razorpay Webhook Received" in titles
    assert title in titles


def test_webhook_normalized_output_matches_the_rest_normalizer_and_persisted_timeline(
    tmp_path: Path, monkeypatch
) -> None:
    entity = {"id": "pay_1", "status": "failed", "amount": 12500, "created_at": 1735689600, "error_description": "gateway timeout"}
    client = _client(tmp_path, monkeypatch)
    response = _post(client, _event("payment.failed", "payment", entity))

    assert response.status_code == 200
    payload = response.json()
    actual = pd.read_csv(payload["dataset"]["path"]).to_dict("records")
    assert actual == normalize_razorpay_payload("payments", entity)
    retrieved = client.get(f"/investigations/{payload['investigation']['investigation_id']}")
    assert retrieved.status_code == 200
    persisted_titles = [event["title"] for event in retrieved.json()["timeline"]]
    assert "Razorpay Webhook Received" in persisted_titles
    assert "Payment Failed" in persisted_titles
