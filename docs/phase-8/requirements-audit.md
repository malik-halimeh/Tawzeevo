# Phase 8 requirements audit

Audit date: 2026-09-19

Status: PASS (P8-M4 freeze) with four storefront-branding items left for the owner's decision (§ F)

This document freezes requirement-to-code/test evidence for `PHASE_08.md`. It does not supersede
the project contract, the decision ledger, or the phase contract. Backend paths are relative to
`apps/api/tawzeevo_api/`, tests to `apps/api/tests/`, the operations client to
`apps/operations-web/src/`, the storefront to `apps/storefront-web/`. Gate G decisions: D-064
(invoiced sales), D-065 (receipts net of reversals, refunds separate), D-066 (outstanding and
payable = positive ledger balances, credits separate), D-067 (historical gross profit from the
sale-time cost snapshot only, coverage reported), D-068 (periods on the tenant calendar; events
dated by confirmation, edit acceptance, cancellation approval), D-069 (lifetime statistics),
D-070 (public aggregates withheld below 5 businesses / 20 customers).

## A — Core metrics

| Requirement | Implementation evidence | Test evidence | Result |
|---|---|---|---:|
| `invoiced_sales` from current confirmed revisions, cancelled excluded, openings never counted, by currency | `services/analytics.py::invoiced_sales` (D-064) | `test_analytics.py::test_overview_reconciles_seed_by_currency_and_excludes_cancelled_and_openings` | PASS |
| `customer_receipts` from payments minus reversals; refunds separate | `services/analytics.py::customer_receipts` (D-065) | same test (receipt, reversal, refund seeded) | PASS |
| `customer_outstanding` / `supplier_payable` = positive ledger balances; credits separate; never netted across parties | `services/analytics.py::customer_outstanding/supplier_payable` (D-066) | same test; E2E dashboard = `customer-ledger/…/balances` | PASS |
| `historical_gross_profit` only from the immutable sale-time revision-cost snapshot; missing snapshot = uncovered, never a later-cost fallback; coverage reported; owner-only | `services/analytics.py::gross_profit` (D-067); `routes/analytics.py` (`require_tenant_owner`) | `test_analytics.py::test_profit_uses_only_the_sale_time_snapshot_and_reports_uncovered_lines`; E2E `(10 − 7) × 5 = 15.0000`, coverage 100 % | PASS |

## B — Revision-aware reporting and periods

| Requirement | Implementation evidence | Test evidence | Result |
|---|---|---|---:|
| Current-value view vs event flow (confirmation date, edit delta on acceptance date, cancellation reversal on approval date) | `services/analytics.py::overview/event_flow` (D-068) | `test_analytics.py::test_event_flow_dates_confirmation_edit_delta_and_cancellation` | PASS |
| Per invoice, 30 d, 90 d, 1 y (+ all time); UTC storage, tenant-calendar boundaries | `services/analytics.py::resolve_period` (Asia/Beirut); `routes/analytics.py` `GET /api/v1/analytics/invoices/{id}` | `::test_period_boundaries_follow_the_tenant_calendar`, `::test_tenant_calendar_boundary_decides_period_membership` | PASS |

## C — Currency

| Requirement | Implementation evidence | Test evidence | Result |
|---|---|---|---:|
| Every figure grouped by currency; no FX aggregation; UI never mixes | `schemas/analytics.py::CurrencyAmount` lists; `AnalyticsPanel.tsx` (one row per currency, explicit "no exchange rate" note) | `test_analytics.py` (USD + LBP seed); `AnalyticsPanel.test.tsx` | PASS |

## D — Customer lifetime statistics

| Requirement | Implementation evidence | Test evidence | Result |
|---|---|---|---:|
| Financial: purchased, receipts, outstanding, largest, average, discounts, markups by currency | `services/customer_stats.py::customer_lifetime` (D-069) | `test_customer_stats.py::test_lifetime_statistics_reconcile_and_never_merge_duplicates`; E2E 50 / 30 / 25 / 35 | PASS |
| Activity: count, first/latest, average interval, frequency, cancellations and requests, late payments | same (`late_payment_count` against the overdue threshold; `insufficient_data` when nothing is confirmed) | same test (20-day rhythm, one late payment, cancelled invoice counted separately) | PASS |
| Habits: top products / categories, monthly spend | same (top 5 by value then quantity per currency; monthly on the tenant calendar) | same test; E2E top product visible | PASS |
| Loyalty: current grade, grade timeline from sale-time snapshots | same | same test (A → B timeline) | PASS |
| Duplicates never merged; cross-tenant denied; storefront hint never attribution | attribution strictly by `customer_id`; owner-only route | same test (twin customer reports only itself; driver 403; other tenant 404) | PASS |
| Drilldown UI, found by phone like the rest of the desk | `AnalyticsPanel.tsx` (phone search → customer → facts, money by currency, habits, grade timeline, monthly spend; EN/AR) | `AnalyticsPanel.test.tsx`; E2E | PASS |

## E — Implementation strategy

