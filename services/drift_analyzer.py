import os
import re
from typing import Dict, Any, List

class AutonomousDriftAnalyzer:
    """
    Autonomous Schema Drift Analyzer
    Inspects poisoned payloads from the Dead-Letter Queue (DLQ),
    compares them against the internal target transactional model,
    and cross-references vendor documentation to dynamically deduce the contract mapping.
    """
    
    TARGET_MODEL = {
        "transaction_id": str,
        "customer_id": str,
        "amount": float,
        "currency": str,
        "status": str
    }

    def analyze(self, sample_payload: Dict[str, Any], doc_path: str = None) -> Dict[str, Any]:
        """
        Dynamically analyzes an incoming payload against the target model.
        Returns a structured drift report with detected renames, nestings, and schema additions.
        """
        if not sample_payload:
            return {"status": "NO_PAYLOAD", "drift_detected": False}

        root_keys = list(sample_payload.keys())
        expected_keys = list(self.TARGET_MODEL.keys())

        missing_keys = [k for k in expected_keys if k not in root_keys and k not in ["status"]]
        extra_keys = [k for k in root_keys if k not in expected_keys and k not in ["event_id", "timestamp"]]

        renames = []
        nestings = []
        schema_extensions = []

        # 1. Detect customer_id rename (e.g. account_ref, customer_ref, user_id)
        if "customer_id" in missing_keys:
            candidate_id_keys = [k for k in root_keys if any(term in k.lower() for term in ["account", "cust", "user", "client", "ref"])]
            for cand in candidate_id_keys:
                val = str(sample_payload.get(cand, ""))
                renames.append({
                    "original_field": "customer_id",
                    "incoming_field": cand,
                    "sample_value": val,
                    "confidence_score": 0.98 if "ref" in cand or "CUST" in val else 0.85,
                    "rationale": f"Field '{cand}' matches customer identifier naming pattern and value format ('{val}')"
                })

        # 2. Detect nested amount / payment_detail structures
        for k, v in sample_payload.items():
            if isinstance(v, dict):
                for nk, nv in v.items():
                    if any(term in nk.lower() for term in ["amount", "total", "settle", "price", "val"]):
                        nestings.append({
                            "original_field": "amount",
                            "incoming_path": f"{k}.{nk}",
                            "sample_value": nv,
                            "type": type(nv).__name__,
                            "rationale": f"Numerical amount found nested under '{k}.{nk}'"
                        })
                    elif any(term in nk.lower() for term in ["fee", "charge", "tax", "commission"]):
                        schema_extensions.append({
                            "field_name": "fee_amount",
                            "incoming_path": f"{k}.{nk}",
                            "data_type": "REAL",
                            "sample_value": nv,
                            "action": "ADD_COLUMN_SQLITE_WAL",
                            "rationale": "Detected surcharge/fee attribute required for partner audit ledger"
                        })

        # 3. Detect idempotency and security tokens
        if "idempotency_token" in root_keys or "idempotency_key" in root_keys:
            token_key = "idempotency_token" if "idempotency_token" in root_keys else "idempotency_key"
            schema_extensions.append({
                "field_name": "idempotency_token",
                "incoming_path": token_key,
                "data_type": "TEXT",
                "sample_value": sample_payload.get(token_key),
                "action": "ADD_COLUMN_SQLITE_WAL",
                "rationale": "Anti-double-spend token detected; requires unique index and deduplication gate"
            })

        # 4. Cross-reference vendor RFC specification if available
        doc_corroboration = []
        if doc_path and os.path.exists(doc_path):
            with open(doc_path, "r", encoding="utf-8") as f:
                doc_text = f.read()

            for r in renames:
                if r["incoming_field"] in doc_text:
                    doc_corroboration.append(f"Confirmed rename '{r['incoming_field']}' documented in {os.path.basename(doc_path)}")
            for n in nestings:
                path_leaf = n["incoming_path"].split(".")[-1]
                if path_leaf in doc_text:
                    doc_corroboration.append(f"Confirmed nested structure '{n['incoming_path']}' specified in {os.path.basename(doc_path)}")

        return {
            "status": "DRIFT_ANALYZED",
            "drift_detected": bool(renames or nestings or schema_extensions),
            "renames": renames,
            "nestings": nestings,
            "schema_extensions": schema_extensions,
            "doc_corroboration": doc_corroboration,
            "recommendation": {
                "db_migration_required": len(schema_extensions) > 0,
                "polymorphic_adapter_required": True,
                "dlq_replay_strategy": "IDEMPOTENT_RETRY"
            }
        }
