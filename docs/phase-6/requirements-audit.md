# Phase 6 requirements audit

Audit date: 2026-09-19

Status: PASS (P6-M5 freeze)

This document freezes requirement-to-code/test evidence for `PHASE_06.md`. It does not supersede
the project contract, the decision ledger, or the phase contract. Backend paths are relative to
`apps/api/tawzeevo_api/`, tests to `apps/api/tests/`, the operations client to
`apps/operations-web/src/`. Gate decisions: D-034 (single cost-history table), D-038/D-039
(supplier openings, payment cap, prepayments), D-058 (procurement lifecycle, carry-forward, waive
with reason), D-059 (QUOTE / ACTUAL_PURCHASE provenance and invoice preload order).

## A — Absolute no-inventory boundary

| Requirement | Implementation evidence | Test evidence | Result |
|---|---|---|---:|
| No stock, inventory, on-hand, reserved, warehouse, movement, deduction or availability concept anywhere | migrations `0022`–`0024` add only demand/progress quantities; `services/procurement.py` derives `remaining` | `test_procurement.py::test_no_inventory_columns_exist_anywhere` (schema-wide column scan); CSV export and driver projection scanned for stock words | PASS |

## B — Supplier profiles

| Requirement | Implementation evidence | Test evidence | Result |
|---|---|---|---:|
| Identity, contacts, address, saved location, notes, audit/version; tenant-private | migration `0022`; `models.py::TenantSupplier`; `schemas/suppliers.py::SupplierProfileFields` (phone normalized); `services/suppliers.py::create_supplier/update_supplier/_apply_profile` (audited, `expected_version` conflict 409); `SupplierSetup.tsx` profile form | `test_supplier_profiles_prices.py::test_supplier_profile_contact_location_version_and_isolation` | PASS |
| Drivers never receive supplier pricing/cost data | supplier routes owner-only; runner projection (`services/procurement.py::my_pickups`) carries identity/location/quantities only | `test_procurement.py::test_assignee_is_neutral_and_driver_projection_has_no_prices` | PASS |

## C — Append-only supplier price history

| Requirement | Implementation evidence | Test evidence | Result |
|---|---|---|---:|
| Extend D-034 entries, no parallel table; every record historical; provenance `QUOTE` / `ACTUAL_PURCHASE` (D-059); quantity context; recorder; reference | migration `0022` (`quantity_context`, `source_type` check); `services/suppliers.py::append_cost_row` (owner may write MANUAL/QUOTE only); `services/supplier_purchases.py` writes ACTUAL_PURCHASE with `source_reference_id` = purchase | `test_supplier_profiles_prices.py::test_price_history_is_append_only_with_provenance_and_derived_insights` (oldest row unchanged, hand-written ACTUAL_PURCHASE 422) | PASS |
| Derived views: latest, lowest, highest, last purchase, recent trend, stability, cheapest comparable, age/source; never compare incompatible unit/package or currency; stale visible | `services/suppliers.py::product_price_insights` (groups by currency + basis + pieces per box; `STALE_AFTER_DAYS = 90`); `SupplierSetup.tsx` insight table | same test (box vs piece separate, stale competitor shown with age, stability labels) | PASS |
| Invoice entry preloads latest actual purchase → latest quote → manual (D-059) | `services/invoice_editor.py::_COST_SOURCE_PRIORITY` | same test (older actual purchase beats newer manual) | PASS |

## D — Best-supplier recommendation

| Requirement | Implementation evidence | Test evidence | Result |
|---|---|---|---:|
| Deterministic: same product, compatible unit/package, same currency, latest valid price per supplier, age/source shown, lowest first, owner override; no AI, no FX | `services/suppliers.py::recommend_supplier` (fresh before stale, ties by newer price / name / id; explanation codes; exclusions with reasons; override = preferred supplier with audited reason) | `test_supplier_profiles_prices.py::test_recommendation_is_deterministic_explainable_and_overridable` | PASS |

## E — Procurement

| Requirement | Implementation evidence | Test evidence | Result |
|---|---|---|---:|
| Lifecycle OPEN → PARTIALLY_PURCHASED → COMPLETE / CANCELLED (D-058) | migration `0023`; `services/procurement.py::refresh_status/complete_list/cancel_list` | `test_procurement.py`, `test_supplier_purchases.py` (auto complete on full purchase, reopen on reversal) | PASS |
| required / target / purchased kept apart; remaining derived; unit snapshot | `models.py::ProcurementItem` (`remaining_quantity` property) | `test_procurement.py::test_demand_generation_quantities_edits_and_lifecycle` | PASS |
| Generate from confirmed demand; manual items; remove without deleting history; edit target; select supplier; group/sort; labelled estimate; partial purchase; complete/waive; carry forward; print/export | `services/procurement.py::confirmed_demand/generate_list/add_manual_item/update_item/remove_item/waive_item/carry_forward/export_csv/_estimate`; `ProcurementPanel.tsx` (default demand range = the Asia/Beirut calendar day via `utils/tenantCalendar.ts`, D-040 — until 2026-09-21 it was the UTC date, so between 00:00 and 03:00 local the default found no demand; the six backend tests that built lists for a UTC 'today' now use the tenant day too) | `test_procurement.py` (all three tests); `ProcurementPanel.test.tsx`; `tenantCalendar.test.ts`; `e2e/phase6-procurement-flow.spec.ts` | PASS |

