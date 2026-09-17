# Tawzeevo

For repository-only continuation, start with [AGENT_START_HERE.md](AGENT_START_HERE.md).
The [continuity audit register](docs/audits/AUDIT_REGISTER.md) records unresolved questions;
completed milestone claims below do not resolve those findings or authorize P3-M6.

Tawzeevo is a multi-tenant Cash Van operations platform with a linked bilingual customer storefront. This repository is the authoritative monorepo for the platform.

Phases 1 and 2 are complete, and Phase 3 milestones P3-M1 through P3-M5 are complete. Tawzeevo includes the FastAPI/PostgreSQL authentication and platform
foundation, the mandatory English/Arabic React operations client, manual tenant onboarding and
lifecycle controls, and the tenant-isolated customer, catalog, barcode, grade-pricing, media, and
production invoice, customer-ledger, payment, allocation, debt, cancellation, and refund foundation.

Later product areas remain governed future work. Invoice confirmation, official numbering,
post-confirm revisions, opening balances, overdue debt alerts, immutable receipts, allocations,
cancellation accounting, credit-limited refunds, private public-invoice links, and WhatsApp sharing are implemented. Tawzeevo also does not yet claim storefront ordering, offline
sync, procurement, delivery routing, analytics, or forecasting as implemented.

## Implemented capabilities

- Public client registration, Argon2id login, short-lived JWT access, rotating refresh sessions, logout, and session revocation
- Safe profile management plus administrator user creation, filtering, pagination, role changes, and soft deletion
- Public active-user statistics
- Client tenant applications plus administrator approval, rejection, access-period management, suspension, and reactivation
- Last-owner protection and strict separation between platform administration and tenant ownership
- Tenant-scoped customer, category, barcode-product, and draft-invoice APIs with PostgreSQL row-level security
- Separate master and tenant catalogs, explicit barcode ownership, known-barcode adoption, and manual missing-product creation
- Customer grades, backend-authoritative `pricing-v1`, explicit grade prices, percentage discounts, and piece/box derivation
- Provider-neutral product-image storage with authenticated retrieval and safe JPEG/PNG/WebP re-encoding
- Versioned, provenance-aware, quality-gated import of the licensed starter Lebanon-market catalog
- Canonical immutable invoice revision schema, tenant/year numbering state, append-only financial records, and tenant-private supplier-cost snapshot foundation
- Atomic invoice confirmation, server-assigned official numbers, exact post-confirm ledger deltas, immutable revision history, and allocation release after downward edits
- Per-currency customer balances, idempotent opening balances, owner-configured overdue thresholds, and deduplicated overdue alerts
- Immutable customer receipts with FIFO or owner-selected allocation, partial/multi-obligation settlement, compensating receipt reversal, and unallocated credit
- Draft/confirmed cancellation accounting that preserves revisions and payments, plus serialized customer-credit refunds that cannot create debt
- Owner-managed invoice links with expiry, replacement, revocation, a restricted EN/AR customer view, and WhatsApp sharing
- Tenant-private supplier opening balances, payable-capped aggregate payments, explicit supplier prepayments, and compensating reversals, without per-purchase allocation
- Owner supplier and product-cost setup (create/rename suppliers, append effective-dated costs, choose the preferred supplier) feeding invoice cost provenance
- English/Arabic operations UI with LTR/RTL, protected routes, accessible forms, and platform dashboards
- Safe administrator bootstrap and synthetic owner-scoped demo seeding

## Repository layout

- `apps/api` — FastAPI service, SQLAlchemy models, Alembic migrations, CLIs, and PostgreSQL-backed tests
- `apps/operations-web` — React/Vite operations client and frontend tests
- `apps/storefront-web` — documented future storefront boundary; no Phase 1 storefront implementation
- `packages` — documented shared-package boundaries reserved for later phases
- `docs/contracts` — approved architecture contracts for current and future work
- `docs/phase-1` and `docs/phase-2` — frozen test, demo, and requirements evidence for completed phases
- `data/master-catalog` — attributed ODbL starter catalog snapshot and machine-readable quality report
- `infra` — local infrastructure guidance
- `scripts` — repository automation guidance

Detailed ownership is documented in [`docs/folder-responsibilities.md`](docs/folder-responsibilities.md), with the system structure in [`docs/architecture.md`](docs/architecture.md).

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

The whole-backend Ruff commands remain the quality gate. Two immutable historical migrations
have exact-path exceptions in `apps/api/pyproject.toml`: `0009` retains its original import order
(`I001` only), and `0009`/`0010` retain their original formatting. All other selected lint rules
still apply to both files; every other/new migration retains full lint and format coverage.
The full test suite fingerprints both historical files (ignoring only Git's LF/CRLF conversion)
so the exceptions cannot conceal later edits. Do not expand the exceptions or update the hashes
to bypass a failure. See [baseline remediation evidence](docs/phase-3/baseline-remediation.md).

The frozen results are in the completed-phase reports:

- [`docs/phase-1/test-report.md`](docs/phase-1/test-report.md)
- [`docs/phase-2/test-report.md`](docs/phase-2/test-report.md)

## Demonstration and audit

- [`docs/demo-role-gallery.md`](docs/demo-role-gallery.md) — isolated public role-gallery walkthrough, boundaries, and teardown checklist
- [`docs/phase-1/demo-guide.md`](docs/phase-1/demo-guide.md) — setup, safe seeding, and presentation checklist
- [`docs/phase-1/requirements-audit.md`](docs/phase-1/requirements-audit.md) — evidence for every Phase 1 contract section and Definition of Done item
- [`docs/phase-2/demo-guide.md`](docs/phase-2/demo-guide.md) — tenant customer, catalog, pricing, media, and barcode presentation workflow
- [`docs/phase-2/requirements-audit.md`](docs/phase-2/requirements-audit.md) — evidence for every Phase 2 milestone and Definition of Done item
- [`docs/future-phases.md`](docs/future-phases.md) — contracted sequence without implementation claims

No general application-source license has been granted for this repository. The catalog snapshot in
[`data/master-catalog`](data/master-catalog) is separately attributed and shared under ODbL 1.0.
