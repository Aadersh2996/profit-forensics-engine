"""Razorpay connection and synchronization endpoints for the ingestion boundary."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.investigations import create_investigation
from app.config import settings
from app.db.db_models import Investigation, TimelineEventORM
from app.db.session import get_db
from app.models.schemas import (
    InvestigationRequest,
    RazorpayConnectionStatus,
    RazorpayConnectRequest,
    RazorpayCredentials,
    RazorpaySyncRequest,
    RazorpaySyncResponse,
    RazorpayWebhookResponse,
    TimelineEvent,
)
from app.services.razorpay_client import RazorpayClient, RazorpayClientError
from app.services.razorpay_ingestion import persist_normalized_razorpay_dataset
from app.services.razorpay_normalization import normalize_razorpay_payload


router = APIRouter(prefix="/razorpay", tags=["razorpay"])
logger = logging.getLogger(__name__)

_WEBHOOK_EVENTS: dict[str, tuple[str, str, str]] = {
    "payment.authorized": ("payments", "payment", "Payment Authorized"),
    "payment.captured": ("payments", "payment", "Payment Captured"),
    "payment.failed": ("payments", "payment", "Payment Failed"),
    "refund.created": ("refunds", "refund", "Refund Created"),
    "refund.processed": ("refunds", "refund", "Refund Processed"),
    "order.paid": ("orders", "order", "Order Paid"),
    "subscription.charged": ("subscriptions", "subscription", "Subscription Charged"),
    "subscription.cancelled": ("subscriptions", "subscription", "Subscription Cancelled"),
    "subscription.paused": ("subscriptions", "subscription", "Subscription Paused"),
    "invoice.paid": ("invoices", "invoice", "Invoice Paid"),
    "invoice.expired": ("invoices", "invoice", "Invoice Expired"),
    "settlement.processed": ("settlements", "settlement", "Settlement Processed"),
}


def _resolve_credentials(
    supplied: RazorpayCredentials | None,
) -> tuple[RazorpayCredentials, str]:
    if supplied is not None:
        return supplied, "request"
    if settings.razorpay_key_id and settings.razorpay_key_secret:
        return (
            RazorpayCredentials(
                key_id=settings.razorpay_key_id,
                key_secret=settings.razorpay_key_secret,
            ),
            "environment",
        )
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Razorpay credentials are not configured.",
    )


def _client(credentials: RazorpayCredentials) -> RazorpayClient:
    return RazorpayClient(
        key_id=credentials.key_id,
        key_secret=credentials.key_secret,
        base_url=settings.razorpay_api_base_url,
        timeout_seconds=settings.razorpay_timeout_seconds,
    )


def _provider_error(exc: RazorpayClientError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))


def _verify_webhook_signature(raw_body: bytes, signature: str | None) -> None:
    """Validate Razorpay's HMAC-SHA256 signature against the unmodified request body."""

    if not settings.razorpay_webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Razorpay webhook secret is not configured.",
        )
    if not signature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Razorpay webhook signature.",
        )
    expected = hmac.new(
        settings.razorpay_webhook_secret.encode("utf-8"), raw_body, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Razorpay webhook signature.",
        )


def _webhook_entity(event: str, payload: object) -> tuple[str, str, str, dict[str, object]]:
    """Extract the primary Razorpay resource entity for one supported event."""

    event_spec = _WEBHOOK_EVENTS.get(event)
    if event_spec is None:
        raise ValueError("Unsupported Razorpay webhook event.")
    resource, payload_key, title = event_spec
    if not isinstance(payload, dict):
        raise ValueError("Webhook payload must be an object.")
    resource_payload = payload.get(payload_key)
    if not isinstance(resource_payload, dict):
        raise ValueError(f"Webhook payload is missing the {payload_key} resource.")
    entity = resource_payload.get("entity")
    if not isinstance(entity, dict) or not isinstance(entity.get("id"), str) or not entity["id"].strip():
        raise ValueError(f"Webhook {payload_key} entity must include a non-empty id.")
    return resource, payload_key, title, entity


def _append_webhook_timeline(
    db: Session, report, *, event: str, title: str
):
    """Annotate a fresh webhook-driven case without changing its graph workflow."""

    annotations = [
        TimelineEvent(
            title="Razorpay Webhook Received",
            description=f"Verified Razorpay event {event} was normalized before investigation.",
            stage="razorpay_webhook",
            progress=1.0,
        ),
        TimelineEvent(
            title=title,
            description="The verified provider event was recorded as the source of this investigation.",
            stage="razorpay_webhook",
            progress=1.0,
        ),
    ]
    investigation = db.get(Investigation, report.investigation_id)
    if investigation is None:
        raise RuntimeError("Webhook investigation was not persisted.")
    investigation.timeline_events.extend(
        TimelineEventORM(
            id=item.id,
            title=item.title,
            description=item.description,
            stage=item.stage,
            progress=item.progress,
            created_at=item.created_at,
        )
        for item in annotations
    )
    db.commit()
    return report.model_copy(update={"timeline": [*report.timeline, *annotations]})


