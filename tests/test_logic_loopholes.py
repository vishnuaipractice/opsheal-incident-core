import pytest
from database import db
from services.contract_adapter import PaymentContractAdapter
from database.migrations.migration_002_add_v2_columns import run_migration
from services.dlq_drainer import drain_and_recover_dlq
from dlq.dlq_manager import clear_dlq, push_to_dlq, get_dlq_count
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

def test_empty_and_non_dict_payload_resilience():
    """
    Loophole Test 1: Empty or malformed inputs must never trigger unhandled exceptions.
    """
    adapter = PaymentContractAdapter()
    
    # Empty dict
    res_empty, _ = adapter.adapt({})
    assert res_empty["customer_id"] == "UNKNOWN_CUSTOMER"
    assert res_empty["amount"] == 0.0
    assert res_empty["status"] == "SETTLED"
    assert res_empty["transaction_id"].startswith("TX-FALLBACK-")

    # None input
    res_none, _ = adapter.adapt(None)  # type: ignore
    assert res_none["amount"] == 0.0

    # List input
    res_list, _ = adapter.adapt([])  # type: ignore
    assert res_list["amount"] == 0.0


def test_multi_currency_symbols_and_formats():
    """
    Loophole Test 2: Foreign or complex string currency notations must be cleanly coerced.
    """
    adapter = PaymentContractAdapter()
    test_cases = [
        ({"transaction_id": "TX-EUR", "customer_id": "CUST-1", "amount": "€ 1,250.50"}, 1250.50),
        ({"transaction_id": "TX-GBP", "customer_id": "CUST-2", "amount": "£ 890.00"}, 890.00),
        ({"transaction_id": "TX-USD", "customer_id": "CUST-3", "amount": "USD $ 3,450.00"}, 3450.00),
        ({"transaction_id": "TX-REFUND", "customer_id": "CUST-4", "amount": "-75.50"}, -75.50),
    ]

    for payload, expected_amount in test_cases:
        norm, _ = adapter.adapt(payload)
        assert norm["amount"] == expected_amount, f"Failed on {payload['amount']}"


def test_anti_double_spend_idempotency_guard():
    """
    Loophole Test 3: Upstream network retries with differing transaction IDs
    but identical idempotency tokens must NEVER double-bill or duplicate rows.
    """
    db.reset_db(migrated=True)
    clear_dlq()

    # Attempt 1
    webhook_1 = {
        "event_id": "EVT-ST-01",
        "transaction_id": "TX-ST-ORIGINAL",
        "account_ref": "CUST-ENTERPRISE-IDEMP",
        "payment_detail": {
            "settlement_amount": 5000.00,
            "fee_amount": 15.00,
            "iso_currency": "USD"
        },
        "idempotency_token": "IDEMP-TOKEN-SECURE-999"
    }
    res1 = client.post("/v1/webhooks/payment", json=webhook_1)
    assert res1.status_code == 200
    assert res1.json()["settled_amount"] == 5000.00

    stats_after_1 = db.get_stats()
    assert stats_after_1["settled_count"] == 1
    assert stats_after_1["settled_volume"] == 5000.00

    # Attempt 2: Same idempotency token, but network generated new transaction_id
    webhook_2 = {
        "event_id": "EVT-ST-02",
        "transaction_id": "TX-ST-RETRY-NETWORK-TIMEOUT",
        "account_ref": "CUST-ENTERPRISE-IDEMP",
        "payment_detail": {
            "settlement_amount": 5000.00,
            "fee_amount": 15.00,
            "iso_currency": "USD"
        },
        "idempotency_token": "IDEMP-TOKEN-SECURE-999"
    }
    res2 = client.post("/v1/webhooks/payment", json=webhook_2)
    assert res2.status_code == 200
    assert res2.json()["deduplicated"] is True

    # Ledger MUST NOT have charged twice!
    stats_after_2 = db.get_stats()
    assert stats_after_2["settled_count"] == 1
    assert stats_after_2["settled_volume"] == 5000.00


def test_idempotent_repeated_migrations():
    """
    Loophole Test 4: Running migrations multiple times concurrently or sequentially
    must be 100% idempotent without throwing duplicate column errors.
    """
    for _ in range(5):
        res = run_migration()
        assert res["status"] in ["APPLIED", "ALREADY_UP_TO_DATE"]


def test_empty_dlq_drain_graceful_handling():
    """
    Loophole Test 5: Triggering remediation or draining when DLQ is empty must return cleanly.
    """
    clear_dlq()
    res = drain_and_recover_dlq()
    assert res["status"] == "DLQ_EMPTY"
    assert res["recovered_count"] == 0
    assert res["recovered_volume_usd"] == 0.0


def test_all_outage_scenarios_mathematical_consistency():
    """
    Loophole Test 6: Verify that all outage scenarios (stripe, mixed, v2)
    consistently produce exactly 15 records, $69,000.00 trapped volume,
    and 100% full recovery upon autonomous remediation.
    """
    for scen in ["v2", "stripe", "mixed"]:
        # Trigger Outage
        outage_res = client.post(f"/v1/demo/trigger-outage?scenario={scen}")
        assert outage_res.status_code == 200

        dlq_data = client.get("/v1/dlq").json()
        assert dlq_data["dlq_count"] == 15
        assert dlq_data["trapped_volume_usd"] == 69000.00

        # Remediate
        heal_res = client.post("/v1/demo/remediate")
        assert heal_res.status_code == 200

        telem = client.get("/v1/telemetry").json()
        assert telem["dlq"]["dlq_count"] == 0
        assert telem["stats"]["settled_count"] == 15
        assert telem["stats"]["settled_volume"] == 69000.00
