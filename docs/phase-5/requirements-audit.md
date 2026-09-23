# Phase 5 requirements audit

Audit date: 2026-09-19

Status: PASS (P5-M6 freeze)

This document freezes requirement-to-code/test evidence for `PHASE_05.md`. It does not supersede
the project contract, the decision ledger, or the phase contract. Backend paths are relative to
`apps/api/tawzeevo_api/`, tests to `apps/api/tests/`, the operations client to
`apps/operations-web/src/`, the storefront to `apps/storefront-web/`.
Gate E decisions: D-046 (provisional order page through a short-lived reference), D-047 (slugs and
audited redirects), D-048 (purchase 10 / view 1), D-049 (one owner notification per checkout,
reminder job records), D-051 (90-day raw signals, monthly rollups), D-062 (30-minute view window),
D-071/D-072/D-075/D-076 (personalized customer context, assurance model, cookie, rate limits).

## A/B — One storefront per business, published assortment only

| Requirement | Implementation evidence | Test evidence | Result |
|---|---|---|---:|
| One storefront per active tenant at `/<slug>`; slugs unique, renames audited with redirects (D-047) | migration `0017`; `services/storefront.py` (slug rules, history); `routes/storefront.py` public catalog; storefront `app/[slug]/page.tsx` | `test_storefront.py` (slug rules, rename history, reserved words) | PASS |
| Only the tenant's published products and current prices; tenant-only or master-linked products | `services/storefront.py` (`is_published`, tenant scope, pricing-v1 `resolve_product_pricing`) | `test_storefront.py` (unpublished hidden, cross-tenant isolation); `test_phase5_freeze.py::test_public_surfaces_carry_no_private_data_and_correct_cache_policy` | PASS |
| Suspended business: catalog refused, provisional pages stay readable | `services/storefront.py`; `services/checkout.py::provisional_order` | `test_checkout.py` (suspended business 409, provisional page readable) | PASS |
| Public catalog cacheable; private surfaces `no-store`/noindex | `public_invoice_security.py` (`PRIVACY_HEADERS` for `customer-context`, `invoice`, `order`; `CATALOG_HEADERS` otherwise); personalized catalog `private, no-store` + `Vary` in `routes/storefront.py::_context` | `test_phase5_freeze.py::test_public_surfaces_carry_no_private_data_and_correct_cache_policy` | PASS |

## C.1 — Personalized customer context (D-071, D-072, D-075, D-076)

| Requirement | Implementation evidence | Test evidence | Result |
|---|---|---|---:|
| Owner-issued opaque link bound to the exact customer; hash-only storage; one active per customer; atomic rotation; revocation without replacement; no automatic expiry | migration `0019`; `services/customer_access.py::issue_link` (customer row lock), `revoke_link`, `link_status` | `test_customer_access.py::test_rotation_revocation_one_active_and_isolation`, `::test_suspended_business_and_concurrent_issuance` (4 concurrent issues, one active) | PASS |
| Current customer pricing on the catalog; nothing private in the projection | `services/customer_access.py::resolve_context`; `routes/storefront.py::_context`; `PublicProduct.pricing` | `test_customer_access.py::test_link_gives_current_customer_pricing_without_exposing_anything_private`; `test_phase5_freeze.py::test_link_lifecycle_is_safe_on_every_private_surface` | PASS |
| Assurance `LINK` only in Phase 5; tenant default + per-customer override; `ACCOUNT_REQUIRED` reserved | `customer_access.py::AVAILABLE_POLICIES`, `set_customer_policy`, `set_tenant_policy`; check constraints in `models.py` | `test_customer_access.py` (policy endpoints, unavailable policies refused) | PASS |
| 30-day-maximum HttpOnly cookie, re-resolved on every request, invalidated by rotation/revocation/suspension | storefront `lib/personal.ts` (`resolveContext`), `app/[slug]/access/session/route.ts` (HttpOnly, SameSite=Lax, path `/{slug}`) | `lib/personal.test.ts`; `e2e/phase5-storefront-flow.spec.ts` | PASS |
| Rate limits are operational policy (60/min private, 600/min catalog), configurable, never the sole control | `config.py::public_private_rate_limit_per_minute` / `public_catalog_rate_limit_per_minute`; `main.py` middleware wiring; constant 404 for bad capabilities | `test_phase5_freeze.py::test_rate_limits_follow_settings_and_are_separate_per_surface`; `test_public_invoices.py::test_public_rate_limit_and_access_log_redaction` | PASS |
| Capabilities never logged | `public_invoice_security.py::CapabilityLogFilter` (redacts message and args in place) | `test_public_invoices.py` (access log redaction) | PASS |

## D/E — Guest checkout, idempotency, provisional representation (D-046, D-049)

