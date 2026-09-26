# CANARY DEPLOYMENT & SAFETY GATE VERIFICATION REPORT

| Field | Value |
| :--- | :--- |
| **Gate Status** | 🟢 PASSED — Promotion Approved |
| **Executed By** | OpsHeal Bob-Canary (IBM Bob 2.0 Agent Mode) |
| **Timestamp** | `2026-09-26T06:10:48 UTC` |
| **Total Gate Duration** | 0.56 ms |
| **Probes Executed** | 5 |
| **Probes Passed** | 5 / 5 |
| **Error Rate** | 0.0% (target: 0.0%) |
| **ADS Replay Attacks Blocked** | 1 |

---

## 1. Synthetic Probe Execution Matrix

| ID | Probe Name | Type | Status | Resolution | Amount | Latency | Transforms |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `P-01` | Legacy Flat v1 Payload | Legacy flat v1 | ✅ PASSED | `INSERTED` | $250.00 | 0.22 ms | 1 applied |
| `P-02` | Modern Nested v2 Payload | Modern nested v2 | ✅ PASSED | `INSERTED` | $9,850.00 | 0.07 ms | 3 applied |
| `P-03` | Stripe Minor-Cents Payload | Stripe minor-cents | ✅ PASSED | `INSERTED` | $47.50 | 0.08 ms | 3 applied |
| `P-04` | Dirty Currency String Payload | Dirty currency string | ✅ PASSED | `INSERTED` | $12,450.75 | 0.06 ms | 3 applied |
| `P-05` | Duplicate Idempotency Token Replay | Duplicate idempotency | ✅ PASSED | `DEDUP_PROTECTED` | $9,850.00 | 0.08 ms | 3 applied |

---

## 2. Per-Probe Transformation Audit

### P-01 — Legacy Flat v1 Payload
_Flat v1 structure — no nesting, plain USD amount_

- Idempotency Synthesis: No vendor token found — generated deterministic SHA-256 token 'syn-8c7f01974b638da4…'

### P-02 — Modern Nested v2 Payload
_v2 payment_detail sub-object, explicit idempotency token_

- Semantic Alias: Mapped 'account_ref' -> 'customer_id' ('CUST-CANARY-B')
- Structural Unnesting: 'payment_detail.settlement_amount' -> 'amount' ($9,850.00)
- Enum Normalization: Mapped status 'succeeded' -> 'SETTLED'

### P-03 — Stripe Minor-Cents Payload
_amount_cents integer (Stripe-style) → divided by 100_

- Unit Scale Coercion: Converted 4750 cents in 'amount_cents' -> $47.50 USD
- Idempotency Synthesis: No vendor token found — generated deterministic SHA-256 token 'syn-63bb0206fff14f90…'
- Enum Normalization: Mapped status 'paid' -> 'SETTLED'

### P-04 — Dirty Currency String Payload
_amount as "$12,450.75" string — regex strip to clean float_

- Currency String Coercion: Normalized '$12,450.75' -> $12,450.75 USD
- Idempotency Synthesis: No vendor token found — generated deterministic SHA-256 token 'syn-e3405e50670bb9e2…'
- Enum Normalization: Mapped status 'completed' -> 'SETTLED'

### P-05 — Duplicate Idempotency Token Replay
_Replay of P-02 token — must be caught and deduplicated_

- Semantic Alias: Mapped 'account_ref' -> 'customer_id' ('CUST-CANARY-B')
- Structural Unnesting: 'payment_detail.settlement_amount' -> 'amount' ($9,850.00)
- Enum Normalization: Mapped status 'succeeded' -> 'SETTLED'

---

## 3. Anti-Double-Spend (ADS) Invariant Proof

**Objective**: prove that replaying an identical idempotency token returns the
cached transaction record rather than inserting a duplicate row in the ledger.

| ADS Field | Value |
| :--- | :--- |
| **Replay Token** | `IDEMP-CANARY-PROBE-02` |
| **Rows before replay (P-02 insert)** | 1 |
| **Rows after replay (P-05 attempt)** | 1 |
| **Cached TX returned** | `TX-CANARY-02` |
| **Double-Spend Blocked** | 🟢 `True` |

**Invariant**:

```
rows_before == rows_after == 1  →  True
```

Probe P-05 replayed token `IDEMP-CANARY-PROBE-02` which was first
registered by Probe P-02 (TX `TX-CANARY-02`).  The shadow-sandbox
idempotency guard detected the existing row and returned `DEDUP_PROTECTED`,
leaving the row count at **1**.  No duplicate charge was created.

---

## 4. Shadow Sandbox Integrity

All synthetic probes executed in a **disposable in-memory SQLite sandbox**
(`sqlite3.connect(':memory:')`) that is destroyed on gate exit.  No canary
records can leak into the production ledger (`database/production.db`).

---

## 5. Production Rollout Decision

```
CANARY GATE: PASSED
All 5 probes cleared · Error rate 0.0% · ADS invariant proven
→ AUTHORISE DLQ DRAIN TO PRODUCTION LEDGER
```
