# ### 🔹 Turn 1: Triage & Incident Root Cause Analysis (Bob-Triage)
**User Input to Bob**:
```text
We are dealing with a critical SEV-1 production incident on our payment gateway ingress. 
Our production microservice endpoint `POST /v1/webhooks/payment` is crashing with:
`KeyError: 'customer_id'`
15 in-flight enterprise transactions worth $69,000.00 have been diverted to our Dead-Letter Queue (DLQ).

Our upstream vendor has silently upgraded to an RFC 8414 v2 contract where:
1. 'customer_id' was renamed to 'account_ref' (or 'client_id' / 'payer_id').
2. Financial amounts are either nested inside 'payment_detail.settlement_amount', given in minor units (e.g., Stripe cents 'amount_cents: 580000'), or passed as dirty formatted strings like '$12,450.75'.
3. The new payload includes audit fields: 'fee_amount' and 'idempotency_token'.

Please act as Bob-Triage:
1. Analyze this compound schema drift.
2. Produce an incident classification and attribute mapping matrix from v1 to v2.
3. Outline the zero-downtime remediation architecture required to resolve this without dropping in-flight traffic.
```

---

**Status:** active  **Date:** 2026-09-25

---

### 👤 User

### 🔹 Turn 1: Triage & Incident Root Cause Analysis (Bob-Triage)
**User Input to Bob**:
```text
We are dealing with a critical SEV-1 production incident on our payment gateway ingress. 
Our production microservice endpoint `POST /v1/webhooks/payment` is crashing with:
`KeyError: 'customer_id'`
15 in-flight enterprise transactions worth $69,000.00 have been diverted to our Dead-Letter Queue (DLQ).

Our upstream vendor has silently upgraded to an RFC 8414 v2 contract where:
1. 'customer_id' was renamed to 'account_ref' (or 'client_id' / 'payer_id').
2. Financial amounts are either nested inside 'payment_detail.settlement_amount', given in minor units (e.g., Stripe cents 'amount_cents: 580000'), or passed as dirty formatted strings like '$12,450.75'.
3. The new payload includes audit fields: 'fee_amount' and 'idempotency_token'.

Please act as Bob-Triage:
1. Analyze this compound schema drift.
2. Produce an incident classification and attribute mapping matrix from v1 to v2.
3. Outline the zero-downtime remediation architecture required to resolve this without dropping in-flight traffic.
```

---

### 🤖 Assistant

> 🔧 called: list_files



> 🔧 **list_files** — .

### 🤖 Assistant

> 🔧 called: list_files, list_files, list_files



> 🔧 **list_files** — api

> 🔧 **list_files** — dlq

> 🔧 **list_files** — services

### 🤖 Assistant

> 🔧 called: read_file, read_file, read_file



> 🔧 **read_file** — services/drift_analyzer.py

> 🔧 **read_file** — services/contract_adapter.py

> 🔧 **read_file** — api/main.py

### 🤖 Assistant

> 🔧 called: read_file, read_file, list_files



> 🔧 **list_files** — docs

> 🔧 **read_file** — dlq/dead_letter_queue.json

> 🔧 **read_file** — services/dlq_drainer.py

### 🤖 Assistant

> 🔧 called: read_file, read_file



> 🔧 **read_file** — docs/VENDOR_PAYMENT_V2_SPEC.md

> 🔧 **read_file** — docs/INCIDENT_SEV1_RUNBOOK.md

### 🤖 Assistant

> 🔧 called: create_html_artifact

Now I have a comprehensive picture of the entire system. Let me produce the full Bob-Triage incident analysis.

> 🔧 **create_html_artifact** — bob_triage_sev1

### 🤖 Assistant

Here is the full Bob-Triage analysis, grounded entirely in the live codebase.

---

## Root Cause Summary

The crash originates at [`api/main.py:119`](api/main.py:119) — a hard dict-key access `payload["customer_id"]` with zero fallback. RFC-GP-2026-V2 replaced that field across **three distinct gateway patterns** simultaneously, so every inbound v2 webhook raises a `KeyError` before any amount extraction or DB write occurs, routing the full payload into the DLQ.

---

## The 5 Compound Drift Categories

| # | Category | v1 Field | v2 Equivalent(s) | Impact |
|---|----------|----------|-------------------|--------|
| 1 | **Field Rename** | `customer_id` | `account_ref` / `client_id` / `payer_id` | 💥 Hard crash — SEV-1 trigger |
| 2 | **Structural Nesting** | `amount` (root float) | `payment_detail.settlement_amount` | Silent $0 amount if not unnested |
| 3 | **Unit Scale Coercion** | `amount` (dollars) | `amount_cents` (integer minor units) | 100× inflation without `/100.0` |
| 4 | **Dirty String Coercion** | `amount` (float) | `"$12,450.75"` (formatted string) | `ValueError` on `float()` cast |
| 5 | **New Audit Fields** | *(absent)* | `fee_amount` + `idempotency_token` | DB insert failure + double-spend risk |

---

## Zero-Downtime Remediation Pipeline

The system already has the full repair chain built in [`services/contract_adapter.py`](services/contract_adapter.py) and wired through [`api/main.py:72–83`](api/main.py:72-83). The pipeline is:

```
Feature Flag ON
  → ADAPTER_ACTIVE = True (no restart, new traffic healed instantly)
  → DB WAL Migration (ALTER TABLE ADD COLUMN fee_amount + idempotency_token, non-blocking)
  → Canary Gate (3 synthetic probes: GlobalPay nested · Stripe cents · dirty string)
  → DLQ Idempotent Drain (15 txns → PaymentContractAdapter → DB insert with dedup guard)
  → Audit Artefacts (PULL_REQUEST_HOTFIX.md + POST_MORTEM.md)
```

All five mutation categories are handled by the [`PaymentContractAdapter.adapt()`](services/contract_adapter.py:39) method via ordered candidate list walks, regex stripping, cents→dollar scaling, nested object traversal, and a `STATUS_MAP` enum table — recoverable without any server restart.

---

## Key Residual Risks

1. **Double-spend on webhook retries** — mitigated by the idempotency gate at [`api/main.py:86–101`](api/main.py:86-101)
2. **Future alias drift** — extend [`PaymentContractAdapter.ID_CANDIDATES`](services/contract_adapter.py:16) without touching any other code
3. **Zero-amount bypass** — the adapter defaults `amount = 0.0`; a business-rule rejection layer for zero-amount settlements is the remaining gap

The one-pager above contains the full attribute mapping matrix with confidence scores and the complete remediation architecture diagram.