# Financial invariant catalog

Updated 2026-09-10 through the independently verified FA-001 closure and bounded FA-008
remediation after the financial audit. This is a derived catalog, not a
specification change. AGENTS.md precedence applies; BINDING rows quote/summarize explicit approved
root authority. Recommendations and observations do not become requirements.

AUDIT_BASE_SHA=2248c137e43c6c043725830c1303756da1d210ee

AUDITED_SHA=868bf1c5d4d49e755c74a6dd2c75a9a78f6ca6e6

GRAPH_SOURCE_SHA=868bf1c5d4d49e755c74a6dd2c75a9a78f6ca6e6

FA001_REMEDIATION_SHA=431a984898484ab132acb11089ecb6dd3a7e406a

FA001_GRAPH_SOURCE_SHA=431a984898484ab132acb11089ecb6dd3a7e406a

FA001_CLOSURE_BASE_SHA=b50696ade61f167311a64b6f57a5e2e5fd11f08f

FA008_REMEDIATION_SHA=65b571488fc05247fad6f405f8d5733b597d98ef

FA008_GRAPH_SOURCE_SHA=65b571488fc05247fad6f405f8d5733b597d98ef

Counts: **32 EXPLICIT/BINDING invariants; 5 CANDIDATE invariants**. A test reference means relevant
executable coverage, not complete proof of the row. Contrary test assumptions are identified.
All 126 existing backend tests passed in this audit; all 34 existing frontend tests passed on a
separate rerun. See [financial audit](../audits/PHASE_3_FINANCIAL_AUDIT.md) for results and findings.

## Reference conventions

Unqualified Python service names below resolve under `apps/api/tawzeevo_api/services/`;
`models.py`, `dependencies.py`, `routes/`, `schemas/`, and `repositories/` resolve under
`apps/api/tawzeevo_api/`. `InvoiceEditor.tsx` resolves under
`apps/operations-web/src/components/`. Migration revisions resolve under `apps/api/alembic/versions/`.
E references are exact executable tests below; P/G references resolve to the audit's diagnostic and
graph tables. Approved provenance for each BINDING row is its named locked decision or root contract
section, accepted under AGENTS.md—not inferred from a passing test or recovered historical guide.

## Binding invariants

