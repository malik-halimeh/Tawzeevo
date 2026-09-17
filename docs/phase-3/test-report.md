# Phase 3 test report

Freeze date: 2026-09-17

Status: PASS

This report records the Phase 3 completion run preserved in `RUN_TESTS.md` and
`03_IMPLEMENTATION_STATUS.md`. Commands assume execution from the repository root and a deliberately
disposable PostgreSQL 18 database (`127.0.0.1:55439`, migrated from zero to `20260909_0012`). No
hosted or production database credentials are recorded here. Application commit at freeze:
`18e9051` (E2E lane) on top of the Sprint 1 remediation commits `2364dba`…`4bdbd88`.

## Final automated results

| Gate | Result | Evidence |
|---|---:|---|
| PostgreSQL-backed backend suite | 161 passed | `apps/api/tests` (was 142 at the start of the day) |
| Backend statement coverage | 93% | pytest-cov over `tawzeevo_api` |
| Frontend unit/integration suite | 49 passed (7 files) | operations client Vitest suite |
| Real-browser E2E critical flow | 1 passed (Chromium) | `apps/operations-web/e2e/phase3-critical-flow.spec.ts` |
| Python lint / formatting | PASS | Ruff check and format check (whole backend) |
| Python static typing | PASS | strict mypy, 55 source files |
| Frontend lint and static typing | PASS | ESLint `--max-warnings 0`, `tsc -b` |
| Frontend production build | PASS | Vite build, 212 modules; non-blocking size advisory only |
| Alembic schema drift | PASS | `alembic check`: no new upgrade operations at `20260909_0012` |
| Migration from an empty database | PASS | `test_hardening.py::test_migrations_build_a_new_database_from_zero` |
| Upgrade from Phase 2 data | PASS | `test_financial_schema.py::test_phase2_draft_rows_upgrade_to_revisions_and_round_trip` |
| Immutable historical migrations | PASS | `test_immutable_migration_files.py` content guards for `0009`/`0010` |
| PostgreSQL tenant isolation (forced RLS, non-bypass roles) | PASS | supplier ledger, public capability and cash-van RLS tests |
| Financial invariants (pricing-v1, revisions, ledger, allocations, refunds, cancellation) | PASS | `test_invoice_editor.py`, `test_fa008_obligations.py`, `test_opening_balances.py` |
| Sprint 1 finding regressions (FA-002/003/004/005/006/010/012) | PASS | `test_fa00x_*.py` files; see `RUN_TESTS.md` ledger |
| Graphify structural refresh | PASS | 0.9.55, 2,673 nodes / 8,710 edges at `4bdbd88`; check-only rerun pending the E2E commit |

## Reproduction

```powershell
# 1. Disposable PostgreSQL (never the hosted database)
& "C:\Program Files\PostgreSQL\18\bin\initdb.exe" -D .tmp\pg-phase3 -U postgres -A trust -E UTF8 --locale=C
& "C:\Program Files\PostgreSQL\18\bin\pg_ctl.exe" -D .tmp\pg-phase3 -o "-p 55439 -c listen_addresses=127.0.0.1" -l .tmp\pg-phase3.log -w start
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -h 127.0.0.1 -p 55439 -U postgres -c "CREATE DATABASE tawzeevo_phase3;"
$env:DATABASE_URL = "postgresql+psycopg://postgres@127.0.0.1:55439/tawzeevo_phase3"
$env:TEST_DATABASE_URL = $env:DATABASE_URL
$env:JWT_SECRET = "use-a-local-test-secret-of-at-least-32-bytes"
.\.venv\Scripts\alembic -c .\apps\api\alembic.ini upgrade head

# 2. Backend, static checks, drift
.\.venv\Scripts\python -m pytest .\apps\api\tests -q --cov=tawzeevo_api --cov-report=term-missing
.\.venv\Scripts\python -m ruff check .\apps\api
.\.venv\Scripts\python -m ruff format --check .\apps\api
.\.venv\Scripts\python -m mypy --config-file .\apps\api\pyproject.toml .\apps\api\tawzeevo_api
.\.venv\Scripts\alembic -c .\apps\api\alembic.ini check

# 3. Frontend
npm run check

# 4. Real-browser E2E (API on 8011, web on 5173, an admin user in the disposable database)
$env:APP_ENV = "development"; $env:CORS_ALLOWED_ORIGINS = '["http://127.0.0.1:5173"]'
# create a platform admin (any of: tawzeevo_api.cli.create_admin in an interactive shell)
.\.venv\Scripts\python -m uvicorn tawzeevo_api.main:app --app-dir .\apps\api --host 127.0.0.1 --port 8011
$env:VITE_API_BASE_URL = "http://127.0.0.1:8011"; npm run dev --workspace=@tawzeevo/operations-web -- --host 127.0.0.1 --port 5173
$env:E2E_API_URL = "http://127.0.0.1:8011"; $env:E2E_WEB_URL = "http://127.0.0.1:5173"
$env:E2E_ADMIN_EMAIL = "admin-e2e@example.com"; $env:E2E_ADMIN_PASSWORD = "<the admin password you set>"
npm run e2e --workspace=@tawzeevo/operations-web
```

## What the E2E proves (executed 2026-09-17, 6.2 s)

Owner registers and is approved (API), signs in through the real login page, creates a supplier and
saves a product cost in the new Suppliers & costs tab, adds a product by barcode in the invoice
editor, saves the draft, confirms and receives an official `YYYY-000001` number, records a 5 USD
receipt, creates a private link whose public projection contains no cost/profit/balance/grade
fields and carries `Cache-Control: no-store`, switches the UI to Arabic (`dir="rtl"`) and back,
cancels the invoice, and the link immediately returns 404. The ledger then shows the customer with
`-5.0000` USD credit and no positive debt.

## Limits

- The E2E runs one Chromium project on Windows; no cross-browser or mobile-emulation matrix yet.
- Public rate limiting is per-process and was tested at unit level, not under a reverse proxy.
- Durable overdue notification cadence is not implemented (later operational policy).
- FA-009 (draft-create command scope) remains open pending the owner's decision; draft creation
  posts no money.
- Deployed database roles/grants and hosted behavior are not certified by this local run (CT-009).