| Requirement | Implementation evidence | Test evidence | Result |
|---|---|---|---:|
| Queries and projections over duplicated financial truth; only necessary structures | no analytics tables; one branding table (`20260919_0027`); indexed transactional queries | `alembic check` clean; latency table in `test-report.md` | PASS |

## F — Business branding

| Requirement | Implementation evidence | Test evidence | Result |
|---|---|---|---:|
| Identity/contact: name, logo, description, phone, WhatsApp, e-mail, address | `models.py::TenantBranding`; `services/branding.py` (phone normalization, logo through `process_product_image` into object storage as WebP); `BrandingPanel.tsx` | `test_branding_public_stats.py::test_branding_is_owner_only_isolated_and_rendered_on_public_pages`; E2E logo upload | PASS |
| Storefront: primary/secondary theme tokens, banner, title, social links, About/Contact/Privacy/Terms | `ShopFrame.tsx` + `lib/theme.ts` (tokens applied only when readable: primary needs 4.5:1 on white, ink chosen by luminance), `app/[slug]/info/[page]`; https-only social links from a fixed key set | `lib/theme.test.ts`; backend validation tests (colour, link); E2E storefront | PASS |
| Storefront: favicon, featured-product presentation, approved promotional banners, configurable homepage layout within approved design boundaries | not implemented — no decision defines "approved design boundaries" or the promotion approval; nothing in the contract depends on them | — | OPEN (owner decision: build in Phase 9 or drop) |
| Invoice: logo/header/footer, terms, thank-you, optional QR only to the safe capability resource | `templates/public_invoice.html`; `services/public_invoices.py::invoice_qr_png` (PNG of the same capability page, header-authorized, `no-store`, only when enabled; CSP `img-src 'self' blob:`) | backend test (QR with header only, disabled → 404, CSP); `PublicInvoicePage.test.ts`; E2E (QR shown, secret not in the address bar) | PASS |
| Localization: default Arabic/English, currency, date format, timezone | `default_language` (storefront and invoice page default; visitor choice wins), `date_format`, `timezone`, `display_currency` stored and shown on the desk | backend test; E2E (storefront RTL by default, `?lang=en` overrides) | PASS |
| Branding never changes roles, scoping, pricing, ledger, cancellation, no-stock, no-tracking, API authority | branding service touches only `tenant_branding`; public projections are explicit Pydantic blocks | `test_branding_public_stats.py::test_branding_is_owner_only_isolated_and_rendered_on_public_pages` captures the confirmed invoice's money and the public price before any branding is saved and asserts they are identical afterwards (the earlier assertion compared `net_sales` with itself — corrected 2026-09-21); E2E (public price and dashboard identical after branding) | PASS |

## G — Public statistics

| Requirement | Implementation evidence | Test evidence | Result |
|---|---|---|---:|
| Phase 1 mandatory stats unchanged; only aggregate, privacy-reviewed additions; small cohorts withheld; never revenue, debt, supplier prices, identifiable history | `routes/users.py` (`/stats/count|average-age|top-cities` untouched; `GET /stats/platform`); `services/public_stats.py` (D-070) | `test_branding_public_stats.py::test_public_stats_keep_phase1_and_withhold_small_cohorts` (field-name scan for revenue/debt/cost/price/profit/tenant_id/customer_name) | PASS |

## H — API/frontend scope

| Requirement | Implementation evidence | Test evidence | Result |
|---|---|---|---:|
| `/api/v1` conventions; owner-only analytics; platform admin gains nothing tenant-private | `routes/analytics.py`, `routes/branding.py` (`require_tenant_owner`) | driver / other-tenant / admin denials in the tests above | PASS |
| EN/AR/RTL/accessibility; colour never the only signal; currencies never mixed | labelled regions and tables, `dir="ltr"` on numbers, coverage written as text next to profit, per-currency rows; readable theme tokens | `AnalyticsPanel.test.tsx`; E2E Arabic storefront and invoice page | PASS |

## I — Migrations

| Requirement | Implementation evidence | Test evidence | Result |
|---|---|---|---:|
| Only necessary structures; tenant_id + forced RLS; applied migrations untouched; zero and Phase 7 upgrade | `20260919_0027_tenant_branding.py` | `alembic check`; `test_hardening.py` head `20260919_0027`; `test_backup.py` manifest | PASS |

## Definition of Done (PHASE_08.md L)

Sales/receipts/outstanding/payable reconcile (unit seed and E2E ledger cross-check); historical
profit only from immutable snapshots with coverage; invoice/30d/90d/1y work; currencies never
mixed; timezone boundaries tested; complete lifetime stats with grade history; branding on the
desk, storefront and invoice in EN/AR; branding cannot change logic; mandatory public stats
remain; extra aggregates privacy-safe; RLS blocks leakage. All PASS with the evidence above. The
four storefront presentation items in § F are recorded as an owner decision, not a defect.
Explicit exclusions unchanged (no forecasting, no FX aggregation, no analytics warehouse).
