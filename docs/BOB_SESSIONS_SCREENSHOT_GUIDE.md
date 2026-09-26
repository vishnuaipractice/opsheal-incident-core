# IBM Bob 2.0 Task Session Screenshot Guide (`bob_sessions/`)

> [!IMPORTANT]
> **Mandatory Lablab.ai Deliverable**: Every hackathon submission **must** include task session summary screenshots in a folder named `bob_sessions/` in your repository root. Submissions without this folder are automatically disqualified.

---

## 📍 Where & How to Capture Screenshots in Bob IDE

Follow these exact steps inside the IBM Bob IDE without burning extra Bobcoins:

### Step 1: Open the Chat & Tasks Panel
1. In IBM Bob IDE, open the **Chat Panel** on the right.
2. At the top of the chat panel, click on **Tasks**.

### Step 2: Open the Session Consumption Header
1. Select the relevant task from the task list.
2. Click directly on the **Task Header** (the title block at the top of the task conversation).
3. A popup/drawer will expand showing the **Session Consumption Summary** (displaying task duration, tokens/Bobcoin consumption, and subagent tool invocations).

### Step 3: Capture the Screenshot
1. Press `Windows + Shift + S` (Snipping Tool).
2. Capture the window showing the task title, prompt, and session consumption summary clearly.
3. Save as a `.png` file directly into the [`bob_sessions/`](file:///c:/vishnu/AI/Hackathons/IBM%20Bob%202.0%20Hackathon%20LabLab%20ai/opsheal-incident-core/bob_sessions) folder.

---

## 📸 The 3 Required Screenshots & Exact Filenames

| File to Save | What Screen to Capture in Bob IDE |
| :--- | :--- |
| **`bob_sessions/opsheal_task01_incident_triage.png`** | Open the task header for **Task 1: Incident Log Ingestion & Root Cause Analysis**. Shows Bob reading `logs/production_error.log` and `docs/VENDOR_PAYMENT_V2_SPEC.md` using Document Understanding. |
| **`bob_sessions/opsheal_task02_contract_adapter_migration.png`** | Open the task header for **Task 2: Database Migration & Polymorphic Adapter Generation**. Shows Bob's subagents writing `migration_002_add_v2_columns.py` and `services/contract_adapter.py`. |
| **`bob_sessions/opsheal_task03_verification_postmortem.png`** | Open the task header for **Task 3: Canary Health Gate & DLQ Draining**. Shows Bob running `pytest -v`, executing the Canary Gate, draining the DLQ, and generating `reports/PULL_REQUEST_HOTFIX.md`. |

---

## 🧪 Validating Your Submission Compliance

Run the automated verification script from your terminal:

```bash
python tools/verify_bob_sessions.py
```

- When all 3 PNG screenshots are in place, the script will output:
  `STATUS: 100% COMPLIANT - All required Bob screenshots present!`
