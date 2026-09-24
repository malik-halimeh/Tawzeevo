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

> **Layout note (2026-09-21).** The backend suite lives flat under `apps/api/tests/` (there is no
> `apps/api/tests/unit/` directory and no `unit` pytest marker; `pyproject.toml` declares only
> `integration`). Every backend test runs from `apps/api` with `TEST_DATABASE_URL` pointing at a
> disposable PostgreSQL database, e.g.
> `python -m pytest tests/<test_file>.py -q -p no:cacheprovider`. The canonical, executed commands
> are `.github/workflows/ci.yml` and `docs/phase-N/test-report.md`; the templates below are kept
> as the historical ledger format and are superseded where they disagree.

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
.\.venv\Scripts\python.exe -m ruff check apps/api
.\.venv\Scripts\python.exe -m ruff format --check apps/api
.\.venv\Scripts\python.exe -m mypy --config-file apps/api/pyproject.toml apps/api/tawzeevo_api
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
| P2-M4 | Pytest/PostgreSQL integration | `apps/api/tests/test_cash_van.py` | `test_pricing_v1_precedence_rounding_packaging_and_invoice_snapshot` | `.\.venv\Scripts\python.exe -m pytest "apps/api/tests/test_cash_van.py::test_pricing_v1_precedence_rounding_packaging_and_invoice_snapshot" -q` | Proves explicit grade price precedence over discount and normal price, true four-decimal half-up tie behavior, independently rounded piece/box derivation, immutable explicit and discounted draft-invoice selling-price snapshots, reset protection, and cross-tenant denial. | PASS / 2026-08-26 |
| P2-M4 | Pytest/PostgreSQL integration | `apps/api/tests/test_cash_van.py` | `test_product_image_upload_reencodes_and_scan_returns_tenant_image` | `.\.venv\Scripts\python.exe -m pytest "apps/api/tests/test_cash_van.py::test_product_image_upload_reencodes_and_scan_returns_tenant_image" -q` | Uploads PNG through provider-neutral storage, verifies WebP re-encoding and authenticated scan/image retrieval, rejects SVG, spoofed input, excessive bytes, and excessive dimensions, and denies cross-tenant image access. | PASS / 2026-08-26 |
| P2-M4 | Pytest/PostgreSQL integration | `apps/api/tests/test_cash_van.py` | `test_media_processor_accepts_supported_formats_and_storage_blocks_traversal` | `.\.venv\Scripts\python.exe -m pytest "apps/api/tests/test_cash_van.py::test_media_processor_accepts_supported_formats_and_storage_blocks_traversal" -q` | Verifies that valid JPEG, PNG, and WebP inputs are decoded and re-encoded as WebP and that the local provider adapter cannot write through a path-traversal key. | PASS / 2026-08-26 |
| P2-M4 | Vitest/jsdom component | `apps/operations-web/src/App.test.tsx` | `manages grade pricing and uploads an authenticated product image` | `npm exec --workspace @tawzeevo/operations-web -- vitest run "src/App.test.tsx" -t "manages grade pricing and uploads an authenticated product image"` | Submits a grade discount, explicit product-grade price, and multipart image without overriding the browser boundary, then renders the authenticated blob image. | PASS / 2026-08-26 |
| P2-M5 | Pytest/PostgreSQL integration | `apps/api/tests/test_catalog_import.py` | `test_catalog_quality_gate_reports_invalid_and_duplicate_gtins` | `.\.venv\Scripts\python.exe -m pytest "apps/api/tests/test_catalog_import.py::test_catalog_quality_gate_reports_invalid_and_duplicate_gtins" -q` | Verifies the committed snapshot passes and that invalid GTIN check digits and duplicate barcodes produce a deterministic failed quality report. | PASS / 2026-08-26 |
| P2-M5 | Pytest/PostgreSQL integration | `apps/api/tests/test_catalog_import.py` | `test_catalog_import_persists_provenance_is_idempotent_and_rolls_back_conflicts` | `.\.venv\Scripts\python.exe -m pytest "apps/api/tests/test_catalog_import.py::test_catalog_import_persists_provenance_is_idempotent_and_rolls_back_conflicts" -q` | Persists import/source/revision/checksum provenance, proves exact replay is a no-op, and rolls back version or existing-identity conflicts without partial data. | PASS / 2026-08-26 |
| P2-M5 | Pytest/PostgreSQL integration | `apps/api/tests/test_catalog_import.py` | `test_catalog_cli_check_only_writes_quality_report_without_database_changes` | `.\.venv\Scripts\python.exe -m pytest "apps/api/tests/test_catalog_import.py::test_catalog_cli_check_only_writes_quality_report_without_database_changes" -q` | Exercises CLI check-only mode, writes the machine-readable report, and proves validation makes no database changes. | PASS / 2026-08-26 |
| P2-M5 | Pytest/PostgreSQL integration | `apps/api/tests/test_cash_van.py` | `test_imported_catalog_scan_returns_tenant_image_price_and_isolated_grade_pricing` | `.\.venv\Scripts\python.exe -m pytest "apps/api/tests/test_cash_van.py::test_imported_catalog_scan_returns_tenant_image_price_and_isolated_grade_pricing" -q` | Imports a licensed master barcode, resolves its name, independently adopts it for two tenants at different prices, returns only the owning tenant's image, applies tenant-specific grade pricing, and denies cross-tenant product access. | PASS / 2026-08-26 |
| P3-M1 | Pytest/PostgreSQL integration | `apps/api/tests/test_financial_schema.py` | `test_financial_schema_is_canonical_numeric_and_database_immutable` | `.\.venv\Scripts\python.exe -m pytest "apps/api/tests/test_financial_schema.py::test_financial_schema_is_canonical_numeric_and_database_immutable" -q` | Proves totals moved off the invoice header, financial values use NUMERIC(20,4), and every append-only financial table has a database immutability trigger. | PASS / 2026-08-26 |
| P3-M1 | Pytest/PostgreSQL integration | `apps/api/tests/test_financial_schema.py` | `test_supplier_costs_are_tenant_private_append_only_and_independently_priced` | `.\.venv\Scripts\python.exe -m pytest "apps/api/tests/test_financial_schema.py::test_supplier_costs_are_tenant_private_append_only_and_independently_priced" -q` | Stores different costs for the same supplier/product concept in separate tenants, rejects cross-tenant supplier binding, and rejects mutation of an existing cost entry. | PASS / 2026-08-26 |
| P3-M1 | Pytest/PostgreSQL integration | `apps/api/tests/test_financial_schema.py` | `test_financial_rls_filters_costs_and_blocks_cross_tenant_writes` | `.\.venv\Scripts\python.exe -m pytest "apps/api/tests/test_financial_schema.py::test_financial_rls_filters_costs_and_blocks_cross_tenant_writes" -q` | Uses a real non-bypass PostgreSQL role to prove tenant supplier/cost reads are filtered and cross-tenant inserts are rejected by RLS. | PASS / 2026-08-26 |
| P3-M1 | Pytest/PostgreSQL integration | `apps/api/tests/test_financial_schema.py` | `test_invoice_order_cardinality_and_cost_snapshot_survive_later_cost_change` | `.\.venv\Scripts\python.exe -m pytest "apps/api/tests/test_financial_schema.py::test_invoice_order_cardinality_and_cost_snapshot_survive_later_cost_change" -q` | Enforces one invoice header per order, preserves a $2.0000 invoice cost snapshot after a later $2.2000 entry, rejects revision mutation, and requires a reason for cost overrides. | PASS / 2026-08-26 |
| P3-M1 | Pytest/PostgreSQL integration | `apps/api/tests/test_financial_schema.py` | `test_phase2_draft_rows_upgrade_to_revisions_and_round_trip` | `.\.venv\Scripts\python.exe -m pytest "apps/api/tests/test_financial_schema.py::test_phase2_draft_rows_upgrade_to_revisions_and_round_trip" -q` | Migrates real Phase 2 draft invoice/item rows into canonical revisions, restores them on downgrade, and re-upgrades without losing values. | PASS / 2026-08-26 |
| P3-M2 | Pytest/PostgreSQL integration | `apps/api/tests/test_invoice_editor.py` | `test_editor_recalculates_pricing_v1_calculator_adjustments_and_immutable_updates` | `uv --system-certs run --extra dev pytest "tests/test_invoice_editor.py::test_editor_recalculates_pricing_v1_calculator_adjustments_and_immutable_updates" -q` (from `apps/api`) | Reproduces pricing-v1 grade precedence, calculator quantities, line/invoice adjustments, prior-balance separation, backend totals, deterministic line order, immutable draft revisions, and stale-predecessor rejection. | PASS / 2026-08-27 |
| P3-M2 | Pytest/PostgreSQL integration | `apps/api/tests/test_invoice_editor.py` | `test_text_parser_is_exact_first_and_never_auto_selects_fuzzy_or_ambiguous_matches` | `uv --system-certs run --extra dev pytest "tests/test_invoice_editor.py::test_text_parser_is_exact_first_and_never_auto_selects_fuzzy_or_ambiguous_matches" -q` (from `apps/api`) | Normalizes Arabic digits/text, extracts quantity, preserves package-level barcode identity, resolves a unique exact match, leaves exact duplicates and fuzzy results unselected, and keeps normal search prefix-first. | PASS / 2026-08-27 |
| P3-M2 | Pytest/PostgreSQL integration | `apps/api/tests/test_invoice_editor.py` | `test_accepted_fuzzy_match_is_audited_and_owner_finance_is_tenant_protected` | `uv --system-certs run --extra dev pytest "tests/test_invoice_editor.py::test_accepted_fuzzy_match_is_audited_and_owner_finance_is_tenant_protected" -q` (from `apps/api`) | Audits an owner-confirmed fuzzy match with a server-recomputed score and denies driver and cross-tenant access to invoice finance. | PASS / 2026-08-27 |
| P3-M2 | Pytest/PostgreSQL integration | `apps/api/tests/test_invoice_editor.py` | `test_editor_prefills_latest_tenant_cost_and_keeps_reasoned_override_revision_only` | `uv --system-certs run --extra dev pytest "tests/test_invoice_editor.py::test_editor_prefills_latest_tenant_cost_and_keeps_reasoned_override_revision_only" -q` (from `apps/api`) | Returns tenant-only supplier cost options, prefills the preferred supplier's latest eligible cost, and snapshots a reasoned owner override without changing the append-only source cost. | PASS / 2026-08-27 |
| P3-M2 | Pytest/PostgreSQL integration | `apps/api/tests/test_invoice_editor.py` | `test_editor_rejects_mixed_currency_package_mismatch_and_unsafe_calculator` | `uv --system-certs run --extra dev pytest "tests/test_invoice_editor.py::test_editor_rejects_mixed_currency_package_mismatch_and_unsafe_calculator" -q` (from `apps/api`) | Rejects mixed currency, barcode/package disagreement, and non-arithmetic calculator input while accepting Arabic-digit arithmetic with exact Q4 output. | PASS / 2026-08-27 |
| P3-M2 / P3-M3 | Vitest/jsdom component | `apps/operations-web/src/components/InvoiceEditor.test.tsx` | `owner confirms an ambiguous suggestion, saves a draft, and confirms its official number` | `npm exec --workspace @tawzeevo/operations-web -- vitest run "src/components/InvoiceEditor.test.tsx" -t "owner confirms an ambiguous suggestion, saves a draft, and confirms its official number"` | Proves the bilingual owner UI does not add an ambiguous parser result before confirmation, sends the accepted fuzzy payload, renders server totals, confirms through the real API contract, and displays the official number. | PASS / 2026-08-27 |
| P3-M3 | Pytest/PostgreSQL integration | `apps/api/tests/test_invoice_editor.py` | `test_confirmation_is_idempotent_assigns_official_number_and_posts_one_charge` | `uv --system-certs run --extra dev pytest "tests/test_invoice_editor.py::test_confirmation_is_idempotent_assigns_official_number_and_posts_one_charge" -q` (from `apps/api`) | Confirms atomically, assigns the first tenant/year official number, posts one invoice charge, and proves replay does not allocate or post again. | PASS / 2026-08-27 |
| P3-M3 | Pytest/PostgreSQL integration | `apps/api/tests/test_invoice_editor.py` | `test_post_confirmation_revision_posts_exact_delta_and_keeps_old_balance_out_of_sales` | `uv --system-certs run --extra dev pytest "tests/test_invoice_editor.py::test_post_confirmation_revision_posts_exact_delta_and_keeps_old_balance_out_of_sales" -q` (from `apps/api`) | Creates immutable confirmed revisions, posts exact negative and zero deltas, preserves history, and proves opening balance remains outside net sales while total due reconciles. | PASS / 2026-08-27 |
| P3-M3 | Pytest/PostgreSQL integration | `apps/api/tests/test_invoice_editor.py` | `test_opening_balance_balance_api_overdue_alert_dedup_and_owner_security` | `uv --system-certs run --extra dev pytest "tests/test_invoice_editor.py::test_opening_balance_balance_api_overdue_alert_dedup_and_owner_security" -q` (from `apps/api`) | Proves opening-balance replay idempotency, per-currency balances, owner-configured overdue age, stable customer/currency alert deduplication, and driver denial. | PASS / 2026-08-27 |
| P3-M3 | Pytest/PostgreSQL integration | `apps/api/tests/test_invoice_editor.py` | `test_invoice_sequence_is_serialized_per_tenant_and_year_under_concurrency` | `uv --system-certs run --extra dev pytest "tests/test_invoice_editor.py::test_invoice_sequence_is_serialized_per_tenant_and_year_under_concurrency" -q` (from `apps/api`) | Confirms two invoices concurrently and proves PostgreSQL row locking issues unique sequential official numbers in one tenant/year scope. | PASS / 2026-08-27 |
| P3-M3 | Pytest/PostgreSQL integration | `apps/api/tests/test_invoice_editor.py` | `test_downward_confirmed_edit_releases_excess_allocation_without_mutating_payment` | `uv --system-certs run --extra dev pytest "tests/test_invoice_editor.py::test_downward_confirmed_edit_releases_excess_allocation_without_mutating_payment" -q` (from `apps/api`) | Lowers a confirmed invoice below its allocated amount, appends reversal/residual allocation effects to match the new value exactly, and leaves the original payment immutable. | PASS / 2026-08-27 |
| P3-M3 | Vitest/jsdom component | `apps/operations-web/src/components/InvoiceEditor.test.tsx` | `debt desk marks an overdue customer with text and a non-color alert mark` | `npm exec --workspace @tawzeevo/operations-web -- vitest run "src/components/InvoiceEditor.test.tsx" -t "debt desk marks an overdue customer with text and a non-color alert mark"` | Renders the overdue balance in the owner debt register with explicit overdue text and a visible alert mark so meaning is not conveyed by red alone. | PASS / 2026-08-27 |
| P3-M4 | Pytest/PostgreSQL integration | `apps/api/tests/test_invoice_editor.py` | `test_receipt_fifo_owner_allocation_partial_multi_obligation_and_reversal_are_immutable` | `uv --system-certs run --extra dev pytest "tests/test_invoice_editor.py::test_receipt_fifo_owner_allocation_partial_multi_obligation_and_reversal_are_immutable" -q` (from `apps/api`) | Records one replay-safe receipt across multiple obligations FIFO, records a partial owner-selected allocation with unallocated credit, and reverses it through compensating payment, ledger, and allocation rows without mutating the original. | PASS / 2026-08-27 |
| P3-M4 | Pytest/PostgreSQL integration | `apps/api/tests/test_invoice_editor.py` | `test_cancellation_preserves_payment_releases_credit_and_refund_ceiling_is_concurrent` | `uv --system-certs run --extra dev pytest "tests/test_invoice_editor.py::test_cancellation_preserves_payment_releases_credit_and_refund_ceiling_is_concurrent" -q` (from `apps/api`) | Cancels a partially paid confirmed invoice, preserves the receipt, reverses allocations into credit, proves cancellation replay is harmless, and proves two concurrent refunds cannot spend the same credit. | PASS / 2026-08-27 |
| P3-M4 | Pytest/PostgreSQL integration | `apps/api/tests/test_invoice_editor.py` | `test_unconfirmed_cancellation_has_no_financial_effect` | `uv --system-certs run --extra dev pytest "tests/test_invoice_editor.py::test_unconfirmed_cancellation_has_no_financial_effect" -q` (from `apps/api`) | Cancels a draft while preserving its provisional revision and proves no customer-ledger reversal or charge is invented. | PASS / 2026-08-27 |
| P3-M4 | Pytest/PostgreSQL integration | `apps/api/tests/test_invoice_editor.py` | `test_confirmed_cancellation_matrix_handles_unpaid_and_fully_paid_invoices` | `uv --system-certs run --extra dev pytest "tests/test_invoice_editor.py::test_confirmed_cancellation_matrix_handles_unpaid_and_fully_paid_invoices" -q` (from `apps/api`) | Covers confirmed unpaid and fully paid cancellation: invoice value reaches zero, full-payment money remains immutable as customer credit, and no payment is deleted. | PASS / 2026-08-27 |
| P3-M4 | Pytest/PostgreSQL integration | `apps/api/tests/test_invoice_editor.py` | `test_confirmed_revision_rejects_zero_net_sales_and_cancellation_compensates` | `uv --system-certs run --extra dev pytest "tests/test_invoice_editor.py::test_confirmed_revision_rejects_zero_net_sales_and_cancellation_compensates" -q` (from `apps/api`) | Refuses a zero-value confirmed revision, then cancels the confirmed invoice and proves the compensating reversal remains explicit and immutable (the row cited a test name that never existed until corrected on 2026-09-21). | PASS / 2026-08-27 |
| P3-M4 | Vitest/jsdom component | `apps/operations-web/src/components/InvoiceEditor.test.tsx` | `owner records a selected receipt allocation and can reverse the immutable receipt` | `npm exec --workspace @tawzeevo/operations-web -- vitest run "src/components/InvoiceEditor.test.tsx" -t "owner records a selected receipt allocation and can reverse the immutable receipt"` | Uses the owner settlement desk to choose an obligation amount, record a partial receipt with unallocated value, inspect the payment slip, and submit a reasoned receipt reversal. | PASS / 2026-08-27 |
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

