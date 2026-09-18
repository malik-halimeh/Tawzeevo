# PHASE_05.md — Linked Bilingual Guest Storefront, Orders, Recommendations, Advertising

## Authority and reconciliation status

This is the authoritative Phase 5 specification, reconciled on 2026-09-07 from the historical
planning copy in `docs/recovered-planning/PHASE_05.md`. D-042 governs confirmed-invoice public
sharing and supersedes incompatible historical capability behavior.

The following remain `REVIEW_REQUIRED` at Gate E and are not executable acceptance criteria until
resolved: the provisional checkout representation/session/revisit flow, exact tenant-slug rename
and redirect behavior, recommendation weights, view-deduplication window and interaction-retention
duration. Candidate values below do not constitute approval.

## Phase objective
Deliver one public storefront per approved/active Cash Van tenant and the complete owner order-review workflow.

Customers browse only that tenant's explicitly published commercial assortment and public prices.

A global/master product existing in Tawzeevo must never automatically make it visible or orderable in a tenant storefront.

## Start gate — Gate E
Before P5-M1 verify:
- order state machine;
- provisional vs confirmed invoice semantics;
- checkout idempotency;
- capability-token lifecycle/cache policy;
- guest customer privacy;
- notification/job behavior;
- delivery-date rule;
- cancellation request/decision state;
- tenant slug routing.

If any is absent/conflicting, stop and ask.

---

# A. Tenant-specific storefront invariant

Public catalog source:
```text
master_products = optional global identity/reference
tenant_products = tenant assortment/pricing/publication
```

A product appears publicly only when:
- it belongs to that tenant's commercial assortment;
- `is_published = true`;
- tenant is `ACTIVE`;
- applicable tenant/category publication rules permit it.

Master product existence alone is never enough.

Owner may:
- adopt/link a master product;
- use bilingual overrides;
- create a tenant-only product if master missing;
- set tenant-specific selling price;
- choose publication.

`is_published` = visibility only, not availability.

Never show/derive:
- in stock;
- out of stock;
- quantity on hand;
- inventory;
- availability state.

---

# B. Storefront routing

Candidate initial public routing — exact slug/rename/redirect behavior is `REVIEW_REQUIRED`:
```text
https://platform.example/{tenant-slug}/...
```

Slug:
- lowercase ASCII/digits/hyphen;
- 3–50 chars;
- globally unique;
- reserved platform names rejected;
- routing identity, never authorization;
- audited rename/redirect.

Custom domains future unless approved.

Suspended/closed tenant storefront cannot accept new orders.

---

# C. Public catalog

Include:
- Arabic/English;
- RTL/LTR;
- tenant categories;
- product names/images;
- public tenant price;
- piece/box presentation where appropriate;
- search/filter;
- mobile-first UI.

Anonymous storefront uses public standard tenant price.

Phone alone never reveals private grade/price.

Search is bounded/paginated, deterministic exact/prefix-first.

## C.1 Personalized customer context (D-071, D-072; BRD v1.1 BR-03/BR-08, FDD §4.12)

Reconciled 2026-09-18 from the approved BRD v1.1. An owner may issue a personalized storefront
link for an existing customer. The link is an opaque capability that resolves to the tenant and the
exact customer record; the storefront then applies that customer's **current** pricing rule
(explicit customer/grade price, otherwise grade discount, otherwise public price) through the
customer identity, so a later grade or price change needs no new link.

Rules:
- one active link per customer; atomic rotation/reissue; revocation without replacement;
- no automatic expiry (optional technical `expires_at`, null by default);
- hash-only persistence; secret carried in the URL fragment and a private header / first-party
  HttpOnly cookie on the storefront, never in a path, query, referrer or log;
- assurance `LINK`: personalized pricing, catalog use and order submission for owner review only;
  never the grade label, debt, payments, prior invoices, cost/profit, profile or security changes;
- access policy = business default + optional per-customer override (`LINK` | `VERIFIED` |
  `ACCOUNT_REQUIRED`); Phase 5 stores the fields and enforces `LINK` only; the other values are
  presented as not yet available and rejected by the API (no lock-out by configuration);
- invalid/revoked/rotated links fail closed without revealing customer existence; rate limits and
  tenant isolation as for D-042;
- suspended/closed business: personalized link resolves to nothing (public catalog rules apply).

Personalized responses are `private, no-store`; anonymous catalog responses stay cacheable.

