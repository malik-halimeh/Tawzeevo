# PHASE_03.md — Production Invoice, Ledger, Payments, Debt, Financial Integrity

## Phase objective
Replace the Phase 1 draft-invoice slice with Tawzeevo's production financial core.

By the end of Phase 3, invoice value, customer debt, payments, allocations, reversals, refunds, overdue state, and post-confirmation edits must be reproducible from immutable server-authoritative financial history.

This phase implements the locked financial contracts. It must not reinterpret them.

## Start gate — Gate C
Do not implement Phase 3 until all are verified:
- Phase 2 `pricing-v1` passes;
- PostgreSQL money uses `NUMERIC(20,4)`;
- application money arithmetic uses Decimal, never authoritative binary float;
- Q4 `ROUND_HALF_UP` examples are locked/tested;
- order/invoice cardinality is locked;
- invoice header vs immutable revision source of truth is locked;
- server-authoritative invoice/revision sequencing is locked;
- customer ledger is locked;
- immutable payment/allocation model is locked;
- cancellation/reversal accounting is locked;
- customer refund ceiling/concurrency rule is locked.

If any required contract conflicts with the repository, stop P3-M1 and ask the user. Do not invent financial behavior.

---

# A. Financial invariants

- `invoices` = identity/lifecycle header, not mutable financial truth.
- `invoice_revisions` = immutable complete financial snapshots.
- `invoices.current_revision_id` = canonical current financial version.
- old revisions/items are never rewritten after catalog/price changes.
- payments, ledger entries, and payment allocations are immutable.
- corrections use new revision/adjustment/reversal records.
- one invoice has exactly one ISO currency.
- balances are always per currency.
- never silently convert/sum USD and LBP.
- backend calculations are authoritative.
- every tenant-owned financial row has explicit `tenant_id` + RLS.
- platform `admin` does not automatically gain tenant-private financial access.

Canonical pricing remains `pricing-v1`:
```text
scale = 4 decimal places
rounding = ROUND_HALF_UP
```

---

# B. Production invoice model

## Invoice header
Use the locked production header semantics:
- UUID id;
- tenant_id;
- order_id nullable;
- customer_id nullable;
- official_invoice_number nullable until first server-accepted confirmation;
- current_revision_id;
- confirmed_revision_id nullable;
- lifecycle `draft | confirmed | cancelled`;
- created/updated/confirmed/cancelled timestamps;
- actor metadata.

Do not duplicate authoritative mutable totals on the header.

## Invoice revisions
Each accepted edit is an immutable full snapshot containing:
- tenant/invoice;
- client revision command UUID;
- predecessor revision;
- server revision number assigned only after server acceptance;
- pricing_version;
- currency;
- customer snapshot/reference;
- prior-balance snapshot;
- subtotal;
- discount/markup totals;
- net_sales;
- amount_due_display;
- actor/timestamps/reason.

## Revision items
Snapshot:
- tenant_product_id nullable;
- barcode/name/media version;
- unit/pieces-per-box;
- quantity;
- normal unit price;
- grade-rule snapshot;
- effective unit price;
- tenant-private supplier and product-cost source reference;
- immutable unit-cost snapshot, currency, piece/box basis, and package context;
- owner override flag/reason where applicable;
- line adjustments;
- line total.

Catalog changes must never rewrite historical invoice content.

## Tenant-private product-cost source

Use D-034 exactly:
- supplier identities, preferred supplier selection, and costs are tenant-scoped;
- the same supplier/product may have different costs in different tenants;
- cost entries are append-only and effective-dated;
- invoice entry preloads the latest eligible matching tenant/product/supplier/currency/basis entry;
- changing the selected supplier reloads only that tenant's eligible cost;
- an owner may override on the invoice with a required reason;
- an override is revision-only unless explicitly saved as a new cost entry;
- confirmation requires a matching cost and snapshots its full provenance;
- no global supplier price, silent currency conversion, stock, FIFO, or weighted-average costing.

Phase 3 establishes the minimum cost-entry and immutable snapshot foundation. Phase 6 procurement
may append supplier-derived cost entries without changing this contract or rewriting history.

---

# C. Invoice numbering

Official invoice number:
```text
YYYY-000001
```

