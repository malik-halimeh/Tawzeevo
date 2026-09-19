# Phase 7 requirements audit

Audit date: 2026-09-19

Status: PASS (P7-M4 freeze)

This document freezes requirement-to-code/test evidence for `PHASE_07.md`. It does not supersede
the project contract, the decision ledger, or the phase contract. Backend paths are relative to
`apps/api/tawzeevo_api/`, tests to `apps/api/tests/`, the operations client to
`apps/operations-web/src/`. Gate F decisions: D-060 (OpenRouteService first, Google only with a
key, offline heuristic otherwise; core delivery never depends on a provider), D-061 (location
precedence), D-063 (ASSIGNED → COMPLETED / CANCELLED, terminal, new task after a mistake).

## A/C — Eligible operator, owner-as-operator

| Requirement | Implementation evidence | Test evidence | Result |
|---|---|---|---:|
| Neutral `assigned_membership_id`; eligible active owner or driver; owner self-assigns; sole owner default with no driver setup; several eligible → owner chooses; reassignment audited; drivers never assign; performer recorded; one membership one role | migration `0025`; `services/delivery.py::eligible_members/create_task/assign_task/complete_task_row`; `routes/delivery.py` (assign owner-only); `routes/team.py` (owner adds a registered user as driver, revokes); `DeliveryPanel.tsx` ("My deliveries" and no assignee field for a sole operator) | `test_delivery_tasks.py::test_sole_owner_is_the_default_operator_and_completes_own_task`, `::test_assignment_is_owner_only_audited_and_protected`, `::test_owner_team_api_adds_registered_driver_and_revocation_locks_access`; `e2e/phase7-field-flow.spec.ts` | PASS |

## B — Delivery task lifecycle

| Requirement | Implementation evidence | Test evidence | Result |
|---|---|---|---:|
| Only a confirmed invoice is eligible; one open task per invoice; ASSIGNED → COMPLETED / CANCELLED terminal; system cancellation from invoice cancellation; amount-to-collect projection; version | `models.py::DeliveryTask` (partial unique index on ASSIGNED); `services/delivery.py::_confirmed_invoice/complete_task_row/cancel_task/cancel_open_tasks_for_invoice/amount_to_collect`; hook in `services/invoice_finance.py::cancel_invoice` | `test_delivery_tasks.py` (draft refused, duplicate 409, closed 409, new task after completion, `::test_invoice_cancellation_closes_the_open_task`) | PASS |
| States never exposed as customer tracking | storefront `ProvisionalOrderResponse` unchanged (no task fields); `test_phase5_freeze.py` private-word scan still green | `test_checkout.py`, `test_phase5_freeze.py` | PASS |

## D — Driver least privilege

| Requirement | Implementation evidence | Test evidence | Result |
|---|---|---|---:|
| Driver receives assigned tasks with contact/location/items/amount and authorized pickup need only; never supplier prices, profit, analytics, unrelated data, settings; enforced by API, bootstrap, pull and cache | `schemas/delivery.py::MyWorkTask`; `services/delivery.py::my_work`; `services/sync.py` (driver bootstrap returns no collections; driver pull filtered to own `delivery_task` rows); `services/sync_push.py` (driver push limited to `delivery_task complete`); owner routes require owner; `MyWorkPanel.tsx` caches only the projection | `test_delivery_tasks.py::test_driver_my_work_is_assigned_only_and_price_free`, `::test_driver_sync_is_scoped_and_offline_completion_applies_once`; E2E (driver tab bar has no supplier desk; My Work text has no cost/margin/profit) | PASS |

## E — Location

| Requirement | Implementation evidence | Test evidence | Result |
|---|---|---|---:|
| Stored provenance (lat/lng, captured_at, accuracy, source gps/manual/geocoded, confirmation and actor); exact location only to owner and assigned operator; confirmed never overwritten automatically; operator confirmation required; worse reading never replaces better; no continuous tracking or history | migration `0026`; `services/delivery.py::update_task_location/_reading_rank` (D-061); `RoutePlanner.tsx` (position read on button press; explicit confirm checkbox) | `test_delivery_routes.py::test_location_precedence_never_overwrites_confirmed_or_better_readings` | PASS |

## F/G — Offline route suggestion and online assistance

| Requirement | Implementation evidence | Test evidence | Result |
|---|---|---|---:|
| Deterministic nearest-neighbour + 2-opt + manual reorder, labelled "offline stop-order suggestion", never claimed optimal | `services/routing.py::offline_order` (id tie-breaks); `RoutePlanner.tsx` (label, up/down reorder, save) | `test_delivery_routes.py::test_offline_heuristic_is_deterministic_and_improves_on_input_order`; `RoutePlanner.test.tsx` | PASS |
| Approved provider through one adapter; quota/error/timeout handling; privacy-conscious payload; outage fallback; completion never depends on the provider | `services/routing.py::openrouteservice_order/suggest_order`; `config.py` (`OPENROUTESERVICE_API_KEY`, `ROUTING_TIMEOUT_SECONDS`, Google key slot) | `test_delivery_routes.py::test_suggest_order_uses_provider_when_configured_and_falls_back_on_failure` (mocked success with coordinates-only payload; timeout → heuristic with note) | PASS |

## H — Nearby supplier reminder

| Requirement | Implementation evidence | Test evidence | Result |
|---|---|---|---:|
| Owner sees supplier identity/location/need (prices in the supplier desk); driver sees identity/location/assigned pickup need only; no background tracking | `services/delivery.py::nearby_suppliers`; `routes/delivery.py` `GET /api/v1/routes/nearby-suppliers`; `RoutePlanner.tsx` "Suppliers near me" | `test_delivery_routes.py::test_nearby_supplier_reminder_respects_role_and_price_privacy` | PASS |

## I — Offline behavior

| Requirement | Implementation evidence | Test evidence | Result |
|---|---|---|---:|
| Assigned task projection, expected version, completion command, exactly once on reconnect, conflict handling, revoked membership locks access | `services/sync_changes.py` (`delivery_task` feed); `services/sync_push.py::_apply_delivery_task`; client `offline/supplierCommands.ts::queueDeliveryCompletion`, `MyWorkPanel.tsx` (device registered while online, queue offline, Sync now) | `test_delivery_tasks.py` (replay flagged, second completion rejected, other member's task rejected; revoked driver 403 on my-work and pull); E2E offline completion synced once, revoked driver refused | PASS |

## J/K — API groups, migrations, RLS

| Requirement | Implementation evidence | Test evidence | Result |
|---|---|---|---:|
| `/api/v1/delivery-tasks`, `/api/v1/routes/suggest-order` (+ `/order`, `/nearby-suppliers`), team routes; tenant, membership, role, assignment, lifecycle, version validated; new tables RLS; no driver-only FK | routers in `main.py`; migrations `0025`–`0026` | `alembic check` clean; cross-tenant 404 assertions; `test_hardening.py` head | PASS |

## Definition of Done (PHASE_07.md N)

Single-owner business works with zero drivers; owner is a recordable assignee; owner assigns and
reassigns drivers; drivers cannot assign; assigned-only access enforced server and local; owner
secrets absent from the driver payload and cache; lifecycle correct; location update safe; offline
completion syncs; offline route and manual reorder work; approved provider works with fallback;
nearby supplier respects price privacy; customers see no tracking; RLS/cross-tenant pass. All PASS
with the evidence above. Explicit exclusions unchanged.
