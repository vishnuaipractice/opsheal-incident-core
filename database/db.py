import sqlite3
import os
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), "production.db")

def get_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=20.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=20000;")
    return conn

def init_db(migrated: bool = False):
    with get_connection() as conn:
        cursor = conn.cursor()
        if migrated:
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_id TEXT UNIQUE NOT NULL,
                customer_id TEXT NOT NULL,
                amount REAL NOT NULL,
                currency TEXT NOT NULL DEFAULT 'USD',
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                fee_amount REAL DEFAULT 0.0,
                idempotency_token TEXT
            );
            """)
        else:
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_id TEXT UNIQUE NOT NULL,
                customer_id TEXT NOT NULL,
                amount REAL NOT NULL,
                currency TEXT NOT NULL DEFAULT 'USD',
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """)
        conn.commit()

def insert_transaction(tx: Dict[str, Any]) -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(transactions);")
        columns = [row["name"] for row in cursor.fetchall()]

        has_idempotency = "idempotency_token" in columns
        has_fee = "fee_amount" in columns
        created_at = tx.get("created_at") or datetime.now(timezone.utc).isoformat()

        if has_idempotency and has_fee:
            cursor.execute("""
            INSERT OR REPLACE INTO transactions (
                transaction_id, customer_id, amount, currency, status, created_at, fee_amount, idempotency_token
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                tx["transaction_id"],
                tx["customer_id"],
                float(tx["amount"]),
                tx.get("currency", "USD"),
                tx.get("status", "SETTLED"),
                created_at,
                float(tx.get("fee_amount", 0.0)),
                tx.get("idempotency_token")
            ))
        else:
            cursor.execute("""
            INSERT OR REPLACE INTO transactions (
                transaction_id, customer_id, amount, currency, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                tx["transaction_id"],
                tx["customer_id"],
                float(tx["amount"]),
                tx.get("currency", "USD"),
                tx.get("status", "SETTLED"),
                created_at
            ))
        conn.commit()
        return cursor.lastrowid

def get_all_transactions() -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM transactions ORDER BY id DESC")
        rows = [dict(row) for row in cursor.fetchall()]
        return rows

def get_transaction_by_id(tx_id: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM transactions WHERE transaction_id = ?", (tx_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def get_transaction_by_idempotency_token(token: str) -> Optional[Dict[str, Any]]:
    if not token:
        return None
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(transactions);")
        columns = [row["name"] for row in cursor.fetchall()]
        if "idempotency_token" not in columns:
            return None
        cursor.execute("SELECT * FROM transactions WHERE idempotency_token = ?", (token,))
        row = cursor.fetchone()
        return dict(row) if row else None

def get_stats() -> Dict[str, Any]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as total_count, COALESCE(SUM(amount), 0.0) as total_volume FROM transactions WHERE status = 'SETTLED'")
        row = cursor.fetchone()
        return {
            "settled_count": row["total_count"],
            "settled_volume": round(float(row["total_volume"]), 2)
        }

def reset_db(migrated: bool = False):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS transactions;")
        conn.commit()
    init_db(migrated=migrated)

# Auto-initialize on import
init_db(migrated=True)
