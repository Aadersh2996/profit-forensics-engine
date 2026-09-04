import httpx
import pytest

from app.services.razorpay_client import RazorpayClient, RazorpayClientError


def test_client_paginates_with_count_and_skip() -> None:
    requests: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(dict(request.url.params))
        skip = int(request.url.params["skip"])
        count = int(request.url.params["count"])
        items = [{"id": f"pay_{value}"} for value in range(skip, min(skip + count, 101))]
        return httpx.Response(200, json={"items": items})

    client = RazorpayClient(
        key_id="key", key_secret="secret", base_url="https://example.test/v1",
        timeout_seconds=1, transport=httpx.MockTransport(handler), sleep=lambda _: None,
    )
    records = client.fetch_resource("payments", max_records=101)
    assert len(records) == 101
    assert [request["skip"] for request in requests] == ["0", "100"]


def test_client_retries_rate_limit_and_rejects_invalid_collections() -> None:
    calls = 0
    sleeps: list[float] = []

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "1"})
        return httpx.Response(200, json={"items": []})

    client = RazorpayClient(
        key_id="key", key_secret="secret", base_url="https://example.test/v1",
        timeout_seconds=1, transport=httpx.MockTransport(handler), sleep=sleeps.append,
    )
    assert client.fetch_resource("refunds", max_records=2) == []
    assert sleeps == [1.0]

    invalid = RazorpayClient(
        key_id="key", key_secret="secret", base_url="https://example.test/v1",
        timeout_seconds=1, transport=httpx.MockTransport(lambda _: httpx.Response(200, json={}))
    )
    with pytest.raises(RazorpayClientError, match="invalid collection"):
        invalid.fetch_resource("payments", max_records=1)


def test_client_uses_time_filters_only_for_supported_collections() -> None:
    observed: list[dict[str, str]] = []
    client = RazorpayClient(
        key_id="key", key_secret="secret", base_url="https://example.test/v1", timeout_seconds=1,
        transport=httpx.MockTransport(lambda request: (observed.append(dict(request.url.params)) or httpx.Response(200, json={"items": []}))),
        sleep=lambda _: None,
    )
    client.fetch_resource("customers", max_records=1, from_timestamp=1, to_timestamp=2)
    client.fetch_resource("payments", max_records=1, from_timestamp=1, to_timestamp=2)
    assert observed == [
        {"count": "1", "skip": "0"},
        {"count": "1", "skip": "0", "from": "1", "to": "2"},
    ]
