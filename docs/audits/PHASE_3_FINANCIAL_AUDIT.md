# Phase 3 financial correctness audit

Audit execution: 2026-09-07; documentation finalized 2026-09-08. Scope: implementation through P3-M5, with directly dependent future
financial contracts inspected. Audit only; no remediation or P3-M6 work.

AUDIT_BASE_SHA=2248c137e43c6c043725830c1303756da1d210ee

AUDITED_SHA=868bf1c5d4d49e755c74a6dd2c75a9a78f6ca6e6

GRAPH_SOURCE_SHA=868bf1c5d4d49e755c74a6dd2c75a9a78f6ca6e6

**Result: NO-GO.** 12 findings: **1 P0, 7 P1, 4 P2, 0 P3**. FA-007 proves that a lost receipt
response followed by the actual UI's retry can create duplicate money. The existing suites pass
but do not cover that path or several newly binding decisions. This conclusion concerns the
inspected code and synthetic local executions, not a claim that production accounts are corrupted.

## Authority and evidence discipline

AGENTS.md precedence is unchanged: exact Phase 1 requirements, approved decisions, project contract,
current phase, stack, compliant implementation, mechanical details. Read sources included
AGENT_START_HERE.md, SOURCE_OF_TRUTH.md, current status, contract/stack, PHASE_03.md, all financial
decisions through D-043, architecture, TRACEABILITY_MATRIX.md and AUDIT_REGISTER.md. Later root
phase specifications were inspected only for directly dependent financial/offline/reporting clauses.
Recovered historical guides and the preserved stash were not used or accessed.

The [invariant catalog](../contracts/financial-invariants.md) contains **32 EXPLICIT/BINDING** rows
and **5 CANDIDATE** questions with provenance, implementation, DB protection, tests and missing
coverage. A passing test is TEST ASSUMPTION evidence, not approval. Each finding below is a reviewer
assessment; its named root rule alone is BINDING. Suggested remediations are not implemented or
new approved product requirements. CANNOT VERIFY is used for unresolved timing/semantic policies
and production state. No second reviewer or independent audit was performed.

## Graph freshness and navigation

Initial HEAD was 868bf1c5d4d49e755c74a6dd2c75a9a78f6ca6e6, with a clean working tree. The prior graph represented
514dee4c53cf066f8ade17bc28fdb282021eb375. Git comparison proved the intervening six files were
assurance documentation/tooling only; no application files changed. Git also showed no application
change from the immutable implementation baseline. Nevertheless the supported repository script
rebuilt the structural graph for the exact audited HEAD before substantive graph reliance:

```powershell
pwsh -NoProfile -File scripts/refresh_graphify.ps1 -IntendedSha 868bf1c5d4d49e755c74a6dd2c75a9a78f6ca6e6
```

Graphify 0.9.55; code-only local extraction, no deep/LLM analysis or clustering; **1,400 nodes,
6,783 edges**. Freshness metadata and validation are recorded in
[GRAPHIFY.md](../assurance/GRAPHIFY.md). The previous count (1,398/6,782) belonged to the pre-tooling
SHA. Final documentation commit is not substituted for this audited source SHA.

| Ref | Navigation used | Directly verified source |
|---|---|---|
| G01 | path confirm_invoice_editor() → confirm_invoice(); path update_confirmed_invoice() → _reconcile_excess_allocations() | routes/invoices.py; services/invoice_finance.py; models/migrations and invoice tests |
| G02 | affected _prepare_cost(), depth 2; source/explain set_tenant_scope() | services/invoice_editor.py/pricing.py; repositories/tenancy.py; cost/revision schema |
| G03 | affected record_customer_receipt(), depth 2; affected _obligations(), depth 2 | routes/payments.py → customer_obligations/_selected_allocations/record_customer_receipt; customer_ledger.py |
| G04 | source enumeration of supplier mutation constructors and mounted routes, supplemented by structural database path | routes/supplier_ledger.py; services/supplier_ledger.py; models and 0008 |
| G05 | source tracing public invoice → _locked_invoice/_revision, cancellation and tests | services/public_invoices.py; services/invoice_finance.py; test_public_invoices.py |
| G06 | explain create_draft_invoice(); extracted caller tenant_create_draft_invoice() | routes/cash_van.py:435; services/cash_van.py:655; modern editor and actual React component |

G04/G05 include direct source tracing; they are not claims that every relationship was returned by
Graphify. Broad queries can be noisy/truncated. Inferred model edges were leads only. Direct constructor
search found financial writes in invoice_editor, invoice_finance, payments, customer_ledger,
supplier_ledger, legacy cash_van and synthetic seed_demo. There is no discovered application cost-entry
constructor/setup mutation; that absence was cross-checked against routes, OpenAPI and UI, not inferred
from a missing graph edge. Dynamic dependency/ORM/FK locking was inspected and experimentally checked.

## Actual financial model

| Area | BINDING requirement | IMPLEMENTATION BEHAVIOR / qualification |
|---|---|---|
| Authoritative values | revision financial fields and line snapshots; NUMERIC/Decimal Q4 | Header contains identity/lifecycle/pointers, not mutable totals. Revision stores currency, prior balance, subtotal, adjustments, net_sales, amount_due_display; line stores quantity, price/grade/package/media/cost provenance. |
| Draft | immutable accepted revision, server revision number | Modern POST creates header+revision+items; PUT checks predecessor and appends. Legacy tenant-nested POST remains mounted and writes canonical rows with a hardcoded zero prior balance. Same create command can create two headers. |
| Confirmation | atomic first number/current revision/one charge | Lock invoice, validate customer/positive sales/cost, lock/upsert tenant/year sequence, set confirmed pointer/status, append charge+audit, commit. Repeated confirmed request returns current response without another charge/number. Order/sync entities are not implemented yet. |
| Confirmed edit | immutable new revision, delta=new-old, reconcile allocations | Invoice lock and predecessor/command checks, recompute complete items/cost/prices, append revision/delta/audit, reverse+replace excess allocations, update pointer, commit. Zero net_sales incorrectly accepted. confirmed_revision_id remains original first-confirmed revision; current_revision_id is current truth. |
| Cancellation | draft no money; confirmed compensate current sales, release allocations, preserve payments | Invoice lock then customer lock, verify invoice ledger sum=current net, append -current net, reverse allocations, cancel header+audit. No automatic cash refund; token lifecycle is not revoked. |
| Customer balance/opening | signed immutable sum per currency, one historical opening | Positive debt/negative credit. Different opening keys create repeated events. No correction surface. Customer opening lacks an explicit party/advisory lock or conflict-to-replay recovery. |
| Receipt/allocation | positive receipt, negative ledger, FIFO/owner allocation, remainder credit | Advisory idempotency key then customer FOR UPDATE; select obligations; append payment/ledger/allocations/audit; commit. Same key replays. Amount/direction/customer/currency replay check ignores some metadata/selection fields; exact changed-command policy is not silently strengthened here. |
| Receipt reversal | immutable compensating payment/ledger/allocation history | One full reversal via uniqueness checks; original preserved. A subsequent positive non-invoice obligation fails String.value access. |
| Refund | positive payment and ledger, bounded existing same-currency credit under serialization | Advisory key/customer lock, recompute sum, reject amount>credit, append refund+audit. Backend refund/refund race test passes. UI retry identity remains unsafe. |
| Supplier balance/payment | signed aggregate by currency, no purchase allocation, separate excess prepayment | Supplier row/advisory lock and immutable payment/reversal; ordinary payment is uncapped; separate prepayment action/direction absent. Supplier opening permits repeated signed nonzero events. |
| Cost/history/profit | tenant-private append-only cost; immutable sale-time snapshot D-031/034 | Latest effective matching tenant/product/supplier/currency/basis at invoice entry; reasoned override not persisted as default. DB triggers protect old cost/revision/line rows. No profit report exists. Dedicated creation/preference setup and manual-line UI cost path missing. |
| Overdue | oldest unpaid by currency, Beirut calendar, strict >, unset off | Read-time calculation/stable alert key; strict > and unset-off correct; now.date() lacks Beirut conversion. Both obligation builders broadly select positive non-invoice effects. No durable notification worker/cadence claimed. |