### 2026-08-26 03:28 Asia/Beirut — P2-M4 independent re-audit

- Command: `.\.venv\Scripts\python.exe -m pytest apps/api/tests -q --cov=tawzeevo_api --cov-report=term-missing --cov-fail-under=80`
- Result: `PASS`
- Counts: `88 passed, 0 failed; 93% coverage`
- Environment: `fresh disposable PostgreSQL 18 migrated from zero to 20260826_0006`
- Notes: `Re-audit strengthened the acceptance proof with true ROUND_HALF_UP tie cases, discounted-invoice provenance preservation, all three permitted upload formats, byte and dimension limits, and local-storage traversal rejection. Alembic drift check, Ruff lint/format, configured strict mypy, full frontend check, and production build also passed.`

### 2026-08-26 11:10 Asia/Beirut — P2-M5 and Phase 2 acceptance

- Command: `.\.venv\Scripts\python.exe -m pytest apps/api/tests -q --cov=tawzeevo_api --cov-report=term-missing --cov-fail-under=80`
- Result: `PASS`
- Counts: `92 passed, 0 failed; 93% coverage`
- Environment: `disposable PostgreSQL 18`
- Notes: `Includes from-zero migration to 20260826_0007, catalog quality/provenance/idempotency/conflict rollback, imported scan-to-name/image/tenant-price, full tenant isolation, pricing-v1, and all earlier Phase 1/2 regressions. Manual 0007 downgrade/upgrade and Alembic drift check passed. Ruff lint/format, strict configured mypy, 27 frontend tests, and the 208-module production build passed.`