## F — Runner / assignee

| Requirement | Implementation evidence | Test evidence | Result |
|---|---|---|---:|
| Neutral membership assignee (owner or driver); sole owner self-assigns; owner may reassign; driver projection operational only | `services/procurement.py::set_assignee/list_assignees/my_pickups`; `routes/procurement.py` (`my-pickups` for any active member); `PickupPanel.tsx` shown to drivers | `test_procurement.py::test_assignee_is_neutral_and_driver_projection_has_no_prices` (self-assign, driver assignable, unknown 404, no money field, driver 403 on owner views, unassigned list disappears, admin 403) | PASS |

## G — Actual supplier purchase

| Requirement | Implementation evidence | Test evidence | Result |
|---|---|---|---:|
| Immutable header/items; internal UUID; finalization: items → price history → ledger obligation → procurement progress → state → audit → commit | migration `0024`; migration `0031` (2026-09-21: database triggers — purchase lines reject every update/delete, the header rejects delete and every update except the single reversal transition; the header is written once with its final total); D-059 preload and cost options skip entries of reversed purchases (`invoice_editor.py::_NOT_FROM_REVERSED_PURCHASE`); `services/supplier_purchases.py::record_purchase` | `test_supplier_purchases.py::test_purchase_finalization_is_atomic_replay_safe_and_rolls_back` (rollback leaves no row anywhere; replay returns the stored purchase; changed body 409) | PASS |

## H — Supplier ledger / payments

| Requirement | Implementation evidence | Test evidence | Result |
|---|---|---|---:|
| Append-only per currency; purchase charge, purchase reversal, payment, prepayment, reversal; D-039 cap; no per-purchase allocation; totals by currency never summed | Phase 3 `services/supplier_ledger.py` reused; `SupplierLedgerEntryType.PURCHASE_REVERSAL`; `services/supplier_purchases.py::reverse_purchase/outstanding_totals`; `PurchasePanel.tsx` totals | `test_supplier_purchases.py` (both tests); `test_supplier_ledger.py` (Phase 3) | PASS |

## I — Offline integration

| Requirement | Implementation evidence | Test evidence | Result |
|---|---|---|---:|
| Supplier price append offline/idempotent; procurement edits with expected version; purchase/payment commands immutable/idempotent; role projection least-privileged; one sync engine | `schemas/sync.py` (entity types `supplier`, `product_cost`, `procurement_item`, `supplier_purchase`, `supplier_payment`); `services/sync_push.py` appliers and financial mapping; `services/sync_changes.py` supplier projection (no costs); client `offline/supplierCommands.ts` + fallbacks in `SupplierSetup.tsx`, `ProcurementPanel.tsx`, `PurchasePanel.tsx` | `test_sync_phase6.py` (create/update with conflict envelope; price append named by operation id never doubles; hand-written ACTUAL_PURCHASE rejected; pull carries supplier without costs; procurement edit replay/conflict; purchase through sync with one effect and list completion; supplier payment capped and applied once) | PASS |

## J/K — API groups, migrations, RLS

| Requirement | Implementation evidence | Test evidence | Result |
|---|---|---|---:|
| `/api/v1/suppliers`, `/supplier-prices`, `/supplier-purchases`, `/supplier-ledger`, `/procurement`; new tables tenant_id + RLS; applied migrations untouched | routers registered in `main.py`; migrations `0022`–`0024` with `_enable_tenant_rls` | `alembic check` clean; foreign-tenant 404 assertions in every Phase 6 test; `test_hardening.py` head assertion | PASS |

## Definition of Done (PHASE_06.md N)

Suppliers/locations work; append-only price history with last/low/high/trend/stability;
deterministic comparable best supplier; daily procurement from confirmed demand with manual,
partial, carry-forward and print/export; sole owner can personally procure; driver receives
pickup need without prices; actual purchase updates history, payable and procurement atomically;
supplier debt/payment/reversal; customer/supplier totals by currency; offline supplier/procurement
through the Phase 4 sync; RLS blocks leakage; no stock/availability. All PASS with the evidence
above. Explicit exclusions unchanged.