Post-commit response reads happen in a new transaction after tenant scope is restored. They may
observe later committed state and cannot be treated as atomic historical response caches. The
commit operation itself remains one SQLAlchemy transaction for each inspected multi-row mutation.
Session cleanup rolls back uncommitted work on failure. No application exception/retry mechanism
can undo an already committed mutation merely because its response is lost.

## Independent known-target results

| Target | Classification | Evidence and exact boundary |
|---|---|---|
| D-038 | CONFIRMED_CONTRADICTION | P02/P03, FA-001: repeated initial opening with distinct keys; corrections absent. Signed/nonzero schema is compatible. |
| D-039 | CONFIRMED_CONTRADICTION | P04, FA-002: ordinary 25 payment against 20 payable produces -5, no explicit prepayment. |
| D-040 | CONFIRMED_CONTRADICTION | P08, FA-003: Beirut calendar day is missed; strict > and unset-disabled are correctly present. |
| D-041 | CONFIRMED_CONTRADICTION | P01/OpenAPI/source/UI, FA-004: required setup absent and cold-start confirmation blocked. This is a before-Phase-3-completion blocker; it does not retroactively invent a P3-M5 supplier CRUD acceptance criterion. |
| D-042 | CONFIRMED_CONTRADICTION | P06/P07, FA-005: multiple draft links and cancelled access. This audit covers financial lifecycle interaction only. |
| D-043 | CONFIRMED_CONTRADICTION | P07b, FA-006: initial zero confirmation rejected but confirmed zero edit accepted; existing test enshrines it. |

## Formula audit

Q means quantize to four decimal places using ROUND_HALF_UP. No new formula is defined here.

| Component | Approved rule / rounding boundary | Source and observed result / pathway differences |
|---|---|---|
| Catalog price | explicit grade price; else normal*(1-discount/100); else normal; Q basis then Q counterpart | pricing.resolve_product_pricing/derive_counterpart_prices. E01 verifies 10.0050 with 12.3456% → 8.7698, box 105.2376, explicit override, half-up tie. |
| Manual price | final effective entered price, no catalog grade adjustment | _prepare_items manual branch; Pydantic ge=0/Q4, correct in E02. No automatic grade reduction. |
| Quantity | Q4 before multiplication, >0 | Calculator returns Q result; _prepare_items rejects <=0. Diagnostic 0.00004→0; 0.00005→0.0001; 1/3→0.3333. The first cannot become a valid positive line. |
| Base/line | base=Q(effective*Q(quantity)); line=Q(base-line_discount+line_markup) | _prepare_items. Discounts/markup are calculator-quantized once per whole line, then checked nonnegative; negative line rejected. No per-unit multiplication of adjustments. |
| Invoice aggregation | subtotal=Q(sum bases); discount=Q(sum line discounts+invoice discount); markup=Q(sum line markups+invoice markup); net=Q(subtotal-discount+markup) | _totals follows D-036. Grade savings already in price, not double-counted. E02 example: base 22.5+6=28.5, discounts 1.5, markup .75, net 27.75. |
| Boundaries | nonnegative amounts; every confirmed revision net>0 | Negative line/net blocked; zero draft permitted; initial zero confirmation denied; confirmed zero edit allowed contrary to D-043. Raw tiny negative expressions that quantize to signed zero are an untested pre-quantization interpretation, not a new approved sign rule. |
| Precision/range | Decimal/NUMERIC(20,4), Q4 HALF_UP | Diagnostic Q(1.23455)=1.2346; basis 1.00005→1.0001 then box*12→12.0012. NUMERIC has 16 integer digits. Direct schema inputs bounded; arbitrary expression result/aggregate overflow yields unhandled failure (FA-012). No ordinary representable-value rounding corruption established. |
| Prior/display | immutable Q(prior snapshot+net), separately labelled from live balance | Modern draft reads currency ledger; confirmed edit excludes this invoice's INVOICE-source effects but keeps payments. Later payments do not rewrite snapshot. Legacy route hardcodes prior zero (P14); UI label insufficient (FA-010/011). Negative due snapshot interpretation remains C-F05. |
| Confirmation/delta | +net once; Q(new-old) once | invoice_finance matches equations and E10/E07. Unchanged positive invoice edit may validly have delta zero; D-043 prohibits zero net, not zero delta. |
| Customer balance | sum signed amounts by currency | customer_balances/_customer_balance; opening outside sales. Overdue/obligations are derived views, not a substitute balance. |
| Allocation/outstanding | apply minus reversed allocation; MAX(0,current net-effective allocated) | Modern service groups invoice charge+adjustments/reversal, then subtracts allocation totals. Downward edit reverses whole affected allocation and re-applies retained portion. Positive standalone labels/eligibility fail FA-008. |
| Customer refund | 0<refund<=MAX(0,-current balance), positive ledger | Recomputed under customer lock; E14 verifies ceiling/concurrency, cancellation never auto-refunds. Later UI retry can nevertheless represent one physical event twice when credit allows. |
| Supplier reduction | payment subtracts amount; reversal adds original; aggregate only | Equations and currency grouping correct; missing payment cap and labelled prepayment are D-039 violations, not a need for per-purchase accounting. |
| Historical cost/profit | chosen revision snapshot with currency/basis/package/provenance; never latest-cost rewrite | Existing immutable schema/tests support D-031/034. New edits may capture a new revision-specific choice while old revisions remain intact. No implemented profit calculation/report to certify or invent. Phase 8 metric details stay at Gate G. |

React uses backend decimal strings for money displays/payload amounts. Number is used for UI
filtering of positive allocation inputs, threshold and fuzzy score; it is not the authoritative
financial calculator. Existing frontend tests mock backend totals and do not independently verify
the formula. Public projection uses current server revision totals. E01 exercises the legacy route,
so it alone does not prove every modern-editor boundary. No FX, tax or inventory calculation exists.

## Transactions, concurrency and idempotency

