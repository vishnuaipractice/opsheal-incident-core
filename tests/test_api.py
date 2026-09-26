import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

def test_health():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "HEALTHY", "service": "settlement-core"}

def test_successful_settlement():
    payload = {
        "transaction_id": "TX-1",
        "base_amount": 100.0,
        "applied_tax": 10.0,
        "discount_amount": 5.0
    }
    res = client.post("/v1/settlements", json=payload)
    assert res.status_code == 200
    assert res.json()["settled_total"] == 105.0
    assert res.json()["status"] == "SETTLED"

def test_sev1_incident_healed():
    # Verifies autonomous remediation: optional null fields are safely coalesced
    payload = {
        "transaction_id": "TX-99482",
        "base_amount": 250.0,
        "applied_tax": None,
        "discount_amount": None
    }
    res = client.post("/v1/settlements", json=payload)
    assert res.status_code == 200
    assert res.json()["settled_total"] == 250.0
    assert res.json()["status"] == "SETTLED"
