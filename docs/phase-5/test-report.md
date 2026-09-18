# Phase 5 test report

Report date: 2026-09-19 (P5-M6 freeze)

Every run below used a disposable local PostgreSQL 18 cluster on `127.0.0.1:55439`; the hosted
database is never used for tests.

## Final automated results

| Lane | Command | Result |
|---|---|---|
| Backend unit/integration | `pytest apps/api/tests -q` | **208 passed** (6 min 49 s) |
| Backend static | `ruff check`, `ruff format --check`, `mypy tawzeevo_api` | clean (75 source files) |
| Migration drift | `alembic check` at head `20260919_0021` | no new operations |
| Operations client | `eslint --max-warnings 0`, `tsc -b`, `vitest run`, `vite build` | **73 passed** (17 files), build OK |
| Storefront | `eslint --max-warnings 0`, `tsc --noEmit`, `vitest run`, `next build` | **5 passed** (2 files), build OK |
| Real-browser E2E (Chromium) | `npm run e2e --workspace=@tawzeevo/operations-web` | **4 passed** (21 s): Phase 3 critical flow, Phase 4 offline flow, Phase 5 storefront flow, Phase 5 Arabic phone |

Phase 5 test files: `test_storefront.py`, `test_storefront_signals.py`, `test_customer_access.py`,
`test_checkout.py`, `test_order_review.py`, `test_phase5_freeze.py`; `CustomerLinkControls.test.tsx`,
`CampaignPanel.test.tsx`, `OrdersPanel.test.tsx`; storefront `lib/personal.test.ts`,
`lib/format.test.ts`; `e2e/phase5-storefront-flow.spec.ts`.

## What the storefront E2E proves (executed 2026-09-19)

Test 1 — `guest checkout → owner link, confirm, delivery date → customer cancellation request → owner decision`:

1. API setup: owner registered and approved, one published product with a supplier cost
   (the Phase 3 confirmation rule), storefront slug set.
2. Guest browser: opens `/<slug>`, adds the product to the cart, fills name/phone/address, places
   the order; lands on `/<slug>/order` with the reference removed from the address bar; the page
   says "Received" and contains none of grade/debt/cost/supplier/driver.
3. Owner browser: signs in, opens the **Orders** tab (shows `1 new`), opens the order; the
   confirm button is disabled until a customer is linked; creates the customer from the
   snapshot (draft re-priced); confirms (official number assigned by Phase 3); saves tomorrow
   as the delivery date (reminder scheduled).
4. Guest browser: reloads the provisional page, sees "Confirmed by the shop" and the planned
   delivery date, asks to cancel with a reason.
5. Owner browser: sees the request with the reason, approves; guest reload shows "Cancelled."
6. API: the public catalog contains no private words; a random order reference returns 404 with
   `no-store`.

Test 2 — `storefront in Arabic on a phone`: 390×844 viewport, `?lang=ar`; the shop renders inside
an `[dir=rtl][lang=ar]` container with no horizontal overflow; add-to-cart, labelled checkout
fields and the Arabic "Received" status work; the cancellation request button is present.

## Defects found and fixed during the freeze

- The confirm action could echo a revision id that predated the link's re-pricing (a 409 with no
  visible message). The order detail now carries the invoice's current revision and the panel
  never clears an error on its automatic refresh.
- The RTL skip link (`inset-inline-start: -999px`) widened every Arabic storefront page by
  999 px on phones. Replaced with the visually-hidden pattern.
- Public rate limits were hard-coded although D-076 defines them as configurable policy; they
  now come from `PUBLIC_PRIVATE_RATE_LIMIT_PER_MINUTE` / `PUBLIC_CATALOG_RATE_LIMIT_PER_MINUTE`
  (defaults 60 / 600).

## Reproduction

```powershell
# 1. Disposable PostgreSQL (never the hosted database)
& "C:\Program Files\PostgreSQL\18\bin\initdb.exe" -D .tmp\pg-phase5 -U postgres -A trust -E UTF8 --locale=C
& "C:\Program Files\PostgreSQL\18\bin\pg_ctl.exe" -D .tmp\pg-phase5 -o "-p 55439 -c listen_addresses=127.0.0.1" -l .tmp\pg-phase5.log -w start
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -h 127.0.0.1 -p 55439 -U postgres -c "CREATE DATABASE tawzeevo_phase5;"
$env:DATABASE_URL = "postgresql+psycopg://postgres@127.0.0.1:55439/tawzeevo_phase5"
$env:TEST_DATABASE_URL = $env:DATABASE_URL
$env:JWT_SECRET = "use-a-local-test-secret-of-at-least-32-bytes"
.\.venv\Scripts\alembic -c .\apps\api\alembic.ini upgrade head

# 2. Backend, static checks, drift
.\.venv\Scripts\python -m pytest .\apps\api\tests -q
.\.venv\Scripts\python -m ruff check .\apps\api
.\.venv\Scripts\python -m ruff format --check .\apps\api
.\.venv\Scripts\python -m mypy --config-file .\apps\api\pyproject.toml .\apps\api\tawzeevo_api
.\.venv\Scripts\alembic -c .\apps\api\alembic.ini check

# 3. Frontends
npm run check

# 4. Real-browser E2E: API on 8011, operations client on 5173, storefront on 3000, an admin user
$env:BACKUP_DRIVE_PROVIDER = "memory"
$env:CORS_ALLOWED_ORIGINS = '["http://127.0.0.1:5173","http://127.0.0.1:3000"]'
.\.venv\Scripts\python -m uvicorn tawzeevo_api.main:app --app-dir .\apps\api --host 127.0.0.1 --port 8011
$env:VITE_API_BASE_URL = "http://127.0.0.1:8011"; npm run dev --workspace=@tawzeevo/operations-web -- --host 127.0.0.1 --port 5173
npm run build --workspace=@tawzeevo/storefront-web
$env:API_BASE_URL = "http://127.0.0.1:8011"; npm run start --workspace=@tawzeevo/storefront-web -- -H 127.0.0.1 -p 3000
.\.venv\Scripts\python -m tawzeevo_api.cli.create_admin --first-name E2E --last-name Admin --email admin-e2e@example.com --phone +96170000000 --city Beirut --age 40
$env:E2E_API_URL = "http://127.0.0.1:8011"; $env:E2E_WEB_URL = "http://127.0.0.1:5173"; $env:E2E_SHOP_URL = "http://127.0.0.1:3000"
$env:E2E_ADMIN_EMAIL = "admin-e2e@example.com"; $env:E2E_ADMIN_PASSWORD = "<the admin password you set>"
npm run e2e --workspace=@tawzeevo/operations-web
```

The backend suite truncates the database; create the E2E administrator after it, not before.

## Known limitations at the freeze

- One Chromium project on Windows; the phone test uses viewport emulation, not a device farm.
- Rate limiting is per API process (in-memory sliding window). Behind more than one instance the
  effective limit multiplies; a shared store is Phase 9 hardening work if the pilot needs it.
- Delivery reminders are job records; the channel that delivers them (e-mail/WhatsApp) is a
  Phase 9 provider decision.
- The provisional order page depends on the browser keeping the reference in `sessionStorage`
  after the fragment is stripped; closing the tab means the customer needs the original link.