| Operation | Transaction/lock and constraints | Assessment |
|---|---|---|
| Create draft, both routes | header+revision+items one commit; deferred canonical pointer FK | No partial committed draft found. Modern create UUID replay is not unique across headers (FA-009); legacy has no client command input. |
| Confirm | invoice FOR UPDATE; tenant/year sequence upsert+FOR UPDATE; unique official number/source effect | Replay/sequence tests pass; same-invoice expected revision checked before first confirmation. Already-confirmed replay returns current view; no new charge. |
| Draft/confirmed edit | invoice FOR UPDATE, expected predecessor, single-successor/revision-number/command uniqueness | Prevents two accepted branches. Confirmed edit does not explicitly lock Customer, but inserting revision obtains customer FK key-share before allocation reconciliation. Missing explicit lock alone is not proof of a race. |
| Edit versus receipt | P11 holds actual edit transaction after reconciliation then starts receipt | Receipt cannot complete while edit holds FK protection; after release, it allocates 50 against new net 50. Suspected race NOT ESTABLISHED. Other orderings/failure windows still need deterministic regression tests. |
| Customer receipt/refund/reversal | advisory key then Customer FOR UPDATE; unique key, original reversal and allocation reversal | Same-customer commands serialize (stronger than per-currency). FK dependencies matter. Refund/refund test passes. Receipt replay validates financial identity, not all metadata. Post-timeout UI creates a new key (P0). |
| Cancellation versus payment | invoice lock then Customer FOR UPDATE; payment uses Customer lock; immutable allocation reversals | Source supports serialization. No new deterministic cancel/payment race test executed; claim limited to inspected locking and existing cancellation/refund tests. |
| Customer opening | unprotected lookup, same-key query, append, one commit; FK locks at flush | Same-key concurrent unique conflict can escape instead of replay; distinct keys repeat opening. No automatic loss of committed effects claimed. |
| Supplier opening/payment/reversal | advisory key then Supplier FOR UPDATE; one reversal/key/effect | No simultaneous double reversal under existing test. Serialization cannot enforce an absent payable cap or opening-count check. |
| Public sharing | invoice lock, selected old-cap lock on rotate; one descendant per old capability | Does not enforce one active capability or cancelled-invoice invalidation. |
| Future sync/job/order effects | not implemented through P3-M5 | CANNOT VERIFY atomic future composition. Current services commit internally; Phase 4 must compose domain + idempotency result + change/audit/job effects in one boundary. This is an explicit integration dependency, not an early implementation demand. |

DB constraints do not by themselves enforce every cross-row equation, allocation sum, supplier cap,
confirmed-positive predicate or lifecycle source-effect count. The controlled services supply several
of these guarantees. Arbitrary privileged SQL corruption is not counted as an application P0.
Failed transactions are rolled back, but there is no universal deadlock/serialization-error retry
adapter; no deadlock/data loss was reproduced. Replay after an intervening edit can return current
state or stale conflict rather than a cached original response; future protocol contracts must
explicitly reconcile that behavior. Candidate payload/creation policies are not silently approved.

## Historical integrity and fresh-tenant journey

The seven financial/cost tables have rejecting UPDATE/DELETE triggers: product-cost entries,
revisions, revision items, customer ledger, supplier ledger, payments and allocations. Tests inspect
those triggers and exercise cost mutation rejection, immutable payments/ledgers, cost/cardinality
snapshots and Phase 2 upgrades. D-031/D-034 remain intact as historical storage rules; no later-price
rewrite was found. Later catalog/grade costs affect new accepted revisions, not old ones. This does
not certify a nonexistent profit dashboard or every future SQL writer. Operational duplicate events
can still make immutable history wrong (FA-007); immutability is not proof that admitted events are valid.

| Fresh tenant stage | Supported surface / result |
|---|---|
| Initialize tenant | Real application submit/approve path works in existing API fixtures; admin/user provisioning is a prerequisite. |
| Customer/category/product | Real tenant owner APIs used by _catalog; bilingual catalog, grade and currency supplied. |
| Supplier/cost/preference | MISSING owner mutation API/UI. _attach_latest_cost inserts Supplier/CostEntry and changes preferred_supplier_id directly. |
| Draft | Works without complete cost snapshot; no debt effect yet. |
| Confirm | Fresh path returns 409 INVOICE_COST_REQUIRED. Fixture-prepared catalog confirmation works. Manual UI line cannot obtain cost controls even if suppliers exist. |
| Receipt/balance | Works for eligible invoice obligations after fixture-only prerequisite setup; positive openings/reversals break obligations and new receipts. Retry can duplicate a cash event. |

Journey verdict: **BLOCKED for a fresh tenant using supported application surfaces**. Test fixture
setup is explicitly not proof of a usable owner setup workflow. No workaround was implemented.

## Executed validation and focused reproduction evidence

Existing application/test files were not edited. Diagnostics used ignored local .tmp files and
synthetic disposable databases only, separate from the test suite's truncating fixture database.
No hosted database, production data, deployment, new dependency or third-party financial service was used.
The disposable PostgreSQL 18 cluster at loopback port 55433 was started for this audit.

| Command / check | Actual result |
|---|---|
| Git application diff: original baseline→initial HEAD, prior graph SHA→HEAD | Empty for apps; prior graph delta consisted of the six assurance files only. |
| Graphify refresh/check for audited SHA | PASS; 0.9.55, code-only, 1400/6783. |
| python -m alembic -c apps/api/alembic.ini upgrade head on newly created disposable audit/probe databases | PASS from zero to 20260827_0011. No migration file changed. |
| ./.venv/Scripts/python -m pytest apps/api/tests -q --disable-warnings --junitxml=.tmp/financial-audit-pytest.xml | **126 passed, 0 failed/skipped**, 1 warning, 281.12s. Includes migration, financial, RLS and concurrency tests. |
| npm run test:operations | Separate rerun **34 passed / 5 files** in 26.05s. Prior overlapping run: 33 passed, 1 existing 10s timeout; preserved as test-stability observation, not suppressed or called an application failure. |
| Disposable Python API/SQLAlchemy probes P01–P11/P13/P14 | Completed; observed defects and counterexample to suspected race below. Harness setup/JSON-key mistakes were corrected only in ignored diagnostics; application untouched. |
| Existing component in jsdom: lost-response receipt retry (P12) | 1 diagnostic passed its assertion of different command keys after one entered receipt/retry. Uses randomUUID rather than constant UUID from current tests. |
| Pure calculator/basis probes | 1.23455→1.2346; .00004→0; .00005→.0001; 1/3→.3333; basis 1.00005→1.0001 then 12-piece box→12.0012. |

An initial full-suite invocation also ran, but its completion output was not retained; it is not
counted as a separate passing result. The listed JUnit-captured run is the verified full-suite evidence.
No new business tests were committed. Lint/type/build are not claimed as rerun for this audit-only
change; the final documentation/reference/diff checks are recorded below.

Reproduce existing tests with a new explicitly disposable local database, then from the repo root:

```powershell
# First create a new disposable database on the local test cluster, never the hosted database.
$env:DATABASE_URL='postgresql+psycopg://postgres@127.0.0.1:55433/<new-disposable-db>'
$env:TEST_DATABASE_URL=$env:DATABASE_URL
./.venv/Scripts/python -m alembic -c apps/api/alembic.ini upgrade head
./.venv/Scripts/python -m pytest apps/api/tests -q --disable-warnings
npm run test:operations
```

