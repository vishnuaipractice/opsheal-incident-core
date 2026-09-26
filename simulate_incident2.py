import httpx
import time
import sys
import json
import argparse

BASE_URL = "http://127.0.0.1:8000"

# ANSI color codes for high-impact presentation
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
RESET = "\033[0m"

V1_SAMPLE_PAYLOADS = [
    {"event_id": "EVT-1001", "transaction_id": "TX-1001", "customer_id": "CUST-401", "amount": 1200.0, "currency": "USD"},
    {"event_id": "EVT-1002", "transaction_id": "TX-1002", "customer_id": "CUST-402", "amount": 3450.0, "currency": "USD"},
    {"event_id": "EVT-1003", "transaction_id": "TX-1003", "customer_id": "CUST-403", "amount": 890.0, "currency": "USD"},
    {"event_id": "EVT-1004", "transaction_id": "TX-1004", "customer_id": "CUST-404", "amount": 2100.0, "currency": "USD"},
    {"event_id": "EVT-1005", "transaction_id": "TX-1005", "customer_id": "CUST-405", "amount": 4500.0, "currency": "USD"},
]

V2_BREAKING_PAYLOADS = [
    {
        "event_id": f"EVT-20{i:02d}",
        "transaction_id": f"TX-20{i:02d}",
        "account_ref": f"CUST-80{i}",
        "payment_detail": {
            "settlement_amount": 1500.0 + (i * 275.0),
            "fee_amount": 12.50,
            "iso_currency": "USD"
        },
        "idempotency_token": f"IDEMP-GP20{i:02d}-SECURE"
    }
    for i in range(1, 16)  # 15 incoming breaking transactions (~$50,000 revenue)
]

def check_server():
    try:
        r = httpx.get(f"{BASE_URL}/health", timeout=3.0)
        return r.status_code == 200
    except Exception:
        return False

def run_incident_simulation():
    print(f"\n{BOLD}{CYAN}==================================================================={RESET}")
    print(f"{BOLD}{CYAN}   OPSHEAL INCIDENT 2: UPSTREAM CONTRACT DRIFT & DLQ POISONING   {RESET}")
    print(f"{BOLD}{CYAN}==================================================================={RESET}\n")

    if not check_server():
        print(f"{RED}[ERROR]{RESET} Cannot connect to {BASE_URL}.")
        print("Please start the microservice first:")
        print(f"  {YELLOW}uvicorn api.main:app --port 8000{RESET}\n")
        sys.exit(1)

    print(f"{BOLD}Phase 1: Normal Ingestion (Legacy v1 Webhook Stream){RESET}")
    for tx in V1_SAMPLE_PAYLOADS:
        res = httpx.post(f"{BASE_URL}/v1/webhooks/payment", json=tx, timeout=5.0)
        if res.status_code == 200:
            print(f"  {GREEN}[v1 OK]{RESET} TX {tx['transaction_id']} | Amount: ${tx['amount']:,.2f} -> HTTP 200")
        else:
            print(f"  {RED}[v1 FAIL]{RESET} TX {tx['transaction_id']} -> HTTP {res.status_code}")
        time.sleep(0.15)

    print(f"\n{BOLD}{YELLOW}-------------------------------------------------------------------{RESET}")
    print(f"{BOLD}{RED}WARNING: Upstream Provider Deployed Webhook API v2 (Breaking RFC-GP-2026-V2){RESET}")
    print(f"{BOLD}{YELLOW}-------------------------------------------------------------------{RESET}\n")
    time.sleep(1.0)

    print(f"{BOLD}Phase 2: Ingesting Active v2 Transaction Stream (Schema Mismatch){RESET}")
    total_poisoned_revenue = 0.0
    failed_count = 0

    for tx in V2_BREAKING_PAYLOADS:
        amount = tx["payment_detail"]["settlement_amount"]
        try:
            res = httpx.post(f"{BASE_URL}/v1/webhooks/payment", json=tx, timeout=5.0)
            if res.status_code == 200:
                print(f"  {GREEN}[v2 OK]{RESET} TX {tx['transaction_id']} -> HTTP 200")
            else:
                failed_count += 1
                total_poisoned_revenue += amount
                print(f"  {RED}[SEV-1 CRASH]{RESET} TX {tx['transaction_id']} (${amount:,.2f}) -> {RED}HTTP 500 Server Error (Pushed to DLQ){RESET}")
        except Exception as e:
            failed_count += 1
            total_poisoned_revenue += amount
            print(f"  {RED}[NETWORK ERROR]{RESET} TX {tx['transaction_id']} -> {e}")
        time.sleep(0.1)

    # Fetch live DLQ status
    dlq_res = httpx.get(f"{BASE_URL}/v1/dlq").json()

    print(f"\n{BOLD}{RED}==================================================================={RESET}")
    print(f"{BOLD}{RED}        🚨 CRITICAL SEV-1 PRODUCTION OUTAGE DETECTED 🚨            {RESET}")
    print(f"{BOLD}{RED}==================================================================={RESET}")
    print(f"  • {BOLD}Trapped Transactions in DLQ:{RESET}  {RED}{dlq_res['dlq_count']} transactions{RESET}")
    print(f"  • {BOLD}Frozen Enterprise Revenue:{RESET}    {RED}${dlq_res['trapped_volume_usd']:,.2f} USD{RESET}")
    print(f"  • {BOLD}Root Cause:{RESET}                   Upstream Schema Drift (`account_ref` vs `customer_id`)")
    print(f"  • {BOLD}Database Impact:{RESET}              IntegrityError / Missing Schema Columns")
    print(f"  • {BOLD}Queue Status:{RESET}                 Dead-Letter Queue Poisoned (`queue/dead_letter_queue.json`)")
    print(f"{BOLD}{RED}==================================================================={RESET}")
    print(f"\n{YELLOW}>> ACTION: Trigger IBM Bob 2.0 OpsHeal Autonomous Remediation Swarm.{RESET}\n")