| ID | Rule | Origin | Authority | Approved provenance | Affected implementation | Database enforcement | Tests | Missing tests | Graph paths | Confidence / result |
|---|---|---|---|---|---|---|---|---|---|---|
| FI-01 | Authoritative money uses Decimal/NUMERIC(20,4), Q4 HALF_UP | EXPLICIT | BINDING | 01_TECH_STACK.md Money; D-030/036 | pricing.py::quantize_money; invoice_editor.py::money/_Calculator | NUMERIC(20,4) columns | E01/E02/E03 | expression/aggregate overflow, negative near-zero and Q4 stage matrix | G02 | HIGH; range handling gap FA-012 |
| FI-02 | Explicit grade price beats percentage, otherwise normal; round basis before counterpart | EXPLICIT | BINDING | D-030 | pricing.py::resolve_product_pricing/derive_counterpart_prices; invoice_editor.py::_selected_prices | grade bounds, price >=0 | E01 | broader grade/package combinations | G02 | HIGH |
| FI-03 | Manual non-catalog price is final, no automatic grade discount | EXPLICIT | BINDING | D-035 | invoice_editor.py::_prepare_items | effective price >=0 | E02 | manual line with every grade and 100% catalog discount | G02 | HIGH |
| FI-04 | Q4 quantity precedes multiplication; line base=Q(price*quantity) | EXPLICIT | BINDING | D-036 | invoice_editor.py::_Calculator.parse/_prepare_items | quantity >0; NUMERIC Q4 | E02 | 0.00004/0.00005 quantity and product half ties | G02 | HIGH |
| FI-05 | Fixed line/invoice adjustments applied once; subtotal/discount/markup/net equation; no double grade savings | EXPLICIT | BINDING | D-036 | invoice_editor.py::_prepare_items/_totals | nonnegative stages; no DB cross-field equation | E02 | exact rounding-stage and aggregate boundaries | G02 | HIGH |
| FI-06 | Every confirmed revision net_sales >0; quantity >0, inputs and line/net totals nonnegative | EXPLICIT | BINDING | D-043 | invoice_finance.py::confirm_invoice/update_confirmed_invoice; invoice_editor.py::_totals | net_sales >=0 only | E08 (contrary zero test); E02 | zero edit rejection, unchanged pointers/ledger/allocations on failure | G01 | HIGH; CONTRADICTED FA-006 |
| FI-07 | One invoice currency; balances grouped by currency; no silent conversion | EXPLICIT | BINDING | PHASE_03.md A/H; D-034 | invoice_editor.py::_prepare_items/_prepare_cost; invoice_finance.py::update_confirmed_invoice; ledger services | composite currency allocation FKs; NUMERIC | E01/E04/E05/E06 | multi-currency mixed mutation sequences | G01/G02/G03 | HIGH within inspected paths |
| FI-08 | Header is identity; current revision canonical; revisions/items immutable | EXPLICIT | BINDING | PHASE_03.md A/B; D-011 | models.py::Invoice/InvoiceRevision/InvoiceRevisionItem; editor/finance services | deferred scoped pointers; update/delete triggers; successor uniqueness | E03/E07/E08 | all historical fields after multi-revision/cancel/catalog changes | G01 | HIGH |
| FI-09 | Later supplier price changes cannot rewrite historical cost/profit snapshots | EXPLICIT | BINDING | D-031/034 | invoice_editor.py::_prepare_cost/_write_revision_items | cost/revision/item immutable triggers | E03/E09 | confirmed edit plus later source/package/preference changes; all cost provenance fields | G02 | HIGH for stored snapshots; no profit report exists |
| FI-10 | Tenant-private latest eligible selected/preferred supplier cost; reasoned revision-only override; complete matching confirmation cost | EXPLICIT | BINDING | D-034; PHASE_03.md B | invoice_editor.py::_prepare_cost/product_cost_options; invoice_finance.py::_validate_confirmable_costs | scoped FKs; cost shape/reason constraints; no cross-table confirmation trigger | E04/E09 | effective-time tie/future entries, manual UI, complete source/basis/currency boundaries | G02 | HIGH for source logic; workflow incomplete |
| FI-11 | Owner supplier creation, cost append/preference setup and missing-cost editor link before Phase 3 completion | EXPLICIT | BINDING | D-041 | routes/invoices.py::invoice_product_cost_options; InvoiceEditor.tsx::loadCostOptions/addManual | tables only | E09/E03 use direct fixture setup | fresh tenant UI/API journey with no supplier/cost SQL inserts | G02/G06 | HIGH; MISSING FA-004 |
| FI-12 | Server tenant/year numbering only at first confirmation, never reuse; concurrency/replay safe | EXPLICIT | BINDING | PHASE_03.md C/E | invoice_finance.py::_allocate_official_number/confirm_invoice | tenant/year PK, official-number uniqueness | E10/E11 | same invoice simultaneous confirm; year-boundary policy C-F04 | G01 | HIGH; tested sequence |
| FI-13 | Confirmation atomically appends exactly one +net_sales charge with lifecycle/pointers/audit | EXPLICIT | BINDING | PHASE_03.md E | invoice_finance.py::confirm_invoice | source-effect uniqueness, scoped FKs; one commit | E10 | fault injection before/after commit and same-invoice concurrency | G01 | HIGH; no Order domain yet |
| FI-14 | Confirmed edit accepts expected predecessor, appends full revision and exact delta once | EXPLICIT | BINDING | PHASE_03.md E; D-011 | invoice_finance.py::update_confirmed_invoice | successor/server-number/command/source-effect uniqueness | E07 | simultaneous same-predecessor commands and lost responses | G01 | HIGH; separate positive-boundary defect |
| FI-15 | Customer balance is immutable signed ledger sum per currency; old balance is not sales | EXPLICIT | BINDING | 00_PROJECT_CONTRACT.md Financial truth; PHASE_03.md F | customer_ledger.py::customer_balances; payments.py::_customer_balance | immutable rows; currency index | E07/E12/E06 | full event-sequence reconciliation, obligation-versus-balance distinction | G03 | HIGH |
| FI-16 | One signed nonzero historical opening per party/currency; corrections are immutable separate events | EXPLICIT | BINDING | D-038 | customer_ledger.py::create_opening_balance/correct_opening_balance; supplier_ledger.py::record_supplier_opening/correct_supplier_opening | partial unique indexes per tenant/party/currency; nonzero; immutable rows; linked correction constraint | E18 plus E12/E05 | none in the verified FA-001 scope | G04 | VERIFIED_FIXED; FA-001 CLOSED |
| FI-17 | Positive immutable receipt atomically posts negative ledger effect and allocations | EXPLICIT | BINDING | PHASE_03.md H | payments.py::record_customer_receipt | positive payment, scoped FKs, immutable triggers, unique effects | E06/E19 | commit fault boundaries | G03 | FIXED_PENDING_FINANCIAL_REGATE FA-008 |
| FI-18 | Receipt allocations match one target/currency, <= receipt and obligation; FIFO default or owner selection; remainder credit | EXPLICIT | BINDING | PHASE_03.md H | payments.py::_selected_allocations/_obligations; customer_ledger.py::opening_obligation_positions | target/currency/customer FKs and positive rows; sums enforced only in service | E06/E13/E19 | broader reverse/edit/payment interleavings | G03 | FIXED_PENDING_FINANCIAL_REGATE FA-008 |
| FI-19 | Receipt reversal appends compensation and reverses effective allocations; original preserved | EXPLICIT | BINDING | PHASE_03.md H/I | payments.py::reverse_customer_receipt | one reversal per payment/allocation/ledger entry; immutability | E06/E19 | broader altered-key and concurrent reversal/payment interleavings | G03 | FIXED_PENDING_FINANCIAL_REGATE FA-008 |
| FI-20 | Downward edit releases excess allocations as credit; upward edit preserves allocations/increases outstanding | EXPLICIT | BINDING | PHASE_03.md E/H | invoice_finance.py::_reconcile_excess_allocations | immutable reversal/replacement rows; uniqueness | E07/E13; diagnostic P11 | receipt/edit both orderings; reversal/edit concurrency; no fixture-only ledger bypass | G01/G03 | HIGH for tested release; wider interleavings missing |
| FI-21 | Draft cancellation no invented effect; confirmed cancellation reverses current value/releases allocations, preserves payments; no automatic refund | EXPLICIT | BINDING | PHASE_03.md I | invoice_finance.py::cancel_invoice | source-effect and reversal uniqueness; immutable originals | E08/E14 | cancel/payment and cancel/revision races; token revocation D-042 | G01/G05 | HIGH ledger paths; sharing defect separate |
| FI-22 | Refund same currency, 0<amount<=MAX(0,-balance); serialize/recompute credit; never new debt | EXPLICIT | BINDING | PHASE_03.md I; 00_PROJECT_CONTRACT.md Financial truth | payments.py::record_customer_refund | customer FOR UPDATE plus advisory key; positive immutable payment | E14 | refund vs opening/receipt reversal/edit; lost-response refund retry | G03 | HIGH backend ceiling; UI retry FA-007 |
| FI-23 | Supplier payments reduce aggregate payable and reverse immutably; never per-purchase allocation | EXPLICIT | BINDING | D-019; PHASE_03.md H | supplier_ledger.py::_write_payment_effect/record_supplier_payment/reverse_supplier_payment | direction/party CHECK, unique reversal/effects, immutable rows | E05 | payable-cap races and prepayment-specific tests | G04 | HIGH aggregate behavior |
| FI-24 | Ordinary supplier payment capped at positive payable; excess requires explicit separately labelled prepayment | EXPLICIT | BINDING | D-039 | supplier_ledger.py::record_supplier_payment; models.py::Payment | no cap; allowed payment directions omit prepayment | E05 (no ceiling case) | 0 payable, exact cap, excess, negative credit, concurrent payments, explicit prepayment | G04 | HIGH; CONTRADICTED FA-002 |
| FI-25 | Oldest unpaid obligation; positive debt; Asia/Beirut calendar age > threshold; unset disables overdue | EXPLICIT | BINDING | D-040; PHASE_03.md G | customer_ledger.py::customer_debts | threshold >=0; no timezone calculation in DB | E12 | midnight/DST, equality, unpaid origin after reversal, unset | G03 | HIGH; CONTRADICTED FA-003 |
| FI-26 | Immutable due=Q(prior snapshot+net_sales); distinguish from live customer balance in UI | EXPLICIT | BINDING | D-037 | invoice_editor.py::_prior_balance/_editor_response; invoice_finance.py::_balance_excluding_invoice; cash_van.py::create_draft_invoice; InvoiceEditor.tsx | immutable due storage | E02/E07/E15 | legacy/editor parity and due-snapshot wording after payment | G06 | PARTIAL; FA-010/011 |
| FI-27 | One active confirmed-invoice capability; replacement invalidates prior, cancellation revokes access | EXPLICIT | BINDING | D-042 | public_invoices.py::issue_capability/resolve_public_invoice; invoice_finance.py::cancel_invoice | unique hash/rotation only; no active-per-invoice constraint | E16 (draft assumptions contradict) | confirmed-only, two creates/rotation, cancellation and races | G05 | HIGH; CONTRADICTED FA-005 |
| FI-28 | Tenant-owned financial rows scoped explicitly and protected by RLS/owner authorization | EXPLICIT | BINDING | PHASE_03.md A/M; 00_PROJECT_CONTRACT.md Multi-tenancy | dependencies.py; financial routes/services; repositories/tenancy.py | forced RLS, composite FKs | E03/E04/E05/E16 | full matrix remains separate tenant/security audit | G01/G03/G04 | HIGH in scoped finance tests; not security certification |
| FI-29 | At most one invoice header per order; nullable order reference; immutable revisions under it | EXPLICIT | BINDING | D-033; PHASE_03.md B | models.py::Invoice | partial tenant/order unique index | E03 | future real order confirmation transaction, Phase 5 | G01 | HIGH schema; future order integration absent as scheduled |
| FI-30 | Preserve applied migrations; zero/Phase 2 upgrade validates canonical history | EXPLICIT | BINDING | AGENTS.md Repository safety; PHASE_03.md M | alembic 0008–0012 | migration immutability/content guards and tenant/financial constraints | E03/E17/E18 | deploy-role migration evidence remains CT-009, outside this local audit | none | HIGH local chain |
| FI-31 | Supplier costs/profit owner-only, never driver or public projection | EXPLICIT | BINDING | D-031/034; PHASE_03.md J | dependencies.py::require_tenant_owner; public_invoices.py::resolve_public_invoice | RLS supplements source-level allowlist | E04/E16 | later driver/analytics projections; broad security audit deferred | G02/G05 | HIGH current scoped projection |
| FI-32 | Replay of a logical payment must return original result without another financial effect | EXPLICIT | BINDING | PHASE_03.md H; P3-M4 Acceptance; 01_TECH_STACK.md Testing | payments.py::_lock_idempotency_key/_existing_payment; InvoiceEditor.tsx::recordReceipt/recordRefund | tenant/key uniqueness only; UI changes key on retry | E06; diagnostics P09/P12 | real lost-response UI→API receipt/refund E2E and persisted pending-command policy | G03 | HIGH; end-to-end CONTRADICTED FA-007 |

