# PHASE_08.md — Analytics, Customer Lifetime Statistics, Branding, Safe Public Statistics

## Phase objective
Turn trustworthy transactional history into reproducible tenant business intelligence and tenant branding without changing underlying business rules.

Analytics must reconcile to canonical invoice revisions, ledgers, payments, supplier obligations, currencies, and tenant-local time.

Never fabricate a metric when reliable source data is missing.

## Start gate — Gate G
Before P8-M1 verify:
- exact metric definitions;
- current-value vs event-flow revision treatment;
- cancellation treatment;
- currency grouping;
- tenant timezone boundary;
- gross-profit cost-basis rules.

If a requested metric lacks a locked definition, ask rather than invent.

---

# A. Core metrics

## invoiced_sales
Current canonical `net_sales` of confirmed, non-cancelled invoices.

Old balance is not sales.

## customer_receipts
Actual effective customer receipt payments.

## customer_outstanding
Positive customer ledger balance by currency.

## supplier_payable
Positive supplier ledger balance by currency.

## gross_profit_estimate
Owner-only, only when defensible cost exists.

Cost precedence:
1. actual supplier purchase linked to relevant demand;
2. latest comparable `actual_purchase` supplier price for same product/unit, clearly labelled estimated with date/source;
3. otherwise unavailable.

Expose cost-coverage percentage when some lines lack cost.

Never fabricate missing cost or compare incompatible package/currency.

---

# B. Revision-aware reporting

Current-value reports use current canonical invoice revision.

Event/trend reporting recognizes:
- confirmation on confirmation date;
- post-confirm revision delta on acceptance date;
- cancellation reversal on approval date.

Report names/UI distinguish current-state from event-flow.

Mandatory:
- per invoice;
- 30 days;
- 90 days;
- 1 year.

Storage UTC.
Boundaries tenant local timezone.

---

# C. Currency

Every financial total grouped by currency.

No implicit FX.

Do not combine USD/LBP into one scalar.

Display rounding does not alter stored 4-decimal truth.

---

# D. Customer lifetime statistics

## Financial
- total purchased from canonical confirmed history;
- total receipts;
- current outstanding by currency;
- largest invoice;
- average invoice value;
- total discounts;
- total markup.

## Activity
- orders/invoices count;
- first purchase;
- latest purchase;
- average interval;
- purchase frequency;
- cancellation request/approved cancellation counts where appropriate;
- late-payment count/indicators.

## Habits
- most/favorite purchased products;
- most/favorite categories;
- average monthly spending by currency;
- seasonal/monthly patterns.

## Loyalty/pricing
- current grade;
- grade-history timeline;
- total grade/loyalty discount.

Every statistic tenant/customer scoped and reproducible.

Never silently merge duplicate customers.

---

# E. Implementation strategy

Start with indexed transactional queries/projections appropriate to measured scale.

Do not add warehouse/OLAP/event lake/materialized architecture unless benchmark evidence justifies and user approves material change.

Backend owns definitions.

---

# F. Business branding

Per tenant:

## Identity/contact
- business name;
- logo;
- description;
- phone;
- WhatsApp;
- email;
- address.

## Storefront
- primary/secondary theme tokens;
- homepage banner;
- featured-product presentation;
- approved promotional banners;
- title;
- favicon;
- social links;
- About/Contact/Privacy/Terms;
- configurable homepage layout only within approved design boundaries.

## Invoice
- logo/header/footer;
- terms;
- thank-you;
- optional QR only to safe capability resource.

## Localization
- default Arabic/English;
- currency;
- date format;
- timezone.

Branding must never change roles, tenant scoping, pricing, ledger, cancellation, no-stock, no-tracking, or API authority.

---

# G. Public statistics

Keep mandatory Phase 1 public stats.

Add only genuinely aggregate/non-sensitive stats after privacy review.

Never expose:
- tenant revenue;
- customer debt;
- supplier price/cost;
- identifiable customer history;
- tiny identifying cohorts.

Where cohort too small, use explicit insufficient-sample behavior if contract permits instead of leaking data.

---

# H. API/frontend scope

