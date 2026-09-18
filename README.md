# Tawzeevo

Tawzeevo is a multi-tenant operations platform for Cash Van distribution businesses, with a linked
bilingual (English/Arabic) customer storefront. Each business runs its own isolated workspace:
customers, catalog, pricing, invoicing, payments, debt follow-up and supplier costs, with the
platform team handling onboarding and access. The operational client is a web/PWA application;
the storefront lets customers order as guests without an account.

## Status

| Phase | Scope | Status |
|---|---|---|
| 1 | Accounts, sessions, platform administration, tenant onboarding, bilingual operations client | Complete |
| 2 | Customers, categories, master/tenant catalog, barcodes, grades, pricing, media, catalog import | Complete |
| 3 | Invoices, immutable revisions, official numbering, customer ledger, payments and allocations, refunds, cancellation, overdue debt, supplier costs and payables, private invoice links | Complete |
| 4 | Offline-first operations with exactly-once synchronization and encrypted Google Drive backup | Next |
| 5 | Public bilingual storefront with guest checkout, owner order review, recommendations, featured products | Planned |
| 6 | Supplier price history, demand-driven procurement, supplier debt | Planned |
| 7 | Delivery tasks, owner/driver assignment, locations, route assistance | Planned |
| 8 | Analytics, customer lifetime statistics, tenant branding | Planned |
| 9 | Production hardening, CI/CD, staging, multi-tenant pilot | Planned |
| 10 | Seasonal best-product forecasting (statistical, optional) | Planned |

### What the next phase delivers (Phase 4)

Owners will keep working with no internet connection: customers, products, invoice drafts and
confirmations, and payments are recorded locally on the device and synchronized exactly once when
the connection returns. Official invoice numbers stay server-assigned, revoked devices can never
apply queued work, and each business gets an encrypted, restorable backup in its own Google Drive
folder.

## Key capabilities

**Platform and access**

- Registration, Argon2id password hashing, short-lived access tokens with rotating refresh sessions and revocation
- Platform administration: user management, tenant applications with approval/rejection, access periods, suspension and reactivation without data loss
- Strict separation between platform administration and business ownership; a business always keeps an active owner

**Customers and catalog**

- Tenant-isolated customers with phone search and duplicate disambiguation (no silent merging), addresses, coordinates and grades (A+, A, B+, B)
- Master and tenant catalogs with explicit barcode ownership, piece/box packaging and per-tenant prices
- Backend-authoritative pricing: explicit grade price, otherwise grade percentage discount, otherwise normal price; Decimal arithmetic only
- Validated, re-encoded product images through a provider-neutral storage layer
- Licensed (ODbL) Lebanon-market starter catalog import with provenance and quality reporting

**Invoicing and money**

- Invoice editor with barcode, catalog, manual and text-list entry, calculator-style quantities, line and invoice discounts/markups
- Immutable invoice revisions, server-assigned official numbers (`YYYY-000001` per business and year), auditable post-confirmation edits with exact ledger deltas
- Append-only customer ledger per currency; opening balances that are never counted as sales; owner-configured overdue threshold on the Lebanon calendar
- Immutable receipts with automatic (oldest-first) or owner-selected allocation, compensating reversals, credit-limited refunds and cancellation accounting that preserves payment history
- Supplier and product-cost setup with effective-dated cost history and sale-time cost snapshots on every confirmed line
- Supplier payables with payable-capped payments, explicit prepayments and reversals (aggregate per currency)
- Private customer invoice links (hashed secrets, expiry, single active link, revoked on cancellation) and WhatsApp sharing

**Product principles**

- No stock or availability tracking: "published" means visible in the catalog, nothing more
- Customers never need an account; a phone number is contact data, not identity
- Every business-owned table carries the business id and is protected by PostgreSQL row-level security
- Financial history is append-only; corrections are new records, never edits

## Architecture

- **API** — Python 3.13, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2, PostgreSQL 16+ (psycopg 3), OpenAPI documentation at `/docs`
- **Operations client** — React 19, TypeScript (strict), Vite, React Router, TanStack Query, React Hook Form + Zod, i18next; PWA foundation
- **Storefront** — Next.js App Router (Phase 5)
- **Quality** — pytest against real PostgreSQL, Vitest + Testing Library, Playwright end-to-end, Ruff, mypy (strict), ESLint, TypeScript

## Repository layout

