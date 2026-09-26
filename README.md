# OpsHeal: The Autonomous Incident Triage & Zero-Downtime Hotfix Agent

An autonomous site-reliability and incident remediation platform built with **IBM Bob 2.0 Agent Mode**, featuring **Document Understanding**, **Subagent Orchestration**, **Database Schema Evolution**, **Dead-Letter Queue (DLQ) Recovery**, and **Automated Hotfix Release Generation**.

---

## 🏆 Hackathon Submission Assets & Quick Links

- 🎬 **Demo Video (2:49)**: [Watch on YouTube](https://youtu.be/i8CV6-nm-bw)
- 📊 **Pitch Deck Presentation**: [`OpsHeal_Pitch_Deck.pptx`](submission_assets/OpsHeal_Pitch_Deck.pptx)
- 📑 **Project Proposal & Specification**: [`OpsHeal_Project_Specification_and_Proposal.docx`](submission_assets/OpsHeal_Project_Specification_and_Proposal.docx)
- 📝 **LabLab.ai Official Submission Pack**: [`docs/LABLAB_SUBMISSION_PACK.md`](docs/LABLAB_SUBMISSION_PACK.md)
- 📸 **Bob Session Audit & Screenshots**: [`docs/BOB_SESSIONS_SCREENSHOT_GUIDE.md`](docs/BOB_SESSIONS_SCREENSHOT_GUIDE.md)

---

## 🎯 The Core Problem & Value Proposition

In modern enterprise architectures, engineering teams bleed the most time, revenue, and sanity during **production Sev-1 outages**:
- **Traditional MTTR**: 3 to 5 hours of panicky multi-engineer war rooms.
- **Enterprise Cost**: Over **$5,600 per minute** in dropped transactions ($300,000+/hr).
- **Secondary Outages**: Over 40% of emergency hotfixes deployed under pressure cause secondary failures.

**OpsHeal leverages IBM Bob 2.0** to turn multi-hour outages into a **48-second autonomous recovery lifecycle** managing multiple operational steps: log ingestion $\rightarrow$ vendor RFC parsing $\rightarrow$ schema migration $\rightarrow$ polymorphic adapter generation $\rightarrow$ DLQ replay $\rightarrow$ automated Git Pull Request generation.

---

## 📁 Repository Structure

```
opsheal-incident-core/
├── api/
│   ├── __init__.py
│   └── main.py                     # FastAPI Settlement Engine & Webhook Ingestion
├── database/
│   ├── db.py                       # SQLite transactional store with WAL mode
│   └── migrations/
│       └── migration_002_add_v2_columns.py # Non-blocking schema evolution
├── dlq/
│   ├── dlq_manager.py              # Persistent Dead-Letter Queue engine
│   └── dead_letter_queue.json      # Poisoned transaction backlog
├── docs/
│   ├── INCIDENT_SEV1_RUNBOOK.md    # Internal incident runbook (Incident 1)
│   └── VENDOR_PAYMENT_V2_SPEC.md   # External vendor breaking RFC (Incident 2)
├── logs/
│   └── production_error.log        # Real server crash dump & stack trace
├── services/
│   ├── payment_orchestrator.py     # Domain settlement engine
│   ├── contract_adapter.py         # Polymorphic v1/v2 payload adapter
│   └── dlq_drainer.py              # Safe DLQ replay & recovery engine
├── tests/
│   ├── test_api.py                 # Incident 1 integration test suite
│   ├── test_incident2.py           # Incident 2 contract drift & DLQ test suite
│   └── test_payment.py             # Unit test suite
├── tools/
│   └── generate_hotfix_pr.py       # Automated CTO-ready Pull Request generator
├── simulate_traffic.py             # Incident 1 live traffic simulator
├── simulate_incident2.py           # Incident 2 contract drift & DLQ outage simulator
└── reports/
    ├── POST_MORTEM.md              # Incident 1 post-mortem report
    └── PULL_REQUEST_HOTFIX.md      # Incident 2 CTO hotfix PR document
```

---

## 🚀 Running the Two Incident Scenarios

### Scenario 1: Baseline Microservice Arithmetic Crash
1. **Start the API**:
   ```bash
   uvicorn api.main:app --port 8000
   ```
2. **Trigger Incident 1**:
   ```bash
   python simulate_traffic.py
   ```
   - Sends valid `TX-1001` (HTTP 200).
   - Sends null-discount `TX-99482` $\rightarrow$ Triggers HTTP 500 unhandled exception and logs to `logs/production_error.log`.

---

### Scenario 2: Upstream Breaking Contract Drift & Poisoned DLQ (The 1st-Place Demo)
1. **Start API in Pre-Patch Mode**:
   ```powershell
   $env:OPSHEAL_ADAPTER_ENABLED="false"; uvicorn api.main:app --port 8000
   ```
2. **Trigger Incident 2 Outage**:
   ```bash
   python simulate_incident2.py
   ```
   - Ingests legacy v1 transactions $\rightarrow$ **HTTP 200 OK**.
   - Upstream gateway upgrades to v2 with breaking schema (`account_ref`, nested `payment_detail`).
   - Webhook crashes with **HTTP 500**, trapping **15 transactions ($69,000.00 USD)** in `dlq/dead_letter_queue.json`.
   - Critical Sev-1 alarm displays on the terminal dashboard.

3. **Autonomous Remediation & DLQ Draining**:
   ```bash
   python database/migrations/migration_002_add_v2_columns.py
   python services/dlq_drainer.py
   python tools/generate_hotfix_pr.py
   ```
   - Database schema migrated without data loss.
   - All 15 poisoned transactions safely replayed and settled (DLQ count $\rightarrow$ 0).
   - CTO Pull Request document generated at `reports/PULL_REQUEST_HOTFIX.md`.

4. **Verify Recovery**:
   ```powershell
   $env:OPSHEAL_ADAPTER_ENABLED="true"; python simulate_incident2.py --verify-recovery
   ```
   - Confirms DLQ backlog is **0**.
   - Proves live v2 webhooks return **HTTP 200 OK**.
   - Proves legacy v1 webhooks remain **100% backward-compatible**.

---

## 🧬 Polymorphic Contract Drift Capabilities

OpsHeal's Subagent-Triage and Dynamic Contract Normalizer are not hardcoded to a single schema. It autonomously classifies and normalizes **5 distinct categories of real-world API drift**:

| Drift Pattern | Example Mutation | Autonomous Normalization |
| :--- | :--- | :--- |
| **1. Field Renaming** | `account_ref`, `client_id`, `payer_id` | Mapped to target model (`customer_id`) |
| **2. Structural Nesting** | `payment_detail.settlement_amount` | Flattened and unnested to root attribute |
| **3. Unit Scale Drift** | `amount_cents: 580000` (Stripe minor units) | Scaled by 100 $\rightarrow$ `$5,800.00 USD` |
| **4. Stringified Currency** | `"amount": "$12,450.75"` (dirty formatted string) | Coerced and cleaned to `12450.75` float |
| **5. Status / Enum Mutation** | `"status": "succeeded"`, `"state": "Authorised"` | Canonicalized to target enum (`"SETTLED"`) |

### 🧪 Live Chaos Webhook Injector
On the web dashboard (`http://localhost:8000/dashboard`), click **"🧪 Chaos Webhook Injector"** to dispatch arbitrary custom payloads with any mixture of these drift patterns and watch OpsHeal normalize them with a detailed audit trail of applied transformations.

---

## 🧪 Automated Test Suite

Run all 21 unit, integration, and loophole resilience tests:
```bash
python -m pytest -v
```
Output:
```
tests/test_api.py::test_health PASSED                                    [  4%]
tests/test_api.py::test_successful_settlement PASSED                     [  9%]
tests/test_api.py::test_sev1_incident_healed PASSED                      [ 14%]
tests/test_incident2.py::test_database_migration_idempotent PASSED       [ 19%]
tests/test_incident2.py::test_contract_adapter_v1_payload PASSED         [ 23%]
tests/test_incident2.py::test_contract_adapter_v2_payload PASSED         [ 28%]
tests/test_incident2.py::test_api_v1_webhook_ingestion PASSED            [ 33%]
tests/test_incident2.py::test_api_v2_webhook_ingestion PASSED            [ 38%]
tests/test_incident2.py::test_dlq_drainer_recovery PASSED                [ 42%]
tests/test_logic_loopholes.py::test_empty_and_non_dict_payload_resilience PASSED [ 47%]
tests/test_logic_loopholes.py::test_multi_currency_symbols_and_formats PASSED [ 52%]
tests/test_logic_loopholes.py::test_anti_double_spend_idempotency_guard PASSED [ 57%]
tests/test_logic_loopholes.py::test_idempotent_repeated_migrations PASSED [ 61%]
tests/test_logic_loopholes.py::test_empty_dlq_drain_graceful_handling PASSED [ 66%]
tests/test_logic_loopholes.py::test_all_outage_scenarios_mathematical_consistency PASSED [ 71%]
tests/test_payment.py::test_normal_transaction PASSED                    [ 76%]
tests/test_payment.py::test_incident_healed PASSED                       [ 80%]
tests/test_payment.py::test_quarantine_fallback_on_corrupt_payload PASSED [ 85%]
tests/test_polymorphic_drift.py::test_unit_scale_drift_cents_to_dollars PASSED [ 90%]
tests/test_polymorphic_drift.py::test_stringified_currency_symbol_drift PASSED [ 95%]
tests/test_polymorphic_drift.py::test_nested_cents_and_status_enum PASSED [100%]

============================= 21 passed in 1.65s ==============================
```
