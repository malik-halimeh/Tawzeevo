# Phase 3 requirements audit

Audit date: 2026-09-17

Status: PASS (P3-M6 freeze)

This document freezes requirement-to-code/test evidence for `PHASE_03.md`. It does not supersede
the project contract, the decision ledger, or the phase contract. Backend paths are relative to
`apps/api/tawzeevo_api/`, tests to `apps/api/tests/`, frontend to `apps/operations-web/src/`.
Historical findings and their closures are kept in the owner's working records outside the
public tree (the former `docs/audits/` register was moved out of the repository on 2026-09-18);
the invariant catalog is `docs/contracts/financial-invariants.md`.

## A/B — Financial invariants and production invoice model

| Requirement | Implementation evidence | Test evidence | Result |
|---|---|---|---:|
| Header is identity; immutable revisions are financial truth; `current_revision_id` canonical | `models.py` Invoice/InvoiceRevision/InvoiceRevisionItem; migration `0008`; immutable triggers | `test_financial_schema.py`; `test_invoice_editor.py` immutable update tests | PASS |
| One invoice currency; balances per currency; Decimal/NUMERIC(20,4) Q4 HALF_UP | `services/invoice_editor.py::money/stored_money`; `services/pricing.py` | `test_cash_van.py` pricing-v1; `test_fa012_money_range.py` | PASS |
| Revision items snapshot price, grade rule, packaging and immutable cost provenance (D-031/D-034) | `invoice_editor.py::_prepare_items/_prepare_cost`; `invoice_finance.py::_validate_confirmable_costs` | `test_invoice_editor.py` cost prefill/override; `test_financial_schema.py` snapshot survives later cost | PASS |
| Owner supplier/product-cost setup before Phase 3 completes (D-041) | `routes/suppliers.py`, `services/suppliers.py`, `schemas/suppliers.py`; `components/SupplierSetup.tsx`; editor setup link and manual-line cost controls | `test_fa004_supplier_setup.py`; `SupplierSetup.test.tsx` | PASS |
| Every tenant-owned financial row has `tenant_id` + RLS; platform admin gains no tenant finance | migrations `0008`–`0012` RLS policies; `dependencies.py::require_tenant_owner` | `test_supplier_ledger.py` forced RLS; `test_public_invoices.py` forced RLS; owner security tests | PASS |

## C/E — Numbering, confirmation and post-confirmation edits

| Requirement | Implementation evidence | Test evidence | Result |
|---|---|---|---:|
| `YYYY-000001` tenant/year sequence under row lock, assigned once on first confirmation | `invoice_finance.py::confirm_invoice`; `InvoiceSequence` | `test_invoice_editor.py` idempotent confirmation and sequence concurrency | PASS |
| Confirmation appends exactly one charge; replay does not duplicate | `invoice_finance.py::confirm_invoice` | `test_confirmation_is_idempotent_assigns_official_number_and_posts_one_charge` | PASS |
| Post-confirmation edit = new immutable revision + exact delta adjustment; stale predecessor rejected; excess allocations reconciled | `invoice_finance.py::update_confirmed_invoice/_reconcile_allocations` | `test_post_confirmation_revision_posts_exact_delta...`; `test_downward_confirmed_edit_releases_excess_allocation...` | PASS |
| Every confirmed revision keeps strictly positive net sales (D-043) | `confirm_invoice` and `update_confirmed_invoice` guards | `test_confirmed_revision_rejects_zero_net_sales_and_cancellation_compensates` | PASS |
| Fixed line/invoice adjustments and Q4 stages (D-036); manual price final (D-035); due snapshot distinct (D-037) | `_prepare_items/_totals`; `InvoiceEditor.tsx` snapshot label | `test_editor_recalculates_pricing_v1_calculator_adjustments...`; `test_fa010_legacy_draft_parity.py`; `InvoiceEditor.test.tsx` label test | PASS |

## D — Invoice editor and deterministic item entry

| Requirement | Implementation evidence | Test evidence | Result |
|---|---|---|---:|
| Customer lookup, barcode/manual/text entry, packaging, calculator input | `invoice_editor.py::_Calculator/parse_item_text`; `InvoiceEditor.tsx` | `test_editor_rejects_mixed_currency_package_mismatch_and_unsafe_calculator`; parser tests | PASS |
| Exact-first, fuzzy-second, ambiguity never auto-selected, accepted match audited | `parse_item_text`; `accepted_fuzzy_match` handling | parser ambiguity and audit tests in `test_invoice_editor.py` | PASS |
| Oversized calculator/monetary results are validation errors | `stored_money` guards | `test_fa012_money_range.py` | PASS |

## F/G — Customer ledger, opening balances and overdue

| Requirement | Implementation evidence | Test evidence | Result |
|---|---|---|---:|
| Append-only ledger; balance = SUM(signed_amount) per currency; opening is not sales | `services/customer_ledger.py`; immutable triggers | `test_opening_balance_balance_api_overdue_alert_dedup_and_owner_security`; delta tests | PASS |
| One signed nonzero opening per party/currency with immutable correction/reversal (D-038) | `create_opening_balance/correct_opening_balance`; migration `0012` partial unique indexes | `test_opening_balances.py` | PASS |
| Obligations interpret opening + correction as one position; reversals/refunds are not obligations | `opening_obligation_positions`; `payments.py::_obligations` | `test_fa008_obligations.py` | PASS |
| Overdue age on the Asia/Beirut calendar, `age > X`, unset disables (D-040) | `customer_debts` with `overdue_calendar_date` | `test_fa003_overdue_calendar.py` | PASS |

