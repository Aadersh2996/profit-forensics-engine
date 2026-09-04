from app.services.razorpay_normalization import normalize_razorpay_payload


def test_payment_normalization_converts_subunits_and_epoch_timestamps() -> None:
    records = normalize_razorpay_payload(
        "payments",
        {
            "items": [
                {
                    "id": "pay_1",
                    "status": "captured",
                    "amount": 12345,
                    "currency": "INR",
                    "created_at": 1_735_689_600,
                    "error_description": "gateway timeout",
                }
            ]
        },
    )

    assert records == [
        {
            "payment_id": "pay_1",
            "status": "captured",
            "amount": 123.45,
            "currency": "INR",
            "created_at": "2025-01-01T00:00:00+00:00",
            "error_reason": "gateway timeout",
        }
    ]


def test_invoice_normalization_maps_collectible_balance_fields() -> None:
    records = normalize_razorpay_payload(
        "invoices",
        {"id": "inv_1", "status": "issued", "amount": 10000, "amount_paid": 2500, "amount_due": 7500},
    )

    assert records[0]["invoice_id"] == "inv_1"
    assert records[0]["amount"] == 100.0
    assert records[0]["paid_amount"] == 25.0
    assert records[0]["balance_due"] == 75.0


def test_order_customer_and_settlement_normalization_are_provider_boundary_only() -> None:
    order = normalize_razorpay_payload("orders", {"id": "order_1", "amount": 10000, "amount_paid": 2500})[0]
    customer = normalize_razorpay_payload("customers", {"id": "cust_1", "email": "owner@example.test"})[0]
    settlement = normalize_razorpay_payload("settlements", {"id": "setl_1", "entity_id": "pay_1", "amount": 5000})[0]

    assert order == {"order_id": "order_1", "amount": 100.0, "amount_paid": 25.0}
    assert customer == {"customer_id": "cust_1", "email": "owner@example.test"}
    assert settlement["payment_id"] == "pay_1"
    assert settlement["amount"] == 50.0
