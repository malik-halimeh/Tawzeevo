# Phase 8 test report

Report date: 2026-09-19 (P8-M4 freeze)

Every run below used a disposable local PostgreSQL 18 cluster on `127.0.0.1:55439`; the hosted
database is never used for tests.

## Final automated results

| Lane | Command | Result |
|---|---|---|
| Backend unit/integration | `pytest apps/api/tests -q` | **237 passed** (11 min 23 s) |
| Backend static | `ruff check`, `ruff format --check`, `mypy tawzeevo_api` | clean (96 source files) |
| Migration drift | `alembic check` at head `20260919_0027` | no new operations |
| Operations client | `eslint --max-warnings 0`, `tsc -b`, `vitest run` | **82 passed** (24 files) |
| Storefront | `eslint`, `tsc --noEmit`, `vitest run`, `next build` | **9 passed**, build OK |
| Real-browser E2E (Chromium) | `npm run e2e --workspace=@tawzeevo/operations-web` | **7 passed** (40 s): Phase 3, Phase 4 offline, Phase 5 ×2, Phase 6, Phase 7, **Phase 8** |

Phase 8 test files: `test_analytics.py` (5), `test_customer_stats.py` (1),
`test_branding_public_stats.py` (2); `AnalyticsPanel.test.tsx`, `PublicInvoicePage.test.ts`
(branded render added), storefront `lib/theme.test.ts`; `e2e/phase8-analytics-branding.spec.ts`.

## What the Phase 8 E2E proves (executed 2026-09-19, 19 s)

1. API setup: owner, product at 10 USD with a 7 USD supplier cost, one customer, two confirmed
   invoices (2 and 3 pieces), one receipt of 15 USD, a storefront slug.
2. Reconciliation through the API: overview `invoiced_sales` 50.0000, `customer_receipts`
   15.0000, `customer_outstanding` 35.0000 = the customer ledger balance; gross profit 15.0000
   with 100 % coverage. The overview answered in well under the 2 s guard.
3. Owner in the browser, **Analytics**: the same three figures and `100.0000% (2/2)` coverage;
   the customer is found by phone; the lifetime table shows purchased 50, largest 30, average
   25, outstanding 35, and the top product.
4. **Branding**: title, banner, primary colour, About text, invoice header/terms/thank-you, QR
   on, default language Arabic; saved; logo uploaded and shown. Afterwards the public price is
   still 10.0000 and the dashboard unchanged.
5. Storefront, fresh context: renders RTL Arabic without a `lang` parameter (business default),
   the new title, the logo, the banner, `--accent:#1f6f5f` on the shop wrapper; the "من نحن"
   link opens the About page; `?lang=en` switches to LTR and shows "About".
6. Customer invoice page opened with a fresh capability: header, terms, thank-you and logo
   visible, RTL by default, the QR image loaded from a blob, the secret removed from the address
   bar; the QR endpoint answers 200 PNG with the header and 404 without it.
7. `/stats/platform` exposes only aggregate counts and withholds them below the D-070 cohort.

## Measured query performance (local API, seeded tenant: 60 confirmed invoices, 10 receipts)

| Endpoint | p50 | max of 5 |
|---|---:|---:|
| `GET /api/v1/analytics/overview?period=30d` | 24 ms | 24 ms |
| `GET /api/v1/analytics/overview?period=all` | 25 ms | 30 ms |
| `GET /api/v1/analytics/events?period=90d` | 16 ms | 18 ms |
| `GET /api/v1/analytics/customers/{id}` | 26 ms | 26 ms |
| `GET /api/v1/tenants/{id}/branding` | 15 ms | 16 ms |
| `GET /stats/platform` | 71 ms | 71 ms |

All far inside the D-078 targets (CRUD < 400 ms). Formal load measurement belongs to Phase 9
P9-M3.

## Defects found and fixed during the freeze

- The lifetime drilldown's customer picker called a listing endpoint that does not exist
  (`GET /tenants/{id}/customers` → 405), so no customer could be chosen from the desk. The
  picker now finds customers by phone through the existing search route, like every other desk
  screen, and selects a single match automatically.
- The customer invoice page's contact block would have echoed the substrings `phone` and
  `address` that the public-projection guard forbids (they protect the customer's data); the
  business contact fields are named `business_tel`, `business_whatsapp`, `business_location`.
- The Phase 3 E2E asserted the "cannot exceed the current payable" refusal with a text locator
  that also matched the desk's explanatory paragraph (strict-mode failure when both rendered);
  it now targets the alert.
- Storefront theme tokens: a light primary colour would have been used as text on white; tokens
  are applied only when readable (4.5:1) and the ink on accent backgrounds follows the colour's
  luminance (`lib/theme.ts`).

## Reproduction

The commands are identical to `docs/phase-5/test-report.md` § Reproduction (backend, client
`npm run check`, local API/web/storefront servers, `npm run e2e`). Rebuild the storefront
(`next build`) after changing it; `next start` serves the last build.

## Known limitations at the freeze

- Favicon, featured-product presentation, promotional banners and a configurable homepage layout
  (PHASE_08.md F) are not built; see the requirements audit § F.
- The QR image encodes `https://{Host}/api/v1/public/invoice#{secret}` using the request's Host
  header (`http` only for loopback); a deployment behind a different public host name must
  present that host to the API.
- The `date_format` setting is stored and shown on the desk; the customer invoice page carries no
  dates today, so nothing renders with it yet.
- Accessibility was verified by labelled landmarks, table names, text alternatives to colour and
  RTL rendering in tests and E2E; no automated axe scan is part of the pipeline.
- One Chromium project on Windows.