---

# D. Product interactions/recommendations

Signals:
- pseudonymous view;
- valid purchase from confirmed non-cancelled sale.

Candidate weights — exact values are `REVIEW_REQUIRED`; purchase must remain higher than view:
```text
purchase = 10
view = 1
```

Purchase must outweigh view.

Candidate deduplication window is one view per session/product in 30 minutes; finalize at Gate E.

Candidate raw-anonymous-interaction retention is 90 days; finalize the duration and deletion/
aggregation policy at Gate E.

Cancelled/non-valid sale must not count as current purchase affinity.

No generative AI.

---

# E. Guest checkout

No customer account required.

Mandatory:
- name;
- phone;
- address.

Store immutable checkout contact snapshot.

Phone is not authentication and never auto-links private history/grade.

Owner later may explicitly:
- choose existing duplicate match;
- link existing customer;
- create new customer.

No automatic merge.

## Idempotency
Client sends `Idempotency-Key` UUID.

Replay:
```text
same key + same semantic request → original result
same key + different request → 409 IDEMPOTENCY_CONFLICT
```

A checkout made through a valid personalized context carries the customer only as an
**intended-customer hint** (`orders.intended_customer_id`, assurance `LINK`); it never links,
prices as final, or confirms anything by itself. Owner review (G) resolves the customer.

Atomic checkout:
- order `RECEIVED`;
- draft invoice;
- first provisional revision;
- provisional presentation reference/session whose exact lifecycle is `REVIEW_REQUIRED` at Gate E;
- idempotency record;
- audit/sync effects;
- exactly one owner notification.

---

# F. Provisional/current invoice

Customer immediately receives a safe provisional order/invoice representation. Its exact
session/receipt/revisit mechanism is `REVIEW_REQUIRED` and must not use or weaken D-042's
confirmed-invoice capability contract.

Financial confirmation happens only when owner confirms.
Every confirmation and later confirmed revision must satisfy D-043's strictly positive net-sales
boundary; zero economic effect uses cancellation/reversal.

Customer-safe projection may show:
- tenant branding;
- checkout contact snapshot;
- current provisional/confirmed items/totals;
- owner-set delivery date after confirmation;
- cancellation request/decision message.

Never show:
- unrelated debt/history;
- grade;
- supplier/cost/profit;
- audit;
- driver identity/state;
- other orders.

For confirmed invoices, D-042 and all Phase 3 capability security remain mandatory: at most one
active owner-issued link, replacement invalidates the old link, and cancellation revokes access.

---

# G. Owner review

Owner receives one in-app notification.

Owner may:
- review contact snapshot and, when present, the intended-customer hint with its assurance level
  (the hint is a suggestion; linking is an explicit owner act — D-072);
- disambiguate/link/create customer;
- apply grade only after authorized linkage;
- add/remove products;
- change quantity;
- replace/remove a product that cannot be provided without creating stock state;
- create latest provisional revision;
- confirm.

Confirmation delegates to Phase 3 financial transaction.

---

# H. One-person Cash Van behavior

Storefront must work with:
```text
1 owner
0 drivers
```

Owner does not need a second driver account to:
- receive/review orders;
- confirm;
- set delivery date;
- later personally deliver.

Actual delivery-task execution is Phase 7.

Phase 5 must never require driver setup before checkout/confirmation.

---

# I. Delivery date/reminders

Only after confirmation:
- owner sets/changes estimated delivery date;
- customer cannot select date;
- reminder jobs created/rescheduled transactionally;
- public view displays date.

Changing delivery schedule does not create a financial invoice revision.

Use tenant local date semantics + UTC execution time.

---

# J. Cancellation

Customer may submit cancellation **request** through capability token.

States:
```text
PENDING
APPROVED
REJECTED
```

Rules:
- one active pending request/order;
- rejected remains history;
- another request may be submitted after rejection while cancellable;
- owner notified;
- owner approves/rejects;
- approval runs Phase 3 reversal accounting;
- customer never writes order state;
- no delivery tracking state exposed.

---

# K. Weekly featured-product advertising

Owner selects tenant product.

Default:
```text
7 days
```

Campaign:
- starts_at;
- ends_at;
- priority;
- created_at/stable id.

Active:
```text
starts_at <= now < ends_at
```

Tie-break:
1. priority;
2. newer creation;
3. stable ID.

