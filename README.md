# Tawzeevo

Tawzeevo is a multi-tenant Cash Van operations platform with a linked bilingual customer storefront. This repository is the authoritative monorepo for the platform.

Phase 1 is complete. It delivers the FastAPI/PostgreSQL authentication and platform foundation, the mandatory English/Arabic React operations client, manual tenant onboarding and lifecycle controls, and a tenant-isolated Cash Van slice for customers, categories, barcode products, and database-backed draft invoices.

Later product areas remain governed future work. Phase 1 does not claim storefront ordering, confirmed financial ledgers, offline sync, procurement, delivery routing, analytics, or forecasting as implemented.

## Phase 1 capabilities

- Public client registration, Argon2id login, short-lived JWT access, rotating refresh sessions, logout, and session revocation
- Safe profile management plus administrator user creation, filtering, pagination, role changes, and soft deletion
- Public active-user statistics
- Client tenant applications plus administrator approval, rejection, access-period management, suspension, and reactivation
- Last-owner protection and strict separation between platform administration and tenant ownership
- Tenant-scoped customer, category, barcode-product, and draft-invoice APIs with PostgreSQL row-level security
- English/Arabic operations UI with LTR/RTL, protected routes, accessible forms, and platform dashboards
- Safe administrator bootstrap and synthetic owner-scoped demo seeding

## Repository layout

- `apps/api` — FastAPI service, SQLAlchemy models, Alembic migrations, CLIs, and PostgreSQL-backed tests
- `apps/operations-web` — React/Vite operations client and frontend tests
- `apps/storefront-web` — documented future storefront boundary; no Phase 1 storefront implementation
- `packages` — documented shared-package boundaries reserved for later phases
- `docs/contracts` — approved architecture contracts for current and future work
- `docs/phase-1` — frozen Phase 1 test, demo, and requirements evidence
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

## Validation

Backend checks require a disposable migrated PostgreSQL database:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://tawzeevo_test:change-me@localhost:5433/tawzeevo_test"
$env:TEST_DATABASE_URL = $env:DATABASE_URL
$env:JWT_SECRET = "use-a-local-test-secret-of-at-least-32-bytes"
.\.venv\Scripts\python -m pytest .\apps\api\tests -q --cov=apps/api/tawzeevo_api --cov-report=term-missing
.\.venv\Scripts\python -m ruff check .\apps\api
.\.venv\Scripts\python -m ruff format --check .\apps\api
.\.venv\Scripts\python -m mypy --config-file .\apps\api\pyproject.toml .\apps\api\tawzeevo_api
.\.venv\Scripts\alembic -c .\apps\api\alembic.ini check
npm run check
```

The frozen results are in [`docs/phase-1/test-report.md`](docs/phase-1/test-report.md).

## Demonstration and audit

- [`docs/demo-role-gallery.md`](docs/demo-role-gallery.md) — isolated public role-gallery walkthrough, boundaries, and teardown checklist
- [`docs/phase-1/demo-guide.md`](docs/phase-1/demo-guide.md) — setup, safe seeding, and presentation checklist
- [`docs/phase-1/requirements-audit.md`](docs/phase-1/requirements-audit.md) — evidence for every Phase 1 contract section and Definition of Done item
- [`docs/future-phases.md`](docs/future-phases.md) — contracted sequence without implementation claims

No license has been granted for this repository.
