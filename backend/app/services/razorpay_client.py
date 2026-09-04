"""Small, retry-bounded Razorpay REST client used only by the ingestion boundary."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

import httpx


logger = logging.getLogger(__name__)
_RESOURCE_PATHS = {
    "payments": "payments", "refunds": "refunds", "orders": "orders",
    "customers": "customers", "subscriptions": "subscriptions", "invoices": "invoices",
    "settlements": "settlements",
}
_RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}
_TIME_FILTERED_RESOURCES = {"payments", "refunds", "orders", "subscriptions", "invoices", "settlements"}


class RazorpayClientError(RuntimeError):
    """Safe provider-facing error that never includes credential values."""


class RazorpayClient:
    """Fetch Razorpay collection resources with Basic auth and bounded retries."""

    def __init__(
        self,
        *,
        key_id: str,
        key_secret: str,
        base_url: str,
        timeout_seconds: float,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url.rstrip("/") + "/",
            auth=(key_id, key_secret),
            timeout=timeout_seconds,
            transport=transport,
        )
        self._sleep = sleep

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "RazorpayClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _get_collection(self, path: str, params: dict[str, int]) -> list[dict[str, Any]]:
        for attempt in range(3):
            try:
                response = self._client.get(path, params=params)
            except httpx.TransportError as exc:
                if attempt == 2:
                    logger.warning("Razorpay request failed for %s after retries", path)
                    raise RazorpayClientError("Razorpay could not be reached.") from exc
                self._sleep(0.5 * (2**attempt))
                continue
            if response.status_code in _RETRYABLE_STATUS_CODES and attempt < 2:
                retry_after = response.headers.get("Retry-After")
                try:
                    delay = min(float(retry_after), 30.0) if retry_after else 0.5 * (2**attempt)
                except ValueError:
                    delay = 0.5 * (2**attempt)
                logger.info("Razorpay returned %s for %s; retrying", response.status_code, path)
                self._sleep(delay)
                continue
            if response.is_error:
                logger.warning("Razorpay returned HTTP %s for %s", response.status_code, path)
                raise RazorpayClientError("Razorpay rejected the request. Verify the credentials and account access.")
            try:
                payload = response.json()
            except ValueError as exc:
                raise RazorpayClientError("Razorpay returned an invalid JSON response.") from exc
            if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
                raise RazorpayClientError("Razorpay returned an invalid collection response.")
            items = payload["items"]
            if not all(isinstance(item, dict) for item in items):
                raise RazorpayClientError("Razorpay returned invalid resource records.")
            return items
        raise AssertionError("retry loop must return or raise")

    def test_connection(self) -> None:
        """Validate credentials with a minimal read-only collection request."""

        self._get_collection("payments", {"count": 1, "skip": 0})

    def fetch_resource(
        self,
        resource: str,
        *,
        max_records: int,
        from_timestamp: int | None = None,
        to_timestamp: int | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch a complete bounded collection using Razorpay's count/skip pagination."""

        path = _RESOURCE_PATHS.get(resource)
        if path is None:
            raise RazorpayClientError(f"Unsupported Razorpay resource '{resource}'.")
        records: list[dict[str, Any]] = []
        skip = 0
        page_size = min(100, max_records)
        while len(records) < max_records:
            params = {"count": min(page_size, max_records - len(records)), "skip": skip}
            if resource in _TIME_FILTERED_RESOURCES and from_timestamp is not None:
                params["from"] = from_timestamp
            if resource in _TIME_FILTERED_RESOURCES and to_timestamp is not None:
                params["to"] = to_timestamp
            page = self._get_collection(path, params)
            records.extend(page)
            if len(page) < params["count"]:
                break
            skip += len(page)
        return records