The E01–E17 index in the invariant catalog maps to exact existing test files/functions. Local
probe scripts are intentionally not a permanent test suite; the following steps preserve their
reproduction inputs without relying on their ignored files or real credentials. Use _owner_context,
_catalog and _attach_latest_cost from apps/api/tests/test_invoice_editor.py for synthetic setup;
mark the last helper as direct supplier/cost fixture insertion, never a supported setup surface.
Modern invoice probe item: product price 12.5000 USD, PIECE barcode 5280000000012, quantity 8,
zero line/invoice adjustments, one item, fresh client_command_id. This produces net_sales 100.

| Probe | Exact scenario / observed result |
|---|---|
| P01 | Without _attach_latest_cost, POST invoice then confirm its expected_revision_id → 409 INVOICE_COST_REQUIRED. |
| P02 | Same customer/USD/effective 2026-09-01T12:00Z; two opening POSTs with amount +10 and different UUID keys → 201,201. |
| P03 | Same supplier/USD/effective timestamp; two +10 openings/different keys → 201,201. |
| P04 | After P03 payable 20, supplier ordinary payment amount 25, fresh key → 201; balance -5 USD. |
| P05 | Identical modern draft POST body including client_command_id, repeated twice → two distinct invoice IDs. |
| P06 | Issue two capabilities for one draft; resolve both using their private header → 200,200. Raw secrets were never included in report/output. |
| P07 | Cancel that draft; resolve first capability → 200. Same missing status/revocation checks apply to confirmed cancellation. |
| P07b | Confirm net 100; PUT new command/predecessor with invoice_discount_expression 100 → 200, CONFIRMED, net 0.0000. |
| P08 | Positive LBP opening at Sep 1 12:00Z; threshold 5; call customer_debts(now=Sep 6 21:15Z), Beirut Sep 7 → actual age5/false, required age6/true. |
| P09 | Fresh customer, receipt10/USD/allocations=[]; repeat same key → same ID; repeat with new UUID → second Payment. Two distinct accepted receipts each append -10; one UI-intended receipt can therefore reduce ledger by 20. |
| P10 | Query obligations after positive opening → 500; fresh customer receipt then immutable reversal followed by obligations → 500. With exceptions enabled, String.value AttributeError at payments.py:208. |
| P11 | New invoice100, edit discount50; barrier holds actual update transaction after _reconcile_excess_allocations. Start receipt50 in another session. It remains blocked for the observation interval, then completes after edit commit with allocation50/new net50. No app functions changed; wrapper only pauses diagnostic thread execution. |
| P12 | Render actual InvoiceEditor; random UUID provider; select customer, enter receipt10; mocked transport records accepted POST then raises lost-response error. Form retains 10 and re-enables; retry sends a different key. Combine with real API P09 to prove duplicate-effect mechanism. This is component+API proof, not a full browser/network outage drill. |
| P13 | POST calculator expression 999999999999999999999999999999 (30 digits, within expression length limit) → 500. |
| P14 | Same customer balance10, same product12.50/qty1: legacy tenant invoice POST → prior0/due12.50; modern editor POST → prior10/due22.50. |

## Findings

All findings have status **OPEN / NOT REMEDIATED**. Their audited and graph source SHAs are
repeated for portability. Evidence paths below follow the prefix conventions in the invariant catalog.
P0/P1 findings rely on direct code plus controlled execution or exhaustive surface inspection,
never on an inferred graph relationship alone. Independent verification means a second reviewer or
permanent regression reproduction, neither performed in this task; it is recommended before closing findings.

### FA-001 — Repeated initial openings and missing correction workflow

| Field | Record |
|---|---|
| ID | FA-001 |
| Severity | P1 |
| Confidence | HIGH for described evidence; broader untested interleavings are explicitly qualified |
| Audited SHA | 868bf1c5d4d49e755c74a6dd2c75a9a78f6ca6e6 |
| Graph source SHA | 868bf1c5d4d49e755c74a6dd2c75a9a78f6ca6e6 |
| Binding authority | D-038; FI-16 |
| Exact evidence | P02/P03: two different keys for +10 USD each both return 201 for the same party/currency. No party/currency initial-opening uniqueness or supported correction route exists. |
| Affected files/symbols | customer_ledger.py::create_opening_balance:48–105; supplier_ledger.py::record_supplier_opening:72–125; models.py::CustomerLedgerEntry/SupplierLedgerEntry; migration 0008 |
| Graphify paths used | G04 |
| Direct source verification | YES; service, schema/models, mounted route and relevant tests inspected. See cited symbols and diagnostic table. |
| Realistic failure scenario | An owner imports the same historical opening twice with different keys: +10 becomes +20, with both rows labelled initial openings. |
| User-visible/business consequence | Incorrect historical debt/credit classification; no supported correction action to cleanly resolve it. |
| Existing protections | Nonzero amounts; same-key replay guards; immutable rows; supplier lock serializes but does not reject a second opening. |
| Recommended remediation | Enforce the approved one-opening rule under concurrency and provide explicit immutable correction/reversal semantics; preserve existing history. |
| Required regression test | Second key and concurrent second opening denied; signed nonzero first events accepted per currency; correction preserves original. |
| Decision impact | Decision resolved by D-038; no new sign or multiplicity question. |
| Independent verification required | YES before closure through direct recheck and permanent regression; no second independent reviewer in this audit. |
| Status | OPEN / NOT REMEDIATED |


### FA-002 — Supplier ordinary payment admits excess without explicit prepayment

| Field | Record |
|---|---|
| ID | FA-002 |
| Severity | P1 |
| Confidence | HIGH for described evidence; broader untested interleavings are explicitly qualified |
| Audited SHA | 868bf1c5d4d49e755c74a6dd2c75a9a78f6ca6e6 |
| Graph source SHA | 868bf1c5d4d49e755c74a6dd2c75a9a78f6ca6e6 |
| Binding authority | D-039/019; FI-23/24 |
| Exact evidence | P04: payable 20 USD accepts ordinary payment 25 (201); resulting supplier balance -5. No prepayment action/direction is mounted. |
| Affected files/symbols | supplier_ledger.py::record_supplier_payment:177–220/_write_payment_effect:127; models.py::Payment:1195; schemas/supplier_ledger.py::SupplierPaymentRequest |
| Graphify paths used | G04 |
| Direct source verification | YES; service, schema/models, mounted route and relevant tests inspected. See cited symbols and diagnostic table. |
| Realistic failure scenario | Owner enters a payment larger than current payable, including a stale payable after another payment. |
| User-visible/business consequence | Operational supplier credit is silently recorded as an ordinary payment, contradicting the approved accounting distinction. |
| Existing protections | Supplier FOR UPDATE and advisory key, immutable effects/reversal, aggregate currency sum; no per-purchase allocation. |
| Recommended remediation | Apply payable cap under the existing transaction and implement the approved explicit prepayment action/label without changing aggregate semantics. |
| Required regression test | Zero/negative payable, exact cap/excess, payment race, replay, explicit prepayment and reversal. |
| Decision impact | D-039 already resolves the policy; exact implementation remains remediation. |
| Independent verification required | YES before closure through direct recheck and permanent regression; no second independent reviewer in this audit. |
| Status | OPEN / NOT REMEDIATED |