Use tenant timezone for date UI.
Expired record retained.

Advertising is not stock/availability.

Never feature another tenant's product or unadopted master product.

---

# L. API scope

Public groups:
```text
/api/v1/public/{tenant_slug}/catalog          (optional X-Customer-Capability header → personalized)
/api/v1/public/{tenant_slug}/checkout
/api/v1/public/customer-context               (fixed path; capability in the private header)
/api/v1/public/invoice
/api/v1/public/invoice/cancellation-request
```

Owner: `…/tenants/{id}/customers/{customer_id}/access-link` (issue/rotate, revoke, status) and the
tenant/customer access-policy fields.

The confirmed-invoice raw capability is carried in the URL fragment in the browser and sent to
these fixed API paths through the private capability header. It must never appear in an API path,
query string, referrer or log. The provisional presentation mechanism is resolved separately at
Gate E.

Owner operations extend existing order/invoice/job/notification APIs.

Raw tokens and sensitive contact data redacted from logs.
Rate-limit public entry points.

---

# M. Frontend scope

## Storefront web
Use Next.js App Router + TypeScript:
- slug resolution;
- tenant branding foundation;
- browse/detail;
- search/filter;
- public price/packaging;
- bilingual metadata;
- mobile cart/checkout;
- capability invoice page;
- personalized entry page (`/{slug}/access#<secret>` → first-party HttpOnly cookie, fragment
  stripped), personalized banner and exit;
- cancellation request;
- expired/revoked pages;
- featured products;
- recommendations.

## Operations web
- order inbox;
- duplicate customer disambiguation;
- link/create customer (intended-customer hint shown, never auto-linked);
- grade application;
- personalized link issue/rotate/revoke per customer;
- item/quantity edit;
- confirm;
- delivery date;
- cancellation decision;
- featured campaign management.

EN/AR/RTL/accessibility mandatory.

---

# N. Migration requirements

New migrations as needed for:
- orders/state fields;
- cancellation requests;
- checkout idempotency;
- product interactions;
- featured campaigns;
- indexes/constraints.

Reuse invoice/public-token/job structures already present.

Every tenant-owned row tenant_id + RLS.
Never edit applied migrations.
Zero + Phase 4 upgrade pass.

---

# O. Required tests

## Catalog isolation
- tenant A never returns tenant B product;
- master-only product invisible;
- adopted unpublished invisible;
- published tenant product visible;
- tenant-specific price used;
- tenant-only manual product publishable;
- no stock/availability exposed.

## Routing
- active slug;
- suspended/closed checkout blocked;
- slug not authorization.

## Personalized customer context (P5-M3)
- anonymous visitor gets public pricing;
- valid link gets the customer's current pricing; grade change alters price without a new link;
- internal grade label, debt, payments, prior invoices never exposed;
- exact tenant/customer association; Customer A's link never resolves Customer B;
- rotation invalidates the old link atomically; revocation invalidates; only one active per
  customer, including under concurrent issuance;
- suspended/closed tenant: link resolves to nothing;
- secret never in logs/paths/query; hash-only persistence; failure responses reveal nothing;
- order via link carries only the intended-customer hint; owner resolution stays authoritative;
- policy fields stored; non-LINK policies rejected/"not available"; tenant isolation.

## Checkout
- no account (a personalized context adds only the intended-customer hint);
- mandatory fields;
- invalid rejected;
- same idempotency intent returns original;
- key/request mismatch conflict;
- exactly one order/draft-invoice/provisional presentation result/notification; no confirmed-invoice
  capability before owner confirmation;
- contact snapshot immutable;
- phone no private history/grade.

## Owner review
- duplicate disambiguation;
- link/create;
- grade after explicit link;
- add/remove/change;
- confirm;
- sole owner zero drivers works.

## Delivery/cancellation
- date impossible before confirm;
- owner date after confirm;
- customer cannot choose;
- reminder reschedule;
- request only;
- owner approve/reject;
- no tracking.

## Confirmed-invoice capability/security
- unguessable/hash-only;
- expired/revoked safe;
- ID alone unauthorized;
- no-store/noindex/no-referrer;
- token not logged;
- rate limit;
- no private owner/customer/driver leakage.

## Recommendations/ads
- approved purchase-higher-than-view ordering; exact weights `REVIEW_REQUIRED`;
- view dedup;
- cancelled sale excluded;
- tenant isolated;
- ad 7-day default;
- interval/tie deterministic;
- history retained;
- ad does not alter availability.

