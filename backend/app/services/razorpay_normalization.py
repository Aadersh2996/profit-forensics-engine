"""Pure boundary normalization for Razorpay API payloads.

This module does not call Razorpay. It converts already obtained provider
payloads into the canonical field names expected by the investigators.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


_SUPPORTED_RESOURCES = {"payments", "refunds", "subscriptions", "invoices"}


def _records(payload: dict[str, Any] | list[dict[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return payload
    items = payload.get("items")
    if isinstance(items, list):
        return items
    if payload.get("id"):
        return [payload]
    raise ValueError("Razorpay payload must be a resource object or an items collection.")


def _major_amount(value: Any) -> float | None:
    if value is None:
        return None
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    return value / 100


def _timestamp(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return datetime.fromtimestamp(value, timezone.utc).isoformat()
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _clean(record: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if value is not None}


def _normalize_payment(record: dict[str, Any]) -> dict[str, Any]:
    return _clean(
        {
            "payment_id": record.get("id"),
            "order_id": record.get("order_id"),
            "customer_id": record.get("customer_id"),
            "status": record.get("status"),
            "amount": _major_amount(record.get("amount")),
            "currency": record.get("currency"),
            "created_at": _timestamp(record.get("created_at")),
            "error_reason": record.get("error_description") or record.get("error_reason"),
        }
    )


def _normalize_refund(record: dict[str, Any]) -> dict[str, Any]:
    return _clean(
        {
            "refund_id": record.get("id"),
            "payment_id": record.get("payment_id"),
            "customer_id": record.get("customer_id"),
            "status": record.get("status"),
            "amount": _major_amount(record.get("amount")),
            "currency": record.get("currency"),
            "created_at": _timestamp(record.get("created_at")),
        }
    )


def _normalize_subscription(record: dict[str, Any]) -> dict[str, Any]:
    plan = record.get("plan") if isinstance(record.get("plan"), dict) else {}
    item = plan.get("item") if isinstance(plan.get("item"), dict) else {}
    return _clean(
        {
            "subscription_id": record.get("id"),
            "customer_id": record.get("customer_id"),
            "status": record.get("status"),
            "plan_amount": _major_amount(item.get("amount")),
            "currency": item.get("currency") or record.get("currency"),
            "created_at": _timestamp(record.get("created_at")),
            "current_start": _timestamp(record.get("current_start")),
            "current_end": _timestamp(record.get("current_end")),
        }
    )


def _normalize_invoice(record: dict[str, Any]) -> dict[str, Any]:
    return _clean(
        {
            "invoice_id": record.get("id"),
            "customer_id": record.get("customer_id"),
            "status": record.get("status"),
            "amount": _major_amount(record.get("amount")),
            "paid_amount": _major_amount(record.get("amount_paid")),
            "balance_due": _major_amount(record.get("amount_due")),
            "currency": record.get("currency"),
            "issued_at": _timestamp(record.get("issued_at")),
            "due_date": _timestamp(record.get("expire_by")),
        }
    )


_NORMALIZERS = {
    "payments": _normalize_payment,
    "refunds": _normalize_refund,
    "subscriptions": _normalize_subscription,
    "invoices": _normalize_invoice,
}


def normalize_razorpay_payload(
    resource: str, payload: dict[str, Any] | list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Normalize a Razorpay resource payload into investigator-compatible records.

    Razorpay communicates monetary values in currency subunits; this boundary
    converts them to major currency units once and preserves the source's
    currency field alongside each normalized amount.
    """

    normalized_resource = resource.strip().lower()
    if normalized_resource not in _SUPPORTED_RESOURCES:
        raise ValueError(f"Unsupported Razorpay resource '{resource}'.")
    normalizer = _NORMALIZERS[normalized_resource]
    records = _records(payload)
    if not all(isinstance(record, dict) for record in records):
        raise ValueError("Razorpay items must be JSON objects.")
    return [normalizer(record) for record in records]