### 2026-08-26 23:50 Asia/Beirut — P3-M1 financial schema acceptance

- Command: `.\.venv\Scripts\python.exe -m pytest apps/api/tests -q --cov=tawzeevo_api --cov-report=term-missing --cov-fail-under=80`
- Result: `PASS`
- Counts: `97 passed, 0 failed; 93% coverage`
- Environment: `fresh disposable PostgreSQL 18 migrated from zero to 20260826_0008`
- Notes: `Includes canonical revision source-of-truth, immutable-row triggers, one-order/one-invoice cardinality, tenant-private supplier costs, historical cost snapshots, non-bypass RLS, Phase 2 data upgrade/downgrade/re-upgrade, and all earlier regressions. Alembic drift, Ruff lint/format, strict mypy, 27 frontend tests, and the 208-module production build passed.`

### 2026-08-27 11:09 Asia/Beirut — P3-M2 invoice editor acceptance

- Command: `uv --system-certs run --extra dev pytest -q --cov=tawzeevo_api --cov-report=term` (from `apps/api`, with `TEST_DATABASE_URL` targeting the disposable database)
- Result: `PASS`
- Counts: `102 passed, 0 failed; 92% coverage`
- Environment: `disposable PostgreSQL 18`
- Notes: `Includes pricing-v1 reconstruction, prior-balance separation, immutable draft revisions, deterministic line ordering, customer/barcode/manual entry, Arabic/English parsing, exact-first/fuzzy-second confirmation and audit, owner/tenant security, tenant-private cost prefilling/override, from-zero migration, and all earlier regressions.`

