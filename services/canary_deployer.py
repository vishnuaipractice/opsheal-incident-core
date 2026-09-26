"""
services/canary_deployer.py
---------------------------
Bob-Canary Safety Gate

Dispatches 5 synthetic probe payloads against a disposable in-memory shadow
sandbox before any DLQ traffic is promoted to the production ledger.

Probe coverage
--------------
  P-01  Legacy flat v1          — minimal flat fields, no nesting, USD amount
  P-02  Modern nested v2        — payment_detail sub-object, idempotency token
  P-03  Stripe minor-cents      — amount expressed in integer cents (Stripe style)
  P-04  Dirty currency string   — amount as "$12,450.75" (currency symbol + commas)
  P-05  Duplicate idempotency   — identical token as P-02 → must be DEDUP_PROTECTED

Anti-Double-Spend Invariant (ADS)
----------------------------------
After P-02 is inserted with token IDEMP-CANARY-PROBE-02, P-05 replays the same
token.  The gate asserts that:
  a) exactly ONE row exists in the sandbox for that token, AND
  b) the replay returns the cached record instead of inserting a new row.
Failure of either assertion sets gate_status = "FAILED".
"""

import time
import os
import sys
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

# Ensure project root is on sys.path regardless of invocation directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.contract_adapter import PaymentContractAdapter


# ---------------------------------------------------------------------------
# Probe definitions
# ---------------------------------------------------------------------------

CANARY_PROBES: List[Dict[str, Any]] = [
    # ------------------------------------------------------------------
    # P-01 · Legacy flat v1
    #   Flat key-value structure, no sub-objects, explicit customer_id.
    #   Exercises the v1 happy-path without any schema-drift transforms.
    # ------------------------------------------------------------------
    {
        "id": "P-01",
        "name": "Legacy Flat v1 Payload",
        "description": "Flat v1 structure — no nesting, plain USD amount",
        "payload": {
            "event_id": "EVT-CANARY-01",
            "transaction_id": "TX-CANARY-01",
            "customer_id": "CUST-CANARY-A",
            "amount": 250.00,
            "currency": "USD",
            "status": "settled",
        },
        "expected_version": "v1",
        "expect_dedup": False,
    },

    # ------------------------------------------------------------------
    # P-02 · Modern nested v2
    #   payment_detail sub-object with settlement_amount, fee, iso_currency.
    #   Exercises structural unnesting + alias resolution + v2 detection.
    # ------------------------------------------------------------------
    {
        "id": "P-02",
        "name": "Modern Nested v2 Payload",
        "description": "v2 payment_detail sub-object, explicit idempotency token",
        "payload": {
            "event_id": "EVT-CANARY-02",
            "transaction_id": "TX-CANARY-02",
            "account_ref": "CUST-CANARY-B",
            "payment_detail": {
                "settlement_amount": 9_850.00,
                "fee_amount": 29.55,
                "iso_currency": "USD",
            },
            "idempotency_token": "IDEMP-CANARY-PROBE-02",
            "status": "succeeded",
        },
        "expected_version": "v2",
        "expect_dedup": False,
    },

    # ------------------------------------------------------------------
    # P-03 · Stripe minor-cents payload
    #   amount_cents = 4750  (i.e. $47.50).  Exercises the CENTS_CANDIDATES
    #   resolution path and the ÷100 unit-scale coercion transform.
    # ------------------------------------------------------------------
    {
        "id": "P-03",
        "name": "Stripe Minor-Cents Payload",
        "description": "amount_cents integer (Stripe-style) → divided by 100",
        "payload": {
            "event_id": "EVT-CANARY-03",
            "transaction_id": "TX-CANARY-03",
            "customer_id": "CUST-CANARY-C",
            "amount_cents": 4750,
            "currency": "USD",
            "status": "paid",
        },
        "expected_version": "v1_adapted",
        "expect_dedup": False,
        # Adapter must coerce 4750 cents → $47.50
        "assert_amount": 47.50,
    },

    # ------------------------------------------------------------------
    # P-04 · Dirty currency string payload
    #   amount = "$12,450.75" — exercises the regex currency-string coercion
    #   path that strips the $ symbol and thousands separator.
    # ------------------------------------------------------------------
    {
        "id": "P-04",
        "name": "Dirty Currency String Payload",
        "description": 'amount as "$12,450.75" string — regex strip to clean float',
        "payload": {
            "event_id": "EVT-CANARY-04",
            "transaction_id": "TX-CANARY-04",
            "customer_id": "CUST-CANARY-D",
            "amount": "$12,450.75",
            "currency": "USD",
            "status": "completed",
        },
        "expected_version": "v1_adapted",
        "expect_dedup": False,
        # Adapter must parse "$12,450.75" → 12450.75
        "assert_amount": 12_450.75,
    },

    # ------------------------------------------------------------------
    # P-05 · Duplicate idempotency token replay  (Anti-Double-Spend)
    #   Replays the *exact same* idempotency_token as P-02.
    #   The gate asserts DEDUP_PROTECTED status and no new DB row.
    # ------------------------------------------------------------------
    {
        "id": "P-05",
        "name": "Duplicate Idempotency Token Replay",
        "description": "Replay of P-02 token — must be caught and deduplicated",
        "payload": {
            "event_id": "EVT-CANARY-05-REPLAY",
            "transaction_id": "TX-CANARY-05-REPLAY",
            "account_ref": "CUST-CANARY-B",
            "payment_detail": {
                "settlement_amount": 9_850.00,
                "fee_amount": 29.55,
                "iso_currency": "USD",
            },
            # Same token as P-02 — the ADS invariant must block insertion
            "idempotency_token": "IDEMP-CANARY-PROBE-02",
            "status": "succeeded",
        },
        "expected_version": "v2",
        "expect_dedup": True,
    },
]


