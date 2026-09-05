# Tawzeevo API

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".\apps\api[dev]"
docker compose up -d postgres postgres-test
$env:DATABASE_URL = "postgresql+psycopg://tawzeevo:change-me@localhost:5432/tawzeevo"
.\.venv\Scripts\alembic -c .\apps\api\alembic.ini upgrade head
.\.venv\Scripts\uvicorn tawzeevo_api.main:app --app-dir .\apps\api --reload
```

The API exposes `/health`, `/health/database`, `/docs`, and `/openapi.json`.

Quality checks use the whole `apps/api` directory, as documented in the root README. Historical
migrations `0009` and `0010` are not reformatted: only `0009` has an `I001` per-file exception, and
both exact paths have formatter exclusions. Every other selected lint rule remains active.
`tests/test_immutable_migration_files.py` locks their content against later edits. New migrations
receive no exemption. This honors the existing applied-migration immutability rule.

Phase 1 authentication routes include:

- `POST /register`
- `POST /login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`

Access tokens use the Swagger bearer authorization control. Refresh tokens are opaque, hashed in PostgreSQL, rotated on every refresh, and sent only through the scoped HttpOnly cookie.

Tenant business APIs are exposed under `/api/v1/tenants/{tenant_id}`, `/api/v1/invoices`,
`/api/v1/customer-ledger`, and `/api/v1/payments`. An active owner membership is required for
customer, category, tenant-product/barcode, grade-pricing, product-image, invoice, ledger, payment,
refund, and debt routes. The tenant ID selects the requested context but never grants access: the
API validates membership and tenant lifecycle state before every business operation.

The initial slice includes:

- `POST /customers`, `GET /customers/{customer_id}`, and `GET /customers/search?phone=...`
- `POST /categories`, `GET /categories`, and `GET /categories/{category_id}`
- `POST /products`, `GET /products/{product_id}`, and `GET /products/barcode/{barcode}`
- `POST /api/v1/invoices`, `POST /api/v1/invoices/{invoice_id}/confirm`, and `GET /api/v1/invoices/{invoice_id}/history`
- `POST /api/v1/invoices/{invoice_id}/cancel` for draft or confirmed cancellation accounting
- `POST /api/v1/customer-ledger/opening-balances`, per-customer balance reads, overdue settings, and the debt register
- customer obligation reads plus immutable receipt, receipt-reversal, and credit-refund endpoints under `/api/v1/payments`

Product and invoice money uses four-decimal values and an explicit ISO currency code. Draft invoices reject mixed-currency products.

Migrations through `20260827_0011` provide the immutable financial source of truth, deterministic
revision item ordering, owner-configured overdue thresholds, and the ledger rule needed to retain
zero-value post-confirm adjustment and cancellation effects. Confirmation allocates `YYYY-000001` numbers under a
tenant/year row lock and posts one customer-ledger charge. Later confirmed edits append a complete
revision and exact adjustment without rewriting history. Receipts post one negative ledger effect and
allocate FIFO by default or by owner selection; allocation/payment corrections append reversals.
Confirmed cancellation appends the invoice reversal, releases allocations into customer credit, and
preserves payments. Refunds lock and recheck credit so concurrent requests cannot overspend it.
Public-sharing and supplier-ledger foundation APIs are implemented in P3-M5 as described below.

## Invoice sharing and supplier-ledger foundation (P3-M5)

Owner endpoints require the existing bearer authentication and `?tenant_id=<tenant UUID>`;
platform administrator status alone does not grant tenant ownership. Paths below start with `/api/v1`.

| Method | Path | Purpose |
|---|---|---|
| GET / POST | `/invoices/{invoice_id}/capabilities` | List metadata / create a 90-day link (secret returned once) |
| POST | `/invoices/{invoice_id}/capabilities/{capability_id}/rotate` | Atomically revoke the old link and issue a replacement |
| DELETE | `/invoices/{invoice_id}/capabilities/{capability_id}` | Revoke a link |
| GET | `/public/invoice` | Public bilingual invoice-page shell |
| GET | `/public/invoice/data` | Restricted current invoice; supply `X-Invoice-Capability` header, not login or an internal ID |
| GET | `/supplier-ledger/{supplier_id}/balances` | Aggregate supplier payable, separately per currency |
| POST | `/supplier-ledger/opening-balances` | Idempotent signed opening event |
| POST | `/payments/supplier-payments` | Idempotent supplier payment and negative payable effect |
| POST | `/payments/supplier-payments/{payment_id}/reverse` | Reasoned, compensating payment/ledger reversal |

Request schemas are available in `/docs`. Supplier commands accept decimal strings and timezone-aware
timestamps; supplier payment replay returns UTC timestamps consistently. Payments do not allocate
to purchases. Procurement and its UI remain Phase 6 work.

The shared URL stores the capability in its fragment; browsers do not send fragments in HTTP URLs.
The page removes the fragment and fetches data using the secret header. Only a SHA-256 hash is stored.
Do not add request-header/body capture or response capture to proxies, telemetry, or application logs:
`X-Invoice-Capability` and newly issued link responses are secrets. Existing access-log filters redact
recognizable capability values as defense in depth. Public responses, including errors, carry
`no-store`, `noindex, nofollow`, and `no-referrer`; the HTML has a restrictive hashed-script CSP.

Public requests have a bounded in-process limit of 60 requests per client IP per 60 seconds (shell and
data requests both count), with a maximum of 4,096 tracked clients and fail-closed capacity handling.
This is not a distributed limiter. Multiple workers multiply the effective limit; clients behind a
shared proxy/NAT can share a quota. Validate trusted proxy configuration and any global edge limit
before scaling; do not trust arbitrary forwarded headers. No new provider or environment variable
is introduced by this milestone. See `docs/phase-3/p3-m5.md` and the root `RUN_TESTS.md`.

## Import the starter master catalog

The committed starter snapshot contains a small Open Food Facts Lebanon-market selection under
ODbL 1.0. It stores no Open Food Facts images and does not create a runtime dependency on that
service. Apply migrations, validate the quality gate, and import from the repository root:

```powershell
.\.venv\Scripts\python.exe -m tawzeevo_api.cli.import_master_catalog --check-only --report data/master-catalog/open-food-facts-lebanon-v1.quality.json
.\.venv\Scripts\python.exe -m tawzeevo_api.cli.import_master_catalog
```

The import persists its source, license, retrieval timestamp, version, dataset checksum, quality
report, and per-product source revision. Exact replay is a no-op; changed content under an existing
version or a conflicting barcode identity is rejected transactionally.

## Seed synthetic demo data

The demo seeder never creates users, tenants, or memberships and never bypasses onboarding. Register a client, have a platform administrator approve its tenant application, then pass that existing active owner and tenant to the command. Currency and customer phone are explicit inputs; no credentials or production data are embedded.

```powershell
$env:DATABASE_URL = "postgresql+psycopg://tawzeevo:change-me@localhost:5432/tawzeevo"
.\.venv\Scripts\python -m tawzeevo_api.cli.seed_demo --owner-email owner@example.com --tenant-id 00000000-0000-0000-0000-000000000000 --customer-phone "+961 70 555 444" --currency USD
```

The command creates one synthetic customer, category, piece-priced barcode product, and database-backed draft invoice in one transaction. It refuses replay for the same tenant instead of silently duplicating the demo slice.

## Create the first platform administrator

There is no public administrator-registration route and no default administrator password. After applying migrations, run the local command below against the intended database. The password is entered twice through a hidden prompt and is never accepted as a command-line argument.

```powershell
$env:DATABASE_URL = "postgresql+psycopg://tawzeevo:change-me@localhost:5432/tawzeevo"
.\.venv\Scripts\python -m tawzeevo_api.cli.create_admin --first-name Platform --last-name Owner --email owner@example.com --phone "+96170123456" --city Beirut --age 30
```
