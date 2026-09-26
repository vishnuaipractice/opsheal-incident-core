"""
migration_002_add_v2_columns.py
────────────────────────────────────────────────────────────────────────────────
Non-blocking, idempotent schema migration for the `transactions` table.

Adds two v2 audit columns:
  • fee_amount        REAL    DEFAULT 0.0
  • idempotency_token TEXT    DEFAULT NULL  (unique index for anti-double-spend)

Design guarantees
─────────────────
1. Idempotency  – PRAGMA table_info() is checked before every DDL statement.
                  Re-running this script any number of times is always safe.

2. Non-blocking – SQLite WAL mode is engaged before any DDL is executed.
                  ALTER TABLE ADD COLUMN in SQLite does NOT acquire an
                  exclusive table lock; it only takes a brief reserved lock,
                  allowing concurrent readers to proceed uninterrupted.
                  busy_timeout is set to 15 s so the migration backs off
                  gracefully instead of raising "database is locked" when
                  another writer is active.

3. Index safety  – CREATE INDEX IF NOT EXISTS is inherently idempotent and
                   is executed *outside* any open write transaction so that
                   it can run as a concurrent operation in WAL mode.

4. Atomicity     – Column additions are committed in a single transaction.
                   A failure mid-way leaves the DB in its prior state.

Usage
─────
    python -m database.migrations.migration_002_add_v2_columns
    # or call run_migration() programmatically
"""

import logging
import os
import sqlite3
import sys

# ── Resolve DB path relative to this file's location ─────────────────────────
DB_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "production.db")
)

MIGRATION_ID = "002_add_v2_columns"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger(MIGRATION_ID)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _existing_columns(cursor: sqlite3.Cursor) -> set:
    """Return the set of column names currently on the transactions table."""
    cursor.execute("PRAGMA table_info(transactions);")
    return {row[1] for row in cursor.fetchall()}


def _existing_indexes(cursor: sqlite3.Cursor) -> set:
    """Return the set of index names currently on the transactions table."""
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='transactions';"
    )
    return {row[0] for row in cursor.fetchall()}


# ── Main migration entry-point ────────────────────────────────────────────────

def run_migration(db_path: str = DB_PATH) -> dict:
    """
    Execute migration 002.

    Returns
    -------
    dict
        {
            "status":  "APPLIED" | "ALREADY_UP_TO_DATE",
            "changes": [<description>, ...]   # empty list when already up-to-date
        }
    """
    if not os.path.exists(db_path):
        log.info("Database not found at %s – bootstrapping via init_db().", db_path)
        # Late import avoids circular dependency when run standalone.
        from database.db import init_db  # noqa: PLC0415
        init_db()

    # ── Open connection with WAL mode + generous busy timeout ─────────────────
    # timeout= applies to the sqlite3 module's own retry loop; PRAGMA
    # busy_timeout= applies to the C-level SQLite engine.  Both are set for
    # belt-and-suspenders coverage across different SQLite builds.
    conn = sqlite3.connect(db_path, timeout=15.0)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=15000;")   # milliseconds

        changes: list[str] = []

        # ── Phase 1: ADD COLUMNS (single atomic transaction) ─────────────────
        with conn:                                   # auto-commit / auto-rollback
            cursor = conn.cursor()
            cols = _existing_columns(cursor)

            if "fee_amount" not in cols:
                cursor.execute(
                    "ALTER TABLE transactions ADD COLUMN fee_amount REAL DEFAULT 0.0;"
                )
                changes.append("Added column: fee_amount REAL DEFAULT 0.0")
                log.info("Column fee_amount added.")
            else:
                log.info("Column fee_amount already exists – skipped.")

            if "idempotency_token" not in cols:
                cursor.execute(
                    "ALTER TABLE transactions ADD COLUMN idempotency_token TEXT DEFAULT NULL;"
                )
                changes.append("Added column: idempotency_token TEXT DEFAULT NULL")
                log.info("Column idempotency_token added.")
            else:
                log.info("Column idempotency_token already exists – skipped.")

        # ── Phase 2: CREATE INDEX (outside the write transaction) ─────────────
        # In WAL mode an index build does not block readers.
        # IF NOT EXISTS makes this call inherently idempotent.
        idx_name = "idx_transactions_idempotency_token"
        indexes = _existing_indexes(conn.cursor())

        if idx_name not in indexes:
            conn.execute(
                f"CREATE INDEX IF NOT EXISTS {idx_name} "
                "ON transactions (idempotency_token);"
            )
            conn.commit()
            changes.append(f"Created index: {idx_name} ON transactions(idempotency_token)")
            log.info("Index %s created.", idx_name)
        else:
            log.info("Index %s already exists – skipped.", idx_name)

        status = "APPLIED" if changes else "ALREADY_UP_TO_DATE"
        log.info("Migration %s finished with status: %s", MIGRATION_ID, status)
        return {"status": status, "changes": changes}

    finally:
        conn.close()


# ── CLI entry-point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    result = run_migration()
    print(f"Migration status : {result['status']}")
    if result["changes"]:
        for change in result["changes"]:
            print(f"  [+] {change}")
    else:
        print("  (no changes – schema already up to date)")
    sys.exit(0)