Sequence scope:
```text
tenant + year
```

Allocate under PostgreSQL transaction/row lock.

Rules:
- assigned only on first server-accepted confirmation;
- published numbers never reused;
- gaps allowed;
- client/offline code must never fabricate authoritative invoice/revision numbers.

Phase 4 later adds temporary offline references while preserving this same authority.

---

# D. Invoice editor

Owner workflow supports:
- customer lookup;
- barcode item entry;
- manual item entry;
- image per item;
- quantity;
- piece/box;
- calculator-style numeric/operator input;
- grade pricing;
- line discount/markup;
- invoice discount/markup;
- previous customer balance display;
- net sales;
- total due.

Frontend may preview. Backend always recalculates/validates.

## Text-to-items
Deterministic parser:
- Arabic/English normalization;
- quantity extraction;
- aliases where supported;
- exact match first;
- fuzzy suggestions only after exact failure;
- configurable threshold;
- never auto-select ambiguity;
- owner confirmation;
- accepted fuzzy match audited.

Normal catalog search remains exact/prefix-first.

---

# E. Confirmation and post-confirmation edit

## Confirmation transaction
Atomically:
1. lock order/invoice;
2. require valid lifecycle/current predecessor;
3. accept/number revision if needed;
4. allocate official invoice number if null;
5. confirm order when applicable;
6. confirm invoice and pointers;
7. append exactly one invoice-charge ledger effect for current `net_sales`;
8. append audit/sync effects;
9. commit.

Replay must not duplicate charge or number.

## Post-confirmation edit
Atomically:
1. lock invoice/current revision;
2. validate expected predecessor;
3. calculate complete new immutable revision;
4. assign server revision number;
5. compute `delta = new_net_sales - old_net_sales`;
6. append exactly one `invoice_adjustment` ledger entry for delta;
7. update current revision pointer;
8. reconcile excess allocations after downward edit;
9. audit/sync;
10. commit.

Never rewrite old payment/revision.

---

# F. Customer ledger and debt

`customer_ledger_entries` are append-only.

Required semantics:
- tenant_id;
- customer_id;
- currency;
- signed_amount;
- entry_type;
- source_type/source_id/source_effect_key;
- effective_at;
- server created_at;
- actor;
- reversal relation;
- idempotency key where applicable;
- safe metadata.

Sign:
```text
positive = customer owes tenant
negative = customer payment/credit
```

Entry types include:
- opening_balance;
- invoice_charge;
- invoice_adjustment;
- invoice_reversal;
- customer_payment;
- customer_payment_reversal;
- customer_refund;
- authorized_manual_adjustment.

Balance:
```text
SUM(customer_ledger_entries.signed_amount)
```
per currency only.

Old/opening balance is a ledger event, not current invoice sales.

---

# G. Overdue behavior

Owner configures:
```text
customer_overdue_threshold_days = X
```

Default receipts allocate FIFO to oldest unpaid obligations.

Overdue age derives from the oldest still-unpaid obligation in that currency.

If age > X and customer balance is positive:
- owner UI flags red;
- in-app owner alert is generated/deduplicated according to policy.

---

# H. Payments and allocations

## Payments
Immutable UUID payment entity:
- tenant;
- customer/supplier party based on direction;
- direction;
- positive amount;
- ISO currency;
- method/reference;
- paid_at;
- server recorded_at;
- recorder;
- source device optional;
- reversal relation;
- notes.

Phase 3 completes customer payments and the final supplier-ledger/payment schema foundation for Phase 6.

## Customer allocations
`payment_allocations` explain which obligation a receipt satisfies.

Rules:
- exactly one target;
- currency match;
- allocations cannot exceed effective payment;
- default FIFO oldest unpaid obligation;
- owner may explicitly allocate differently;
- corrections use reversal/new allocation;
- unallocated receipt remains customer credit.

Invoice outstanding:
```text
MAX(0, current canonical net_sales - effective allocated amount)
```

Downward invoice edit below allocated amount:
- reverse excess allocations;
- released amount becomes unallocated credit;
- original payment remains immutable.

Upward edit:
- existing allocations remain;
- outstanding increases.