| Requirement | Implementation evidence | Test evidence | Result |
|---|---|---|---:|
| Checkout without an account; mandatory name/phone/address; published products only; single currency | `services/checkout.py::checkout`; `schemas/checkout.py::CheckoutRequest` | `test_checkout.py` (validation matrix, unpublished product, invalid phone) | PASS |
| Retries never duplicate: one order per `Idempotency-Key`, replay returns the same order, different body refused | `checkout.py` advisory lock + fingerprint in `checkout_idempotency` | `test_checkout.py` (replay, conflicting body 409) | PASS |
| Provisional invoice immediately: RECEIVED order + draft invoice + first revision priced by the server, no customer, no official number | `checkout.py` (Invoice `customer_id=None`, `InvoiceRevision` with `client_command_id` = key) | `test_checkout.py` (counts 1/1/1/1/1) | PASS |
| Safe provisional page through a 72-hour reference in a private header; fragment stripped; no private data | `routes/storefront.py` `GET /api/v1/public/order`; storefront `components/OrderView.tsx`, `app/[slug]/order/view/route.ts` | `test_checkout.py` (no grade/debt/cost/supplier/driver); E2E provisional page assertions | PASS |
| Exactly one owner notification per accepted checkout | `checkout.py` (`OwnerNotification(kind="ORDER_RECEIVED")`, partial unique index narrowed in `0021`) | `test_checkout.py`; `test_order_review.py` (unread count) | PASS |
| Phone never links history; a personalized link gives a hint only, never attribution | `checkout.py` (`intended_customer_id`, `intended_assurance`; invoice stays unlinked) | `test_checkout.py`; `test_phase5_freeze.py` (dead link gives no hint) | PASS |

## G/H/I/J — Owner review, confirmation, delivery date, cancellation

| Requirement | Implementation evidence | Test evidence | Result |
|---|---|---|---:|
| Owner inbox; explicit customer link (existing by phone match or created from the snapshot); the hint is never auto-linked; the link re-prices the draft as a new revision | `services/orders.py::list_orders/candidate_customers/link_customer` (Phase 3 `update_editor_draft`); `OrdersPanel.tsx` | `test_order_review.py` (confirm before link refused; re-price to grade); `OrdersPanel.test.tsx` (confirm disabled until linked; re-priced revision echoed) | PASS |
| Confirmation only through the Phase 3 confirmation (official number, ledger); stale revision refused | `orders.py::confirm_order` → `invoice_finance.confirm_invoice` with `expected_revision_id` | `test_order_review.py`; E2E confirm | PASS |
| Decline closes the draft | `orders.py::decline_order` → `cancel_invoice` | `test_order_review.py` | PASS |
| Sole owner with zero drivers works | no driver dependency in any Phase 5 route; the E2E runs with an owner only | `e2e/phase5-storefront-flow.spec.ts` | PASS |
| Delivery date only after confirmation; reminder job record (09:00 Asia/Beirut stored in UTC), one per order | migration `0021` `delivery_reminders`; `orders.py::set_delivery_date`; execution by `services/jobs.py::run_due_delivery_reminders` (one `DELIVERY_REMINDER` owner notification per due reminder, idempotent; scheduled in-process since 2026-09-21, previously never executed) | `test_order_review.py` (refused before confirmation, accepted after, UTC due); `test_jobs.py` (execution, replay, cancellation, reschedule) | PASS |
| The customer can only request cancellation; the owner approves (Phase 3 reversal, reminder cancelled) or rejects | `routes/storefront.py` `POST /api/v1/public/order/cancellation-request`; `orders.py::request_cancellation/decide_cancellation`; storefront `app/[slug]/order/cancel/route.ts` | `test_order_review.py` (one pending per order; approval reverses; rejection keeps); E2E request then approval | PASS |

## K/L — Recommendations, featured campaigns, signals (D-048, D-051, D-062)

| Requirement | Implementation evidence | Test evidence | Result |
|---|---|---|---:|
| Purchase 10 / view 1; cancelled sales excluded; 30-minute view window; tenant isolated; deterministic ties | migration `0018`; `services/storefront_signals.py` | `test_storefront_signals.py` | PASS |
| Raw rows 90 days then monthly rollups (session ids dropped) | `cli/backup_jobs.py rollup-views`; `storefront_signals.py`; scheduled hourly by the in-process scheduler (`services/jobs.py`, since 2026-09-21 — previously CLI only, never scheduled) | `test_storefront_signals.py` (rollup); `test_jobs.py` (scheduler table) | PASS |
| Featured campaigns: 7-day default, never alter availability | `storefront_signals.py`; `CampaignPanel.tsx` | `test_storefront_signals.py`; `CampaignPanel.test.tsx` | PASS |

## M/N — Confirmed-invoice capability (D-042) and abuse

| Requirement | Implementation evidence | Test evidence | Result |
|---|---|---|---:|
| Unguessable, hash-only, expired/revoked safe, id alone unauthorized, `no-store`/noindex/no-referrer, not logged, rate limited | Phase 3 `services/public_invoices.py`; `public_invoice_security.py` | `test_public_invoices.py`; `test_phase5_freeze.py` (order id alone refused; reference in the header only) | PASS |
| No customer tracking: pseudonymous per-shop session only, no cross-shop identity, no third-party scripts | `storefront_signals.py`; `apps/storefront-web/app/layout.tsx` | `test_storefront_signals.py`; review of the storefront layout | PASS |

## O — EN/AR/RTL, mobile, accessibility

| Requirement | Implementation evidence | Test evidence | Result |
|---|---|---|---:|
| Storefront and owner screens in EN/AR with RTL; labelled form fields; skip link; status regions | storefront `lib/i18n.ts`, `components/ShopFrame.tsx` (`lang`/`dir`); operations `i18n.ts` `orders.*` | E2E Arabic phone test (RTL container, no horizontal overflow, labelled fields); `OrdersPanel.test.tsx` (roles/labels) | PASS |
| Defect found and fixed at the freeze: the RTL skip link widened the page by 999 px on phones | `app/globals.css` (`.skip-link` visually-hidden pattern) | E2E overflow assertion | PASS |

## Definition of Done (PHASE_05.md Q)

All items PASS with the evidence above. Explicit exclusions unchanged: no customer accounts or
OTP (D-073/D-074, Phase 9), no driver selection, no stock, no tracking, no generative
recommendations.
