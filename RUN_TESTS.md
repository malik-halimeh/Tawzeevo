# Tawzeevo Unit Test Run Ledger

## Purpose

This is the living execution ledger for the testing strategy in `UNIT_TEST_STRATEGY.md`. Update it continuously as later milestones create tests.

This file records how to run each individual test from the repository root. It does not replace assertions in source control, CI output, or the PostgreSQL-backed Phase 1 test report.

## Strict update rules

1. Add one ledger row immediately for every new test function or parameterized test case.
2. Use the exact committed test file path and formal pytest node ID or Vitest test name.
3. Store a copy/paste-ready command that runs that specific test—not merely the whole suite.
4. Describe the observable behavior and boundary in one sentence.
5. Record `NOT RUN`, `PASS`, `FAIL`, or `SKIPPED` plus the last run date. Never record a skipped test as passed.
6. After running a complete file or milestone suite, append a validation-run entry below the ledger.
7. If a test is renamed, moved, parameterized, or removed, update its row in the same change.
8. Keep unit and PostgreSQL integration evidence distinct.
9. Never place secrets, environment values, access tokens, hosted database URLs, or private data in commands or descriptions.
10. Commands are run from the Tawzeevo repository root unless a row explicitly says otherwise.

## Exact command formats

The following are templates. Replace every `<...>` placeholder before adding a real ledger entry.

### Backend — one test file

```powershell
.\.venv\Scripts\python.exe -m pytest apps/api/tests/unit/<test_file>.py -m unit -q
```

### Backend — one test function/node

```powershell
.\.venv\Scripts\python.exe -m pytest "apps/api/tests/unit/<test_file>.py::<test_function_or_node_id>" -m unit -q
```

For a parameterized case, copy the exact node ID shown by pytest collection, including the case suffix:

```powershell
.\.venv\Scripts\python.exe -m pytest "apps/api/tests/unit/<test_file>.py::<test_function>[<case_id>]" -m unit -q
```

### Backend — all proposed unit tests

```powershell
.\.venv\Scripts\python.exe -m pytest apps/api/tests/unit -m unit -q
```

### Backend — unit coverage

```powershell
.\.venv\Scripts\python.exe -m pytest apps/api/tests/unit -m unit -q --cov=apps/api/tawzeevo_api --cov-report=term-missing
```

### Frontend — one test file

```powershell
npm exec --workspace @tawzeevo/operations-web -- vitest run "src/test/unit/<test_file>.unit.test.ts"
```

Use `.tsx` instead of `.ts` for React component tests.

### Frontend — one named test

```powershell
npm exec --workspace @tawzeevo/operations-web -- vitest run "src/test/unit/<test_file>.unit.test.tsx" -t "<exact test name>"
```

### Frontend — all proposed unit tests

```powershell
npm exec --workspace @tawzeevo/operations-web -- vitest run src/test/unit
```

### Required aggregate quality commands

```powershell
.\.venv\Scripts\python.exe -m ruff check apps/api/tawzeevo_api apps/api/tests/unit
.\.venv\Scripts\python.exe -m mypy apps/api/tawzeevo_api
npm run lint:operations
npm run typecheck:operations
npm run test:operations
npm run build:operations
```

The full backend integration command requires a deliberately disposable PostgreSQL database through `TEST_DATABASE_URL`; never run it against shared, staging, or production data:

```powershell
.\.venv\Scripts\python.exe -m pytest apps/api/tests -q
```

## Unit test ledger

