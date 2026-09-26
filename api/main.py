from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
from decimal import Decimal
import logging
import os
import json
import traceback

from database import db
from dlq.dlq_manager import push_to_dlq, get_dlq_records, get_dlq_count, clear_dlq

app = FastAPI(
    title="OpsHeal: Autonomous SRE Core & Incident Healer",
    description="Enterprise settlement and payment webhook microservice with autonomous incident recovery",
    version="2.0.0"
)

# Ensure logs directory exists
os.makedirs("logs", exist_ok=True)

# Production file logger
logger = logging.getLogger("production")
logger.setLevel(logging.ERROR)

if not logger.handlers:
    file_handler = logging.FileHandler("logs/production_error.log", mode="a", encoding="utf-8")
    formatter = logging.Formatter('%(asctime)s ERROR [%(filename)s:%(lineno)d] %(message)s')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

class SettlementRequest(BaseModel):
    transaction_id: str
    base_amount: float
    applied_tax: Optional[float] = None
    discount_amount: Optional[float] = None

@app.get("/health")
def health():
    return {"status": "HEALTHY", "service": "settlement-core"}

# ============================================================
# INCIDENT 1: Real-time Settlement Arithmetic Endpoint
# ============================================================
@app.post("/v1/settlements")
def settle_transaction(req: SettlementRequest):
    try:
        # Defensive null-coalescing with Decimal('0.00')
        base = Decimal(str(req.base_amount))
        tax = Decimal(str(req.applied_tax)) if req.applied_tax is not None else Decimal("0.00")
        disc = Decimal(str(req.discount_amount)) if req.discount_amount is not None else Decimal("0.00")

        total = base + tax - disc

        return {
            "transaction_id": req.transaction_id,
            "settled_total": float(total),
            "status": "SETTLED"
        }
    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f"CRITICAL: Transaction {req.transaction_id} caused unhandled crash: {str(e)}\n{error_trace}")
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error: Settlement Engine Down"
        )

# ============================================================
# INCIDENT 2: Upstream Gateway Webhook Ingestion Endpoint
# ============================================================
ADAPTER_ACTIVE = True

@app.post("/v1/webhooks/payment")
def ingest_payment_webhook(payload: Dict[str, Any]):
    global ADAPTER_ACTIVE
    try:
        use_adapter = ADAPTER_ACTIVE
        if use_adapter:
            try:
                from services.contract_adapter import PaymentContractAdapter
                adapter = PaymentContractAdapter()
                normalized, _transforms = adapter.adapt(payload)

                # Anti-Double-Spend Guard: Check idempotency token before insertion
                idemp_token = normalized.get("idempotency_token")
                if idemp_token:
                    existing = db.get_transaction_by_idempotency_token(idemp_token)
                    if existing:
                        return {
                            "status": "PROCESSED",
                            "deduplicated": True,
                            "transaction_id": existing["transaction_id"],
                            "version_handled": normalized.get("detected_version", "v2"),
                            "account_ref": existing["customer_id"],
                            "settled_amount": existing["amount"],
                            "fee_amount": existing.get("fee_amount", 0.0),
                            "idempotency_token": idemp_token,
                            "db_id": existing["id"],
                            "note": "Idempotent Replay Protected (Anti-Double-Spend)"
                        }

                tx_id = db.insert_transaction(normalized)
                return {
                    "status": "PROCESSED",
                    "transaction_id": normalized["transaction_id"],
                    "version_handled": normalized.get("detected_version", "v2"),
                    "account_ref": normalized["customer_id"],
                    "settled_amount": normalized["amount"],
                    "fee_amount": normalized.get("fee_amount", 0.0),
                    "idempotency_token": normalized.get("idempotency_token"),
                    "db_id": tx_id
                }
            except ImportError:
                pass

        # PRE-PATCH BEHAVIOR: Assumes legacy v1 flat payload schema
        # Fails with KeyError when upstream vendor sends v2 schema without customer_id
        customer_id = payload["customer_id"]
        amount = payload["amount"]
        currency = payload.get("currency", "USD")

        tx_id = db.insert_transaction({
            "transaction_id": payload["transaction_id"],
            "customer_id": customer_id,
            "amount": amount,
            "currency": currency,
            "status": "SETTLED"
        })
        return {
            "status": "PROCESSED",
            "transaction_id": payload["transaction_id"],
            "version_handled": "v1",
            "customer_id": customer_id,
            "amount": amount,
            "db_id": tx_id
        }
    except Exception as e:
        error_trace = traceback.format_exc()
        tx_id = payload.get("transaction_id", "UNKNOWN")
        logger.error(f"CRITICAL SEV-1: Webhook ingestion crashed on TX {tx_id}: {str(e)}\n{error_trace}")
        # Route unhandled/broken transaction to Dead-Letter Queue
        push_to_dlq(payload, error_reason=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Webhook Ingestion Failed: Schema Mismatch ({str(e)})"
        )

