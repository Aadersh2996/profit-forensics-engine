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
