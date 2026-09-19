# Phase 6 test report

Report date: 2026-09-19 (P6-M5 freeze)

Every run below used a disposable local PostgreSQL 18 cluster on `127.0.0.1:55439`; the hosted
database is never used for tests.

## Final automated results

| Lane | Command | Result |
|---|---|---|
| Backend unit/integration | `pytest apps/api/tests -q` | **219 passed** (7 min 42 s) |
| Backend static | `ruff check`, `ruff format --check`, `mypy tawzeevo_api` | clean (81 source files) |
| Migration drift | `alembic check` at head `20260919_0024` | no new operations |
| Operations client | `eslint --max-warnings 0`, `tsc -b`, `vitest run`, `vite build` | **76 passed** (19 files), build OK |
| Storefront | unchanged in Phase 6 | 5 passed |
| Real-browser E2E (Chromium) | `npm run e2e --workspace=@tawzeevo/operations-web` | **5 passed**: Phase 3 critical flow, Phase 4 offline flow, Phase 5 storefront ×2, **Phase 6 procurement chain** |

Phase 6 test files: `test_supplier_profiles_prices.py` (3), `test_procurement.py` (4),
`test_supplier_purchases.py` (2), `test_sync_phase6.py` (2); `SupplierSetup.test.tsx`,
`ProcurementPanel.test.tsx` (2), `PurchasePanel.test.tsx`; `e2e/phase6-procurement-flow.spec.ts`.

## What the Phase 6 E2E proves (executed 2026-09-19, 5.9 s)

1. API setup: owner, product at 10 USD, supplier "Bekaa Dairy" with a 7.00 cost, one confirmed
   invoice of 6 pieces.
2. **Procurement** tab → *Build from confirmed demand*: one line, required 6, labelled estimate
   42.0000 USD, no stock column; the sole owner assigns the list to themself.
3. **Suppliers & costs** → *Record purchase*: choosing the list preloads the remaining 6; the
   owner records 4 at 7.20 → "28.8000 USD added to the supplier payable"; the totals block shows
   *Owed to suppliers · USD*; the price insight table shows the actual purchase.
4. **Procurement**: the list is *Partly purchased*, purchased 4, remaining 2.
5. **Supplier ledger**: a 50 USD payment is refused (D-039 cap), a 10 USD payment brings the
   payable to 18.8000; the totals API returns exactly one USD row, nothing summed across
   currencies.

## Reproduction

The commands are identical to `docs/phase-5/test-report.md` § Reproduction (backend, `npm run
check`, then the three local servers and `npm run e2e`). The backend suite truncates the
database; create the E2E administrator after it.

## Known limitations at the freeze

- Offline Phase 6 commands (price append, procurement target edit, purchase) queue on the
  device and apply exactly once on reconnect; the device keeps no local projection of
  suppliers, price history or procurement lists, so those screens need a connection to read.
  The change feed does carry supplier profiles for later local use.
- Supplier payments offline are supported by the protocol (`supplier_payment`) but the ledger
  panel has no offline fallback yet; it reports the network error.
- Estimates use the latest comparable price per supplier at read time; they are never stored and
  never booked.
- One Chromium project on Windows for the E2E lane.
