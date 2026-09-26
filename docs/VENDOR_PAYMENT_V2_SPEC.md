# GlobalPay Developer Documentation: Webhook API v2.0 Specification

- **Document Reference**: `RFC-GP-2026-V2`
- **Published By**: GlobalPay Merchant Services Engineering
- **Version**: 2.0.0-GA
- **Target Audience**: External Merchant Integrators & Payment Engineering Teams

---

## 1. Executive Summary
Effective September 2026, GlobalPay has upgraded its payment settlement webhook infrastructure to Webhook API v2.0. This release introduces enriched settlement accounting, multi-currency ISO-4217 standardizations, and mandatory idempotency tracking for real-time transaction reconciliation.

---

## 2. Webhook Event Specification: `payment.settled`

### Endpoint Ingress:
When a customer checkout or enterprise wire transfer settles, GlobalPay dispatches an HTTP POST request to the merchant's registered webhook URL.

```http
POST /v1/webhooks/payment HTTP/1.1
Host: merchant-api.example.com
Content-Type: application/json
User-Agent: GlobalPay-Webhook-Agent/2.0
X-GlobalPay-Signature: t=1727254800,v1=9f83ac7491d90c
```

### JSON Schema & Field Definitions:
- `event_id` (string, required): Unique identifier for the webhook delivery event. Format: `EVT-[0-9]+`.
- `transaction_id` (string, required): GlobalPay global transaction tracking reference. Format: `TX-[0-9]+`.
- `account_ref` (string, required): Merchant customer or enterprise account identifier. Format: `CUST-[A-Z0-9-]+`. Note: In v2.0, this replaces merchant-specific consumer identifiers with unified account references.
- `payment_detail` (object, required): Enriched monetary breakdown object containing:
  - `settlement_amount` (number, required): The net settled volume in standard decimal units.
  - `fee_amount` (number, required): The GlobalPay processing surcharge deducted at gateway.
  - `iso_currency` (string, required): Three-letter ISO-4217 currency code (e.g. `USD`, `EUR`, `GBP`).
- `idempotency_token` (string, required): Unique cryptographic token generated per settlement. Merchants MUST record this token to guarantee at-most-once processing and protect against network replay duplicates.

### Sample Webhook Payload (v2.0 Active Production):
```json
{
  "event_id": "EVT-2001",
  "transaction_id": "TX-2001",
  "account_ref": "CUST-901",
  "payment_detail": {
    "settlement_amount": 250.00,
    "fee_amount": 3.75,
    "iso_currency": "USD"
  },
  "idempotency_token": "IDEMP-88492-AX"
}
```

---

## 3. Deprecation Notice
Earlier iterations of GlobalPay merchant webhooks (v1.x flat schemas using `customer_id` and unnested `amount`) are officially deprecated. Merchants must ensure their ingestion services support the v2.0 schema to prevent service interruption.