## Candidate questions — non-binding

These are explicitly unresolved details, not permission to change code or reasons to override
approved behavior. They may be settled only through the applicable authority/gate.

| ID | Rule under review | Origin | Authority | Provenance / limitation | Affected implementation | Database enforcement | Tests | Missing tests | Graph paths | Confidence |
|---|---|---|---|---|---|---|---|---|---|---|
| C-F01 | Cross-header draft creation deduplication and exact command payload conflict scope | PROPOSED | CANDIDATE | PHASE_03.md B/M provide revision-command constraints; Phase 4 F and Phase 5 E require future command replay; current create route duplicates a command across headers | invoice_editor.py::create_editor_draft; models.py::uq_invoice_revisions_client_command | only tenant/invoice/command uniqueness | P05 diagnostic; no existing same-create-key test | same-create replay, changed body, response loss | G06 | HIGH observation; current exact scope requires formalization |
| C-F02 | Whether confirmation must reload/reconfirm a cost that changed after draft acceptance | DERIVED | CANDIDATE | D-034 requires latest eligible invoice-entry cost and immutable confirmed snapshots; does not specify a draft-expiry/revalidation cutoff | invoice_editor.py::_prepare_cost; invoice_finance.py::_validate_confirmable_costs | immutable chosen draft snapshot | E09/E03 do not specify between-draft-and-confirm refresh | intervening cost/preference edit | G02 | CANNOT VERIFY policy; do not invent a reprice |
| C-F03 | How existing unallocated credit is explicitly allocated to later obligations | PROPOSED | CANDIDATE | PHASE_03.md H preserves unallocated credit; no separately approved later-credit allocation action identified | payments.py::_selected_allocations/_obligations; customer_ledger.py::customer_debts | ledger balance retains credit; no new standalone reallocation surface | E06 verifies remainder only | credit then later invoice with zero new receipt | G03 | CANNOT VERIFY workflow rule; no automatic allocation assumed |
| C-F04 | Which timezone determines tenant/year official invoice numbering at New Year | DERIVED | CANDIDATE | PHASE_03.md C says tenant+year; D-040 fixes overdue calendar only | invoice_finance.py::_allocate_official_number uses UTC confirmed_at.year | tenant/year PK and numbering uniqueness | E11 does not cover Beirut/UTC year crossover | Dec 31 UTC/Jan 1 Beirut | G01 | CANNOT VERIFY policy; do not extend D-040 by inference |
| C-F05 | Whether D-043 nonnegative invoice totals includes the signed due snapshot when prior credit exceeds sales | DERIVED | CANDIDATE | D-037 requires Q(prior+net); D-038 permits credit; D-043 does not name amount_due_display. Do not silently cap/override either rule. | invoice_editor.py::create_editor_draft; invoice_finance.py::update_confirmed_invoice | no nonnegative due CHECK | E07 does not resolve negative display | prior -20 + net 10 = due -10 | G01/G06 | REVIEW_REQUIRED authority terminology |

