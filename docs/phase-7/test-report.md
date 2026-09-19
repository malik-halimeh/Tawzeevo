# Phase 7 test report

Report date: 2026-09-19 (P7-M4 freeze)

Every run below used a disposable local PostgreSQL 18 cluster on `127.0.0.1:55439`; the hosted
database is never used for tests.

## Final automated results

| Lane | Command | Result |
|---|---|---|
| Backend unit/integration | `pytest apps/api/tests -q` | **229 passed** (8 min 17 s) |
| Backend static | `ruff check`, `ruff format --check`, `mypy tawzeevo_api` | clean (86 source files) |
| Migration drift | `alembic check` at head `20260919_0026` | no new operations |
| Operations client | `eslint --max-warnings 0`, `tsc -b`, `vitest run`, `vite build` | **79 passed** (22 files), build OK |
| Storefront | unchanged in Phase 7 | 5 passed |
| Real-browser E2E (Chromium) | `npm run e2e --workspace=@tawzeevo/operations-web` | **6 passed** (35 s): Phase 3, Phase 4 offline, Phase 5 ×2, Phase 6, **Phase 7 field flow** |

Phase 7 test files: `test_delivery_tasks.py` (6), `test_delivery_routes.py` (4);
`DeliveryPanel.test.tsx`, `MyWorkPanel.test.tsx`, `RoutePlanner.test.tsx`;
`e2e/phase7-field-flow.spec.ts`.

## What the Phase 7 E2E proves (executed 2026-09-19, 7.2 s)

1. API setup: owner, a registered driver account (not yet a member), product with a supplier
   cost, two customers with coordinates, two confirmed invoices.
2. Owner, sole operator: the **Deliveries** tab is titled "My deliveries" and asks for no driver;
   the owner creates a delivery for Hamra Grocer and marks it delivered.
3. Owner opens **Team (drivers)**, adds the driver by e-mail; the tab now says "Deliveries"; the
   owner creates the Achrafieh Market delivery and assigns it to the driver.
4. Driver, second browser context: the workspace shows **My route** with the Achrafieh stop only
   (no Hamra, no supplier desk tab); the text contains the amount to collect and no
   cost/margin/profit; *Suggest stop order* returns a labelled suggestion.
5. Driver goes offline, marks the stop delivered → "No connection: the completion is saved on
   this device…"; back online, *Sync now* → "Sent."; the stop disappears; the owner API shows
   two completed tasks, the Achrafieh one performed by the driver.
6. Owner revokes the driver; a fresh driver login gets 403 on *My Work*.

## Defects found and fixed during the freeze

- A driver device that first tried to register while offline could not push on reconnect (404
  device not registered). *My Work* now registers the device while online (a driver bootstrap
  downloads nothing) and *Sync now* re-checks registration before pushing.
- The owner's Deliveries screen showed two "My deliveries" headings (list and operator route);
  the operator route is now "My route".

## Reproduction

The commands are identical to `docs/phase-5/test-report.md` § Reproduction (backend, `npm run
check`, local API/web/storefront servers, `npm run e2e`). Set `OPENROUTESERVICE_API_KEY` to
exercise the online provider; without it the offline heuristic is used and labelled.

## Known limitations at the freeze

- The Google Maps fallback slot in D-060 is a configuration key only; no Google adapter is
  implemented or tested because no key exists. OpenRouteService is exercised through a mocked
  HTTP response in tests and through the real key on the live service.
- Geocoding of typed addresses is not part of Phase 7; `geocoded` is a stored provenance value
  the precedence rule already understands.
- The driver cache holds the *My Work* projection in browser storage for offline reading; the
  Dexie stores keep no driver data. Revocation locks the driver out on the next contact.
- One Chromium project on Windows.
