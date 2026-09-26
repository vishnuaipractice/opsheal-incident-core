from typing import Dict, Any, List, Tuple
import hashlib
import json
import re
import time

class PaymentContractAdapter:
    """
    Universal Polymorphic Anti-Corruption Layer (ACL) — Bob-Adapter.

    Heals ingress schema drift for v1 and v2 vendor payloads without breaking
    backward compatibility.  Resolves six transformation categories:

      1. Alias Resolution       — account_ref / client_id / payer_id / user_id → customer_id
      2. Minor-Unit Handling    — amount_cents (and variants) ÷ 100.0 → standard currency units
      3. Dirty-String Coercion  — '$12,450.75' / '€3,200.00' → clean float via regex
      4. Nested Object Traversal— payment_detail.* / charge.* safely unnested
      5. Idempotency Synthesis  — deterministic SHA-256 token generated when vendor omits one
      6. Status Enum Norm.      — succeeded / completed / authorised / paid → SETTLED

    Returns
    -------
    adapt(raw_payload) -> Tuple[normalized_dict, transformations_list]
        normalized_dict      : canonical payment record ready for downstream processing
        transformations_list : ordered audit trail of every mutation applied
    """

    # Spec-required aliases first; extras kept for broader v1 compatibility.
    ID_CANDIDATES = [
        "account_ref", "client_id", "customer_id", "payer_id", "user_id",
        "client_ref", "payer_ref", "user_ref", "account_no", "member_id",
    ]
    AMOUNT_CANDIDATES = [
        "amount", "settlement_amount", "gross_amount", "total_amount", 
        "charged_amount", "payment_amount", "subtotal"
    ]
    CENTS_CANDIDATES = [
        "amount_cents", "amount_in_cents", "cents", "total_cents", 
        "settlement_amount_cents", "gross_amount_cents"
    ]
    STATUS_MAP = {
        "settled": "SETTLED",
        "completed": "SETTLED",
        "succeeded": "SETTLED",
        "success": "SETTLED",
        "paid": "SETTLED",
        "authorised": "SETTLED",
        "authorized": "SETTLED",
        "captured": "SETTLED"
    }

    # ------------------------------------------------------------------ #
    #  Idempotency synthesis helpers                                       #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _synthesize_idempotency_token(payload: Dict[str, Any]) -> str:
        """
        Derive a deterministic SHA-256 idempotency token from stable payload
        fields (customer_id / amount / currency / transaction_id / timestamp).
        This guarantees anti-double-spend protection even when the vendor
        omits an explicit token.
        """
        stable_fields = {
            k: payload.get(k)
            for k in ("customer_id", "amount", "currency", "transaction_id", "timestamp")
            if payload.get(k) is not None
        }
        if not stable_fields:
            # Last-resort: hash the entire serialised payload deterministically.
            stable_fields = {k: str(v) for k, v in sorted(payload.items())}

        canonical = json.dumps(stable_fields, sort_keys=True, default=str)
        return "syn-" + hashlib.sha256(canonical.encode()).hexdigest()

    # ------------------------------------------------------------------ #
    #  Main adaptation entry-point                                         #
    # ------------------------------------------------------------------ #

    def adapt(
        self, raw_payload: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], List[str]]:
        """
        Normalise *raw_payload* and return ``(normalized_dict, transformations)``.

        Parameters
        ----------
        raw_payload : dict
            Raw vendor payload in any supported schema version.

        Returns
        -------
        tuple[dict, list[str]]
            A 2-tuple of the canonical payment record and an ordered audit log
            of every transformation applied.
        """
        if not isinstance(raw_payload, dict):
            raw_payload = {}

        transformations: List[str] = []
        # Tracks whether any *schema-drift* transformation fired (alias/unit/nesting).
        # Security enrichments (idempotency synthesis, status normalisation) do NOT count.
        schema_adapted: bool = False
        is_v2_spec = ("payment_detail" in raw_payload or "charge" in raw_payload or "account_ref" in raw_payload)

        # 1. Resolve Customer Identifier (Semantic Alias Matching)
        customer_id = None
        for key in self.ID_CANDIDATES:
            if key in raw_payload:
                customer_id = str(raw_payload[key])
                if key != "customer_id":
                    transformations.append(f"Semantic Alias: Mapped '{key}' -> 'customer_id' ('{customer_id}')")
                    schema_adapted = True
                break

        # Check inside nested objects (e.g. payment_detail.account_ref, customer.id)
        if not customer_id:
            for k, v in raw_payload.items():
                if isinstance(v, dict):
                    for sub_k in self.ID_CANDIDATES:
                        if sub_k in v:
                            customer_id = str(v[sub_k])
                            transformations.append(f"Nested Field Extraction: '{k}.{sub_k}' -> 'customer_id' ('{customer_id}')")
                            schema_adapted = True
                            break
                    if customer_id:
                        break
        customer_id = customer_id or raw_payload.get("customer_id") or "UNKNOWN_CUSTOMER"

        # 2. Resolve Amount & Unit Scale (Dollars vs Cents vs Strings)
        amount = None
        # Check for minor units (CENTS)
        for key in self.CENTS_CANDIDATES:
            if key in raw_payload:
                try:
                    clean_cents_str = re.sub(r"[^\d.-]", "", str(raw_payload[key]))
                    raw_cents = float(clean_cents_str)
                    amount = round(raw_cents / 100.0, 2)
                    transformations.append(f"Unit Scale Coercion: Converted {int(raw_cents)} cents in '{key}' -> ${amount:,.2f} USD")
                    schema_adapted = True
                    break
                except (ValueError, TypeError):
                    pass

        # Check inside nested objects for cents
        if amount is None:
            for k, v in raw_payload.items():
                if isinstance(v, dict):
                    for sub_k in self.CENTS_CANDIDATES:
                        if sub_k in v:
                            try:
                                clean_cents_str = re.sub(r"[^\d.-]", "", str(v[sub_k]))
                                raw_cents = float(clean_cents_str)
                                amount = round(raw_cents / 100.0, 2)
                                transformations.append(f"Nested Unit Scale Coercion: '{k}.{sub_k}' ({int(raw_cents)} cents) -> ${amount:,.2f} USD")
                                schema_adapted = True
                                break
                            except (ValueError, TypeError):
                                pass
                    if amount is not None:
                        break

        # Check for standard amount candidates (root level)
        if amount is None:
            for key in self.AMOUNT_CANDIDATES:
                if key in raw_payload:
                    try:
                        raw_val_str = str(raw_payload[key]).strip()
                        clean_str = re.sub(r"[^\d.-]", "", raw_val_str)
                        amount = float(clean_str)
                        if re.search(r"[^\d.-]", raw_val_str):
                            transformations.append(f"Currency String Coercion: Normalized '{raw_val_str}' -> ${amount:,.2f} USD")
                            schema_adapted = True
                        if key != "amount":
                            transformations.append(f"Semantic Alias: Mapped '{key}' -> 'amount' (${amount:,.2f})")
                            schema_adapted = True
                        break
                    except (ValueError, TypeError):
                        pass

        # Check inside nested objects (e.g. payment_detail.settlement_amount)
        if amount is None:
            for k, v in raw_payload.items():
                if isinstance(v, dict):
                    for sub_k in self.AMOUNT_CANDIDATES:
                        if sub_k in v:
                            try:
                                raw_val_str = str(v[sub_k]).strip()
                                clean_str = re.sub(r"[^\d.-]", "", raw_val_str)
                                amount = float(clean_str)
                                if re.search(r"[^\d.-]", raw_val_str):
                                    transformations.append(f"Currency String Coercion: Normalized '{raw_val_str}' -> ${amount:,.2f} USD")
                                    schema_adapted = True
                                transformations.append(f"Structural Unnesting: '{k}.{sub_k}' -> 'amount' (${amount:,.2f})")
                                schema_adapted = True
                                break
                            except (ValueError, TypeError):
                                pass
                    if amount is not None:
                        break

        amount = amount if amount is not None else 0.0

        # 3. Resolve Processing Fee (New Attribute)
        fee_amount = 0.0
        for k, v in raw_payload.items():
            if "fee" in k.lower() and not isinstance(v, dict):
                try:
                    clean_fee = re.sub(r"[^\d.-]", "", str(v))
                    fee_amount = float(clean_fee)
                except (ValueError, TypeError):
                    pass
            elif isinstance(v, dict):
                for sub_k, sub_v in v.items():
                    if "fee" in sub_k.lower():
                        try:
                            clean_fee = re.sub(r"[^\d.-]", "", str(sub_v))
                            fee_amount = float(clean_fee)
                        except (ValueError, TypeError):
                            pass

        # 4. Resolve Currency
        currency = raw_payload.get("currency") or raw_payload.get("iso_currency")
        if not currency:
            for k, v in raw_payload.items():
                if isinstance(v, dict):
                    currency = v.get("currency") or v.get("iso_currency")
                    if currency:
                        break
        currency = str(currency or "USD").upper()

        # 5. Resolve Idempotency Token  (Req-5: synthesise if vendor omitted it)
        idempotency_token = (
            raw_payload.get("idempotency_token")
            or raw_payload.get("idempotency_key")
            or raw_payload.get("replay_token")
        )
        if not idempotency_token:
            for k, v in raw_payload.items():
                if isinstance(v, dict):
                    idempotency_token = (
                        v.get("idempotency_token")
                        or v.get("idempotency_key")
                        or v.get("replay_token")
                    )
                    if idempotency_token:
                        break

        if not idempotency_token:
            # Synthesise a deterministic SHA-256 token for anti-double-spend.
            _seed = {
                "customer_id": customer_id,
                "amount": amount,
                "currency": currency,
                "transaction_id": raw_payload.get("transaction_id")
                    or raw_payload.get("event_id")
                    or raw_payload.get("id"),
                "timestamp": raw_payload.get("timestamp") or raw_payload.get("created_at"),
            }
            idempotency_token = self._synthesize_idempotency_token(_seed)
            transformations.append(
                f"Idempotency Synthesis: No vendor token found — "
                f"generated deterministic SHA-256 token '{idempotency_token[:20]}…'"
            )

        # 6. Status Enum Normalization
        raw_status = str(
            raw_payload.get("status")
            or raw_payload.get("payment_status")
            or raw_payload.get("state")
            or "settled"
        ).lower()
        normalized_status = self.STATUS_MAP.get(raw_status, "SETTLED")
        # Only log a transformation when the raw value was not already canonical.
        if raw_status != "settled":
            transformations.append(
                f"Enum Normalization: Mapped status '{raw_status}' -> '{normalized_status}'"
            )

        # 7. Resolve Transaction ID
        tx_id = (
            raw_payload.get("transaction_id")
            or raw_payload.get("event_id")
            or raw_payload.get("id")
        )
        if not tx_id:
            tx_id = f"TX-FALLBACK-{int(time.time() * 1000) % 100_000}"

        detected_ver = "v2" if is_v2_spec else ("v1_adapted" if schema_adapted else "v1")

        normalized: Dict[str, Any] = {
            "transaction_id": str(tx_id),
            "customer_id": str(customer_id),
            "amount": float(amount),
            "fee_amount": float(fee_amount),
            "currency": str(currency),
            "status": normalized_status,
            "idempotency_token": str(idempotency_token),
            "detected_version": detected_ver,
        }

        return normalized, transformations
