import pytest
from services.contract_adapter import PaymentContractAdapter

def test_unit_scale_drift_cents_to_dollars():
    """Verify autonomous detection and normalization of Stripe-style minor unit (cents) drift."""
    adapter = PaymentContractAdapter()
    payload = {
        "event_id": "EVT-STRIPE-01",
        "transaction_id": "TX-STRIPE-01",
        "client_id": "CUST-STRIPE-404",
        "amount_cents": 580000,
        "payment_status": "succeeded",
        "idempotency_key": "IDEMP-STRIPE-99"
    }
    res, transforms = adapter.adapt(payload)
    assert res["customer_id"] == "CUST-STRIPE-404"
    assert res["amount"] == 5800.00
    assert res["status"] == "SETTLED"
    assert res["idempotency_token"] == "IDEMP-STRIPE-99"
    assert any("Unit Scale Coercion" in t for t in transforms)
    assert any("Semantic Alias" in t for t in transforms)
    assert any("Enum Normalization" in t for t in transforms)

def test_stringified_currency_symbol_drift():
    """Verify autonomous coercion of dirty stringified currency values."""
    adapter = PaymentContractAdapter()
    payload = {
        "transaction_id": "TX-DIRTY-01",
        "payer_ref": "CUST-DIRTY-77",
        "gross_amount": "$12,450.75",
        "currency": "usd",
        "status": "Authorised"
    }
    res, _transforms = adapter.adapt(payload)
    assert res["customer_id"] == "CUST-DIRTY-77"
    assert res["amount"] == 12450.75
    assert res["status"] == "SETTLED"
    assert res["currency"] == "USD"

def test_nested_cents_and_status_enum():
    """Verify nested structure with status enum and fee detection."""
    adapter = PaymentContractAdapter()
    payload = {
        "transaction_id": "TX-ADYEN-88",
        "user_ref": "CUST-ADYEN-12",
        "payment_detail": {
            "settlement_amount_cents": 92500,
            "processing_fee": 18.50,
            "iso_currency": "EUR"
        },
        "status": "completed",
        "replay_token": "IDEMP-REPLAY-11"
    }
    res, _transforms = adapter.adapt(payload)
    assert res["customer_id"] == "CUST-ADYEN-12"
    assert res["amount"] == 925.00
    assert res["fee_amount"] == 18.50
    assert res["currency"] == "EUR"
    assert res["status"] == "SETTLED"
    assert res["idempotency_token"] == "IDEMP-REPLAY-11"