### FA-003 — Overdue calendar can lag the approved Beirut day

| Field | Record |
|---|---|
| ID | FA-003 |
| Severity | P1 |
| Confidence | HIGH for described evidence; broader untested interleavings are explicitly qualified |
| Audited SHA | 868bf1c5d4d49e755c74a6dd2c75a9a78f6ca6e6 |
| Graph source SHA | 868bf1c5d4d49e755c74a6dd2c75a9a78f6ca6e6 |
| Binding authority | D-040; PHASE_03.md G; FI-25 |
| Exact evidence | P08: oldest=2026-09-01T12:00Z, now=2026-09-06T21:15Z (Sep 7 00:15 Beirut), threshold 5. Actual age 5/not overdue; approved age 6/overdue. |
| Affected files/symbols | customer_ledger.py::customer_debts:191–281, especially 259 |
| Graphify paths used | G03 |
| Direct source verification | YES; service, schema/models, mounted route and relevant tests inspected. See cited symbols and diagnostic table. |
| Realistic failure scenario | Owner checks debts after local midnight before UTC midnight. |
| User-visible/business consequence | A debt can miss its required red overdue indication and alert on the required local day. |
| Existing protections | Strict > comparator, null disables detection, currency grouping and positive-balance gate are correct. |
| Recommended remediation | Convert both instants to the approved calendar before extracting dates; preserve threshold/unset rules. |
| Required regression test | UTC/Beirut midnight, DST transitions, exactly threshold and threshold+1, database session timezone independence. |
| Decision impact | D-040 is binding; durable alert scheduling/cadence remains deferred. |
| Independent verification required | YES before closure through direct recheck and permanent regression; no second independent reviewer in this audit. |
| Status | OPEN / NOT REMEDIATED |


### FA-004 — Fresh tenants cannot provision required costs; manual lines have no cost controls

| Field | Record |
|---|---|
| ID | FA-004 |
| Severity | P1 |
| Confidence | HIGH for described evidence; broader untested interleavings are explicitly qualified |
| Audited SHA | 868bf1c5d4d49e755c74a6dd2c75a9a78f6ca6e6 |
| Graph source SHA | 868bf1c5d4d49e755c74a6dd2c75a9a78f6ca6e6 |
| Binding authority | D-041/034; PHASE_03.md B/D/L; FI-10/11 |
| Exact evidence | P01: fresh API-created catalog/customer draft confirmation returns 409 INVOICE_COST_REQUIRED. OpenAPI inventory has cost read-options and supplier ledger/payment paths only; no supplier/cost/preference setup mutations. Fixture helper directly inserts these prerequisites. Manual addLine has no productId, loadCostOptions returns, controls require nonempty options. |
| Affected files/symbols | routes/invoices.py::invoice_product_cost_options:78; invoice_editor.py::product_cost_options:248/_prepare_cost:446; InvoiceEditor.tsx::loadCostOptions:246/addManual:333 and conditional controls:718; test_invoice_editor.py::_attach_latest_cost:171 |
| Graphify paths used | G02/G06 |
| Direct source verification | YES; service, schema/models, mounted route and relevant tests inspected. See cited symbols and diagnostic table. |
| Realistic failure scenario | New owner creates products and customers but cannot create a supplier or append/select cost; even a pre-provisioned owner cannot provide manual-line cost through the UI. |
| User-visible/business consequence | Supported create→confirm→pay journey stops before confirmation. Dedicated setup is required before Phase 3 completes. |
| Existing protections | Server blocks incomplete/currency-mismatched cost, reasoned override supported by API, tenant-private schema exists. |
| Recommended remediation | Implement the already approved setup API/UI/editor link and allow required cost selection for manual lines; do not substitute fixture/SQL instructions. |
| Required regression test | New owner reaches confirmed catalog and manual invoices using real API/UI without supplier/cost fixture insertion. |
| Decision impact | D-041 resolved scope and phase; no deferral to Phase 6 authorized. |
| Independent verification required | YES before closure through direct recheck and permanent regression; no second independent reviewer in this audit. |
| Status | OPEN / NOT REMEDIATED |


### FA-005 — Sharing lifecycle conflicts with confirmed financial document rules

| Field | Record |
|---|---|
| ID | FA-005 |
| Severity | P1 |
| Confidence | HIGH for described evidence; broader untested interleavings are explicitly qualified |
| Audited SHA | 868bf1c5d4d49e755c74a6dd2c75a9a78f6ca6e6 |
| Graph source SHA | 868bf1c5d4d49e755c74a6dd2c75a9a78f6ca6e6 |
| Binding authority | D-042; FI-27 |
| Exact evidence | P06/P07: two issued draft links both resolve 200; after draft cancellation an existing link still resolves 200. No confirmed-status checks in issue/resolve; cancellation does not revoke capabilities. Rotation revokes only the selected link. |
| Affected files/symbols | public_invoices.py::issue_capability:66/resolve_public_invoice:151; invoice_finance.py::cancel_invoice:209; models.py::PublicInvoiceCapability:1374 |
| Graphify paths used | G05 |
| Direct source verification | YES; service, schema/models, mounted route and relevant tests inspected. See cited symbols and diagnostic table. |
| Realistic failure scenario | An owner sends multiple links for a draft, or cancels an invoice whose prior link remains accessible. |
| User-visible/business consequence | External customer continues receiving a financially ineligible document under the approved lifecycle; unsafe dependency for Phase 5. |
| Existing protections | Hash-only secret, expiry, explicit single-link revoke/rotation and restricted projection remain; no broad security conclusion here. |
| Recommended remediation | Enforce one active confirmed-only capability, replace/revoke previous links and revoke on cancellation atomically with lifecycle. |
| Required regression test | Draft/cancelled issue/resolve denial; confirmed create twice/rotate; existing link denied after cancellation, including races. |
| Decision impact | D-042 resolved; Phase 5 provisional representation still a separate gate detail. |
| Independent verification required | YES before closure through direct recheck and permanent regression; no second independent reviewer in this audit. |
| Status | OPEN / NOT REMEDIATED |


### FA-006 — Confirmed revision can reduce net sales to zero