# ============================================================
# DASHBOARD & TELEMETRY ENDPOINTS
# ============================================================
@app.get("/dashboard", response_class=HTMLResponse)
def get_dashboard():
    dashboard_path = os.path.join(os.path.dirname(__file__), "dashboard.html")
    if os.path.exists(dashboard_path):
        with open(dashboard_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h2>Dashboard file not found</h2>", status_code=404)

@app.get("/v1/dlq")
def get_dlq_status():
    records = get_dlq_records()
    trapped_amount = 0.0
    for r in records:
        p = r.get("payload", {})
        amt = None
        if "amount_cents" in p:
            try:
                amt = float(p["amount_cents"]) / 100.0
            except Exception:
                pass
        if amt is None:
            raw_amt = p.get("amount") or (p.get("payment_detail", {}).get("settlement_amount") if isinstance(p.get("payment_detail"), dict) else 0.0) or 0.0
            try:
                clean_str = str(raw_amt).replace("$", "").replace(",", "").strip()
                amt = float(clean_str)
            except Exception:
                amt = 0.0
        trapped_amount += (amt or 0.0)
    return {
        "dlq_count": len(records),
        "trapped_volume_usd": round(trapped_amount, 2),
        "records": records
    }

@app.get("/v1/transactions")
def list_transactions():
    return {
        "stats": db.get_stats(),
        "recent_transactions": db.get_all_transactions()[:20]
    }

@app.get("/v1/telemetry")
def get_telemetry():
    dlq_data = get_dlq_status()
    stats = db.get_stats()
    recent_txs = db.get_all_transactions()[:20]
    return {
        "status": "SEV-1 OUTAGE" if dlq_data["dlq_count"] > 0 else "OPERATIONAL",
        "dlq": dlq_data,
        "stats": stats,
        "recent_transactions": recent_txs
    }

# ============================================================
# DEMO CONTROL & CLIENT ACTION ENDPOINTS
# ============================================================
SWARM_STAGE = "STANDBY"
ACTIVE_SCENARIO = "mixed"

@app.post("/v1/demo/trigger-outage")
def trigger_demo_outage(scenario: Optional[str] = "mixed"):
    """
    Simulates incoming breaking contract mutations that crash into the DLQ.
    Scenarios:
    - 'mixed': Realistic multi-gateway catastrophe (5 Stripe cents + 5 GlobalPay nested + 5 Dirty strings = $69,000.00)
    - 'stripe': 15 Stripe minor unit payloads (amount_cents: 580000 -> $5,800.00 = $69,000.00)
    - 'v2': 15 GlobalPay v2 RFC payloads (account_ref + payment_detail = $69,000.00)
    """
    global ADAPTER_ACTIVE, SWARM_STAGE, ACTIVE_SCENARIO
    ADAPTER_ACTIVE = False
    SWARM_STAGE = "OUTAGE_DETECTED"
    ACTIVE_SCENARIO = scenario or "mixed"
    os.environ["OPSHEAL_ADAPTER_ENABLED"] = "false"
    clear_dlq()
    db.reset_db(migrated=False)

    if scenario == "stripe":
        # 15 Stripe Minor Unit payloads (sum = $69,000.00)
        for i in range(1, 16):
            dollars = 1800.0 + (i * 350.0)
            sample_stripe = {
                "event_type": "charge.captured",
                "transaction_id": f"TX-STRIPE-20{i:02d}",
                "client_id": f"CUST-STRIPE-{i*10}",
                "amount_cents": int(dollars * 100),
                "fee_amount": 14.50,
                "currency": "usd",
                "status": "succeeded",
                "idempotency_key": f"IDEMP-STRIPE-20{i:02d}-SECURE"
            }
            push_to_dlq(sample_stripe, error_reason="KeyError: 'customer_id' (Stripe minor unit drift: amount_cents & client_id)")

    elif scenario == "mixed":
        # 15 Mixed Multi-Gateway Chaos Outage:
        # 5 GlobalPay Nested ($20,000) + 5 Stripe Cents ($23,000) + 5 Dirty Strings ($26,000) = $69,000.00
        # 1-5: GlobalPay v2 Nested
        for i in range(1, 6):
            gp_amt = 2500.0 + (i * 500.0)  # 3000, 3500, 4000, 4500, 5000 = $20,000
            sample_gp = {
                "event_id": f"EVT-GP-20{i:02d}",
                "transaction_id": f"TX-GP-20{i:02d}",
                "account_ref": f"CUST-GLOBAL-{i*10}",
                "payment_detail": {
                    "settlement_amount": gp_amt,
                    "fee_amount": 12.50,
                    "iso_currency": "USD"
                },
                "idempotency_token": f"IDEMP-GP-20{i:02d}-SECURE"
            }
            push_to_dlq(sample_gp, error_reason="KeyError: 'customer_id' (GlobalPay v2 nested drift)")

        # 6-10: Stripe Cents (3800, 4200, 4600, 5000, 5400 = $23,000)
        for i in range(6, 11):
            idx = i - 5
            stripe_dollars = 3400.0 + (idx * 400.0)
            sample_stripe = {
                "event_type": "charge.captured",
                "transaction_id": f"TX-STRIPE-20{i:02d}",
                "client_id": f"CUST-STRIPE-{i*10}",
                "amount_cents": int(stripe_dollars * 100),
                "fee_amount": 15.00,
                "currency": "usd",
                "status": "succeeded",
                "idempotency_key": f"IDEMP-STRIPE-20{i:02d}-SECURE"
            }
            push_to_dlq(sample_stripe, error_reason="KeyError: 'customer_id' (Stripe minor units drift)")

        # 11-15: Dirty String Currency / Status (4800, 5000, 5200, 5400, 5600 = $26,000)
        for i in range(11, 16):
            idx = i - 10
            dirty_dollars = 4600.0 + (idx * 200.0)
            sample_dirty = {
                "event_id": f"EVT-DIRTY-20{i:02d}",
                "transaction_id": f"TX-DIRTY-20{i:02d}",
                "payer_id": f"CUST-HOLDINGS-{i*10}",
                "amount": f"${dirty_dollars:,.2f}",
                "fee": "$18.50",
                "currency": "USD",
                "state": "Authorised",
                "idempotency_token": f"IDEMP-DIRTY-20{i:02d}-SECURE"
            }
            push_to_dlq(sample_dirty, error_reason="KeyError: 'customer_id' (Stringified currency & enum drift)")

    else:
        # Default v2 RFC (15 records = $69,000.00)
        for i in range(1, 16):
            sample_v2 = {
                "event_id": f"EVT-DEMO-20{i:02d}",
                "transaction_id": f"TX-LIVE-20{i:02d}",
                "account_ref": f"CUST-ENTERPRISE-{i*10}",
                "payment_detail": {
                    "settlement_amount": 1800.0 + (i * 350.0),
                    "fee_amount": 14.50,
                    "iso_currency": "USD"
                },
                "idempotency_token": f"IDEMP-LIVE-20{i:02d}-SECURE"
            }
            push_to_dlq(sample_v2, error_reason="KeyError: 'customer_id' (Vendor v2 contract drift RFC-GP-2026-V2)")

    return {"status": "OUTAGE_SIMULATED", "scenario": scenario, "poisoned_records_count": 15}

@app.post("/v1/demo/remediate")
def execute_demo_remediation():
    """
    Executes the complete OpsHeal autonomous remediation swarm:
    1. Schema Migration (Non-blocking SQLite WAL)
    2. Canary Gate Verification (Synthetic probes & idempotency)
    3. DLQ Replay and Recovery (100% funds recovered)
    4. CTO Pull Request Generation
    """
    global ADAPTER_ACTIVE, SWARM_STAGE
    from database.migrations.migration_002_add_v2_columns import run_migration
    from services.canary_deployer import run_canary_health_gate
    from services.dlq_drainer import drain_and_recover_dlq
    from tools.generate_hotfix_pr import generate_pull_request_document

    ADAPTER_ACTIVE = True
    SWARM_STAGE = "HEALED"
    os.environ["OPSHEAL_ADAPTER_ENABLED"] = "true"
    migration_res = run_migration()
    canary_res = run_canary_health_gate()
    drain_res = drain_and_recover_dlq()
    pr_path = generate_pull_request_document()

    return {
        "status": "HEALED_SUCCESSFULLY",
        "migration": migration_res,
        "canary_gate": canary_res,
        "dlq_recovery": drain_res,
        "pull_request_path": pr_path
    }

@app.post("/v1/demo/reset")
def reset_demo_state():
    global ADAPTER_ACTIVE, SWARM_STAGE
    ADAPTER_ACTIVE = False
    SWARM_STAGE = "STANDBY"
    os.environ["OPSHEAL_ADAPTER_ENABLED"] = "false"
    clear_dlq()
    db.reset_db(migrated=False)
    return {"status": "RESET_COMPLETE"}

@app.get("/v1/demo/triage-report")
def get_triage_report():
    global SWARM_STAGE
    spec_path = os.path.join(os.path.dirname(__file__), "..", "docs", "VENDOR_PAYMENT_V2_SPEC.md")

    if SWARM_STAGE == "STANDBY":
        spec_content = ""
        if os.path.exists(spec_path):
            with open(spec_path, "r", encoding="utf-8") as f:
                spec_content = f.read()
        return {
            "stage": "STANDBY",
            "title": "Subagent-Triage: Standby (Monitoring Production Baseline v1)",
            "summary": "========================================================================================\n"
                       "🟢 OPSHEAL SUBAGENT-TRIAGE: STANDBY / MONITORING MODE\n"
                       "========================================================================================\n\n"
                       "SYSTEM STATE: HEALTHY (Production Baseline v1 Active)\n"
                       "• Active Microservice Router: api/main.py (Flat 'customer_id' & 'amount')\n"
                       "• Active Database Schema: 7 Columns (Baseline Unmigrated)\n"
                       "• Dead-Letter Queue: 0 Trapped Records\n"
                       "• Contract Adapter: INACTIVE (Standby)\n\n"
                       "----------------------------------------------------------------------------------------\n"
                       "NOTE ON THE EXTERNAL VENDOR SPECIFICATION DISPLAYED BELOW:\n"
                       "----------------------------------------------------------------------------------------\n"
                       "In an enterprise architecture, external partners (e.g. GlobalPay, Stripe) publish RFC\n"
                       "documentation on developer portals. OpsHeal pre-indexes this external partner document\n"
                       "into its knowledge catalog (docs/VENDOR_PAYMENT_V2_SPEC.md).\n\n"
                       "• CURRENT STATUS: OpsHeal has NOT applied any v2 changes.\n"
                       "• AUTONOMOUS TRIGGER: If an unannounced breaking payload crashes into the DLQ,\n"
                       "  Subagent-Triage will autonomously comprehend the diff between the error telemetry\n"
                       "  and this indexed specification to synthesize the zero-downtime hotfix.\n\n"
                       "========================================================================================\n"
                       "INDEXED EXTERNAL PARTNER RFC SPECIFICATION (docs/VENDOR_PAYMENT_V2_SPEC.md):\n"
                       "========================================================================================\n\n" + spec_content
        }

    elif SWARM_STAGE == "OUTAGE_DETECTED":
        records = get_dlq_records()
        sample_payload = records[0].get("payload", {}) if records else {}
        return {
            "stage": "OUTAGE_DETECTED",
            "title": "Subagent-Triage: Incident Detected & Payload Captured",
            "summary": "========================================================================================\n"
                       "🚨 OPSHEAL SUBAGENT-TRIAGE: CRITICAL INCIDENT REPORT\n"
                       "========================================================================================\n\n"
                       f"Status: CONTRACT DRIFT OUTAGE DETECTED\n"
                       f"Trapped In-Flight Transactions: {len(records)} in Dead-Letter Queue\n"
                       "Captured Exception: KeyError: 'customer_id' on POST /v1/webhooks/payment\n\n"
                       "Poisoned Payload Intercepted at Gateway:\n" +
                       json.dumps(sample_payload, indent=2) +
                       "\n\nPreliminary Assessment:\n"
                       "• Upstream vendor transitioned to breaking contract without prior coordination.\n"
                       "• Target model expected root 'customer_id'; incoming payload contains 'account_ref'.\n"
                       "• Subagent-Triage is awaiting operator approval to dispatch autonomous remediation swarm.\n"
                       "Click 'Run OpsHeal Autonomous Healer' to trigger full document comprehension & adapter synthesis."
        }

    else:
        # HEALED
        from services.drift_analyzer import AutonomousDriftAnalyzer
        analyzer = AutonomousDriftAnalyzer()
        sample_v2 = {
            "event_id": "EVT-GP-2026-V2",
            "transaction_id": "TX-SAMPLE",
            "account_ref": "CUST-ENTERPRISE-100",
            "payment_detail": {
                "settlement_amount": 5400.0,
                "fee_amount": 14.50,
                "iso_currency": "USD"
            },
            "idempotency_token": "IDEMP-GP2026-SECURE"
        }
        drift = analyzer.analyze(sample_v2, doc_path=spec_path)
        
        spec_content = ""
        if os.path.exists(spec_path):
            with open(spec_path, "r", encoding="utf-8") as f:
                spec_content = f.read()

        report_text = "========================================================================================\n"
        report_text += "🤖 OPSHEAL SUBAGENT-TRIAGE: AUTONOMOUS DRIFT DISCOVERY REPORT (RUNTIME GENERATED)\n"
        report_text += "Ingested Vendor RFC: RFC-GP-2026-V2 (docs/VENDOR_PAYMENT_V2_SPEC.md)\n"
        report_text += "========================================================================================\n\n"
        report_text += "🔍 DYNAMIC DRIFT MAPPINGS DISCOVERED AT RUNTIME:\n"
        for r in drift["renames"]:
            report_text += f"1. Field Rename Detected: '{r['original_field']}' -> '{r['incoming_field']}' (Confidence: {int(r['confidence_score']*100)}%)\n"
            report_text += f"   Rationale: {r['rationale']}\n"
        for n in drift["nestings"]:
            report_text += f"2. Structural Nesting Detected: '{n['original_field']}' -> '{n['incoming_path']}' ({n['type']})\n"
            report_text += f"   Rationale: {n['rationale']}\n"
        for s in drift["schema_extensions"]:
            report_text += f"3. Enterprise Schema Extension: '{s['field_name']}' ({s['data_type']})\n"
            report_text += f"   Action: {s['action']} | Rationale: {s['rationale']}\n"
        
        if drift.get("doc_corroboration"):
            report_text += "\n📄 SPECIFICATION CORROBORATION:\n"
            for c in drift["doc_corroboration"]:
                report_text += f"  ✓ {c}\n"

        report_text += "\n========================================================================================\n"
        report_text += "FULL INGESTED VENDOR SPECIFICATION (docs/VENDOR_PAYMENT_V2_SPEC.md):\n"
        report_text += "========================================================================================\n\n"
        report_text += spec_content

        return {
            "stage": "HEALED",
            "title": "Subagent-Triage: Autonomous Drift Discovery Report",
            "summary": report_text
        }

@app.get("/v1/reports/pr")
def get_pr_report():
    pr_path = os.path.join(os.path.dirname(__file__), "..", "reports", "PULL_REQUEST_HOTFIX.md")
    if os.path.exists(pr_path):
        with open(pr_path, "r", encoding="utf-8") as f:
            return {"content": f.read()}
    from tools.generate_hotfix_pr import generate_pull_request_document
    p = generate_pull_request_document()
    with open(p, "r", encoding="utf-8") as f:
        return {"content": f.read()}

@app.get("/v1/reports/canary")
def get_canary_report():
    canary_path = os.path.join(os.path.dirname(__file__), "..", "reports", "CANARY_VERIFICATION.md")
    if os.path.exists(canary_path):
        with open(canary_path, "r", encoding="utf-8") as f:
            return {"content": f.read()}
    from services.canary_deployer import run_canary_health_gate
    run_canary_health_gate()
    with open(canary_path, "r", encoding="utf-8") as f:
        return {"content": f.read()}

@app.get("/v1/reports/postmortem")
def get_postmortem_report():
    pm_path = os.path.join(os.path.dirname(__file__), "..", "reports", "POST_MORTEM.md")
    if os.path.exists(pm_path):
        with open(pm_path, "r", encoding="utf-8") as f:
            return {"content": f.read()}
    return {"content": "# Post-Mortem Report Not Found"}

# ============================================================
# LIVE INSPECTION & DEMO EVIDENCE ENDPOINTS
# ============================================================
@app.get("/v1/demo/schema")
def get_database_schema():
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(transactions);")
        columns = [dict(row) for row in cursor.fetchall()]
        has_fee = any(c["name"] == "fee_amount" for c in columns)
        has_idemp = any(c["name"] == "idempotency_token" for c in columns)
        is_migrated = has_fee and has_idemp
        return {
            "table": "transactions",
            "columns": columns,
            "status": "MIGRATED_V2" if is_migrated else "UNMIGRATED_V1",
            "total_columns": len(columns),
            "migration_applied": is_migrated
        }

@app.get("/v1/demo/vendor-spec")
def get_vendor_spec():
    spec_path = os.path.join(os.path.dirname(__file__), "..", "docs", "VENDOR_PAYMENT_V2_SPEC.md")
    if os.path.exists(spec_path):
        with open(spec_path, "r", encoding="utf-8") as f:
            return {"content": f.read()}
    return {"content": "# Vendor Spec Not Found"}

@app.get("/v1/demo/adapter-code")
def get_adapter_code():
    code_path = os.path.join(os.path.dirname(__file__), "..", "services", "contract_adapter.py")
    if os.path.exists(code_path):
        with open(code_path, "r", encoding="utf-8") as f:
            return {"content": f.read()}
    return {"content": "# Contract adapter not yet generated"}

@app.post("/v1/demo/send-test-v2")
def send_test_v2_probe(scenario: Optional[str] = None):
    import time
    global ADAPTER_ACTIVE, ACTIVE_SCENARIO
    scen = scenario or ACTIVE_SCENARIO or "mixed"
    test_tx_id = f"TX-PROBE-{int(time.time()*1000)%100000}"

    if scen == "stripe":
        probe_payload = {
            "event_type": "charge.captured",
            "transaction_id": test_tx_id,
            "client_id": "CUST-STRIPE-ENTERPRISE",
            "amount_cents": 580000,
            "fee_amount": 17.40,
            "currency": "usd",
            "status": "succeeded",
            "idempotency_key": f"IDEMP-{test_tx_id}-SECURE"
        }
        probe_title = "Stripe Minor Units (amount_cents: 580000)"
        error_field = "customer_id"
    elif scen == "dirty":
        probe_payload = {
            "event_id": f"EVT-{test_tx_id}",
            "transaction_id": test_tx_id,
            "payer_id": "CUST-GLOBAL-HOLDINGS",
            "amount": "$12,450.75",
            "fee": "$37.35",
            "currency": "USD",
            "state": "Authorised",
            "idempotency_token": f"IDEMP-{test_tx_id}-SECURE"
        }
        probe_title = "Stringified Currency Coercion ($12,450.75)"
        error_field = "customer_id"
    else:
        # Default / GlobalPay v2 / Mixed
        probe_payload = {
            "event_id": f"EVT-{test_tx_id}",
            "transaction_id": test_tx_id,
            "account_ref": "CUST-ENTERPRISE-PROBE",
            "payment_detail": {
                "settlement_amount": 3500.00,
                "fee_amount": 10.50,
                "iso_currency": "USD"
            },
            "idempotency_token": f"IDEMP-{test_tx_id}-SECURE"
        }
        probe_title = "GlobalPay RFC-GP-2026-V2 (account_ref & payment_detail)"
        error_field = "customer_id"

    if not ADAPTER_ACTIVE:
        return {
            "status_code": 500,
            "status_text": "INTERNAL SERVER ERROR",
            "scenario": scen,
            "probe_title": probe_title,
            "request_payload": probe_payload,
            "response_body": {
                "detail": f"Webhook Ingestion Failed: Schema Mismatch ('{error_field}' missing from root)"
            },
            "error_trace": f"Traceback (most recent call last):\n  File 'api/main.py', line 94, in ingest_payment_webhook\n    customer_id = payload['{error_field}']\nKeyError: '{error_field}'\n\n[Captured Server Crash]:\nUnpatched base router expects flat legacy v1 schema.\nHalts on first unhandled exception before amount extraction or database persistence.\n\n[OpsHeal Swarm Action]:\nSubagent-Triage analyzes full contract delta, maps aliases, coerces minor units/strings, and deploys zero-downtime adapter.",
            "healed": False
        }
    else:
        from services.contract_adapter import PaymentContractAdapter
        adapter = PaymentContractAdapter()
        normalized, transforms = adapter.adapt(probe_payload)
        return {
            "status_code": 200,
            "status_text": "OK - POLYMORPHIC SUCCESS",
            "scenario": scen,
            "probe_title": probe_title,
            "request_payload": probe_payload,
            "response_body": {
                "status": "PROCESSED",
                "transaction_id": test_tx_id,
                "version_handled": normalized["detected_version"],
                "account_ref": normalized["customer_id"],
                "settled_amount": normalized["amount"],
                "fee_amount": normalized["fee_amount"],
                "currency": normalized["currency"],
                "status_code": normalized["status"],
                "idempotency_token": normalized["idempotency_token"],
                "transformations_applied": transforms
            },
            "error_trace": None,
            "healed": True
        }

@app.post("/v1/demo/send-custom-webhook")
def send_custom_webhook_payload(payload: Dict[str, Any]):
    global ADAPTER_ACTIVE
    if not ADAPTER_ACTIVE:
        try:
            cust = payload["customer_id"]
            amt = payload["amount"]
            return {
                "status_code": 200,
                "status_text": "OK - BASE ROUTER",
                "request_payload": payload,
                "response_body": {"status": "PROCESSED", "customer_id": cust, "amount": amt},
                "error_trace": None,
                "healed": False
            }
        except Exception as e:
            return {
                "status_code": 500,
                "status_text": "INTERNAL SERVER ERROR",
                "request_payload": payload,
                "response_body": {
                    "detail": f"Webhook Ingestion Failed: Schema Mismatch ({str(e.__class__.__name__)}: '{str(e)}')"
                },
                "error_trace": f"Traceback (most recent call last):\n  File 'api/main.py', line 94, in ingest_payment_webhook\n    {str(e.__class__.__name__)}: {str(e)}\n\n[OpsHeal Triage]: Unpatched base router failed to extract expected legacy v1 keys from custom payload.",
                "healed": False
            }
    else:
        from services.contract_adapter import PaymentContractAdapter
        adapter = PaymentContractAdapter()
        normalized, transforms = adapter.adapt(payload)
        return {
            "status_code": 200,
            "status_text": "OK - POLYMORPHIC SUCCESS",
            "request_payload": payload,
            "response_body": {
                "status": "PROCESSED",
                "transaction_id": normalized["transaction_id"],
                "version_handled": normalized["detected_version"],
                "account_ref": normalized["customer_id"],
                "settled_amount": normalized["amount"],
                "fee_amount": normalized["fee_amount"],
                "currency": normalized["currency"],
                "status_code": normalized["status"],
                "idempotency_token": normalized["idempotency_token"],
                "transformations_applied": transforms
            },
            "error_trace": None,
            "healed": True
        }
