"""Razorpay connection and synchronization endpoints for the ingestion boundary."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.investigations import create_investigation
from app.config import settings
from app.db.session import get_db
from app.models.schemas import (
    InvestigationRequest,
    RazorpayConnectionStatus,
    RazorpayConnectRequest,
    RazorpayCredentials,
    RazorpaySyncRequest,
    RazorpaySyncResponse,
)
from app.services.razorpay_client import RazorpayClient, RazorpayClientError
from app.services.razorpay_ingestion import persist_normalized_razorpay_dataset
from app.services.razorpay_normalization import normalize_razorpay_payload


router = APIRouter(prefix="/razorpay", tags=["razorpay"])


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
