from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


def test_csv_upload_returns_inspected_dataset_metadata(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    client = TestClient(app)

    response = client.post(
        "/datasets/upload",
        data={"dataset_type": "payments"},
        files={"file": ("payments.csv", b"payment_id,amount\np1,100\n", "text/csv")},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["dataset"]["dataset_type"] == "payments"
    assert payload["dataset"]["row_count"] == 1
    assert payload["dataset"]["columns"] == ["payment_id", "amount"]


def test_csv_upload_rejects_other_file_types(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    response = TestClient(app).post(
        "/datasets/upload",
        data={"dataset_type": "payments"},
        files={"file": ("payments.json", b"[]", "application/json")},
    )

    assert response.status_code == 415


def test_csv_upload_rejects_whitespace_dataset_type(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    response = TestClient(app).post(
        "/datasets/upload",
        data={"dataset_type": "   "},
        files={"file": ("payments.csv", b"payment_id,amount\np1,100\n", "text/csv")},
    )

    assert response.status_code == 422