## Executable test index

For any exact test below, run `./.venv/Scripts/python -m pytest <path>::<function> -q` after the
disposable PostgreSQL setup in the audit report. Entries with multiple names share the stated file.
Do not run the truncating fixture against the hosted application database.

| Ref | Existing executable tests |
|---|---|
| E01 | apps/api/tests/test_cash_van.py::test_pricing_v1_precedence_rounding_packaging_and_invoice_snapshot |
| E02 | apps/api/tests/test_invoice_editor.py::test_editor_recalculates_pricing_v1_calculator_adjustments_and_immutable_updates |
| E03 | apps/api/tests/test_financial_schema.py (all five tests: schema/immutability, tenant costs, RLS, cardinality/history, Phase 2 migration) |
| E04 | apps/api/tests/test_invoice_editor.py::test_editor_rejects_mixed_currency_package_mismatch_and_unsafe_calculator; test_accepted_fuzzy_match_is_audited_and_owner_finance_is_tenant_protected |
| E05 | apps/api/tests/test_supplier_ledger.py (all four tests: aggregate/replay/reversal/currency; tenant/concurrent reversal; schema; forced RLS) |
| E06 | apps/api/tests/test_invoice_editor.py::test_receipt_fifo_owner_allocation_partial_multi_obligation_and_reversal_are_immutable |
| E07 | apps/api/tests/test_invoice_editor.py::test_post_confirmation_revision_posts_exact_delta_and_keeps_old_balance_out_of_sales |
| E08 | apps/api/tests/test_invoice_editor.py::test_unconfirmed_cancellation_has_no_financial_effect; test_confirmed_cancellation_matrix_handles_unpaid_and_fully_paid_invoices; test_zero_value_confirmed_cancellation_keeps_an_explicit_immutable_reversal |
| E09 | apps/api/tests/test_invoice_editor.py::test_editor_prefills_latest_tenant_cost_and_keeps_reasoned_override_revision_only |
| E10 | apps/api/tests/test_invoice_editor.py::test_confirmation_is_idempotent_assigns_official_number_and_posts_one_charge |
| E11 | apps/api/tests/test_invoice_editor.py::test_invoice_sequence_is_serialized_per_tenant_and_year_under_concurrency |
| E12 | apps/api/tests/test_invoice_editor.py::test_opening_balance_balance_api_overdue_alert_dedup_and_owner_security |
| E13 | apps/api/tests/test_invoice_editor.py::test_downward_confirmed_edit_releases_excess_allocation_without_mutating_payment |
| E14 | apps/api/tests/test_invoice_editor.py::test_cancellation_preserves_payment_releases_credit_and_refund_ceiling_is_concurrent |
| E15 | apps/operations-web/src/components/InvoiceEditor.test.tsx (three tests; mocked fetch/constant randomUUID) |
| E16 | apps/api/tests/test_public_invoices.py (seven tests); apps/operations-web/src/components/InvoiceSharing.test.tsx; apps/operations-web/src/components/PublicInvoicePage.test.ts |
| E17 | apps/api/tests/test_immutable_migration_files.py |
| E18 | apps/api/tests/test_opening_balances.py (customer/supplier uniqueness, signed values, correction/reversal, database enforcement, concurrency and tenant scope); apps/api/tests/test_hardening.py::test_migrations_build_a_new_database_from_zero |
| E19 | apps/api/tests/test_fa008_obligations.py (six signed opening/correction positions, ORM string runtime, receipt allocation/balance/debt, invoice coexistence, receipt reversal, refund compensation, tenant/currency isolation) |

## Historical-cost boundary retained

D-031/D-034 remain unchanged. Cost entries, revision snapshots, payments, allocations, and ledgers
are append-only; compensating events retain history. Current source selection is tenant-private,
effective-dated and selected/preferred-supplier scoped. A reasoned owner override remains revision-only
unless explicitly saved as a new cost entry. Such save/setup UI is currently missing (FA-004).
No current profit report exists to certify. Phase 8 must use revision cost snapshots and cannot
substitute later supplier prices or purchase costs. No stock, FIFO inventory costing, automatic FX,
per-purchase supplier allocation, tax, or new profit formula is introduced by this catalog.