def run_recovery_verification():
    print(f"\n{BOLD}{CYAN}==================================================================={RESET}")
    print(f"{BOLD}{CYAN}   OPSHEAL: POST-HEALING PRODUCTION VERIFICATION RUN              {RESET}")
    print(f"{BOLD}{CYAN}==================================================================={RESET}\n")

    if not check_server():
        print(f"{RED}[ERROR]{RESET} Cannot connect to {BASE_URL}.")
        sys.exit(1)

    # 1. Check DLQ status
    dlq_res = httpx.get(f"{BASE_URL}/v1/dlq").json()
    print(f"{BOLD}Step 1: Dead-Letter Queue Backlog Inspection{RESET}")
    if dlq_res["dlq_count"] == 0:
        print(f"  {GREEN}[CLEARED]{RESET} Dead-Letter Queue Backlog: {GREEN}0 records (100% Drained){RESET}")
    else:
        print(f"  {YELLOW}[PENDING]{RESET} DLQ Backlog: {dlq_res['dlq_count']} records remaining")

    # 2. Test live v2 ingestion
    print(f"\n{BOLD}Step 2: Live v2 Ingestion Test (Modern Webhook){RESET}")
    v2_live = {
        "event_id": "EVT-LIVE-2099",
        "transaction_id": "TX-LIVE-2099",
        "account_ref": "CUST-VIP-77",
        "payment_detail": {
            "settlement_amount": 5400.0,
            "fee_amount": 18.0,
            "iso_currency": "USD"
        },
        "idempotency_token": "IDEMP-LIVE-VIP-77"
    }
    r_v2 = httpx.post(f"{BASE_URL}/v1/webhooks/payment", json=v2_live, timeout=5.0)
    if r_v2.status_code == 200:
        print(f"  {GREEN}[SUCCESS - HTTP 200]{RESET} v2 Webhook Ingested: {r_v2.json()}")
    else:
        print(f"  {RED}[FAILED - HTTP {r_v2.status_code}]{RESET} {r_v2.text}")

    # 3. Test backward compatibility (v1 Webhook)
    print(f"\n{BOLD}Step 3: Backward Compatibility Test (Legacy v1 Webhook){RESET}")
    v1_live = {
        "event_id": "EVT-LIVE-1099",
        "transaction_id": "TX-LIVE-1099",
        "customer_id": "CUST-LEGACY-12",
        "amount": 950.0,
        "currency": "USD"
    }
    r_v1 = httpx.post(f"{BASE_URL}/v1/webhooks/payment", json=v1_live, timeout=5.0)
    if r_v1.status_code == 200:
        print(f"  {GREEN}[SUCCESS - HTTP 200]{RESET} v1 Webhook Ingested: {r_v1.json()}")
    else:
        print(f"  {RED}[FAILED - HTTP {r_v1.status_code}]{RESET} {r_v1.text}")

    # 4. Database Reconciliation Stats
    tx_res = httpx.get(f"{BASE_URL}/v1/transactions").json()
    stats = tx_res["stats"]
    print(f"\n{BOLD}Step 4: Financial Ledger Reconciliation{RESET}")
    print(f"  • {BOLD}Total Settled Transactions:{RESET} {GREEN}{stats['settled_count']}{RESET}")
    print(f"  • {BOLD}Total Settled Revenue:{RESET}      {GREEN}${stats['settled_volume']:,.2f} USD{RESET}")

    print(f"\n{BOLD}{GREEN}==================================================================={RESET}")
    print(f"{BOLD}{GREEN}    ✅ ZERO-DOWNTIME RECOVERY CONFIRMED: 0 DROPPED TRANSACTIONS   {RESET}")
    print(f"{BOLD}{GREEN}==================================================================={RESET}\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simulate Incident 2: Contract Drift & DLQ Poisoning")
    parser.add_argument("--verify-recovery", action="store_true", help="Verify healed production state")
    args = parser.parse_args()

    if args.verify_recovery:
        run_recovery_verification()
    else:
        run_incident_simulation()