## H/I — Payments, allocations, cancellation, refunds, supplier ledger

| Requirement | Implementation evidence | Test evidence | Result |
|---|---|---|---:|
| Immutable receipt + one negative effect + allocations; FIFO default or owner selection; allocations <= receipt; remainder credit | `payments.py::record_customer_receipt/_selected_allocations` | `test_receipt_fifo_owner_allocation_partial_multi_obligation_and_reversal_are_immutable` | PASS |
| Replay idempotent; same physical receipt keeps one command identity across retry/reload (D-044) | `payments.py::_existing_payment`; `api/financialIntent.ts` | `test_customer_receipt_retries_one_command_and_a_new_intent_posts_again`; `financialIntent.test.ts`; `InvoiceEditor.test.tsx` lost-response tests | PASS |
| Cancellation reverses charge and allocations, preserves payments; refund ceiling serialized per customer/currency | `invoice_finance.py::cancel_invoice`; `payments.py::record_customer_refund` | `test_cancellation_preserves_payment_releases_credit_and_refund_ceiling_is_concurrent`; cancellation matrix | PASS |
| Supplier aggregate payable; ordinary payment capped at payable; explicit prepayment credit; compensating reversals; no per-purchase allocation (D-019/D-039) | `services/supplier_ledger.py::record_supplier_payment/_write_payment_effect` | `test_fa002_supplier_payment_cap.py`; `test_supplier_ledger.py` | PASS |

## J — Public capability and WhatsApp

| Requirement | Implementation evidence | Test evidence | Result |
|---|---|---|---:|
| >=256-bit secret, SHA-256 only, 90-day default, expiry/revocation/rotation, raw token never logged | `services/public_invoices.py`; `public_invoice_security.py` | `test_capability_rotation_expiry_revocation_and_uniform_invalid_access`; log-redaction tests | PASS |
| Confirmed-only, at most one active link, replacement and cancellation revoke (D-042) | `issue_capability/revoke_active_capabilities`; `cancel_invoice` revocation | `test_fa005_capability_lifecycle.py` | PASS |
| Restricted projection; `no-store`/`noindex`/`no-referrer`; rate limit | `resolve_public_invoice`; privacy middleware | `test_capability_projection_current_revision_privacy_and_no_stored_secret`; rate-limit test | PASS |
| WhatsApp share uses normalized phone, summary and capability URL | `issue_capability`; `InvoiceSharing.tsx` | `InvoiceSharing.test.tsx` | PASS |

## K/L/M — API scope, frontend scope, migrations

| Requirement | Implementation evidence | Test evidence | Result |
|---|---|---|---:|
| Canonical groups `/api/v1/invoices`, `/payments`, `/customer-ledger`, `/supplier-ledger`, `/suppliers`; thin routes | `routes/*.py`; OpenAPI (72 paths) | route-level tests across suites | PASS |
| Operations frontend: editor, balances, packaging, grade explanation, history, receipts, allocation, refund, debt, cancellation, sharing, supplier setup, EN/AR/RTL | `InvoiceEditor.tsx`, `InvoiceSharing.tsx`, `SupplierSetup.tsx`, `i18n.ts` | Vitest suites (49 tests) | PASS |
| Never edit applied migrations; from-zero and Phase 2 upgrade pass; head `20260909_0012` | `alembic/versions/`; content guards for `0009`/`0010` | `test_hardening.py::test_migrations_build_a_new_database_from_zero`; `test_financial_schema.py::test_phase2_draft_rows_upgrade...`; `test_immutable_migration_files.py`; `alembic check` | PASS |

## Definition of Done

| Item | Result |
|---|---:|
| Production invoice editor works; calculations reproducible | PASS |
| Immutable revision model canonical; confirmed edits auditable/reconciled | PASS |
| Sequence server-authoritative and concurrency-safe | PASS |
| Customer ledger reconciles by currency; opening balance correct and not sales | PASS |
| Payments immutable/idempotent; allocations deterministic/reversible; partial payments correct | PASS |
| Refund ceiling/concurrency safe; cancellation preserves payment history | PASS |
| Overdue red behavior works (Beirut calendar) | PASS |
| WhatsApp uses safe capability; single active confirmed-only link | PASS |
| Supplier-ledger foundation ready for Phase 6 (payable cap, prepayment, owner setup) | PASS |
| RLS blocks tenant financial leakage | PASS |
| Migrations from zero/Phase 2 pass | PASS |
| No stock/availability introduced | PASS |

## Open items carried forward (not blockers)

- FA-009 draft-create command idempotency across headers: closed by D-045 (approved 2026-09-17); since 2026-09-21 a replay must also match every monetary intent of the request (manual unit prices, line/invoice discounts and markups, cost overrides) or answer 409 (`test_fa009_create_command.py`)
  (`OWNER_ACTIONS.md` A1). Draft creation posts no money.
- Durable notification cadence for overdue alerts and exact public rate-limit constants remain
  operational policy for a later phase.
- Real-browser E2E: see `test-report.md` for the executed lane and its limits.

## Phase boundary

Phase 3 delivers the financial core only. No offline sync, storefront checkout, procurement,
delivery routing, analytics, or forecasting exists. Phase 4/5 begin only on an explicit
`Start Phase N` command after their gate decisions are recorded.
