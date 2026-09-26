import os
import sys

BOB_SESSIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "bob_sessions")

REQUIRED_SCREENSHOTS = [
    {
        "filename": "opsheal_task01_incident_triage.png",
        "task_name": "Task 1: Incident Log Ingestion & Root Cause Analysis",
        "description": "Evidence of Bob reading logs/production_error.log and docs/VENDOR_PAYMENT_V2_SPEC.md via Document Understanding."
    },
    {
        "filename": "opsheal_task02_contract_adapter_migration.png",
        "task_name": "Task 2: Database Migration & Polymorphic Adapter Generation",
        "description": "Evidence of Bob subagents writing migration_002_add_v2_columns.py and services/contract_adapter.py."
    },
    {
        "filename": "opsheal_task03_verification_postmortem.png",
        "task_name": "Task 3: Canary Health Gate, DLQ Recovery & CTO PR Generation",
        "description": "Evidence of Bob running pytest suite, draining DLQ, and creating reports/PULL_REQUEST_HOTFIX.md."
    }
]

def verify_bob_sessions():
    os.makedirs(BOB_SESSIONS_DIR, exist_ok=True)
    existing_files = os.listdir(BOB_SESSIONS_DIR)
    
    print("\n========================================================")
    print("      LABLAB.AI BOB SESSIONS DELIVERABLE VERIFIER      ")
    print("========================================================\n")
    print(f"Target Directory: {os.path.abspath(BOB_SESSIONS_DIR)}\n")
    
    missing_count = 0
    
    for item in REQUIRED_SCREENSHOTS:
        fname = item["filename"]
        path = os.path.join(BOB_SESSIONS_DIR, fname)
        if os.path.exists(path) and os.path.getsize(path) > 0:
            size_kb = round(os.path.getsize(path) / 1024, 1)
            print(f"  [OK] {fname} ({size_kb} KB)")
            print(f"       Task: {item['task_name']}\n")
        else:
            missing_count += 1
            print(f"  [MISSING] {fname}")
            print(f"       Task: {item['task_name']}")
            print(f"       Action: {item['description']}\n")
            
    print("--------------------------------------------------------")
    if missing_count == 0:
        print("  STATUS: 100% COMPLIANT - All required Bob screenshots present!")
        print("========================================================\n")
        return True
    else:
        print(f"  STATUS: {missing_count} SCREENSHOT(S) PENDING")
        print("  Please capture the task consumption headers in Bob IDE.")
        print("  See guide: docs/BOB_SESSIONS_SCREENSHOT_GUIDE.md")
        print("========================================================\n")
        return False

if __name__ == "__main__":
    is_compliant = verify_bob_sessions()
    sys.exit(0 if is_compliant else 1)
