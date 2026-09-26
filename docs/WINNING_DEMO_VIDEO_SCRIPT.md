# 🎬 Grand-Prize 3-Minute Video Recording Script: OpsHeal

**Target Duration**: 2 minutes 50 seconds *(Strict LabLab rule: Under 3:00, with >90s showing the solution in action)*.

---

## ⏱️ Timeline & Action Breakdown

### **[0:00 – 0:30] ACT 1: The Hook & The Enterprise Problem**
* **Screen**: Show Slide 1 or Slide 2 of `docs/OpsHeal_Pitch_Deck.pptx` (Title Hero & the $1.17M Problem).
* **Voice**:
  > "Every year, enterprise payment platforms lose millions when upstream gateways like Stripe or GlobalPay silently push breaking API contract changes. When field names change or amounts switch to cents, backend ingestion crashes with HTTP 500s—trapping thousands of in-flight customer orders in Dead-Letter Queues.  
  > Traditional war rooms take an average of 3.5 hours to assemble SREs, DBAs, and developers—costing over $1.1 million per incident.  
  > We built **OpsHeal**, powered by the **IBM Bob 2.0 Agent Core**: an autonomous incident triage and zero-downtime hotfix swarm that resolves contract drift in 48 seconds."

---

### **[0:30 – 1:15] ACT 2: Real Code & Terminal Execution in IBM Bob IDE**
* **Screen**: Switch to **IBM Bob IDE**:
  1. Show the **Tasks panel** on the right with your completed task sessions (`Turn 1: Triage`, `Turn 2: Migration`, `Turn 3: Adapter`, `Turn 4: Canary`).
  2. Open `services/contract_adapter.py` or `database/migrations/migration_002_add_v2_columns.py` in the editor.
  3. In the Bob terminal at the bottom, run:
     `python -m pytest -v`
     *(Show all 21 tests passing in green!)*
* **Voice**:
  > "Here inside IBM Bob 2.0, we operated in full Agent Mode. Bob did not just give us chat suggestions—it acted directly on our repository.  
  > Across 5 specialized turns, Bob analyzed breaking vendor tracebacks, authored our non-blocking SQLite WAL migration with 15-second busy timeouts, and synthesized a 300-line polymorphic Anti-Corruption Layer.  
  > As you can see in the Bob terminal, our automated test suite executes across 21 unit and integration tests with a 100% pass rate in under two seconds."

---

### **[1:15 – 2:20] ACT 3: Live Incident Outage & Autonomous Healing**
* **Screen**: Switch to browser: `http://localhost:8000` (War Room Dashboard):
  1. In the dropdown, select **`🌐 Outage: Multi-Gateway Chaos`**.
  2. Click **`🚨 Trigger Sev-1 Outage`**. Point to the red **`HTTP 500 CRASH`** console, `Revenue at Risk: $69,000.00`, and `DLQ: 15`.
  3. Click **`⚡ Run OpsHeal Autonomous Healer`**. Watch the 6 subagent cards sequentially activate (`Bob-Triage`, `Bob-DBA`, `Bob-Adapter`, `Bob-Canary`, `Bob-Drainer`, `Bob-Release`).
  4. Show the Live Execution Console flip to green **`HTTP 200 OK`**.
* **Voice**:
  > "Now let's see OpsHeal heal a live SEV-1 production incident.  
  > We inject a multi-gateway outage: upstream partners have sent mixed payloads with Stripe minor cents, dirty localized currency strings, and nested structures.  
  > Immediately, the legacy router crashes with a KeyError. 15 enterprise transactions worth $69,000.00 are trapped in our Dead-Letter Queue.  
  > Now, watch our IBM Bob swarm take control with one click:  
  > Bob-Triage ingests the tracebacks and vendor specs.  
  > Bob-DBA executes an online non-blocking WAL migration without table locks.  
  > Bob-Adapter deploys the polymorphic engine in memory.  
  > Bob-Canary runs synthetic probes with SHA-256 idempotency checks.  
  > And Bob-Drainer flushes the DLQ. In just 48 seconds, the service is fully restored to HTTP 200 OK!"

---

### **[2:20 – 2:55] ACT 4: Mathematical Invariants, Chaos Injector & ROI Post-Mortem**
* **Screen**: 
  1. Point to **`Dead-Letter Queue: 0`** and **`Settled Ledger: $69,000.00`**.
  2. Click **`🧪 Chaos Webhook Injector`** $\rightarrow$ select `Stripe Minor Units` $\rightarrow$ click **`Dispatch Chaos Webhook`** (show instant HTTP 200 OK with transformations applied).
  3. Click **`📑 View Post-Mortem`** on the dashboard to display the executive report and the $1.17M ROI table.
* **Voice**:
  > "Look at the mathematical ledger invariant: **$69,000.00 trapped in DLQ equals exactly $69,000.00 settled in the database**. Zero financial slippage, and zero double-spend charges.  
  > With our Chaos Webhook Injector, you can see the system now polymorphically handles minor units, dirty currency symbols, and nested hierarchies in real time.  
  > In our automated post-mortem report, OpsHeal reduced Mean Time to Recovery from 210 minutes down to 48 seconds—saving **$1,171,520 in direct downtime losses per incident**."

---

### **[2:55 – 3:00] ACT 5: Closing**
* **Screen**: Close modal, showing the clean dashboard with the **`IBM Bob 2.0 Swarm`** header badge.
* **Voice**:
  > "OpsHeal turns hours of high-stress human war rooms into 48 seconds of verifiable autonomous recovery, powered by IBM Bob 2.0. Thank you!"

---

## 🎯 Recording Tips
1. **Resolution**: Record at 1080p (1920x1080) for sharp text clarity.
2. **Audio**: Speak briskly and clearly; avoid long pauses.
3. **Timer**: Keep an eye on the clock—stop recording at around 2:52 to guarantee you are under 3:00.
