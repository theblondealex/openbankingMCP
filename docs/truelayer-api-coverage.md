# TrueLayer API endpoint coverage

Last audited: 25 July 2026.

This inventory was generated from TrueLayer's official `llms.txt` index and
every linked API-reference Markdown page. The audit fetched 92 reference pages
and extracted 89 unique HTTP operations with no fetch failures.

The decision rule is deliberately narrow:

- **Use** means the endpoint is required for local read-only account data or
  for securely creating, refreshing, inspecting, or deleting that access.
- **Defer** means it is read-only or connection-related, but does not improve
  the current MCP contract enough to justify more scopes, PII, or complexity.
- **Prohibit** means it belongs to payments, payouts, mandates, merchant money
  movement, verification, Signup+, or a legacy payment product.

`openbankingmcp.truelayer.endpoint_allowed` enforces the **Use** set before any
HTTP request is sent. A policy test proves that payment and payout URLs are
rejected.

## Authentication and Data APIs

| Method and endpoint | Decision | Reason |
|---|---|---|
| `POST auth:/connect/token` | **Use** | Exchange, refresh, and Data v3 client-credentials tokens. |
| `DELETE auth:/api/delete` | **Use** | Revoke the TrueLayer credential when the user removes a connection. |
| `POST auth:/api/debug`; `DELETE auth:/api/debug` | Defer | Support diagnostic IDs are unnecessary during normal local operation. |
| `GET auth:/api/providers` | Defer | TrueLayer-hosted provider selection already filters available banks. |
| `POST auth:/v1/authuri` | Defer | Requires an approved custom consent screen; hosted OAuth is safer. |
| `POST auth:/v1/reauthuri` | Defer | UK-only shortcut; the existing full reconnect flow works across providers. |
| `GET data-v1:/me` | **Use** | Validate scopes and read provider/consent metadata without requesting PII. |
| `GET data-v1:/info` | Defer | Requires the `info` scope and returns user identity data the MCP does not need. |
| `GET data-v1:/accounts` | **Use** | Discover all current and savings accounts. |
| `GET data-v1:/accounts/{account_id}` | Defer | Redundant after the accounts collection response. |
| `GET data-v1:/accounts/{account_id}/balance` | **Use** | Current account balance. |
| `GET data-v1:/accounts/{account_id}/transactions` | **Use** | Settled account transactions. |
| `GET data-v1:/accounts/{account_id}/transactions/pending` | **Use** | Pending account transactions; audited after the July 2026 omission. |
| `GET data-v1:/accounts/{account_id}/direct_debits` | Defer | Needs an extra scope and describes instructions rather than actual spend. |
| `GET data-v1:/accounts/{account_id}/standing_orders` | Defer | Needs an extra scope and describes instructions rather than actual spend. |
| `GET data-v1:/cards` | **Use** | Discover credit-card accounts. |
| `GET data-v1:/cards/{account_id}` | Defer | Redundant after the cards collection response. |
| `GET data-v1:/cards/{account_id}/balance` | **Use** | Credit-card balance and available credit. |
| `GET data-v1:/cards/{account_id}/transactions` | **Use** | Settled card transactions. |
| `GET data-v1:/cards/{account_id}/transactions/pending` | **Use** | Pending card transactions. |
| `POST data-v1:/connections/extend` | Defer | Requires an additional consent-extension UX; reconnect already fails closed. |
| `POST /v3/data-connections` | **Use** | Supported Data v3 connection creation path. |
| `GET /v3/connected-accounts` | **Use** | Supported Data v3 connected-account discovery path. |
| `GET /v3/data-connections/{connection_id}/user-info` | Defer | End-user identity is deliberately excluded from storage and MCP output. |

## Diagnostics, Signup+, and verification

| Product | Endpoints reviewed | Decision |
|---|---|---|
| Client Tracking | `GET /v1/tracked-events` | Defer. Useful only for manual authorization-flow support diagnostics. |
| Signup+ | `GET /signup-plus/accounts`; `GET /signup-plus/mandates`; `GET /signup-plus/payments`; `POST /signup-plus/authuri` | Prohibit. These retrieve onboarding identity data or depend on payment/mandate flows. |
| Verification | `POST /verification/v1/verify`; `POST /v3/account-holder-verifications/requests`; `GET /v3/account-holder-verifications/requests/{id}`; `POST /v3/verification/fr/verify-account-details`; `POST /v3/bank-lookup` | Prohibit. Verification is a separate identity/account-checking product and is not needed for financial reporting. |

## Payments API v3, mandates, and merchant accounts