| Field | Record |
|---|---|
| ID | FA-006 |
| Severity | P1 |
| Confidence | HIGH for described evidence; broader untested interleavings are explicitly qualified |
| Audited SHA | 868bf1c5d4d49e755c74a6dd2c75a9a78f6ca6e6 |
| Graph source SHA | 868bf1c5d4d49e755c74a6dd2c75a9a78f6ca6e6 |
| Binding authority | D-043; FI-06/14 |
| Exact evidence | P07b: confirm 100 USD, edit with invoice discount 100: HTTP 200, CONFIRMED, net_sales 0.0000. Existing test explicitly accepts the same forbidden boundary. |
| Affected files/symbols | invoice_finance.py::confirm_invoice:144 vs update_confirmed_invoice:444–568; invoice_editor.py::_totals:841; models.py::InvoiceRevision:995; test_invoice_editor.py::test_zero_value_confirmed_cancellation_keeps_an_explicit_immutable_reversal:1336 |
| Graphify paths used | G01 |
| Direct source verification | YES; service, schema/models, mounted route and relevant tests inspected. See cited symbols and diagnostic table. |
| Realistic failure scenario | Owner discounts all remaining value on a confirmed invoice instead of cancelling it. |
| User-visible/business consequence | Confirmed zero-sale history violates the approved lifecycle and later valid-sales/reporting assumptions. |
| Existing protections | Initial zero confirmation blocked; negatives blocked; zero delta for unchanged positive invoice remains legitimate. |
| Recommended remediation | Apply strictly positive net_sales to every confirmed revision while retaining the approved cancellation/reversal route and legitimate zero-delta edits. |
| Required regression test | Initial and revised zero rejected atomically, negative rejected, smallest positive accepted, zero-delta positive edit allowed; cancellation compensates. |
| Decision impact | D-043 resolved; do not remove historical zero rows or edit migration 0011. |
| Independent verification required | YES before closure through direct recheck and permanent regression; no second independent reviewer in this audit. |
| Status | OPEN / NOT REMEDIATED |


### FA-007 — Lost receipt response followed by UI retry can duplicate money

| Field | Record |
|---|---|
| ID | FA-007 |
| Severity | P0 |
| Confidence | HIGH for described evidence; broader untested interleavings are explicitly qualified |
| Audited SHA | 868bf1c5d4d49e755c74a6dd2c75a9a78f6ca6e6 |
| Graph source SHA | 868bf1c5d4d49e755c74a6dd2c75a9a78f6ca6e6 |
| Binding authority | PHASE_03.md H payment replay; P3-M4 Acceptance; FI-32 |
| Exact evidence | P12 renders the real InvoiceEditor: simulated commit then lost response retains amount 10, retry generates a different UUID. P09 calls the real PostgreSQL-backed API: same key returns original payment; changed key creates a second receipt. Source confirms each accepted key posts another -amount ledger entry. Existing UI tests mock randomUUID to one constant. |
| Affected files/symbols | InvoiceEditor.tsx::run:165/recordReceipt:484–527/recordRefund:553–584; payments.py::record_customer_receipt:379/_existing_payment:300; models.py::uq_payments_idempotency |
| Graphify paths used | G03 |
| Direct source verification | YES; service, schema/models, mounted route and relevant tests inspected. See cited symbols and diagnostic table. |
| Realistic failure scenario | One actual cash receipt of 10 USD commits; the response is lost; the owner retries the still-filled form, which sends a new idempotency key. |
| User-visible/business consequence | Two receipts/-20 ledger effect for one actual 10 cash event; understated debt or fabricated refundable credit. This meets the requested P0 clause for proven materially incorrect money under normal retry, although compensating reversal can repair known duplicates. |
| Existing protections | Same-key backend replay is safe; busy flag prevents a simultaneous ordinary click, not retry after failure. Refund ceiling cannot prevent a second logical refund when enough credit remains. |
| Recommended remediation | Retain one command identity and exact payload for an unresolved financial submission; retry/reconcile that command before issuing a new logical command. |
| Required regression test | Real UI plus API/database: lose committed response, retry, one Payment and one ledger effect; receipt and refund; restart strategy at Phase 4 gate. |
| Decision impact | No new financial formula/policy needed. Persistence mechanics require bounded design; Phase 4 does not justify current duplicate receipts. |
| Independent verification required | YES before treating this blocker as resolved; component+API/database proof already exists, but no second reviewer or full browser outage drill. |
| Status | OPEN / NOT REMEDIATED |


### FA-008 — Opening/reversal obligations break customer receipt workflow

| Field | Record |
|---|---|
| ID | FA-008 |
| Severity | P1 |
| Confidence | HIGH for described evidence; broader untested interleavings are explicitly qualified |
| Audited SHA | 868bf1c5d4d49e755c74a6dd2c75a9a78f6ca6e6 |
| Graph source SHA | 868bf1c5d4d49e755c74a6dd2c75a9a78f6ca6e6 |
| Binding authority | PHASE_03.md F/G/H; FI-17/18/19/25 |
| Exact evidence | P10: obligations after a positive opening and after a receipt reversal return 500. Direct exception is AttributeError: 'str' object has no attribute 'value'; entry_type maps to String(50). record_customer_receipt calls _obligations before posting. Both obligation builders also select all positive non-INVOICE entries, including refund/reversal compensations. |
| Affected files/symbols | payments.py::_obligations:123–214, especially 154/208; models.py::CustomerLedgerEntry.entry_type:1140; customer_ledger.py::customer_debts:238 |
| Graphify paths used | G03 |
| Direct source verification | YES; service, schema/models, mounted route and relevant tests inspected. See cited symbols and diagnostic table. |
| Realistic failure scenario | An owner records historical debt then tries to collect it, or reverses a receipt then records the corrected one. |
| User-visible/business consequence | Obligation listing/receipt creation fails. The broad positive-entry eligibility also needs review so fixing the label alone does not expose doubled obligations (original invoice restored plus reversal compensation). That second consequence is a source-level lead, not a separately reproduced production corruption. |
| Existing protections | Failure before receipt insert rolls back cleanly; ledgers remain intact; schema/type annotations do not deserialize String into Enum. |
| Recommended remediation | Correct runtime type handling and reconcile eligible obligation origins against immutable compensations; do not treat a reversal/refund as an independent sale by default. |
| Required regression test | Opening→FIFO/owner receipt; receipt→reversal→new receipt; refund→new sale; obligations reconcile with canonical invoice allocations and credit. |
| Decision impact | Existing obligation/reversal requirements suffice for the crash. Any new credit-reallocation product flow stays C-F03. |
| Independent verification required | YES before closure through direct recheck and permanent regression; no second independent reviewer in this audit. |
| Status | OPEN / NOT REMEDIATED |


### FA-009 — Repeated draft-create command creates different invoice headers

| Field | Record |
|---|---|
| ID | FA-009 |
| Severity | P2 |
| Confidence | HIGH for described evidence; broader untested interleavings are explicitly qualified |
| Audited SHA | 868bf1c5d4d49e755c74a6dd2c75a9a78f6ca6e6 |
| Graph source SHA | 868bf1c5d4d49e755c74a6dd2c75a9a78f6ca6e6 |
| Binding authority | PHASE_03.md B/M revision-command foundation; future PHASE_04.md F; C-F01 |
| Exact evidence | P05 sends the identical create payload/client_command_id twice; both succeed with distinct header IDs. Command uniqueness is scoped to tenant+invoice+command, so it cannot deduplicate header creation. |
| Affected files/symbols | invoice_editor.py::create_editor_draft:864–920; models.py::InvoiceRevision command uniqueness:971–976; InvoiceEditor.tsx::saveDraft:367 |
| Graphify paths used | G06 |
| Direct source verification | YES; service, schema/models, mounted route and relevant tests inspected. See cited symbols and diagnostic table. |
| Realistic failure scenario | A client retries a create after losing its response; two drafts appear or an unreferenced draft remains. |
| User-visible/business consequence | Unnecessary duplicate documents and an expensive future offline/checkout exactly-once integration hazard; no charge is posted by draft creation alone. |
| Existing protections | Edit predecessor/command uniqueness works within one header; draft creation does not itself charge money. |
| Recommended remediation | Before exposing replayed creates through sync/checkout, define and enforce a stable create identity consistent with those approved protocols. |
| Required regression test | Same logical create replay returns one header; conflicting payload and concurrent same-key creation cases. |
| Decision impact | Exact current cross-header dedup scope remains C-F01; do not invent a new key contract in this audit. |
| Independent verification required | YES before closure through direct recheck and permanent regression; no second independent reviewer in this audit. |
| Status | OPEN / NOT REMEDIATED |