- `apps/api` — FastAPI service, models, migrations, CLIs and PostgreSQL-backed tests
- `apps/operations-web` — React/Vite operations client, component tests and the Playwright end-to-end lane
- `apps/storefront-web` — storefront application boundary (Phase 5)
- `packages` — shared package boundaries reserved for later phases
- `docs/contracts` — architecture and domain contracts
- `docs/phase-1`, `docs/phase-2`, `docs/phase-3` — requirements evidence, test reports and demonstration guides for completed phases
- `data/master-catalog` — attributed ODbL starter catalog snapshot and quality report
- `infra`, `scripts` — infrastructure notes and repository tooling

Folder ownership is described in [`docs/folder-responsibilities.md`](docs/folder-responsibilities.md); the system structure in [`docs/architecture.md`](docs/architecture.md).

## Local setup

Prerequisites:

- Python 3.13+
- Node.js 22+
- a PostgreSQL database, either the hosted Supabase project or Docker Compose locally
- Docker with Compose only if using the local PostgreSQL option

### Run with hosted Supabase PostgreSQL on Windows (no Docker)

This is the normal no-Docker workflow. Run every command from the repository root in PowerShell.

1. Create and activate the Python virtual environment:

```powershell
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

The execution-policy command affects only the current PowerShell process and is needed only when
PowerShell blocks `Activate.ps1`.

2. Install the API and frontend dependencies:

```powershell
python -m pip install --upgrade pip
python -m pip install -e ".\apps\api[dev]"
npm ci
```

3. Create the local environment file if it does not already exist:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
notepad .env
```