Every operation below is prohibited. Read-only `GET` operations are also
excluded because they describe merchant payment products, not the user's
connected AIS accounts, and enabling their scopes would weaken the simple
read-only-data security boundary.

### Payments and refunds

- `POST /v3/payments`
- `GET /v3/payments/{id}`
- `POST /v3/payments/{id}/actions/cancel`
- `POST /v3/payments/{id}/actions/save-user-account`
- `POST /v3/payments/{id}/authorization-flow`
- `POST /v3/payments/{id}/authorization-flow/actions/branch-selection`
- `POST /v3/payments/{id}/authorization-flow/actions/consent`
- `POST /v3/payments/{id}/authorization-flow/actions/form`
- `POST /v3/payments/{id}/authorization-flow/actions/provider-selection`
- `POST /v3/payments/{id}/authorization-flow/actions/scheme-selection`
- `POST /v3/payments/{id}/authorization-flow/actions/user-account-selection`
- `GET /v3/payments/{id}/refunds`
- `POST /v3/payments/{id}/refunds`
- `GET /v3/payments/{payment_id}/refunds/{refund_id}`
- `POST /v3/payments-provider-return`
- `POST /v3/payments-providers/search`
- `GET /v3/payments-providers/{id}`

### Payment links and payouts

- `POST /v3/payment-links`
- `GET /v3/payment-links/{id}`
- `GET /v3/payment-links/{id}/payments`
- `POST /v3/payouts`
- `GET /v3/payouts/{id}`
- `POST /v3/payouts/{id}/authorization-flow`
- `GET /v3/payouts/{id}/authorization-flow`

### Merchant accounts and sweeping

- `GET /v3/merchant-accounts`
- `GET /v3/merchant-accounts/{id}`
- `GET /v3/merchant-accounts/{id}/transactions`
- `GET /v3/merchant-accounts/{id}/payment-sources`
- `GET /v3/merchant-accounts/{id}/sweeping`
- `POST /v3/merchant-accounts/{id}/sweeping`
- `DELETE /v3/merchant-accounts/{id}/sweeping`

### Mandates

- `GET /v3/mandates`
- `POST /v3/mandates`
- `GET /v3/mandates/{id}`
- `POST /v3/mandates/{id}/authorization-flow`
- `POST /v3/mandates/{id}/authorization-flow/actions/consent`
- `POST /v3/mandates/{id}/authorization-flow/actions/provider-selection`
- `GET /v3/mandates/{id}/constraints`
- `GET /v3/mandates/{id}/funds`
- `POST /v3/mandates/{id}/revoke`

## Legacy payment APIs

All legacy endpoints are prohibited. They initiate or inspect payments,
deposits, withdrawals, or merchant-account data and have no role in an AIS
personal-finance cache.

### Legacy Payments API v2

- `GET /v2/single-immediate-payments-providers`
- `POST /v2/single-immediate-payment-initiation-requests`
- `GET /v2/single-immediate-payments/{sip_id}`
- `POST /v2/single-immediate-payments/{sip_id}/embedded-auth-steps/{step_id}/submission`

### Legacy PayDirect

- `GET /v1/balances`
- `GET /v1/transactions`
- `GET /v1/users/{id}`
- `GET /v1/users/{id}/accounts`
- `POST /v1/users/deposits`
- `GET /v1/users/{user_id}/deposits/{deposit_id}`
- `POST /v1/users/withdrawals`
- `GET /v1/users/{user_id}/accounts/{account_id}/withdrawals/{transaction_id}`
- `POST /v1/withdrawals`
- `GET /v1/withdrawals/{transaction_id}`

## Webhooks and asynchronous variants

TrueLayer also documents payment, refund, payout, mandate, merchant-account,
payment-link, Signup+, verification, and provider-availability webhooks. They
are not outbound HTTP operations in the extracted OpenAPI path inventory.

- Payment-capable product webhooks are prohibited with their parent products.
- Data asynchronous calls and provider-availability webhooks are deferred.
  They require a reachable webhook receiver, which conflicts with the
  loopback-only design. Synchronous refresh with safe retry handling remains
  the correct local architecture.

## Maintenance procedure

For each TrueLayer release:

1. Read `https://docs.truelayer.com/llms.txt`.
2. Compare all `/reference/*.md` OpenAPI paths with this inventory.
3. Classify every new operation before changing the network allowlist.
4. Add contract tests for every newly allowed response and failure mode.
5. Keep payment, payout, mandate, refund, sweeping, and verification paths
   outside `endpoint_allowed`.
