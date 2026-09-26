# ⚡ Ultra-Fast 2:15 Demo Video Script (188 Words)

**Total Duration**: ~2 minutes 15 seconds *(Guaranteed under the 3:00 limit with >90s on screen)*.

---

### **[0:00 – 0:20] 1. The Hook (20 seconds — 36 words)**
* **ACTION**: Screen shows the Title Slide of `docs/OpsHeal_Pitch_Deck.pptx` or your browser at `http://localhost:8000`.
* **SPEAK**:
  > "Every year, breaking payment API changes crash enterprise webhooks, trapping millions in Dead-Letter Queues and taking three and a half hours to fix. We built **OpsHeal**, powered by **IBM Bob 2.0**, to heal breaking contract drift in forty-eight seconds."

---

### **[0:20 – 0:55] 2. IBM Bob IDE & Code Proof (35 seconds — 38 words)**
* **ACTION**: 
  1. Switch to **IBM Bob IDE**.
  2. Point mouse to the **Tasks panel** showing your 4 completed Bob sessions.
  3. In the Bob integrated terminal, run: `python -m pytest -v` (let the 21 green tests pass!).
* **SPEAK**:
  > "Inside IBM Bob 2.0, our agent swarm analyzed the crash, generated a non-blocking SQLite WAL migration, and built a polymorphic Anti-Corruption Layer. In the Bob terminal, all twenty-one automated tests pass with zero failures in under two seconds."

---

### **[0:55 – 1:45] 3. Live SEV-1 Outage & Healer (50 seconds — 65 words)**
* **ACTION**: 
  1. Switch to browser: `http://localhost:8000`.
  2. Click **`🚨 Trigger Sev-1 Outage`**. Point mouse to the red **`HTTP 500 CRASH`** console and **`DLQ: 15 ($69,000)`**.
  3. Click **`⚡ Run OpsHeal Autonomous Healer`**. Watch the 6 Bob subagents execute.
  4. Show the live console flip to green **`HTTP 200 OK`**.
* **SPEAK**:
  > "Now, watch it heal a live SEV-1 outage. Upstream gateways send mixed schemas: Stripe cents and nested fields. The router crashes with HTTP 500, trapping sixty-nine thousand dollars in our Dead-Letter Queue.  
  > I click 'Run OpsHeal Autonomous Healer'. The six Bob subagents execute online: migrating the database, deploying the adapter, and draining the queue. In forty-eight seconds, the service is fully restored to HTTP 200!"

---

### **[1:45 – 2:15] 4. Proof of Invariant, Chaos & Closing (30 seconds — 49 words)**
* **ACTION**: 
  1. Point to **`DLQ: 0`** and **`Settled Ledger: $69,000.00`**.
  2. Click **`🧪 Chaos Webhook Injector`** → click **`Dispatch Chaos Webhook`** (show instant HTTP 200).
  3. Click **`📑 View Post-Mortem`** to flash the $1.17M savings table.
* **SPEAK**:
  > "Look at the result: zero DLQ backlog, and exactly sixty-nine thousand dollars settled with one-to-one ledger parity. With our Chaos Webhook Injector, Stripe minor cents process instantly. OpsHeal reduced MTTR by ninety-nine point six percent, saving one point one seven million dollars per incident.  
  > This is OpsHeal, powered by IBM Bob 2.0. Thank you!"

---

### 💡 Pro-Tips for Recording
- **Do not read every detail on screen**—the screen speaks for itself! You only need to guide the viewer's eyes.
- If you stumble on a sentence, don't stop the recording: just pause 2 seconds, repeat that sentence, and trim it or keep going!