### 2026-08-27 11:06 Asia/Beirut — P3-M2 frontend acceptance

- Command: `npm run lint; npm run typecheck; npm run test -- --run; npm run build` (from `apps/operations-web`)
- Result: `PASS`
- Counts: `28 passed, 0 failed; production build 209 modules`
- Environment: `jsdom and Vite production build`
- Notes: `The real API-backed EN/AR invoice counter passed strict TypeScript, ESLint, component tests, responsive/RTL implementation checks, and production build. Vite emitted only its existing non-blocking chunk-size advisory.`

### 2026-08-27 15:37 Asia/Beirut — P3-M3 confirmation, ledger, and debt acceptance

- Command: `uv --system-certs run --extra dev pytest -q --cov=tawzeevo_api --cov-report=term --cov-fail-under=80` (from `apps/api`, with `TEST_DATABASE_URL` targeting the disposable database)
- Result: `PASS`
- Counts: `107 passed, 0 failed; 92% coverage`
- Environment: `disposable PostgreSQL 18`
- Notes: `Includes confirmation replay, tenant/year sequence concurrency, exact post-confirm ledger deltas, immutable history, downward allocation release, opening balances, per-currency balances, overdue alert deduplication, owner security, from-zero migration, 0010 downgrade/re-upgrade, Alembic drift, and all earlier regressions.`

### 2026-08-27 15:37 Asia/Beirut — P3-M3 frontend acceptance

- Command: `npm run lint; npm run typecheck; npm test -- --run; npm run build` (from `apps/operations-web`, fail-fast)
- Result: `PASS`
- Counts: `29 passed, 0 failed; production build 209 modules`
- Environment: `jsdom and Vite production build`
- Notes: `The owner invoice counter now demonstrates confirmation, official numbering, immutable history, balance entry, overdue threshold, and non-color-only red debt alerts in EN/AR and RTL. Vite emitted only its existing non-blocking chunk-size advisory.`

### 2026-08-27 17:40 Asia/Beirut — P3-M4 payment and cancellation acceptance

- Command: `uv --system-certs run --extra dev pytest -q --cov=tawzeevo_api --cov-report=term --cov-fail-under=80` (from `apps/api`, with `TEST_DATABASE_URL` targeting the disposable database)
- Result: `PASS`
- Counts: `113 passed, 0 failed; 92% coverage`
- Environment: `disposable PostgreSQL 18`
- Notes: `Includes FIFO and owner-selected allocation, partial/multi-obligation receipts, replay protection, immutable receipt/allocation reversal, draft and confirmed unpaid/partial/full/zero-value cancellation, preserved payments, serialized refund ceiling concurrency, from-zero migration coverage, 0011 downgrade/re-upgrade, Alembic drift, and all earlier regressions.`

### 2026-08-27 17:40 Asia/Beirut — P3-M4 frontend acceptance

- Command: `npm run lint; npm run typecheck; npm test -- --run; npm run build` (from `apps/operations-web`, fail-fast)
- Result: `PASS`
- Counts: `30 passed, 0 failed; production build 209 modules`
- Environment: `jsdom and Vite production build`
- Notes: `The EN/AR owner settlement desk demonstrates FIFO/selected allocations, receipts, unallocated credit, reversal, server-limited refunds, and cancellation actions with responsive RTL-safe controls. Vite emitted only its existing non-blocking chunk-size advisory.`