| Milestone | Stack | Test file | Formal test node/function name | Exact terminal command | Behavior under test | Status / last run |
|---|---|---|---|---|---|---|
| P2-M2 | Pytest/PostgreSQL integration | `apps/api/tests/test_cash_van.py` | `test_customer_grades_locations_updates_and_duplicate_phone_disambiguation` | `.\.venv\Scripts\python.exe -m pytest "apps/api/tests/test_cash_van.py::test_customer_grades_locations_updates_and_duplicate_phone_disambiguation" -q` | Normalizes phone numbers, retains duplicate customer records, exposes disambiguating address/grade data, validates paired coordinates, updates a selected record, and denies cross-tenant update access. | PASS / 2026-08-25 |
| P2-M2 | Pytest/PostgreSQL integration | `apps/api/tests/test_cash_van.py` | `test_bilingual_category_order_master_link_archive_and_slug_invariants` | `.\.venv\Scripts\python.exe -m pytest "apps/api/tests/test_cash_van.py::test_bilingual_category_order_master_link_archive_and_slug_invariants" -q` | Verifies master/tenant category separation, bilingual names, normalized tenant-unique slugs, explicit ordering, archival retention, and rejection of new products in archived categories. | PASS / 2026-08-25 |
| P2-M2 | Pytest/PostgreSQL integration | `apps/api/tests/test_cash_van.py` | `test_authenticated_user_lists_only_their_tenant_contexts` | `.\.venv\Scripts\python.exe -m pytest "apps/api/tests/test_cash_van.py::test_authenticated_user_lists_only_their_tenant_contexts" -q` | Returns only the authenticated user's active tenant memberships with tenant status and membership role. | PASS / 2026-08-25 |
| P2-M2 | Vitest/jsdom component | `apps/operations-web/src/App.test.tsx` | `keeps duplicate phone matches separate and updates the selected customer` | `npm exec --workspace @tawzeevo/operations-web -- vitest run "src/App.test.tsx" -t "keeps duplicate phone matches separate and updates the selected customer"` | Renders duplicate phone matches as separate address/grade/ID cards and sends an update for the explicitly selected customer. | PASS / 2026-08-25 |
| P2-M2 | Vitest/jsdom component | `apps/operations-web/src/App.test.tsx` | `shows bilingual ordered categories, archives safely, and remains usable in RTL` | `npm exec --workspace @tawzeevo/operations-web -- vitest run "src/App.test.tsx" -t "shows bilingual ordered categories, archives safely, and remains usable in RTL"` | Displays bilingual ordered categories, archives without removing the row, and preserves Arabic RTL plus LTR slug controls. | PASS / 2026-08-25 |
| P2-M3 | Pytest/PostgreSQL integration | `apps/api/tests/test_cash_van.py` | `test_known_master_barcode_scans_then_adopts_with_tenant_price_and_publication` | `.\.venv\Scripts\python.exe -m pytest "apps/api/tests/test_cash_van.py::test_known_master_barcode_scans_then_adopts_with_tenant_price_and_publication" -q` | Resolves a globally owned master barcode, adopts its product exactly once for a tenant, returns every package barcode with tenant price, and treats publication only as visibility. | PASS / 2026-08-25 |
| P2-M3 | Pytest/PostgreSQL integration | `apps/api/tests/test_cash_van.py` | `test_unknown_barcode_manual_product_extra_package_barcode_and_visibility_update` | `.\.venv\Scripts\python.exe -m pytest "apps/api/tests/test_cash_van.py::test_unknown_barcode_manual_product_extra_package_barcode_and_visibility_update" -q` | Converts an unknown scan into a manual tenant product, adds a package-level tenant barcode, toggles publication, permits tenant-local barcode namespaces, and denies cross-tenant access. | PASS / 2026-08-25 |
| P2-M3 | Pytest/PostgreSQL integration | `apps/api/tests/test_hardening.py` | `test_postgresql_rls_enforces_tenant_visibility_and_write_checks` | `.\.venv\Scripts\python.exe -m pytest "apps/api/tests/test_hardening.py::test_postgresql_rls_enforces_tenant_visibility_and_write_checks" -q` | Uses a non-bypass PostgreSQL role to prove tenant barcode reads are filtered and cross-tenant barcode inserts are rejected by RLS. | PASS / 2026-08-25 |
| P2-M3 | Vitest/jsdom component | `apps/operations-web/src/App.test.tsx` | `scans a known master barcode and adopts it with tenant price and visibility` | `npm exec --workspace @tawzeevo/operations-web -- vitest run "src/App.test.tsx" -t "scans a known master barcode and adopts it with tenant price and visibility"` | Prefills a known master identity after scan and submits the selected tenant category, tenant price, and publication visibility. | PASS / 2026-08-25 |
| P2-M3 | Vitest/jsdom component | `apps/operations-web/src/App.test.tsx` | `turns an unknown scan into a manual product and adds a package barcode` | `npm exec --workspace @tawzeevo/operations-web -- vitest run "src/App.test.tsx" -t "turns an unknown scan into a manual product and adds a package barcode"` | Prefills a manual product from an unknown scan and adds a second tenant-owned box barcode through the UI. | PASS / 2026-08-25 |
| P2-M4 | Pytest/PostgreSQL integration | `apps/api/tests/test_cash_van.py` | `test_pricing_v1_precedence_rounding_packaging_and_invoice_snapshot` | `.\.venv\Scripts\python.exe -m pytest "apps/api/tests/test_cash_van.py::test_pricing_v1_precedence_rounding_packaging_and_invoice_snapshot" -q` | Proves explicit grade price precedence over discount and normal price, four-decimal half-up rounding, piece/box derivation, immutable draft-invoice selling-price snapshots, reset protection, and cross-tenant denial. | PASS / 2026-08-26 |
| P2-M4 | Pytest/PostgreSQL integration | `apps/api/tests/test_cash_van.py` | `test_product_image_upload_reencodes_and_scan_returns_tenant_image` | `.\.venv\Scripts\python.exe -m pytest "apps/api/tests/test_cash_van.py::test_product_image_upload_reencodes_and_scan_returns_tenant_image" -q` | Uploads PNG through provider-neutral storage, verifies WebP re-encoding and authenticated scan/image retrieval, rejects SVG and spoofed input, and denies cross-tenant image access. | PASS / 2026-08-26 |
| P2-M4 | Vitest/jsdom component | `apps/operations-web/src/App.test.tsx` | `manages grade pricing and uploads an authenticated product image` | `npm exec --workspace @tawzeevo/operations-web -- vitest run "src/App.test.tsx" -t "manages grade pricing and uploads an authenticated product image"` | Submits a grade discount, explicit product-grade price, and multipart image without overriding the browser boundary, then renders the authenticated blob image. | PASS / 2026-08-26 |
<!-- Add one row per real test. Do not add example or fictional completed rows. -->

