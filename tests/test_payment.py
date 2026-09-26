import pytest
from services.payment_orchestrator import PaymentOrchestrator

def test_normal_transaction():
    orchestrator = PaymentOrchestrator()
    tx = {"transaction_id": "TX-100", "base_amount": 100.0, "applied_tax": 10.0, "discount_amount": 5.0}
    res = orchestrator.process_settlement(tx)
    assert res["status"] == "SETTLED"
    assert res["settled_total"] == 105.0

def test_incident_healed():
    # Verifies the healed handling of null optional fields
    orchestrator = PaymentOrchestrator()
    corrupt_tx = {"transaction_id": "TX-99482", "base_amount": 250.0, "applied_tax": None, "discount_amount": None}
    res = orchestrator.process_settlement(corrupt_tx)
    assert res["status"] == "SETTLED"
    assert res["settled_total"] == 250.0

def test_quarantine_fallback_on_corrupt_payload():
    # Verifies dead-letter quarantine fallback on non-numeric corruption
    orchestrator = PaymentOrchestrator()
    unrecoverable_tx = {"transaction_id": "TX-CORRUPT", "base_amount": "INVALID_NUMBER"}
    res = orchestrator.process_settlement(unrecoverable_tx)
    assert res["status"] == "QUARANTINED"