## P3-M5 — Individual test ledger (2026-09-05)

Run these commands from the repository root after installing the existing development dependencies.
Backend commands require `TEST_DATABASE_URL` and `DATABASE_URL` pointing to the same disposable,
migrated PostgreSQL database. The tests truncate data: never use a shared or production database.
Each row identifies one test; the full-suite acceptance result is recorded below separately.

| Formal test file / case | Exact command | Behavior |
|---|---|---|
| `apps/api/tests/test_public_invoices.py::test_capability_projection_current_revision_privacy_and_no_stored_secret` | `.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_public_invoices.py::test_capability_projection_current_revision_privacy_and_no_stored_secret -q` | Checks the public allowlist, current revision, privacy headers and hash-only capability persistence. |
| `apps/api/tests/test_public_invoices.py::test_capability_rotation_expiry_revocation_and_uniform_invalid_access` | `.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_public_invoices.py::test_capability_rotation_expiry_revocation_and_uniform_invalid_access -q` | Checks replacement/revocation/expiry and uniform denial for invalid tokens/internal IDs. |
| `apps/api/tests/test_public_invoices.py::test_capability_owner_authority_tenant_hint_and_suspension` | `.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_public_invoices.py::test_capability_owner_authority_tenant_hint_and_suspension -q` | Rejects non-owner/cross-tenant management, altered tenant hints and suspended tenants. |
| `apps/api/tests/test_public_invoices.py::test_capability_rotation_is_serialized` | `.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_public_invoices.py::test_capability_rotation_is_serialized -q` | Concurrent replacement permits one successor for the old capability. |
| `apps/api/tests/test_public_invoices.py::test_public_capability_resolves_under_forced_rls_without_bypass` | `.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_public_invoices.py::test_public_capability_resolves_under_forced_rls_without_bypass -q` | Resolves the authorized invoice using a non-bypass database role with forced RLS. |
| `apps/api/tests/test_public_invoices.py::test_public_rate_limit_and_access_log_redaction` | `.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_public_invoices.py::test_public_rate_limit_and_access_log_redaction -q` | Checks bounded rate limiting, 429 privacy headers and emitted access-log redaction. |
| `apps/api/tests/test_public_invoices.py::test_public_unexpected_failure_is_private_and_does_not_log_token` | `.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_public_invoices.py::test_public_unexpected_failure_is_private_and_does_not_log_token -q` | Unexpected resolver errors return a generic private response without exposing the token. |
| `apps/api/tests/test_supplier_ledger.py::test_supplier_payment_aggregate_balance_replay_reversal_and_currency` | `.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_supplier_ledger.py::test_supplier_payment_aggregate_balance_replay_reversal_and_currency -q` | Checks aggregate per-currency payable, replay, compensating reversal, immutability and no purchase allocations. |
| `apps/api/tests/test_supplier_ledger.py::test_supplier_cross_tenant_rejected_and_reversal_serialized` | `.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_supplier_ledger.py::test_supplier_cross_tenant_rejected_and_reversal_serialized -q` | Checks tenant/owner authorization and concurrent reversal serialization. |
| `apps/api/tests/test_supplier_ledger.py::test_supplier_payment_schema_rejects_allocations_and_naive_timestamps` | `.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_supplier_ledger.py::test_supplier_payment_schema_rejects_allocations_and_naive_timestamps -q` | Rejects allocation fields and timestamps without timezones. |
| `apps/api/tests/test_supplier_ledger.py::test_supplier_ledger_forced_rls_hides_other_tenant_and_rejects_insert` | `.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_supplier_ledger.py::test_supplier_ledger_forced_rls_hides_other_tenant_and_rejects_insert -q` | Checks non-bypass forced-RLS read isolation and cross-tenant insert rejection. |
| `InvoiceSharing.test.tsx` — owner creates, shares, rotates and revokes a private invoice link without storing the secret | `npm exec --workspace @tawzeevo/operations-web -- vitest run src/components/InvoiceSharing.test.tsx -t "owner creates, shares, rotates and revokes a private invoice link without storing the secret"` | Checks owner controls, normalized WhatsApp URL, replacement/revocation and unchanged local storage. |
| `InvoiceSharing.test.tsx` — invoice sharing supports Arabic labels and reports request failures | `npm exec --workspace @tawzeevo/operations-web -- vitest run src/components/InvoiceSharing.test.tsx -t "invoice sharing supports Arabic labels and reports request failures"` | Checks Arabic sharing controls and visible API errors. |
| `PublicInvoicePage.test.ts` — public invoice uses a secret header, safe text rendering, and Arabic RTL | `npm exec --workspace @tawzeevo/operations-web -- vitest run src/components/PublicInvoicePage.test.ts -t "public invoice uses a secret header, safe text rendering, and Arabic RTL"` | Executes the committed public HTML script; checks fragment removal, secret header, XSS-safe text and RTL. |
| `PublicInvoicePage.test.ts` — public invoice invalid and unavailable links show no financial content | `npm exec --workspace @tawzeevo/operations-web -- vitest run src/components/PublicInvoicePage.test.ts -t "public invoice invalid and unavailable links show no financial content"` | Checks invalid/unavailable public URLs do not expose financial content. |

### P3-M5 validation history