Payment transaction:
1. create immutable receipt;
2. append one negative ledger effect;
3. create allocations;
4. audit/sync;
5. commit atomically.

Idempotent replay returns original result.

---

# I. Cancellation and refund

## Unconfirmed cancellation
- no invoice-charge exists;
- preserve provisional revisions;
- mark order/invoice cancelled;
- no financial reversal invented.

## Confirmed cancellation
Atomically:
1. lock order/invoice/revision;
2. determine effective allocations;
3. append invoice-reversal ledger effect;
4. reverse allocations so paid money becomes customer credit;
5. mark order/invoice cancelled;
6. preserve payments/revisions;
7. audit/sync;
8. commit.

Cancellation never automatically returns cash.

## Customer refund ceiling
For each currency:
```text
current_customer_balance = SUM(ledger signed_amount)
available_credit = MAX(0, -current_customer_balance)
0 < refund_amount <= available_credit
```

Refund must:
- match credit currency;
- serialize/lock per customer+currency;
- recompute credit inside transaction;
- reject excess;
- create immutable `customer_refund`;
- append positive refund ledger entry;
- audit/sync;
- commit.

No refund may create new customer debt.

---

# J. Public capability + WhatsApp foundation

Phase 3 implements the safe public invoice capability used for WhatsApp and later Phase 5.

Capability:
- >=256 random bits;
- store SHA-256 hash only;
- tenant/order/invoice scoped;
- expires/revokes/rotates;
- current default hard lifetime 90 days;
- raw token never logged.

Public projection may show only:
- tenant branding;
- checkout/contact snapshot if applicable;
- current invoice/order representation;
- owner-set delivery date after confirmation;
- cancellation decision message where applicable.

Never show unrelated debt/history/grade/supplier/cost/profit/driver data.

Headers:
```text
Cache-Control: no-store
X-Robots-Tag: noindex, nofollow
Referrer-Policy: no-referrer
```

Rate limit.

WhatsApp share:
- normalized customer phone;
- invoice text summary;
- safe capability URL;
- no internal-ID authorization.

Generated PDF is not mandatory unless later approved.

---

# K. API/backend scope

Use canonical groups:
```text
/api/v1/invoices
/api/v1/payments
/api/v1/customer-ledger
```
plus established public capability group.

Thin routes.
Financial rules in services/domain layer.
Multi-row invariants use explicit SQLAlchemy/PostgreSQL transactions.

---

# L. Frontend scope

Operations frontend must support:
- invoice editor;
- customer balance by currency;
- barcode/manual/text entry;
- packaging;
- grade-price explanation;
- discount/markup;
- draft/confirmed state;
- confirmation;
- immutable revision/history view;
- payment receipt;
- allocation/outstanding;
- customer debt/overdue red indicator;
- valid-credit refund;
- owner cancellation actions;
- WhatsApp share.

EN/AR, RTL/LTR, accessibility, error/loading states remain mandatory.

---

# M. Migration requirements

- never edit applied migrations;
- extend/upgrade Phase 1/2 invoice entities, do not create a competing invoice system;
- add revision/item/sequence/ledger/payment/allocation/public-token/supplier-ledger-foundation structures as needed;
- preserve/migrate Phase 1 draft data safely;
- tenant IDs/FKs/checks/idempotency uniqueness;
- RLS on every new tenant-owned table;
- migration from zero passes;
- upgrade from Phase 2 passes.

---

# N. Required test matrix

## Invoice/pricing
- pricing-v1 examples exact;
- piece/box + grade precedence;
- mixed currency rejected;
- old balance excluded from net_sales;
- confirmation creates one charge;
- confirmation replay no duplicate;
- tenant/year sequence concurrency;
- post-confirm edit = one revision + exact delta;
- stale predecessor rejected;
- historical snapshot unaffected by catalog change.

## Ledger
- balance = immutable entry sum by currency;
- invoice value = current revision;
- delta = ledger adjustment;
- no mixed-currency scalar.

## Payment/allocation
- receipt + ledger effect;
- FIFO;
- owner-selected allocation;
- partial/multi-obligation;
- allocation <= payment;
- replay idempotent;
- reversal preserves original;
- downward edit releases credit;
- upward edit increases outstanding.