Analytics/branding APIs follow established `/api/v1` conventions.

Owner-only financial analytics require tenant-owner authorization.

Platform admin does not automatically gain tenant-private analytics.

Owner dashboard:
- invoice/30d/90d/1y;
- sales/receipts/outstanding/payable by currency;
- profit only with coverage;
- customer lifetime;
- grade history;
- late indicators;
- product/category habits.

Branding UI:
- identity/contact;
- media/theme/banner/content;
- invoice presentation;
- language/currency/timezone.

Storefront/invoice render branding safely.

EN/AR/RTL/accessibility mandatory.
Charts must not rely on color alone or mix currencies misleadingly.

---

# I. Migration requirements

Add only necessary Phase 8 structures/settings/indexes.

Prefer queries/projections over duplicated financial truth.

Add tenant branding/settings if not already present.

All tenant configuration tenant_id + RLS.
Never edit applied migrations.
Zero + Phase 7 upgrade pass.

---

# J. Tests

## Metrics
- sales excludes cancelled;
- current revision;
- confirmation/delta/cancel event timing;
- old balance not sales;
- receipts from payments;
- outstanding/payable from ledgers;
- currencies separate.

## Profit
- actual linked cost precedence;
- comparable actual fallback;
- missing cost unavailable;
- coverage correct;
- owner-only.

## Periods
- 30/90/1y;
- UTC storage;
- tenant timezone boundaries;
- boundary/DST cases where relevant.

## Lifetime
- purchases/payments/balance;
- count/date/average/frequency;
- top products/categories;
- monthly/seasonal;
- grade/current/history;
- discount totals;
- late/cancellation;
- duplicates not merged;
- cross-tenant denied.

## Branding/public
- tenant isolation;
- EN/AR;
- storefront/invoice render;
- safe QR;
- branding cannot alter logic;
- Phase 1 stats remain;
- sensitive public metrics absent;
- small-cohort protection.

## E2E
- seeded dashboard reconciles;
- customer lifetime drilldown;
- branding reflected storefront/invoice;
- EN/AR/RTL/accessibility.

---

# K. Milestones

## P8-M1 — Trusted metric service + periods
Implement Gate G verification, metric services, current/event-flow handling, 30/90/1y, currency grouping, timezone boundaries, dashboard baseline.

Acceptance:
- seeded reconciliation exact;
- no currency mixing;
- revision/cancellation tests;
- no fabricated cost.

STOP.

## P8-M2 — Customer lifetime statistics
Implement full financial/activity/habit/loyalty metrics, grade history, late/cancellation indicators, drilldown API/UI, indexes.

Acceptance:
- lifetime matrix passes;
- duplicates not merged;
- cross-tenant secure.

STOP.

## P8-M3 — Tenant branding + safe public aggregate stats
Implement branding/settings, storefront/invoice application, localization settings, privacy-reviewed public aggregates.

Acceptance:
- branding EN/AR;
- business logic unchanged;
- public privacy tests.

STOP.

## P8-M4 — Reconciliation, accessibility, performance, freeze
No new scope.

Complete reconciliation, frontend/chart tests, timezone/currency, RLS, accessibility, migrations, OpenAPI/docs, measured query performance, final audit.

Acceptance:
- DoD passes;
- no critical/high analytics/privacy defect.

Mark Phase 8 COMPLETE and STOP. Do not start Phase 9.

---

# L. Definition of Done

- sales/receipts/outstanding/payable reconcile;
- profit only with defensible cost/coverage;
- invoice/30d/90d/1y work;
- currencies never mixed;
- timezone boundaries tested;
- complete lifetime stats;
- grade history;
- branding operations/storefront/invoice EN/AR;
- branding cannot change logic;
- mandatory public stats remain;
- extra aggregates privacy-safe;
- RLS blocks leakage.

## Explicit exclusions
No Phase 10 forecasting, unapproved metrics, FX aggregation, analytics warehouse without evidence/approval, public tenant revenue/debt/supplier prices, or design-driven behavior change.

First milestone to implement: **P8-M1 — Trusted metric service + periods**