- Initial backend acceptance: 123 passed, 1 failed, 92.22% coverage. The failing access-log capture test was affected by Alembic disabling unrelated loggers earlier in the suite; its capture setup now restores the test logger using automatic teardown. The final rerun result follows below.
- Frontend acceptance: `npm run check` PASS — ESLint, strict TypeScript, all 34 tests across 5 files, and production build (210 modules). Existing non-blocking Vite chunk-size advisory remains.
- Backend application/test lint: `.\.venv\Scripts\python.exe -m ruff check apps/api/tawzeevo_api apps/api/tests` PASS; matching `ruff format --check` PASS (68 files).
- Broader lint diagnostic: `.\.venv\Scripts\python.exe -m ruff check apps/api` reports pre-existing `I001` import ordering in `alembic/versions/20260827_0009_invoice_item_line_order.py`. This milestone does not modify existing migrations or suppress that rule. It is separate from the passing application/test lint scope.
- Final full backend rerun: `.\.venv\Scripts\python.exe -m pytest apps/api/tests -q --cov=tawzeevo_api --cov-report=term --cov-fail-under=80 --tb=short` PASS — **124 passed, 0 failed; 92.29% statement coverage**, disposable local PostgreSQL 18. This includes earlier regression and migration tests. The existing Starlette/httpx deprecation warning remains non-blocking; no dependency upgrade was made.
- Strict backend types: `.\.venv\Scripts\python.exe -m mypy --config-file apps/api/pyproject.toml apps/api/tawzeevo_api` PASS — 52 source files.
- Final focused public/log-safety recheck: `.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_public_invoices.py -q --tb=short` PASS — 7 tests, including an explicit assertion that the generic failure message was actually captured (not just absence of the secret).
- Schema drift: `.\.venv\Scripts\python.exe -m alembic -c apps/api/alembic.ini check` PASS — no new upgrade operations detected. No new or modified migration in P3-M5.
- `git diff --check` PASS. Production deployment, live WhatsApp sending, and a full browser visual/accessibility audit were not performed in this milestone.

## P3-M5 baseline remediation — immutable migration guards

These are content-integrity regression checks, not new application behavior. The shared integration
fixture requires the same disposable database as the full suite. Only LF/CRLF checkout conversion
is normalized; imports, SQL, comments and all other whitespace remain fingerprinted.

| File / formal case | Exact command from repository root | Behavior | Last run |
|---|---|---|---|
| `apps/api/tests/test_immutable_migration_files.py::test_historical_migration_content_is_unchanged[0009]` | `.\.venv\Scripts\python.exe -m pytest "apps/api/tests/test_immutable_migration_files.py::test_historical_migration_content_is_unchanged[0009]" -q` | Detects any content edit concealed by the exact historical import/format exceptions for 0009. | PASS / 2026-09-05 |
| `apps/api/tests/test_immutable_migration_files.py::test_historical_migration_content_is_unchanged[0010]` | `.\.venv\Scripts\python.exe -m pytest "apps/api/tests/test_immutable_migration_files.py::test_historical_migration_content_is_unchanged[0010]" -q` | Detects any content edit concealed by the exact historical format exception for 0010. | PASS / 2026-09-05 |

### 2026-09-05 — P3-M5 baseline remediation acceptance

- Full backend: `.\.venv\Scripts\python -m pytest .\apps\api\tests -q --cov=tawzeevo_api --cov-report=term-missing --cov-fail-under=80` — PASS, 126 tests, 0 skipped/failed, 92.29% coverage, disposable local PostgreSQL 18.
- Exact documented whole-backend checks: `.\.venv\Scripts\python -m ruff check .\apps\api` and `.\.venv\Scripts\python -m ruff format --check .\apps\api` — PASS (80 formatted files; two exact immutable historical format exceptions, one I001 exception; content guards pass).
- `.\.venv\Scripts\python -m mypy --config-file .\apps\api\pyproject.toml .\apps\api\tawzeevo_api` — PASS, 52 source files.
- `.\.venv\Scripts\python -m alembic -c .\apps\api\alembic.ini upgrade head` and `.\.venv\Scripts\alembic -c .\apps\api\alembic.ini check` — PASS at 20260827_0011, no drift. Full suite includes migration-from-zero and Phase 2 legacy migration regressions.
- `npm run check` — PASS, ESLint, TypeScript, 34 tests and production build (210 modules); existing chunk-size advisory only.
- `git diff --check`, conflict-marker scan and skipped-test/code-marker inspection — PASS. No existing application source or migration was rewritten. Full classification and preserved-work instructions: `docs/phase-3/baseline-remediation.md`.

### 2026-09-06 — Independent clean-checkout reproduction

- Detached checkout of `1097593b00c1773e70d1df783fa6dca4322f3ed5`; fresh backend environment via `uv sync --locked --extra dev`, fresh frontend dependencies via `npm ci`; neither lockfile changed.
- From that checkout root, `.\apps\api\.venv\Scripts\python -m pytest .\apps\api\tests -q --cov=tawzeevo_api --cov-report=term-missing --cov-fail-under=80` — PASS, 126 tests, 0 skipped/failed, 92.29% coverage, including both migration-content guards and migration regressions.
- Whole-backend Ruff lint/format, strict mypy (52 files), Alembic upgrade to `20260827_0011` and drift check — PASS using the fresh environment. `npm run check` — PASS, ESLint, TypeScript, 34 tests / 5 files, production build / 210 modules.
- Full-checkpoint whitespace/conflict/introduced-code-marker checks and post-validation Git cleanliness — PASS. Exact setup/check commands and warning details are in `docs/phase-3/baseline-remediation.md`.
- Warnings were not suppressed: existing Vite size and Starlette/httpx advisories, plus the clean development environment's short JWT placeholder warning; production settings reject that placeholder and short secrets. No production data or configuration was used.

## FA-008 — Individual regression ledger (2026-09-10)

These PostgreSQL-backed cases require `DATABASE_URL` and `TEST_DATABASE_URL` to name the same
disposable migrated database. The suite truncates data and must never target shared or production
data.