### FA-010 — Legacy draft route omits actual prior balance from its due snapshot

| Field | Record |
|---|---|
| ID | FA-010 |
| Severity | P2 |
| Confidence | HIGH for described evidence; broader untested interleavings are explicitly qualified |
| Audited SHA | 868bf1c5d4d49e755c74a6dd2c75a9a78f6ca6e6 |
| Graph source SHA | 868bf1c5d4d49e755c74a6dd2c75a9a78f6ca6e6 |
| Binding authority | D-037; PHASE_03.md B/D/F; FI-26 |
| Exact evidence | P14: same customer with 10 USD balance and 12.50 product: legacy route stores prior 0/due 12.50; editor route stores prior 10/due 22.50. Both write the canonical revision table. |
| Affected files/symbols | cash_van.py::create_draft_invoice:655–779, especially 729–735; invoice_editor.py::_prior_balance:664/create_editor_draft:880; routes/cash_van.py::tenant_create_draft_invoice:435 |
| Graphify paths used | G06 |
| Direct source verification | YES; service, schema/models, mounted route and relevant tests inspected. See cited symbols and diagnostic table. |
| Realistic failure scenario | A still-mounted tenant-nested draft route is used while the customer has a historical/current balance. |
| User-visible/business consequence | Different entry paths create contradictory due snapshots. Ledger/net-sales values are not altered by this draft-only defect. |
| Existing protections | Canonical immutable storage and grade service shared; modern editor includes prior balance correctly. |
| Recommended remediation | Align supported draft paths with approved snapshot semantics without inventing a second invoice model. |
| Required regression test | Legacy/editor parity for positive, negative and zero prior balance, USD/LBP separation. |
| Decision impact | D-037 resolves due semantics; compatibility handling must preserve Phase 1 required routes. |
| Independent verification required | YES before closure through direct recheck and permanent regression; no second independent reviewer in this audit. |
| Status | OPEN / NOT REMEDIATED |


### FA-011 — Due snapshot is still labelled as current total due

| Field | Record |
|---|---|
| ID | FA-011 |
| Severity | P2 |
| Confidence | HIGH for described evidence; broader untested interleavings are explicitly qualified |
| Audited SHA | 868bf1c5d4d49e755c74a6dd2c75a9a78f6ca6e6 |
| Graph source SHA | 868bf1c5d4d49e755c74a6dd2c75a9a78f6ca6e6 |
| Binding authority | D-037; FI-26 |
| Exact evidence | Saved total_due is immutable and not refreshed by later ledger events, but label is Total due (and Arabic equivalent), without revision/snapshot distinction. Live balances render separately. |
| Affected files/symbols | InvoiceEditor.tsx:734 and recordReceipt/recordRefund refresh flow; apps/operations-web/src/i18n.ts:27/54 |
| Graphify paths used | G06 |
| Direct source verification | YES; service, schema/models, mounted route and relevant tests inspected. See cited symbols and diagnostic table. |
| Realistic failure scenario | 100 invoice is paid 100; immutable tally still says Total due 100 while live customer balance is 0. |
| User-visible/business consequence | Owner can confuse historical revision display with collectible current balance. |
| Existing protections | Separate current balance/obligations exist; backend preserves the approved historical snapshot. |
| Recommended remediation | Label the snapshot explicitly in both languages and present current balance/outstanding distinctly; do not rewrite the snapshot after payment. |
| Required regression test | Receipt/refund updates live balance while historical due remains and labels clearly distinguish them. |
| Decision impact | Already approved by D-037; no formula change required. |
| Independent verification required | YES before closure through direct recheck and permanent regression; no second independent reviewer in this audit. |
| Status | OPEN / NOT REMEDIATED |


### FA-012 — Calculator/storage range failures escape as server errors

| Field | Record |
|---|---|
| ID | FA-012 |
| Severity | P2 |
| Confidence | HIGH for described evidence; broader untested interleavings are explicitly qualified |
| Audited SHA | 868bf1c5d4d49e755c74a6dd2c75a9a78f6ca6e6 |
| Graph source SHA | 868bf1c5d4d49e755c74a6dd2c75a9a78f6ca6e6 |
| Binding authority | 01_TECH_STACK.md Money; PHASE_03.md D; FI-01 |
| Exact evidence | P13: syntactically valid 30-digit calculator input returns HTTP 500. parse uses local precision 38 then quantizes outside its caught block/default precision; expression inputs have length limits but no representable-result bound. DB NUMERIC limits can also reject oversized staged totals. |
| Affected files/symbols | invoice_editor.py::_Calculator.parse:88–105/money:58/_prepare_items:627/_totals:841; schemas/invoice_editor.py::CalculatorRequest |
| Graphify paths used | G02 |
| Direct source verification | YES; service, schema/models, mounted route and relevant tests inspected. See cited symbols and diagnostic table. |
| Realistic failure scenario | Owner pastes or multiplies a large value into the supported calculator. |
| User-visible/business consequence | Opaque failure instead of a usable validation result; no demonstrated rounding corruption for ordinary representable money. |
| Existing protections | Pydantic bounds direct Decimal fields; transaction rollback prevents partial persistence; expression length bound and operator allowlist exist. |
| Recommended remediation | Validate representability/catch arithmetic overflow before persistence; retain approved Q4 HALF_UP stages. |
| Required regression test | Expression length-valid overflow, max NUMERIC value, large product/aggregate and no partial rows on rejection. |
| Decision impact | Mechanical error handling can follow existing API errors; no new monetary formula or tighter business limit assumed. |
| Independent verification required | YES before closure through direct recheck and permanent regression; no second independent reviewer in this audit. |
| Status | OPEN / NOT REMEDIATED |

## Test quality and remaining critical coverage

The existing suites establish real PostgreSQL behavior, not just arithmetic mocks. They exercise
sequence concurrency, refund ceiling serialization, supplier reversal serialization, RLS, immutable
migration protection, and snapshot survival. They are useful regression evidence but insufficient
for current decisions: the zero-confirmed-edit test and draft-sharing helper explicitly encode
behavior superseded by D-043/D-042. Opening tests exercise same-key replay, not different-key
multiplicity. Supplier payment tests never try excess. The 40-day overdue test cannot resolve
midnight/calendar correctness. Formula examples validate selected paths, not every Q4 boundary.

