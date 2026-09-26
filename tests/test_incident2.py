import pytest
from fastapi.testclient import TestClient
from api.main import app
from database import db
from database.migrations.migration_002_add_v2_columns import run_migration
from services.contract_adapter import PaymentContractAdapter
from dlq.dlq_manager import push_to_dlq, get_dlq_count, clear_dlq
from services.dlq_drainer import drain_and_recover_dlq

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_test_environment():
    # Ensure database and schema are initialized
    db.init_db()
    run_migration()
    clear_dlq()
    yield
    clear_dlq()

def test_database_migration_idempotent():
    # Verify migration applies cleanly and is idempotent
    result = run_migration()
    assert result["status"] in ["APPLIED", "ALREADY_UP_TO_DATE"]

def test_contract_adapter_v1_payload():
    adapter = PaymentContractAdapter()
    v1_raw = {
        "event_id": "EVT-TEST-1",
        "transaction_id": "TX-T1",
        "customer_id": "CUST-001",
        "amount": 150.0,
        "currency": "USD"
    }
    normalized, _transforms = adapter.adapt(v1_raw)
    assert normalized["transaction_id"] == "TX-T1"
    assert normalized["customer_id"] == "CUST-001"
    assert normalized["amount"] == 150.0
    assert normalized["currency"] == "USD"
    assert normalized["detected_version"] == "v1"

def test_contract_adapter_v2_payload():
    adapter = PaymentContractAdapter()
    v2_raw = {
        "event_id": "EVT-TEST-2",
        "transaction_id": "TX-T2",
        "account_ref": "CUST-002",
        "payment_detail": {
            "settlement_amount": 340.50,
            "fee_amount": 5.25,
            "iso_currency": "EUR"
        },
        "idempotency_token": "IDEMP-TOKEN-123"
    }
    normalized, _transforms = adapter.adapt(v2_raw)
    assert normalized["transaction_id"] == "TX-T2"
    assert normalized["customer_id"] == "CUST-002"
    assert normalized["amount"] == 340.50
    assert normalized["fee_amount"] == 5.25
    assert normalized["currency"] == "EUR"
    assert normalized["idempotency_token"] == "IDEMP-TOKEN-123"
    assert normalized["detected_version"] == "v2"

def test_api_v1_webhook_ingestion():
    v1_payload = {
        "event_id": "EVT-V1-100",
        "transaction_id": "TX-V1-100",
        "customer_id": "CUST-100",
        "amount": 500.0,
        "currency": "USD"
    }
    res = client.post("/v1/webhooks/payment", json=v1_payload)
    assert res.status_code == 200
    assert res.json()["status"] == "PROCESSED"

def test_api_v2_webhook_ingestion():
    v2_payload = {
        "event_id": "EVT-V2-200",
        "transaction_id": "TX-V2-200",
        "account_ref": "CUST-200",
        "payment_detail": {
            "settlement_amount": 750.0,
            "fee_amount": 7.5,
            "iso_currency": "USD"
        },
        "idempotency_token": "IDEMP-V2-200"
    }
    res = client.post("/v1/webhooks/payment", json=v2_payload)
    assert res.status_code == 200
    assert res.json()["status"] == "PROCESSED"
    assert res.json()["version_handled"] == "v2"

def test_dlq_drainer_recovery():
    # Push 3 mock poisoned items to the DLQ
    for i in range(1, 4):
        push_to_dlq({
            "event_id": f"EVT-DLQ-{i}",
            "transaction_id": f"TX-DLQ-{i}",
            "account_ref": f"CUST-DLQ-{i}",
            "payment_detail": {
                "settlement_amount": 1000.0 * i,
                "fee_amount": 10.0,
                "iso_currency": "USD"
            },
            "idempotency_token": f"IDEMP-DLQ-{i}"
        }, error_reason="IntegrityError: NOT NULL constraint failed")

    assert get_dlq_count() == 3

    # Execute recovery drainer
    result = drain_and_recover_dlq()
    assert result["status"] == "RECOVERED_SUCCESS"
    assert result["recovered_count"] == 3
    assert result["recovered_volume_usd"] == 6000.0
    assert get_dlq_count() == 0  # 100% drained!
