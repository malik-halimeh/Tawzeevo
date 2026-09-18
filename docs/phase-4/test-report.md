# Phase 4 test report

Freeze date: 2026-09-18

Status: PASS

This report records the Phase 4 completion run. Commands assume execution from the repository
root and a deliberately disposable PostgreSQL 18 database (`127.0.0.1:55439`, migrated from zero
to `20260918_0016`). No hosted or production database credentials are recorded here. Phase 4
commits: `137e152` (P4-M1), `3fdd7d6` (P4-M2), `8230184`/`241acf2` (P4-M3), `758491e`/`0f28fb2`
(P4-M4), `ac8d049` (P4-M5) and the P4-M6 freeze commit that carries this report.

## Final automated results

| Gate | Result | Evidence |
|---|---:|---|
| PostgreSQL-backed backend suite | 188 passed | `apps/api/tests` (161 at the Phase 3 freeze; +27 for sync, backup and hardening) |
| Backend statement coverage | 91% | pytest-cov over `tawzeevo_api` |
| Frontend unit/integration suite | 70 passed (14 files) | Vitest with `fake-indexeddb` for the offline suites |
| Real-browser E2E, Phase 3 critical flow | 1 passed (Chromium) | `apps/operations-web/e2e/phase3-critical-flow.spec.ts` |
| Real-browser E2E, Phase 4 offline flow (network emulation off) | 1 passed (Chromium) | `apps/operations-web/e2e/phase4-offline-flow.spec.ts` |
| Python lint / formatting | PASS | Ruff check and format check (whole backend) |
| Python static typing | PASS | strict mypy, 67 source files |
| Frontend lint and static typing | PASS | ESLint `--max-warnings 0`, `tsc -b` |
| Frontend production build | PASS | Vite build; non-blocking size advisory only |
| Alembic schema drift | PASS | `alembic check`: no new upgrade operations at `20260918_0016` |
| Migrations `0014`–`0016` upgrade, downgrade, upgrade | PASS | executed on the disposable cluster; `test_hardening.py` from-zero build |
| Forced RLS on every new tenant-owned table (sync and backup) | PASS | migrations; `test_sync_bootstrap.py::test_forced_rls_hides_other_tenant_sync_rows` |
| Sync idempotency: replay ×1/×10/×100, concurrent identical pushes, crash between commits | PASS | `test_sync_push.py`, `test_sync_hardening.py` |
| Financial offline: one official number, two devices no collision, refund ceiling, stale confirmation | PASS | `test_sync_financial_push.py` |
| Revocation: membership revoke, tenant suspend, retired device, device id alone | PASS | `test_sync_pull.py`, `test_sync_bootstrap.py`, `test_sync_hardening.py` |
| Protocol mismatch and local schema migration | PASS | `test_sync_bootstrap.py`; `outbox.test.ts`; `db.test.ts` |
| Encrypted backup: manifest, ciphertext privacy, retention, tamper, wrong key, drill, empty-tenant import, rotation, schedule | PASS | `test_backup.py` (4 tests, in-memory Drive double) |
| Google Drive live run | NOT RUN | needs the owner's OAuth client; the HTTP client is not exercised against Google in this freeze |
| Graphify structural refresh | see `private/docs/assurance/GRAPHIFY.md` | 0.9.55 refresh at the freeze commit |

## What the offline E2E proves (executed 2026-09-18, 7.8 s)

1. Owner signs in and downloads the business (1 customer / 1 product / 0 invoices on the device).
2. The browser goes offline (Playwright `context.setOffline(true)`): the connection badge says
   Offline and *Sync now* is disabled.
3. Still offline, the owner creates a new customer (queued on the device), finds that customer by
   phone from the device projection, scans the product barcode from the device catalog, and saves
   an invoice: the editor shows a `PENDING-XXXXXXXX` reference, never an official number.
4. The Offline tab lists both commands as *Waiting to send*.
5. The browser comes back online; one *Sync now* sends exactly 2 changes; a second *Sync now*
   sends 0.
6. Through the API the business has exactly one new customer and one draft invoice pointing at
   that customer, with the scanned product line and no official number.

## Reproduction

```powershell
# 1. Disposable PostgreSQL (never the hosted database)
& "C:\Program Files\PostgreSQL\18\bin\initdb.exe" -D .tmp\pg-phase4 -U postgres -A trust -E UTF8 --locale=C
& "C:\Program Files\PostgreSQL\18\bin\pg_ctl.exe" -D .tmp\pg-phase4 -o "-p 55439 -c listen_addresses=127.0.0.1" -l .tmp\pg-phase4.log -w start
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -h 127.0.0.1 -p 55439 -U postgres -c "CREATE DATABASE tawzeevo_phase4;"
$env:DATABASE_URL = "postgresql+psycopg://postgres@127.0.0.1:55439/tawzeevo_phase4"
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

# 4. Real-browser E2E (API on 8011 with the in-memory Drive double, web on 5173, an admin user)
$env:BACKUP_DRIVE_PROVIDER = "memory"
.\.venv\Scripts\python -m uvicorn tawzeevo_api.main:app --app-dir .\apps\api --host 127.0.0.1 --port 8011
$env:VITE_API_BASE_URL = "http://127.0.0.1:8011"; npm run dev --workspace=@tawzeevo/operations-web -- --host 127.0.0.1 --port 5173
$env:E2E_API_URL = "http://127.0.0.1:8011"; $env:E2E_WEB_URL = "http://127.0.0.1:5173"
$env:E2E_ADMIN_EMAIL = "admin-e2e@example.com"; $env:E2E_ADMIN_PASSWORD = "<the admin password you set>"
npm run e2e --workspace=@tawzeevo/operations-web
```

The backend suite truncates the database; create the E2E administrator after it, not before.

## Known limitations at the freeze

- The E2E runs one Chromium project on Windows; no cross-browser or mobile-emulation matrix yet.
- A physically offline browser cannot learn about a revocation until it reconnects; queued work
  from a revoked device is then quarantined, never applied.
- The Google Drive HTTP client follows the documented Drive v3 endpoints and is covered only
  through the in-memory double until the owner supplies an OAuth client.
- Backup import restores one business into an empty tenant of the recovery environment; platform
  users and memberships come from the platform database backup.
