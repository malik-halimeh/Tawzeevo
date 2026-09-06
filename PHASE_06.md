# PHASE_06.md — Suppliers, Price History, Demand-Driven Procurement, Supplier Debt

## Authority and reconciliation status

This is the authoritative Phase 6 specification, reconciled on 2026-09-07 from the historical
planning copy in `docs/recovered-planning/PHASE_06.md`. D-034's tenant-private append-only
`TenantProductCostEntry` is the single cost-history foundation; Phase 6 extends it and must not
create a parallel supplier-price truth. D-038/D-039 govern supplier openings, payments and credit.

The exact procurement terminal/waive/carry-forward transitions and the final quote versus
actual-purchase provenance mapping remain `REVIEW_REQUIRED` before Phase 6 implementation.

## Phase objective
Implement supplier management and demand-driven purchasing without creating inventory.

Traceable chain:
```text
confirmed customer demand
→ procurement
→ supplier selection
→ actual supplier purchase
→ supplier ledger payable
→ aggregate supplier payment
```

No quantity-on-hand is created.

## Start condition
- Phase 5 DoD passed.
- Phase 3 supplier-ledger/payment foundation exists.
- Phase 4 sync protocol can carry D-034 product-cost append and procurement edits without new sync semantics.

---

# A. Absolute no-inventory boundary

Never add:
- stock quantity;
- inventory quantity;
- on-hand;
- reserved;
- warehouse;
- stock movement;
- automatic deduction;
- availability state;
- “needs supplier” availability.

Procurement quantities are demand/purchasing progress only.

---

# B. Supplier profiles

Tenant-scoped supplier:
- identity/name;
- contacts;
- address;
- saved location;
- notes where appropriate;
- audit/version fields.

Supplier data is tenant-private.

Drivers never receive broad supplier pricing/cost data.

---

# C. Append-only supplier price history

Extend the existing D-034 `TenantProductCostEntry` foundation. Do not create
`supplier_product_prices` or any parallel authoritative cost table.

Every record is historical; never overwrite old price.

Record:
- tenant;
- supplier;
- tenant_product;
- price;
- currency;
- unit;
- pieces_per_box snapshot if relevant;
- quantity context;
- provenance kind `quote | actual_purchase`, with the exact mapping to the existing cost-entry
  source model finalized before P6-M1 (`REVIEW_REQUIRED`);
- effective_at;
- recorded_at;
- recorder;
- source/notes;
- purchase/reference context where available.

Derived owner views:
- latest comparable;
- lowest historical comparable;
- highest historical comparable;
- last purchase date;
- recent N-price trend;
- stability/variation;
- cheapest currently known comparable supplier;
- price age/source.

Never compare incompatible unit/package or different currency.
Missing/stale data remains visible.

---

# D. Best-supplier recommendation

Deterministic:
1. same tenant product;
2. compatible normalized unit/package;
3. same currency;
4. latest valid comparable price per supplier;
5. show age/source;
6. lowest comparable ranks first;
7. owner may override.

No AI.
No automatic FX.

---

# E. Procurement

The lifecycle names below are a candidate state model. Terminal, waive and carry-forward semantics
must be finalized at the Phase 6 gate before this section becomes executable acceptance criteria.

Lifecycle:
```text
OPEN
PARTIALLY_PURCHASED
COMPLETE
CANCELLED
```

Each item distinguishes:
- required_quantity from confirmed demand;
- manual adjustment / target_quantity;
- purchased_quantity;
- `remaining_quantity = MAX(0, target - purchased)`;
- unit/package snapshot.

Do not overload one quantity field with all meanings.

Owner may:
- generate from demand;
- add manual items;
- remove unnecessary line without deleting demand history;
- edit target quantity;
- select/override supplier;
- group/sort supplier;
- see estimated cost clearly labelled;
- record partial purchase;
- complete/waive according to contract;
- carry remaining forward;
- print/export.

---

# F. Procurement runner/assignee

Procurement/pickup responsibility may be assigned to an active:
- `owner`;
- `driver`.

Use neutral membership assignee semantics.

Sole owner can self-assign without second driver account.

Owner may assign/reassign.

Driver projection contains only operational pickup information.

Driver never receives:
- supplier price history;
- supplier costs;
- profit/margin;
- broad supplier analytics;
- unrelated procurement.

Phase 7 later adds route/location field workflow.

---

# G. Actual supplier purchase

Use immutable supplier purchase header/items.

Record:
- tenant/supplier;
- product;
- actual quantity;
- unit/package;
- actual price;
- currency;
- purchase time;
- procurement link;
- optional supplier invoice/reference;
- notes.

Internal UUID sufficient; do not invent supplier-purchase business sequence.

Finalization transaction:
1. create purchase/items;
2. append actual price-history record;
3. append supplier-ledger obligation;
4. increment linked procurement purchased quantity;
5. update procurement state;
6. audit/sync;
7. commit.

Still no inventory.

---

# H. Supplier ledger/payments

Supplier ledger append-only per currency.

Entry types:
- supplier_purchase;
- supplier_adjustment;
- supplier_payment;
- supplier_payment_reversal;
- supplier_purchase_reversal.

Supplier payment:
- immutable;
- reduces aggregate supplier payable;
- reversal compensating.

Under D-039, an ordinary payment may not exceed the current positive payable in that currency.
Excess money requires a separate explicit supplier-prepayment action and clearly labelled credit.
Under D-038, a signed negative initial opening may represent pre-existing historical credit, but it
is not an operational payment/prepayment and only one initial opening is permitted per currency.