| Formal test case | Exact command | Behavior | Last run |
|---|---|---|---|
| `test_opening_obligation_uses_combined_signed_economic_position[positive-opening]` | `.\.venv\Scripts\python.exe -m pytest "apps/api/tests/test_fa008_obligations.py::test_opening_obligation_uses_combined_signed_economic_position[positive-opening]" -q` | A +10 opening is one +10 historical obligation and the ORM runtime type is string-backed. | PASS / 2026-09-10 |
| `test_opening_obligation_uses_combined_signed_economic_position[negative-opening]` | `.\.venv\Scripts\python.exe -m pytest "apps/api/tests/test_fa008_obligations.py::test_opening_obligation_uses_combined_signed_economic_position[negative-opening]" -q` | A -10 opening remains credit and creates no debt obligation. | PASS / 2026-09-10 |
| `test_opening_obligation_uses_combined_signed_economic_position[positive-corrected-up]` | `.\.venv\Scripts\python.exe -m pytest "apps/api/tests/test_fa008_obligations.py::test_opening_obligation_uses_combined_signed_economic_position[positive-corrected-up]" -q` | +10 corrected by +2 is one +12 obligation targeted to the original immutable opening. | PASS / 2026-09-10 |
| `test_opening_obligation_uses_combined_signed_economic_position[positive-reversed-to-zero]` | `.\.venv\Scripts\python.exe -m pytest "apps/api/tests/test_fa008_obligations.py::test_opening_obligation_uses_combined_signed_economic_position[positive-reversed-to-zero]" -q` | +20 corrected by -20 has zero position and no opening obligation. | PASS / 2026-09-10 |
| `test_opening_obligation_uses_combined_signed_economic_position[negative-remains-credit]` | `.\.venv\Scripts\python.exe -m pytest "apps/api/tests/test_fa008_obligations.py::test_opening_obligation_uses_combined_signed_economic_position[negative-remains-credit]" -q` | -10 corrected by +5 remains -5 credit and creates no debt obligation. | PASS / 2026-09-10 |
| `test_opening_obligation_uses_combined_signed_economic_position[credit-crosses-into-debt]` | `.\.venv\Scripts\python.exe -m pytest "apps/api/tests/test_fa008_obligations.py::test_opening_obligation_uses_combined_signed_economic_position[credit-crosses-into-debt]" -q` | -10 corrected by +15 becomes one +5 obligation dated and targeted to the original opening, not a +15 correction obligation. | PASS / 2026-09-10 |
| `test_receipt_allocates_once_to_effective_opening_and_updates_balance_and_debt` | `.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_fa008_obligations.py::test_receipt_allocates_once_to_effective_opening_and_updates_balance_and_debt -q` | A receipt allocates once against a corrected opening and reconciles allocation, balance, remaining obligation and debt age. | PASS / 2026-09-10 |
| `test_corrected_opening_and_invoice_remain_distinct_obligations` | `.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_fa008_obligations.py::test_corrected_opening_and_invoice_remain_distinct_obligations -q` | One net opening obligation coexists deterministically with the ordinary invoice obligation. | PASS / 2026-09-10 |
| `test_receipt_reversal_restores_opening_without_creating_a_reversal_obligation` | `.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_fa008_obligations.py::test_receipt_reversal_restores_opening_without_creating_a_reversal_obligation -q` | Reversal restores the original obligation through allocation history, does not create a compensating-row obligation, and permits the corrected receipt. | PASS / 2026-09-10 |
| `test_refund_compensation_is_not_an_allocatable_customer_obligation` | `.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_fa008_obligations.py::test_refund_compensation_is_not_an_allocatable_customer_obligation -q` | A positive refund ledger effect reduces credit but is not independently allocatable debt. | PASS / 2026-09-10 |
| `test_opening_obligations_are_isolated_by_tenant_and_currency` | `.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_fa008_obligations.py::test_opening_obligations_are_isolated_by_tenant_and_currency -q` | Opening/correction positions remain isolated by tenant and currency and cross-tenant lookup is denied. | PASS / 2026-09-10 |

### 2026-09-10 — FA-008 focused regression run

- Command: `.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_fa008_obligations.py -q --tb=short`
- Result: `PASS`
- Counts: `11 passed, 0 failed/skipped; one existing Starlette/httpx deprecation warning`
- Environment: `fresh disposable PostgreSQL 18 cluster on loopback, migrated from zero through 20260909_0012`

### 2026-09-10 — FA-008 application validation

- Focused FA-008: `11 passed`, no failures/skips.
- Preserved FA-001 opening plus existing invoice/payment/allocation/debt tests: `21 passed`, no
  failures/skips.
- Full backend: `142 passed`, no failures/skips, `92.41%` statement coverage; the existing
  Starlette/httpx deprecation warning remains non-blocking.
- Whole-backend Ruff lint: PASS.
- Whole-backend Ruff formatting check: PASS, 83 files.
- Strict mypy: PASS, 52 source files.
- Alembic drift check at `20260909_0012`: PASS, no new upgrade operations.
- Frontend checks: not run because FA-008 changed no frontend source, API schema, or frontend behavior.


## Sprint 1 remediation — regression ledger (2026-09-17)

PostgreSQL-backed cases require `DATABASE_URL` and `TEST_DATABASE_URL` to name the same disposable
migrated database (this run: fresh PostgreSQL 18 cluster on 127.0.0.1:55439, migrated from zero to
`20260909_0012`). Application HEAD `4bdbd88a9b719bedc94f1949278a816a9917666e`.

| Finding | Exact command | Behavior | Result |
|---|---|---|---|
| FA-003 | `.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_fa003_overdue_calendar.py -q` | Beirut-calendar overdue age; 4 of 5 cases failed before the fix | PASS (5) |
| FA-006 | `.\.venv\Scripts\python.exe -m pytest "apps/api/tests/test_invoice_editor.py::test_confirmed_revision_rejects_zero_net_sales_and_cancellation_compensates" -q` | Zero/negative confirmed edit rejected, smallest positive accepted, cancellation compensates; failed before the fix | PASS |
| FA-002 | `.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_fa002_supplier_payment_cap.py apps/api/tests/test_supplier_ledger.py -q` | Payable cap, prepayment credit, replay, reversal, concurrent race | PASS (6) |
| FA-005 | `.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_fa005_capability_lifecycle.py apps/api/tests/test_public_invoices.py -q` | Confirmed-only, single active link, cancellation revokes, concurrent issue | PASS (9) |
| FA-004 | `.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_fa004_supplier_setup.py -q` | Fresh owner provisions supplier/cost via API and confirms catalog + manual invoices; tenant-private, owner-only | PASS (2) |
| FA-004 UI | `npm run test --workspace=@tawzeevo/operations-web -- src/components/SupplierSetup.test.tsx` | Supplier creation, cost append, preferred supplier, Arabic labels | PASS (2) |
| FA-011 | `npm run test --workspace=@tawzeevo/operations-web -- src/components/InvoiceEditor.test.tsx` | Snapshot label distinct in EN/AR | PASS |
| FA-010 | `.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_fa010_legacy_draft_parity.py -q` | Legacy/editor prior-balance and due parity; 2 of 3 failed before the fix | PASS (3) |
| FA-012 | `.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_fa012_money_range.py -q` | Overflow -> 400, no partial rows, max value accepted; 4 of 5 failed before the fix | PASS (5) |