## E2E
browse→checkout→safe provisional representation→owner edit→confirm→owner issues D-042 link→date→customer view; cancellation request→decision; EN/AR/RTL/mobile/accessibility.

---

# P. Milestones

## P5-M1 — Tenant storefront routing + published catalog
Implement storefront shell, slug routing, active tenant resolution, categories/products/images/prices, tenant publication, search/filter, bilingual/mobile/accessibility.

Acceptance:
- master catalog never leaks automatically;
- tenant isolation;
- unpublished absent;
- suspended checkout blocked;
- no stock language/state.

STOP.

## P5-M2 — Interactions, recommendations, featured campaigns
Implement views/session ids, valid purchase signals, deterministic scoring, view dedup/retention, recommendations, campaigns, owner campaign UI.

Acceptance:
- scoring/cancellation correct;
- campaign interval/tie correct;
- tenant-scoped.

STOP.

## P5-M3 — Personalized customer context (inserted 2026-09-18, D-071/D-072)
Implement the customer access link (one active per customer, atomic rotation, revocation,
hash-only), the customer-context resolver with assurance `LINK`, server-side personalized pricing
in the public catalog, the storefront entry/banner/exit, the owner per-customer link controls,
the access-policy fields (LINK enforced only), rate limiting/log redaction, and the tests in O.

Acceptance:
- exact-customer resolution and isolation;
- current pricing follows the customer, never the token;
- lifecycle (rotate/revoke/one-active) correct under concurrency;
- no private history/grade leakage; no secrets logged;
- no OTP, sessions, accounts or providers.

STOP.

## P5-M4 — Guest checkout, idempotency, provisional representation
After resolving the Gate E presentation contract, implement cart/checkout, snapshot, atomic
idempotency, RECEIVED order (with the intended-customer hint when a personalized context is
present), provisional invoice, safe provisional representation, owner notification and public
page. Do not issue a D-042 invoice capability before confirmation.

Acceptance:
- retries no duplicate;
- phone privacy;
- security headers/log redaction;
- immediate provisional view;
- hint carried, never auto-linked.

STOP.

## P5-M5 — Owner review, confirmation, delivery date, cancellation
Implement order inbox, customer link/create/disambiguation, grade, revision edits, confirmation, delivery date/reminders, cancellation request/decision, one-owner/no-driver UX.

Acceptance:
- zero-driver owner workflow;
- date only after confirm;
- cancellation owner decision;
- Phase 3 financial effects reused;
- no tracking.

STOP.

## P5-M6 — Public security/E2E/accessibility freeze
No new scope.

Complete abuse/rate-limit, privacy, token lifecycle, accessibility, EN/AR/RTL, mobile, E2E, migrations/OpenAPI/docs/final audit.

Acceptance:
- DoD passes;
- no critical/high storefront/public security defect.

Mark Phase 5 COMPLETE and STOP. Do not start Phase 6.

---

# Q. Definition of Done

- one storefront per active tenant;
- only tenant published assortment/prices shown;
- owner can publish master-linked or tenant-only products;
- guest checkout without account;
- retries no duplicate;
- provisional invoice immediate;
- D-042 confirmed-invoice capability secure/no-store and one-active-link lifecycle enforced;
- phone no private history/grade;
- personalized customer link: exact customer, current pricing, one active, atomic rotation,
  revocation, no private data, hint-only order attribution (D-071/D-072);
- owner reviews/edits/confirms;
- sole owner zero drivers works;
- delivery date only after confirmation;
- reminder jobs;
- cancellation request/decision only;
- no customer tracking;
- recommendations;
- weekly ads not availability;
- EN/AR/RTL/mobile/accessibility;
- RLS/tenant isolation.

## Explicit exclusions
Customer accounts are not globally mandatory for storefront use (optional accounts and OTP
verification are approved later work under D-073/D-074, not Phase 5); no customer-selected driver, driver product catalogs, driver referral tracking unless later approved, stock/inventory, customer tracking, Phase 6 procurement, Phase 7 routes, generative recommendations.

Milestone order (renumbered 2026-09-18 after P5-M1/P5-M2 completed): P5-M3 personalized customer
context → P5-M4 guest checkout → P5-M5 owner review → P5-M6 freeze.
