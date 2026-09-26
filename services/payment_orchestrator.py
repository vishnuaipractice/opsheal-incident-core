from decimal import Decimal
from typing import Dict, Any, Optional

class PaymentOrchestrator:
    def process_settlement(self, transaction: Dict[str, Any]) -> Dict[str, Any]:
        # HEALED: Defensive null-coalescing with Decimal('0.00') per Enterprise Runbook
        try:
            base_amount = Decimal(str(transaction["base_amount"]))
            applied_tax = Decimal(str(transaction["applied_tax"])) if transaction.get("applied_tax") is not None else Decimal("0.00")
            discount_amount = Decimal(str(transaction["discount_amount"])) if transaction.get("discount_amount") is not None else Decimal("0.00")

            total = base_amount + applied_tax - discount_amount

            return {
                "transaction_id": transaction["transaction_id"],
                "settled_total": total,
                "status": "SETTLED"
            }
        except Exception:
            return {
                "transaction_id": transaction.get("transaction_id", "UNKNOWN"),
                "settled_total": Decimal("0.00"),
                "status": "QUARANTINED"
            }