### 2026-09-17 — Sprint 1 full validation

- Full backend: `.\.venv\Scripts\python.exe -m pytest apps/api/tests -q --cov=tawzeevo_api` -> `161 passed`, `93%` statement coverage, one existing Starlette/httpx deprecation warning.
- Whole-backend Ruff lint and format check: PASS. Strict mypy: PASS (55 source files).
- Frontend `npm run check`: ESLint PASS, strict TypeScript PASS, Vitest `49 passed` (7 files), production build PASS (212 modules).
- Graphify refresh + validation at HEAD: PASS (0.9.55, 2,673 nodes, 8,710 edges).

### 2026-09-17 — FA-009 closure (D-045)

- `.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_fa009_create_command.py -q` -> `3 passed` (replay returns the same header, conflicting request 409, concurrent same command yields one header, tenant-scoped commands).
- `npm run test --workspace=@tawzeevo/operations-web -- src/components/InvoiceEditor.test.tsx` -> `11 passed` including the failed-save-retries-with-same-command case.
- Migration `20260917_0013` applied from `0012`; `alembic check` PASS; from-zero migration test updated to the new head.

## Order workflow fix — regression ledger (2026-09-24, D-090)

Backend commands run from `apps/api` with `TEST_DATABASE_URL` on a disposable cluster. Playwright needs the local E2E stack (API 8011, client 5173, storefront 3000).

| Milestone | Stack | Test | Exact command | Behavior | Status |
|---|---|---|---|---|---|
| M1 | Pytest | `tests/test_checkout.py::test_personalized_checkout_belongs_to_the_link_customer_and_phone_never_links` | `python -m pytest "tests/test_checkout.py::test_personalized_checkout_belongs_to_the_link_customer_and_phone_never_links" -q` | Order through A's link carrying B's name/phone belongs to A (order, invoice, revision); id/grade/discount fields refused; saved-address fallback; rotated link is the public path | PASS / 2026-09-24 |
| M1 | Pytest | `tests/test_checkout.py::test_guest_checkout_is_atomic_idempotent_and_provisional` (extended) | `python -m pytest "tests/test_checkout.py::test_guest_checkout_is_atomic_idempotent_and_provisional" -q` | Public order unchanged; each missing contact field is 422 `CONTACT_REQUIRED` | PASS / 2026-09-24 |
| M1 | Pytest | `tests/test_order_review.py::test_link_order_arrives_linked_and_the_owner_may_still_relink_or_decline` | `python -m pytest "tests/test_order_review.py::test_link_order_arrives_linked_and_the_owner_may_still_relink_or_decline" -q` | Link order arrives linked with the customer's name; owner correction path and decline still work | PASS / 2026-09-24 |
| M1 | Pytest | `tests/test_customer_verification.py::test_link_alone_is_not_enough_under_verified_and_the_code_grants_a_session` (extended) | `python -m pytest "tests/test_customer_verification.py::test_link_alone_is_not_enough_under_verified_and_the_code_grants_a_session" -q` | Non-granted link: public order, no customer, contact required; once VERIFIED the order is the customer's | PASS / 2026-09-24 |
| M1 | Pytest | `tests/test_customer_access.py::test_link_gives_current_customer_pricing_without_exposing_anything_private` (extended) | `python -m pytest "tests/test_customer_access.py::test_link_gives_current_customer_pricing_without_exposing_anything_private" -q` | Context call adds only `has_saved_address`, never the address | PASS / 2026-09-24 |
| M1 | Vitest (storefront) | `lib/cart.test.ts` | `npm run test --workspace=@tawzeevo/storefront-web` | Two contexts keep separate carts and checkout keys; public cart keeps its key; links carry `c=` | PASS / 2026-09-24 |
| M1 | Vitest (storefront) | `lib/personal.test.ts` › each link gets a stable one-way context reference | `npm run test --workspace=@tawzeevo/storefront-web` | Context reference is stable, per link, not the secret; per-context cookie names | PASS / 2026-09-24 |
| M1 | Vitest (client) | `OrdersPanel.test.tsx` › an order placed through a personalized link arrives linked | `npm exec --workspace @tawzeevo/operations-web -- vitest run src/components/OrdersPanel.test.tsx` | No create/select/link controls for a linked order; confirm enabled | PASS / 2026-09-24 |
| M1 | Playwright | `e2e/order-workflow-isolation.spec.ts` | `npx playwright test e2e/order-workflow-isolation.spec.ts` (in `apps/operations-web`) | Two customers in two tabs of one browser context: identity, cart and checkout stay separate; each order linked to its own customer; a link revoked mid-checkout continues as a public order | PASS / 2026-09-24 |
| M1 | Playwright | `e2e/phase9-verification-flow.spec.ts` (URL assertion allows `?c=`) | `npx playwright test e2e/phase9-verification-flow.spec.ts` | Verified flow unchanged; the tab keeps its context reference | PASS / 2026-09-24 |
| M2 | Pytest | `tests/test_order_review.py::test_orders_awaiting_review_are_tenant_isolated_and_drop_after_a_decision` | `python -m pytest "tests/test_order_review.py::test_orders_awaiting_review_are_tenant_isolated_and_drop_after_a_decision" -q` | `?status=RECEIVED` returns only this business's awaiting orders (id, name, time); another owner is refused; a decision removes one | PASS / 2026-09-24 |
| M2 | Vitest (client) | `pendingOrders.test.tsx` (3 tests) | `npm exec --workspace @tawzeevo/operations-web -- vitest run src/components/pendingOrders.test.tsx` | Baseline without a notice; one and several arrivals; badge and `(n)` title follow the count; decisions clear it | PASS / 2026-09-24 |
| M2 | Vitest (client) | `OrdersPanel.test.tsx` › a link naming an order opens that order directly | `npm exec --workspace @tawzeevo/operations-web -- vitest run src/components/OrdersPanel.test.tsx` | `order=` deep link opens the order; panel counter reads "awaiting review" | PASS / 2026-09-24 |
| M2 | Playwright | `e2e/phase5-storefront-flow.spec.ts` (Orders link/counter locators) | `npx playwright test e2e/phase5-storefront-flow.spec.ts` | Unchanged flow with the new counter wording and badge in the link name | PASS / 2026-09-24 |