Critical missing regressions are the tests listed on FA-001–FA-008: retained payment command identity
after lost response; supported supplier/cost/manual-line setup; opening uniqueness/corrections;
opening/reversal/refund→obligations→receipt; cap/prepayment races; Beirut midnight; positive confirmed
revision boundary; sharing/cancel lifecycle. Also add simultaneous same-predecessor edits and
confirm/cancel/payment/reversal interleavings, rollback injection at multi-record boundaries,
confirmation same-invoice replay under concurrency, and snapshot survival across later cost/package
changes. These are recommendations for remediation acceptance, not implemented tests.

Test fixture blind spots: _attach_latest_cost writes supplier/cost/preference directly; financial
schema tests construct rows directly; the downward-allocation test inserts Payment/Allocation without
its corresponding customer receipt ledger effect. That last test proves allocation release in isolation,
not end-to-end financial reconciliation. Existing frontend tests replace fetch and set crypto.randomUUID
to a constant, concealing changing-command retry behavior. A mocked successful confirmation cannot
prove the owner workflow's missing prerequisites. Full browser E2E/accessibility remains P3-M6 work.

Specific later Hypothesis candidates (not installed):

- FI-01–05: bounded Decimal quantities/prices/adjustments, HALF_UP ties, basis→counterpart order,
  grade precedence, fixed adjustment aggregation and no double-discount.
- FI-13–22/32: generated command histories/replays with invariant balance=sum ledger, one effect per
  command, telescoping revision deltas, allocation conservation/reversal and refund credit ceiling.
- FI-16/23/24: per-party/per-currency opening uniqueness, signed historical credit, capped ordinary
  supplier payment versus explicit prepayment and immutable reversal.
- FI-09/10: later cost/preference/package changes never mutate previous revision snapshots.
- FI-25: timezone-aware dates around Beirut calendar/DST boundaries, threshold equality and null.

Property generation does not replace deterministic PostgreSQL race tests or real UI/API outage tests.
No Hypothesis, security scanner, browser package, architecture tool or additional agent framework
was installed. No CANDIDATE was promoted into BINDING by recommending a property.

## Direct future-phase dependencies that become expensive later

| Future scope | Explicit approved dependency on current foundation | Consequence if deferred |
|---|---|---|
| Phase 4 F/H/I/O | Domain mutation+idempotency result+change/audit/job effects one transaction; replay original canonical result; predecessor conflicts; server numbers | Preserve logical keys, reconcile internally committing service composition and create identity before sync adapters. A duplicate immutable payment would be replicated/backed up; cleanup becomes cross-device reconciliation. |
| Phase 5 E/F and cancellation | Atomic checkout with one order/draft; provisional representation separate from D-042 confirmed sharing; reuse Phase 3 cancellation | Do not reuse current permissive sharing/create retries as approved contracts. Existing header/order unique index is useful, but no actual Order transaction is implemented yet. |
| Phase 6 C/H/I | Extend existing append-only cost table; D-038/039 supplier openings/aggregate payments/prepayment; never second cost truth | Fix current provisioning and credit semantics before purchases generate more dependent history. No purchase-specific allocation or inventory costing introduced. |
| Phase 7 task projections | Relevant invoices only, owner supplier costs/profit excluded | Preserve revision/cost separation and correct canonical financial lifecycle; broad driver/security audit remains separate. |
| Phase 8 A/B/C, Gate G | Confirmed noncancelled canonical sales, effective receipts, per-currency ledgers, immutable revision-cost historical profit, local calendar | Duplicate receipts and zero-sale confirmed records become false aggregates/training features. Snapshot storage is sound, but metric formula/date/coverage questions remain the phase gate's responsibility. |
| Phase 9 D/E and pilot/recovery | Invoice/refund/payment concurrency, idempotency, reconciliation and recovery drills | Future backups/restore must verify ledgers and event identity, not merely immutable-row counts. Deployment runtime-role/telemetry remains outside this local audit. |
| Phase 10 gate/A | Trustworthy confirmed/noncancelled sales history, currencies/calendar, stable product history | Do not build forecasting on unresolved foundational financial defects; no future model or metric redesigned here. |

## Final disposition and documentation validation

Apply the requested rubric exactly: any unresolved confirmed P0 → NO-GO; otherwise blocking P1 →
CONDITIONAL GO; otherwise GO. **FA-007 is confirmed P0, so NO-GO.** FA-001–FA-006 and FA-008 are
additional P1 blockers for their dependent workflows and Phase 3 completion. FA-009–FA-012 are P2;
they do not independently determine the NO-GO. The passed test suite does not cancel these findings.

Five candidate details remain non-binding: cross-header create-command scope, between-draft-and-confirm
cost refresh timing, later allocation of existing credit, numbering year timezone, and the meaning of
D-043 nonnegative invoice totals when D-037 produces a negative due snapshot. No candidate is used
as the sole reason for P0/P1. C-F05 is a focused authority-terminology question for affected remediation;
this audit does not silently cap due or weaken either approved rule. Existing D-038–D-043 contradictions
need implementation correction, not the owner re-answering already approved decisions.

Final changed files are audit/invariant/freshness documentation only. Original AUDIT_BASE_SHA stays
immutable; all application, business test, migration, phase specification, decision and dependency files
remain unchanged. Ignored synthetic diagnostic scripts/results are not committed. The old graph-policy
source paths were corrected to actual tawzeevo_api paths as a documentation accuracy fix.

The accompanying register follow-up links this report and supersedes prior financial uncertainty only
where this audit established direct evidence. It does not close unrelated continuity findings. No
financial remediation, P3-M6, tenant/security audit, deployment or push took place.

Documentation self-checks completed 2026-09-08:

- Graphify check-only passed against the exact audited SHA (1,400 nodes / 6,783 edges).
- All 12 findings retain 18 metadata fields; severity totals match the register.
- All 32 binding and five candidate table rows have consistent columns and separate provenance.
- The 17 executable-test index rows resolve; all 15 explicitly named test functions and 48 explicit
  file/symbol pairs resolve in repository source. This is reference validation, not additional test execution.
- All local Markdown link targets in the four changed documents exist; all 17 E, 15 P and six G
  definitions resolve their uses. Heading navigation was not browser-tested.
- Complete documentation changes reviewed; no application/business-test/migration/dependency/specification
  or decision changes. Final staging is restricted to these four Markdown files.
- JUnit recheck confirms 126 tests, zero failures/errors/skips. The preserved stash reference still
  equals 9050d544791b5e22d15c2ff1a1acdbd503b40418; no stash content was read or changed.
- The dedicated local PostgreSQL test cluster is no longer running at finalization. Ignored synthetic
  databases/diagnostics remain local and are not part of the commit.

Whitespace/conflict/unmerged-index and post-commit clean-tree checks accompany the final handoff.
The documentation commit does not replace either the original implementation baseline or audited
graph-source SHA. No completed implementation milestone is being declared by this audit checkpoint.

Recommended next action only: independently verify and then authorize a bounded remediation plan
starting with FA-007's payment-retry identity, followed by the confirmed P1 blockers; preserve this
audit as the pre-remediation evidence baseline.
