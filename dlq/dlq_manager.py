import json
import os
from typing import List, Dict, Any
from datetime import datetime, timezone

DLQ_FILE_PATH = os.path.join(os.path.dirname(__file__), "dead_letter_queue.json")

def init_dlq():
    os.makedirs(os.path.dirname(DLQ_FILE_PATH), exist_ok=True)
    if not os.path.exists(DLQ_FILE_PATH):
        with open(DLQ_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump([], f)

def push_to_dlq(payload: Dict[str, Any], error_reason: str) -> Dict[str, Any]:
    init_dlq()
    records = get_dlq_records()
    dlq_item = {
        "event_id": payload.get("event_id", f"EVT-UNKNOWN-{len(records)+1}"),
        "transaction_id": payload.get("transaction_id", f"TX-UNKNOWN-{len(records)+1}"),
        "payload": payload,
        "error_reason": error_reason,
        "failed_at": datetime.now(timezone.utc).isoformat(),
        "status": "POISONED"
    }
    records.append(dlq_item)
    temp_path = DLQ_FILE_PATH + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)
    os.replace(temp_path, DLQ_FILE_PATH)
    return dlq_item

def get_dlq_records() -> List[Dict[str, Any]]:
    init_dlq()
    try:
        with open(DLQ_FILE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def get_dlq_count() -> int:
    return len(get_dlq_records())

def clear_dlq():
    init_dlq()
    temp_path = DLQ_FILE_PATH + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump([], f, indent=2)
    os.replace(temp_path, DLQ_FILE_PATH)