In the Supabase dashboard, open the Tawzeevo project and click **Connect**. Use the direct database
connection when IPv6 is available; otherwise use the **Session pooler** on port `5432`. Replace the
`postgresql://` prefix in the copied URI with `postgresql+psycopg://` for SQLAlchemy/psycopg. If the
password contains URI-reserved characters, URL-encode it. Do not use the transaction pooler on port
`6543` for migrations. See the
[Supabase database connection guide](https://supabase.com/docs/guides/database/connecting-to-postgres)
for the current connection modes.

Configure `.env` with real local values while keeping secrets out of Git:

```dotenv
APP_ENV=development
DATABASE_URL=postgresql+psycopg://postgres.PROJECT_REFERENCE:URL_ENCODED_PASSWORD@SESSION_POOLER_HOST:5432/postgres?sslmode=require
CORS_ALLOWED_ORIGINS=["http://localhost:5173"]
JWT_SECRET=replace-with-a-long-random-local-secret
ACCESS_TOKEN_TTL_MINUTES=15
REFRESH_TOKEN_TTL_DAYS=30
REFRESH_COOKIE_SECURE=false
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_DEMO_PREVIEW=false
```

Never commit `.env`, database passwords, connection strings, or JWT secrets.

4. Apply every database migration before starting the API:

```powershell
python -m alembic -c .\apps\api\alembic.ini upgrade head
python -m alembic -c .\apps\api\alembic.ini current
```

The second command should show the latest revision followed by `(head)`.

Import the bundled, versioned starter master catalog after migrations. The first command validates
the snapshot and refreshes its quality report; the second performs an idempotent database import:

```powershell
python -m tawzeevo_api.cli.import_master_catalog --check-only --report .\data\master-catalog\open-food-facts-lebanon-v1.quality.json
python -m tawzeevo_api.cli.import_master_catalog
```

Repeating the import with the same version and checksum is safe and creates no duplicate products.

5. Start the FastAPI service in the first PowerShell terminal:

```powershell
python -m uvicorn tawzeevo_api.main:app `
  --app-dir .\apps\api `
  --reload `
  --host 127.0.0.1 `
  --port 8000
```

Keep this terminal open. The API is ready when Uvicorn reports that it is running on
`http://127.0.0.1:8000`. Verify both the service and PostgreSQL connection from another terminal:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/health/database
```

Interactive API documentation is available at `http://127.0.0.1:8000/docs`.

6. Start the React operations client in a second PowerShell terminal:

```powershell
cd C:\path\to\Tawzeevo
$env:VITE_API_BASE_URL = "http://127.0.0.1:8000"
npm run dev:operations
```

Open `http://localhost:5173`. Keep both terminals running while using Tawzeevo. Press `Ctrl+C` in
each terminal to stop the frontend and API; this does not delete or stop the hosted database.

If `/health` works but `/health/database` returns `503`, confirm the Supabase project is running and
recheck the database URL, password encoding, and pooler mode. If the browser reports `Failed to
fetch`, confirm the API terminal is running, `VITE_API_BASE_URL` points to port `8000`, and
`CORS_ALLOWED_ORIGINS` contains `http://localhost:5173`.

### Run with local PostgreSQL through Docker Compose

From the repository root:

```powershell
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".\apps\api[dev]"
npm ci
docker compose up -d postgres postgres-test
$env:DATABASE_URL = "postgresql+psycopg://tawzeevo:change-me@localhost:5432/tawzeevo"
.\.venv\Scripts\alembic -c .\apps\api\alembic.ini upgrade head
.\.venv\Scripts\uvicorn tawzeevo_api.main:app --app-dir .\apps\api --reload
```

In another terminal:

```powershell
npm run dev:operations
```

The operations client defaults to `http://localhost:5173`, the API to `http://localhost:8000`, and interactive API documentation to `http://localhost:8000/docs`. Replace every local placeholder before any non-development deployment and never commit `.env`.

## Share a saved invoice with a customer

1. Start the API and operations client using the setup instructions above, then sign in as the tenant owner.
2. Open a saved invoice and select **Manage invoice links**, then **Create private link**.
3. Select **Open customer view** to preview the English/Arabic invoice without a customer login.
4. Copy the displayed URL or select **Share on WhatsApp**. WhatsApp uses the invoice's normalized customer-phone snapshot; no message is sent automatically. A valid snapshot phone is required.
5. Share the new link immediately: its secret is shown only when created or replaced and is not recoverable from the link list. **Replace link** creates a new link and revokes the old one; **Revoke link** disables that link.

Anyone holding the link can view that invoice until expiry (90 days), revocation, or tenant suspension.
The page shows the current invoice revision, not unrelated balances, costs, profit, suppliers, or history.
It is not an account statement or payment-status page. After the page clears the secret from the
address bar, reload by reopening the original shared link.

No new environment variables are required: `VITE_API_BASE_URL` must point to the reachable API origin
(not localhost when sharing remotely). Deploy both existing services and use HTTPS in production.
The API itself serves the customer invoice page; this is not the future storefront/checkout.
See [P3-M5 implementation and demonstration notes](docs/phase-3/p3-m5.md) for security and supplier-foundation boundaries.

## Validation

Backend checks require a disposable migrated PostgreSQL database:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://tawzeevo_test:change-me@localhost:5433/tawzeevo_test"
$env:TEST_DATABASE_URL = $env:DATABASE_URL
$env:JWT_SECRET = "use-a-local-test-secret-of-at-least-32-bytes"
.\.venv\Scripts\python -m pytest .\apps\api\tests -q --cov=tawzeevo_api --cov-report=term-missing
.\.venv\Scripts\python -m ruff check .\apps\api
.\.venv\Scripts\python -m ruff format --check .\apps\api
.\.venv\Scripts\python -m mypy --config-file .\apps\api\pyproject.toml .\apps\api\tawzeevo_api
.\.venv\Scripts\alembic -c .\apps\api\alembic.ini check
npm run check
```

Two historical migrations (`0009`, `0010`) keep their original formatting by design and are fingerprinted by the test suite; new migrations follow the full lint and format rules.

A real-browser end-to-end lane (Playwright, Chromium) covers the critical owner flow and runs against a started API and client:

```powershell
npm run e2e --workspace=@tawzeevo/operations-web
```

Executed results for each completed phase are recorded in `docs/phase-1/test-report.md`, `docs/phase-2/test-report.md` and `docs/phase-3/test-report.md`.

## Documentation

- [`docs/architecture.md`](docs/architecture.md) — request flows, data model and runtime configuration
- [`docs/contracts`](docs/contracts) — pricing, financial invariants, tenant isolation, public access, sync protocol and other contracts
- [`docs/phase-3/demo-guide.md`](docs/phase-3/demo-guide.md) — end-to-end demonstration of the financial core with synthetic data
- [`docs/phase-3/requirements-audit.md`](docs/phase-3/requirements-audit.md) — requirement-to-code/test evidence for Phase 3
- [`docs/future-phases.md`](docs/future-phases.md) — planned phases and their boundaries

## License

No general application-source license has been granted for this repository. The catalog snapshot in
[`data/master-catalog`](data/master-catalog) is separately attributed and shared under ODbL 1.0.