@router.get("/status", response_model=RazorpayConnectionStatus)
def razorpay_status() -> RazorpayConnectionStatus:
    """Report only whether environment credentials are available; never expose secrets."""

    configured = bool(settings.razorpay_key_id and settings.razorpay_key_secret)
    return RazorpayConnectionStatus(
        configured=configured,
        source="environment" if configured else None,
        message=("Razorpay environment credentials are available." if configured else "Provide credentials to connect or configure environment variables."),
    )


@router.post("/connect", response_model=RazorpayConnectionStatus)
def connect_razorpay(request: RazorpayConnectRequest) -> RazorpayConnectionStatus:
    """Test read-only Razorpay access with transient or environment credentials."""

    credentials, source = _resolve_credentials(request.credentials)
    client = _client(credentials)
    try:
        client.test_connection()
    except RazorpayClientError as exc:
        raise _provider_error(exc) from exc
    finally:
        client.close()
    return RazorpayConnectionStatus(
        configured=True, source=source, message="Razorpay connection validated."
    )


@router.post("/sync", response_model=RazorpaySyncResponse, status_code=status.HTTP_201_CREATED)
def sync_razorpay(
    request: RazorpaySyncRequest, db: Session = Depends(get_db)
) -> RazorpaySyncResponse:
    """Fetch, normalize, and optionally investigate Razorpay resources without provider-aware graph code."""

    credentials, _ = _resolve_credentials(request.credentials)
    client = _client(credentials)
    normalized: list[tuple[str, list[dict[str, object]]]] = []
    try:
        for resource in request.resources:
            name = resource.value
            payload = client.fetch_resource(
                name,
                max_records=request.max_records_per_resource,
                from_timestamp=request.from_timestamp,
                to_timestamp=request.to_timestamp,
            )
            normalized.append((name, normalize_razorpay_payload(name, payload)))
    except (RazorpayClientError, ValueError) as exc:
        raise _provider_error(
            exc if isinstance(exc, RazorpayClientError) else RazorpayClientError("Razorpay data could not be normalized.")
        ) from exc
    finally:
        client.close()

    datasets = [
        persist_normalized_razorpay_dataset(
            upload_dir=settings.upload_dir, resource=resource, records=records
        )
        for resource, records in normalized
        if records
    ]
    if not datasets:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="No records were returned for the selected Razorpay resources.",
        )
    report = (
        create_investigation(
            InvestigationRequest(investigation_id=request.investigation_id, datasets=datasets), db
        )
        if request.run_investigation
        else None
    )
    return RazorpaySyncResponse(
        datasets=datasets,
        investigation=report,
        message=("Razorpay data synchronized and investigation completed." if report else "Razorpay data synchronized."),
    )


@router.post("/webhook", response_model=RazorpayWebhookResponse)
async def receive_razorpay_webhook(
    request: Request, db: Session = Depends(get_db)
) -> RazorpayWebhookResponse:
    """Verify, normalize, and investigate one supported Razorpay webhook event."""

    raw_body = await request.body()
    _verify_webhook_signature(raw_body, request.headers.get("X-Razorpay-Signature"))
    try:
        envelope = json.loads(raw_body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Webhook body must be valid JSON."
        ) from exc
    if not isinstance(envelope, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Webhook body must be a JSON object.",
        )
    event = envelope.get("event")
    if not isinstance(event, str) or not event.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Webhook event must be a non-empty string.",
        )
    event = event.strip()
    if event not in _WEBHOOK_EVENTS:
        logger.info("Ignoring unsupported verified Razorpay webhook event: %s", event)
        return RazorpayWebhookResponse(
            accepted=True, event=event, message="Webhook event is not supported and was ignored."
        )
    try:
        resource, _, title, entity = _webhook_entity(event, envelope.get("payload"))
        records = normalize_razorpay_payload(resource, entity)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    dataset = persist_normalized_razorpay_dataset(
        upload_dir=settings.upload_dir, resource=resource, records=records
    )
    report = create_investigation(InvestigationRequest(datasets=[dataset]), db)
    report = _append_webhook_timeline(db, report, event=event, title=title)
    logger.info("Processed verified Razorpay webhook event: %s", event)
    return RazorpayWebhookResponse(
        accepted=True,
        event=event,
        message="Webhook normalized and investigated.",
        dataset=dataset,
        investigation=report,
    )