## Milestone summary

| Milestone | Scope | Status | Tests added | Last validation |
|---|---|---:|---:|---|
| UT-M0 | Harness separation and baseline | NOT STARTED | 0 | — |
| UT-M1 | Pure normalization, schemas, dates, and money | NOT STARTED | 0 | — |
| UT-M2 | Security, authentication decisions, and cookies | NOT STARTED | 0 | — |
| UT-M3 | User and tenant lifecycle decisions | NOT STARTED | 0 | — |
| UT-M4 | Cash Van catalog and draft-invoice rules | NOT STARTED | 0 | — |
| UT-M5 | Frontend API, authentication, and guards | NOT STARTED | 0 | — |
| UT-M6 | Frontend query/payload, errors, CLI, and residual gaps | NOT STARTED | 0 | — |
| UT-M7 | Final gap review and stable execution contract | NOT STARTED | 0 | — |

## Validation-run log

Append one entry after each file-level or milestone-level run:

```markdown
### <YYYY-MM-DD HH:MM timezone> — <milestone or scope>

- Command: `<exact command>`
- Result: `PASS | FAIL | SKIPPED`
- Counts: `<passed/failed/skipped counts>`
- Environment: `unit/no database | disposable PostgreSQL | jsdom`
- Notes: `<failure reason, coverage observation, or none>`
```

### 2026-08-25 09:41 Asia/Beirut — P2-M2 backend acceptance

- Command: `.\.venv\Scripts\python.exe -m pytest apps/api/tests -q --cov=tawzeevo_api --cov-report=term-missing --cov-fail-under=80`
- Result: `PASS`
- Counts: `83 passed, 0 failed; 93% coverage`
- Environment: `disposable PostgreSQL 18`
- Notes: `Includes migration-from-zero, non-bypass RLS, membership lifecycle, customer, grade, location, and category coverage.`

### 2026-08-25 09:44 Asia/Beirut — P2-M2 frontend acceptance

- Command: `npm run check`
- Result: `PASS`
- Counts: `24 passed, 0 failed; production build 208 modules`
- Environment: `jsdom and Vite production build`
- Notes: `Lint, strict TypeScript, component tests, responsive/RTL contracts, and build passed; Vite emitted only its non-blocking chunk-size advisory.`

### 2026-08-25 13:19 Asia/Beirut — P2-M3 backend acceptance

- Command: `.\.venv\Scripts\python.exe -m pytest apps/api/tests -q --cov=tawzeevo_api --cov-report=term-missing --cov-fail-under=80`
- Result: `PASS`
- Counts: `85 passed, 0 failed; 93% coverage`
- Environment: `disposable PostgreSQL 18`
- Notes: `Includes from-zero migration, legacy-barcode upgrade/downgrade proof, explicit master/tenant barcode ownership, scan/adoption/manual-product flows, cross-tenant API denial, and non-bypass-role RLS.`

### 2026-08-25 13:16 Asia/Beirut — P2-M3 frontend acceptance

- Command: `npm run check`
- Result: `PASS`
- Counts: `26 passed, 0 failed; production build 208 modules`
- Environment: `jsdom and Vite production build`
- Notes: `Lint, strict TypeScript, known/unknown barcode component flows, responsive bilingual UI, and build passed; Vite emitted only its non-blocking chunk-size advisory.`

### 2026-08-26 03:04 Asia/Beirut — P2-M4 backend acceptance

- Command: `.\.venv\Scripts\python.exe -m pytest apps/api/tests -q --cov=tawzeevo_api --cov-report=term-missing --cov-fail-under=80`
- Result: `PASS`
- Counts: `87 passed, 0 failed; 93% coverage`
- Environment: `disposable PostgreSQL 18`
- Notes: `Includes from-zero migration, downgrade/upgrade, pricing-v1 precedence and exact rounding, invoice selling-price snapshots, media validation/re-encoding, cross-tenant API denial, and non-bypass-role RLS for pricing tables.`

### 2026-08-26 03:05 Asia/Beirut — P2-M4 frontend acceptance

- Command: `npm run check`
- Result: `PASS`
- Counts: `27 passed, 0 failed; production build 208 modules`
- Environment: `jsdom and Vite production build`
- Notes: `Lint, strict TypeScript, grade-pricing controls, multipart image upload, authenticated blob rendering, bilingual responsive UI, and build passed; Vite emitted only its non-blocking chunk-size advisory.`
