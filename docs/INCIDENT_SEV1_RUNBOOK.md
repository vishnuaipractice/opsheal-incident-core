# INCIDENT-2026-0925: Critical Checkout & Payment Stream Failure

- **Severity**: SEV-1 (Production Halting)
- **Target Endpoint**: `POST /v1/settlements` in `api/main.py`
- **Domain Service**: `services/payment_orchestrator.py`
- **Symptom**: Unhandled `TypeError: unsupported operand type(s) for +: 'NoneType' and 'Decimal'` triggering HTTP 500 server crashes during currency settlement calculations when optional tax/discount values are null.

## Enterprise Remediation Policy & Constraints
1. **Defensive Null-Coalescing**:
   - Default null/omitted taxes or discounts safely to `Decimal('0.00')`.
   - Maintain strict `Decimal` arithmetic to prevent IEEE-754 floating-point inaccuracies.
2. **Dead-Letter Quarantine Pattern**:
   - Never drop a transaction; if corrupt beyond recovery, return `{"status": "QUARANTINED"}` with HTTP 202 instead of crashing with HTTP 500.
3. **Continuous Parity & Regression Verification**:
   - Both unit tests (`tests/test_payment.py`) and live API integration tests (`tests/test_api.py`) must pass with 100% success rate.
4. **Audit & Compliance Post-Mortem**:
   - Any hotfix must generate an official incident post-mortem report under `reports/POST_MORTEM.md` outlining root cause, affected files, resolution metrics, and mitigation steps.