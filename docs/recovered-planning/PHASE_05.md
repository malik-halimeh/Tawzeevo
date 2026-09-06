# PHASE_05.md — Linked Bilingual Guest Storefront, Orders, Recommendations, Advertising

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

Initial public routing follows locked slug contract:
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

---

# D. Product interactions/recommendations

Signals:
- pseudonymous view;
- valid purchase from confirmed non-cancelled sale.

Weights:
```text
purchase = 10
view = 1
```

Purchase must outweigh view.

Count at most one view per session/product in rolling 30 minutes for scoring.

Raw anonymous interactions default retention 90 days, then delete/aggregate according to retention policy.

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

Atomic checkout:
- order `RECEIVED`;
- draft invoice;
- first provisional revision;
- capability token;
- idempotency record;
- audit/sync effects;
- exactly one owner notification.

---

# F. Provisional/current invoice

Customer immediately receives secure capability access to current provisional order/invoice representation.

Financial confirmation happens only when owner confirms.

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

Phase 3 capability security remains mandatory.

---

# G. Owner review

Owner receives one in-app notification.

Owner may:
- review contact snapshot;
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
/api/v1/public/{tenant_slug}/catalog
/api/v1/public/{tenant_slug}/checkout
/api/v1/public/access/{capability_token}
/api/v1/public/access/{capability_token}/cancellation-request
```

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
- cancellation request;
- expired/revoked pages;
- featured products;
- recommendations.

## Operations web
- order inbox;
- duplicate customer disambiguation;
- link/create customer;
- grade application;
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

## Checkout
- no account;
- mandatory fields;
- invalid rejected;
- same idempotency intent returns original;
- key/request mismatch conflict;
- exactly one order/invoice/token/notification;
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

## Capability/security
- unguessable/hash-only;
- expired/revoked safe;
- ID alone unauthorized;
- no-store/noindex/no-referrer;
- token not logged;
- rate limit;
- no private owner/customer/driver leakage.

## Recommendations/ads
- 10:1 weighting;
- view dedup;
- cancelled sale excluded;
- tenant isolated;
- ad 7-day default;
- interval/tie deterministic;
- history retained;
- ad does not alter availability.

## E2E
browse→checkout→provisional invoice→owner edit→confirm→date→customer view; cancellation request→decision; EN/AR/RTL/mobile/accessibility.

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

## P5-M3 — Guest checkout, idempotency, provisional invoice, capability
Implement cart/checkout, snapshot, atomic idempotency, RECEIVED order, provisional invoice, capability, owner notification/public page.

Acceptance:
- retries no duplicate;
- phone privacy;
- security headers/log redaction;
- immediate provisional view.

STOP.

## P5-M4 — Owner review, confirmation, delivery date, cancellation
Implement order inbox, customer link/create/disambiguation, grade, revision edits, confirmation, delivery date/reminders, cancellation request/decision, one-owner/no-driver UX.

Acceptance:
- zero-driver owner workflow;
- date only after confirm;
- cancellation owner decision;
- Phase 3 financial effects reused;
- no tracking.

STOP.

## P5-M5 — Public security/E2E/accessibility freeze
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
- capability secure/no-store;
- phone no private history/grade;
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
No customer login requirement, customer-selected driver, driver product catalogs, driver referral tracking unless later approved, stock/inventory, customer tracking, Phase 6 procurement, Phase 7 routes, generative recommendations.

First milestone to implement: **P5-M1 — Tenant storefront routing + published catalog**