Do not allocate supplier payments to specific purchases in Phases 1–10 unless user later approves.

Dashboard may show:
- customer outstanding by currency;
- supplier payable by currency.

Never sum currencies.

---

# I. Offline integration

After Phase 6:
- supplier price append may be offline/idempotent;
- procurement edits offline with expected version;
- financial purchase/payment commands follow immutable/idempotent rules;
- role projection remains least-privileged.

Reuse Phase 4 sync. Never create second sync engine.

---

# J. API/frontend scope

Canonical groups:
```text
/api/v1/suppliers
/api/v1/supplier-prices
/api/v1/supplier-purchases
/api/v1/supplier-ledger
/api/v1/procurement
```

Thin routes; explicit transactions.

Owner UI:
- supplier CRUD/location/contact;
- price history;
- last/low/high/trend/stability;
- comparison with age/source;
- procurement list;
- required/target/purchased/remaining;
- grouping/estimate;
- owner/driver assignee;
- partial/carry-forward;
- print/export;
- actual purchase;
- payable/payment/reversal;
- customer/supplier outstanding totals.

Driver/runner:
- supplier identity/location;
- assigned pickup items/quantities;
- no price/cost/profit.

EN/AR/RTL/accessibility mandatory.

---

# K. Migration requirements

New migrations extend, rather than duplicate, the existing Phase 3 foundation:
- supplier contact/location fields where absent;
- D-034 product-cost provenance needed for quote/actual-purchase history;
- procurement lists/items;
- supplier purchases/items;
- assignee membership references;
- indexes/constraints/versions.

Reuse Phase 3 supplier ledger/payment structures.
All tenant tables tenant_id + RLS.
Never edit applied migrations.
Zero + Phase 5 upgrade pass.

---

# L. Tests

## Supplier
- CRUD isolation;
- location/contact;
- cross-tenant denied.

## Price history
- append-only;
- old record unchanged;
- quote/actual;
- unit/package/currency;
- last/low/high/trend/stability;
- stale/missing visible.

## Comparison
- incompatible units excluded;
- currencies separated;
- latest valid per supplier;
- lowest comparable first;
- owner override.

## Procurement
- aggregate confirmed demand;
- quantity meanings;
- state transitions;
- partial;
- carry-forward;
- manual edits preserve demand history;
- print/export no stock.

## Assignee
- sole owner self-assigns;
- active driver assignable;
- driver no price/cost;
- unrelated procurement denied;
- platform admin no automatic supplier access.

## Purchase/payment
- purchase finalization atomic;
- rollback all on failure;
- no inventory row;
- payable correct;
- payment/reversal correct;
- no per-purchase payment allocation;
- currencies separated;
- replay safe.

## Offline/E2E
- supplier price offline/reconnect;
- procurement edit offline/reconnect;
- demand→procurement→purchase→payable→payment;
- EN/AR/RTL/accessibility.

---

# M. Milestones

## P6-M1 — Supplier-management expansion + append-only cost history
Extend the D-041 supplier/product-cost setup API/UI with full location/contact management,
quote/actual-purchase provenance, derived metrics, RLS and sync foundation. Reuse D-034 cost entries.

Acceptance:
- no history overwrite;
- unit/currency rules;
- tenant isolation.

STOP.

## P6-M2 — Comparable supplier recommendation
Implement deterministic comparison, age/source/staleness, owner recommendation/override UI.

Acceptance:
- incompatible data not ranked;
- no FX;
- reproducible;
- owner can explain ranking.

STOP.

## P6-M3 — Demand-driven procurement + owner/driver assignee
After finalizing RP-P6-01, implement procurement lifecycle, demand aggregation, quantities, manual
edits, grouping/estimate, carry-forward, print/export, neutral assignment and restricted driver
projection.

Acceptance:
- sole owner zero drivers works;
- lifecycle correct;
- driver sees no price/cost;
- no inventory.

STOP.

## P6-M4 — Actual purchases, supplier ledger/payment, debt totals
Implement supplier purchases/items, atomic history/ledger/procurement effects, payable, payments/reversals, customer/supplier totals.

Acceptance:
- chain reconciles;
- no purchase allocation;
- currencies separate;
- replay/rollback tests pass.

STOP.

## P6-M5 — Offline/E2E/hardening + freeze
No new scope.

Complete sync integration, RLS/security, migrations, frontend tests, E2E chain, EN/AR/RTL/accessibility, OpenAPI/docs, no-stock audit.

Acceptance:
- DoD passes;
- no critical/high supplier/procurement defect.

Mark Phase 6 COMPLETE and STOP. Do not start Phase 7.

---

# N. Definition of Done

- suppliers/locations work;
- append-only price history;
- last/low/high/trend/stability;
- deterministic comparable best supplier;
- daily procurement from confirmed demand;
- manual/partial/carry-forward/print-export;
- sole owner can personally procure;
- driver can receive pickup need without prices;
- actual purchase updates history/payable/procurement atomically;
- supplier debt/payment/reversal;
- customer/supplier totals by currency;
- offline supplier/procurement uses Phase 4 sync;
- RLS blocks leakage;
- no stock/availability.

## Explicit exclusions
No inventory, warehouse, per-purchase supplier payment allocation, Phase 7 routing, driver price visibility, generative supplier recommendation, automatic FX.

First milestone to implement: **P6-M1 — Suppliers + append-only price history**