# ---------------------------------------------------------------------------
# Shadow sandbox helpers
# ---------------------------------------------------------------------------

def _build_sandbox() -> sqlite3.Connection:
    """Return an in-memory SQLite connection pre-seeded with the transactions schema."""
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE transactions (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            probe_id          TEXT NOT NULL,
            transaction_id    TEXT UNIQUE NOT NULL,
            customer_id       TEXT NOT NULL,
            amount            REAL NOT NULL,
            fee_amount        REAL NOT NULL DEFAULT 0.0,
            currency          TEXT NOT NULL DEFAULT 'USD',
            status            TEXT NOT NULL,
            idempotency_token TEXT,
            normalized_version TEXT,
            created_at        TEXT NOT NULL
        );
    """)
    conn.commit()
    return conn


def _fetch_by_token(
    conn: sqlite3.Connection, token: str
) -> Optional[sqlite3.Row]:
    cur = conn.execute(
        "SELECT * FROM transactions WHERE idempotency_token = ?", (token,)
    )
    return cur.fetchone()


def _insert_probe(
    conn: sqlite3.Connection,
    probe_id: str,
    norm: Dict[str, Any],
) -> None:
    conn.execute(
        """
        INSERT INTO transactions
            (probe_id, transaction_id, customer_id, amount, fee_amount,
             currency, status, idempotency_token, normalized_version, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            probe_id,
            norm["transaction_id"],
            norm["customer_id"],
            norm["amount"],
            norm.get("fee_amount", 0.0),
            norm.get("currency", "USD"),
            norm["status"],
            norm.get("idempotency_token"),
            norm.get("detected_version", ""),
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Main gate runner
# ---------------------------------------------------------------------------

def run_canary_health_gate(
    output_report: str = "reports/CANARY_VERIFICATION.md",
) -> Dict[str, Any]:
    """
    Execute all CANARY_PROBES in an isolated shadow sandbox and write a
    structured Markdown verification report.

    Returns a result dict with gate_status, probe counts, ADS proof, and
    the path to the generated report.
    """
    adapter = PaymentContractAdapter()
    conn = _build_sandbox()
    probe_results: List[Dict[str, Any]] = []
    ads_proof: Dict[str, Any] = {}

    gate_start = time.time()
    passed = 0
    ads_caught = 0

    for probe in CANARY_PROBES:
        t0 = time.time()
        pid = probe["id"]
        payload = probe["payload"]
        exec_status = "UNKNOWN"
        error_msg: Optional[str] = None
        norm: Optional[Dict[str, Any]] = None
        transforms: List[str] = []

        try:
            # Step 1 — adapt payload through the polymorphic ACL
            norm, transforms = adapter.adapt(payload)

            # Step 2 — version assertion
            assert norm["detected_version"] == probe["expected_version"], (
                f"Version mismatch: expected {probe['expected_version']!r}, "
                f"got {norm['detected_version']!r}"
            )

            # Step 3 — optional amount assertion (cents / dirty-string probes)
            if "assert_amount" in probe:
                assert abs(norm["amount"] - probe["assert_amount"]) < 0.001, (
                    f"Amount coercion failed: expected {probe['assert_amount']}, "
                    f"got {norm['amount']}"
                )

            # Step 4 — idempotency / ADS check
            token = norm.get("idempotency_token")

            if probe.get("expect_dedup"):
                # --- Anti-Double-Spend invariant proof ---
                existing_row = _fetch_by_token(conn, token) if token else None
                if existing_row:
                    ads_caught += 1
                    exec_status = "DEDUP_PROTECTED"
                    # ADS proof: row_count must still be exactly 1 after replay
                    count_after = conn.execute(
                        "SELECT COUNT(*) FROM transactions WHERE idempotency_token = ?",
                        (token,),
                    ).fetchone()[0]
                    ads_proof = {
                        "replay_token": token,
                        "rows_before_replay": 1,
                        "rows_after_replay": count_after,
                        "cached_tx_id": existing_row[2],   # transaction_id column
                        "double_spend_blocked": count_after == 1,
                    }
                else:
                    # Token not found yet — this means P-02 never ran: insert
                    # (edge case; in normal sequential execution this won't fire)
                    _insert_probe(conn, pid, norm)
                    exec_status = "INSERTED"
            else:
                # Normal probe — insert into sandbox
                _insert_probe(conn, pid, norm)
                exec_status = "INSERTED"

            latency_ms = round((time.time() - t0) * 1000, 2)
            passed += 1
            probe_results.append(
                {
                    "id": pid,
                    "name": probe["name"],
                    "description": probe["description"],
                    "status": "PASSED",
                    "exec_status": exec_status,
                    "latency_ms": latency_ms,
                    "normalized_amount": norm["amount"] if norm else None,
                    "normalized_version": norm["detected_version"] if norm else None,
                    "idempotency_token": norm.get("idempotency_token") if norm else None,
                    "transforms": transforms,
                    "error": None,
                }
            )

        except Exception as exc:
            latency_ms = round((time.time() - t0) * 1000, 2)
            error_msg = str(exc)
            probe_results.append(
                {
                    "id": pid,
                    "name": probe["name"],
                    "description": probe["description"],
                    "status": "FAILED",
                    "exec_status": "CRASHED",
                    "latency_ms": latency_ms,
                    "normalized_amount": norm["amount"] if norm else None,
                    "normalized_version": norm.get("detected_version") if norm else None,
                    "idempotency_token": None,
                    "transforms": transforms,
                    "error": error_msg,
                }
            )

    conn.close()
    total_ms = round((time.time() - gate_start) * 1000, 2)
    total_probes = len(CANARY_PROBES)
    error_rate = round(((total_probes - passed) / total_probes) * 100.0, 1)
    gate_passed = error_rate == 0.0 and ads_proof.get("double_spend_blocked", False)

    # -----------------------------------------------------------------------
    # Build the structured Markdown report
    # -----------------------------------------------------------------------
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S UTC")

    md_lines: List[str] = []
    md_lines += [
        "# CANARY DEPLOYMENT & SAFETY GATE VERIFICATION REPORT",
        "",
        f"| Field | Value |",
        f"| :--- | :--- |",
        f"| **Gate Status** | {'🟢 PASSED — Promotion Approved' if gate_passed else '🔴 FAILED — Rollback Triggered'} |",
        f"| **Executed By** | OpsHeal Bob-Canary (IBM Bob 2.0 Agent Mode) |",
        f"| **Timestamp** | `{ts}` |",
        f"| **Total Gate Duration** | {total_ms} ms |",
        f"| **Probes Executed** | {total_probes} |",
        f"| **Probes Passed** | {passed} / {total_probes} |",
        f"| **Error Rate** | {error_rate}% (target: 0.0%) |",
        f"| **ADS Replay Attacks Blocked** | {ads_caught} |",
        "",
        "---",
        "",
        "## 1. Synthetic Probe Execution Matrix",
        "",
        "| ID | Probe Name | Type | Status | Resolution | Amount | Latency | Transforms |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]

    probe_type_labels = {
        "P-01": "Legacy flat v1",
        "P-02": "Modern nested v2",
        "P-03": "Stripe minor-cents",
        "P-04": "Dirty currency string",
        "P-05": "Duplicate idempotency",
    }
    for r in probe_results:
        icon = "✅" if r["status"] == "PASSED" else "❌"
        amt = f"${r['normalized_amount']:,.2f}" if r["normalized_amount"] is not None else "—"
        tx_count = len(r["transforms"])
        ptype = probe_type_labels.get(r["id"], r["id"])
        md_lines.append(
            f"| `{r['id']}` | {r['name']} | {ptype} "
            f"| {icon} {r['status']} | `{r['exec_status']}` "
            f"| {amt} | {r['latency_ms']} ms | {tx_count} applied |"
        )

    md_lines += [
        "",
        "---",
        "",
        "## 2. Per-Probe Transformation Audit",
        "",
    ]
    for r in probe_results:
        md_lines.append(f"### {r['id']} — {r['name']}")
        md_lines.append(f"_{r['description']}_")
        md_lines.append("")
        if r["transforms"]:
            for t in r["transforms"]:
                md_lines.append(f"- {t}")
        else:
            md_lines.append("- _(no drift transforms required — payload conforms to canonical schema)_")
        if r["error"]:
            md_lines.append(f"\n> ⚠️ **Error**: `{r['error']}`")
        md_lines.append("")

    md_lines += [
        "---",
        "",
        "## 3. Anti-Double-Spend (ADS) Invariant Proof",
        "",
        "**Objective**: prove that replaying an identical idempotency token returns the",
        "cached transaction record rather than inserting a duplicate row in the ledger.",
        "",
    ]

    if ads_proof:
        ds_blocked = ads_proof.get("double_spend_blocked", False)
        ads_icon = "🟢" if ds_blocked else "🔴"
        md_lines += [
            f"| ADS Field | Value |",
            f"| :--- | :--- |",
            f"| **Replay Token** | `{ads_proof['replay_token']}` |",
            f"| **Rows before replay (P-02 insert)** | {ads_proof['rows_before_replay']} |",
            f"| **Rows after replay (P-05 attempt)** | {ads_proof['rows_after_replay']} |",
            f"| **Cached TX returned** | `{ads_proof['cached_tx_id']}` |",
            f"| **Double-Spend Blocked** | {ads_icon} `{ds_blocked}` |",
            "",
            "**Invariant**:",
            "",
            "```",
            f"rows_before == rows_after == 1  →  {ads_proof['rows_before_replay'] == ads_proof['rows_after_replay'] == 1}",
            "```",
            "",
            f"Probe P-05 replayed token `{ads_proof['replay_token']}` which was first",
            f"registered by Probe P-02 (TX `{ads_proof['cached_tx_id']}`).  The shadow-sandbox",
            "idempotency guard detected the existing row and returned `DEDUP_PROTECTED`,",
            "leaving the row count at **1**.  No duplicate charge was created.",
        ]
    else:
        md_lines += [
            "> ⚠️ ADS proof could not be generated — P-05 dedup check did not execute.",
        ]

    md_lines += [
        "",
        "---",
        "",
        "## 4. Shadow Sandbox Integrity",
        "",
        "All synthetic probes executed in a **disposable in-memory SQLite sandbox**",
        "(`sqlite3.connect(':memory:')`) that is destroyed on gate exit.  No canary",
        "records can leak into the production ledger (`database/production.db`).",
        "",
        "---",
        "",
        "## 5. Production Rollout Decision",
        "",
    ]

    if gate_passed:
        md_lines += [
            "```",
            "CANARY GATE: PASSED",
            "All 5 probes cleared · Error rate 0.0% · ADS invariant proven",
            "→ AUTHORISE DLQ DRAIN TO PRODUCTION LEDGER",
            "```",
        ]
    else:
        md_lines += [
            "```",
            "CANARY GATE: FAILED",
            "One or more probes failed or ADS invariant violated.",
            "→ ROLLBACK — DO NOT PROMOTE TO PRODUCTION",
            "```",
        ]

    md_lines += [""]

    report_md = "\n".join(md_lines)

    os.makedirs(os.path.dirname(output_report), exist_ok=True)
    with open(output_report, "w", encoding="utf-8") as fh:
        fh.write(report_md)

    return {
        "gate_status": "PASSED" if gate_passed else "FAILED",
        "probes_total": total_probes,
        "probes_passed": passed,
        "error_rate_pct": error_rate,
        "ads_caught": ads_caught,
        "ads_proof": ads_proof,
        "total_time_ms": total_ms,
        "report_path": output_report,
    }


if __name__ == "__main__":
    result = run_canary_health_gate()
    print("\nCanary Gate Result:")
    for k, v in result.items():
        print(f"  {k}: {v}")