## Cancellation/refund
- unconfirmed;
- confirmed unpaid/partial/full;
- allocation reversals;
- payments remain;
- refund separate;
- no-credit refund rejected;
- excess refund rejected;
- concurrent refund cannot double-spend credit.

## Debt/security
- opening balance;
- overdue/red;
- alert dedup;
- RLS/cross-tenant;
- driver denied owner finance;
- platform admin no automatic tenant finance;
- capability cannot enumerate;
- token not logged.

## E2E
- create→confirm→pay;
- post-confirm edit;
- partial payment;
- debt/overdue;
- WhatsApp;
- cancel/refund;
- EN/AR/RTL/accessibility.

---

# O. Milestones

## P3-M1 — Financial schema, Gate C verification, immutable source of truth
Implement Gate C verification, invoice header/revisions/items, tenant/year sequence, customer ledger, payments, allocations, tenant supplier/product-cost foundation, supplier-ledger skeleton, public-token schema as needed, RLS/constraints/migrations.

Acceptance:
- Phase 2 and zero migrations pass;
- every new tenant table RLS-protected;
- immutable source of truth established;
- idempotency/source-effect constraints exist.

STOP.

## P3-M2 — Production invoice editor + deterministic item entry
Implement owner invoice editor APIs/UI, customer/barcode/manual entry, image/packaging snapshots, pricing-v1, calculator entry, Arabic/English text parser, exact-first/fuzzy-second, ambiguity confirmation/audit.

Acceptance:
- pricing examples reproduce;
- ambiguity never auto-selected;
- currency/tenant rules enforced;
- frontend uses real API.

STOP.

## P3-M3 — Confirmation, revisions, ledger, debt
Implement confirmation transaction, official numbering, post-confirm delta revisions, opening balances, balance APIs, overdue/red alerts, history UI.

Acceptance:
- confirmation replay = one effect;
- post-confirm reconciliation exact;
- old balance not sales;
- sequence concurrency and overdue tests pass.

STOP.

## P3-M4 — Payments, allocations, cancellation, refunds
Implement receipts, FIFO/owner allocation, partial/multi-obligation, reversal, cancellation accounting, refund ceiling/concurrency, UI.

Acceptance:
- financial scenario matrix passes;
- replay no duplicate;
- cancellation preserves payments;
- concurrent refunds cannot overspend credit.

STOP.

## P3-M5 — Public capability, WhatsApp, supplier-ledger foundation
Implement token lifecycle, safe projection, headers/log redaction/rate limit, WhatsApp action, supplier-ledger/payment schema/service foundation, remaining owner finance UX.

Acceptance:
- internal ID alone cannot authorize;
- no private leakage;
- raw token never logged;
- WhatsApp safe resource works.

STOP.

## P3-M6 — Financial hardening and phase freeze
No new scope.

Complete property/integration/E2E/RLS/accessibility/migration/OpenAPI/docs/reconciliation audits.

Acceptance:
- all Phase 3 requirements have evidence;
- no critical/high Phase 3 defect;
- DoD passes.

Mark Phase 3 COMPLETE and STOP. Do not start Phase 4.

---

# P. Definition of Done

- production invoice editor works;
- calculations reproducible;
- immutable revision model canonical;
- confirmed edit auditable/reconciled;
- invoice sequence server-authoritative/concurrency-safe;
- customer ledger reconciles by currency;
- old balance correct and not sales;
- payments immutable/idempotent;
- allocations deterministic/reversible;
- partial payments/outstanding correct;
- refund ceiling/concurrency safe;
- cancellation accounting preserves payment history;
- overdue red behavior works;
- WhatsApp uses safe capability;
- supplier-ledger foundation ready for Phase 6;
- RLS blocks tenant financial leakage;
- migrations from zero/Phase 2 pass;
- no stock/availability introduced.

## Explicit exclusions
Do not implement Phase 4 sync, Phase 5 checkout, Phase 6 procurement, Phase 7 routes, Phase 8 final analytics/branding, subscription payment provider, tax/VAT, supplier per-purchase allocations, inventory, or AI.

First milestone to implement: **P3-M1 — Financial schema, Gate C verification, immutable source of truth**
