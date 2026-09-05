# Phase 2 requirements audit

Audit date: 2026-08-26

Status: PASS

This document freezes evidence for `PHASE_02.md`. It does not supersede the project contract,
locked decisions, or phase contract.

## P2-M1 — Tenant security and membership lifecycle

| Requirement | Implementation evidence | Test evidence | Result |
|---|---|---|---:|
| Tenant scope is explicit and authorization precedes business access | `dependencies.py`, `repositories/tenancy.py`, `services/cash_van.py`, tenant-prefixed routes | Tenant API denial coverage in `test_cash_van.py`; protected-route sweep in `test_hardening.py` | PASS |
| Membership lifecycle preserves usable ownership | `services/memberships.py`, membership constraints and lifecycle fields in `models.py` | Activation, revocation, last-owner, and concurrent-owner coverage in `test_cash_van.py` and `test_users.py` | PASS |
| Cross-tenant reads and writes are denied at API and database layers | Explicit tenant predicates plus forced PostgreSQL RLS in migrations `0003`–`0006` | Non-bypass PostgreSQL-role RLS tests and cross-tenant API tests | PASS |
| Tenant suspension blocks business access without deleting data | Tenant-context dependency and platform lifecycle service | Suspension/reactivation retention regressions | PASS |

## P2-M2 — Customers, grades, and categories

| Requirement | Implementation evidence | Test evidence | Result |
|---|---|---|---:|
| Customers can be created, viewed, updated, and searched within one tenant | Customer schemas, routes, models, and `services/cash_van.py` | Customer CRUD/search integration coverage | PASS |
| Phone numbers are normalized while duplicate matches remain separate | Shared phone normalization and deterministic search response | Duplicate-phone disambiguation test with separate IDs, addresses, and grades | PASS |
| Address, paired coordinates, and grades A+, A, B+, B are supported | Customer model/schema and migration `0004` | Location validation, grade assignment, update, and cross-tenant tests | PASS |
| Automatic customer merging is absent | Customer service retains distinct records sharing a normalized phone | Duplicate-phone regression proves both records remain addressable | PASS |
| Master and tenant categories remain distinct | `MasterCategory` and `TenantCategory` models and same-tenant relationships | Master-link and tenant category tests | PASS |
| Categories support bilingual names, tenant slugs/order, and safe archive | Category schemas/service and migration `0004` | Bilingual ordering, slug uniqueness, archive retention, and archived-category rejection tests | PASS |
| Customer/category workflows are available in the bilingual operations UI | `TenantWorkspace.tsx`, typed client contracts, English/Arabic strings | `App.test.tsx` duplicate-phone, category, and RTL component tests | PASS |

## P2-M3 — Master/tenant products and barcodes

| Requirement | Implementation evidence | Test evidence | Result |
|---|---|---|---:|
| Master identity and tenant adoption are separate | `MasterProduct`, `TenantProduct`, related schemas/services, migration `0005` | Known master barcode scan and idempotent tenant-adoption test | PASS |
| Master and tenant barcode ownership is explicit | Separate master/tenant barcode models and ownership responses | Ownership assertions plus non-bypass RLS coverage | PASS |
| Unknown barcodes can become manual tenant products | Manual-product service and product creation route | Unknown scan-to-manual-product regression | PASS |
| Package-level piece/box barcodes are supported | Barcode package-level fields and add-barcode route | Additional box-barcode integration and UI tests | PASS |
| Publication controls visibility only | `is_published` on tenant products without stock fields | Publication toggle tests and no-stock contract regression | PASS |
| Scan resolves the correct master or tenant identity and tenant price | Barcode lookup and tenant product response services | Known/unknown scan, tenant price, and cross-tenant tests | PASS |

## P2-M4 — Packaging, pricing, and media

| Requirement | Implementation evidence | Test evidence | Result |
|---|---|---|---:|
| Piece/box packaging and price basis are explicit | Product pricing fields, schemas, and migration `0006` | Piece/box derivation and validation tests | PASS |
| `pricing-v1` is backend-authoritative | `services/pricing.py` and resolved-price route | Precedence, fallback, reset, and invoice snapshot tests | PASS |
| Explicit grade price beats percentage discount, otherwise normal price | Grade discount and product-grade-price services | A+/A/B+/B precedence and fallback assertions | PASS |
| Financial calculations use Decimal/NUMERIC and four-decimal half-up rounding | Decimal service logic and NUMERIC database columns | True tie cases and independently rounded package derivations | PASS |
| Image storage is provider-neutral | Storage protocol and local development adapter in `services/media.py` | Authenticated upload/retrieval and adapter tests | PASS |
| Uploads accept JPEG/PNG/WebP, decode and re-encode safely, and reject SVG/spoofed/oversized input | Media processor, size/dimension checks, WebP output | All permitted formats, spoofing, SVG, byte/dimension, and traversal tests | PASS |
| Supplier cost/profit was not invented in Phase 2 | Selling-price-only pricing models; D-031 reserves later immutable cost snapshots | Contract inspection and absence of supplier-cost fields/workflow | PASS |

## P2-M5 — Catalog import and acceptance

| Requirement | Implementation evidence | Test evidence | Result |
|---|---|---|---:|
| Starter Lebanon-market catalog has an approved legal source | `data/master-catalog` Open Food Facts snapshot, attribution, and ODbL notice; D-032 | Committed quality-gate test | PASS |
| Source, license, retrieval time, version, checksum, and per-product provenance persist | `MasterCatalogImport`, `MasterProductSource`, migration `0007`, import service | Provenance persistence and exact-replay idempotency test | PASS |
| Invalid/duplicate data produces a deterministic quality report | Import validator and committed JSON quality report | Invalid GTIN check-digit and duplicate-barcode tests | PASS |
| Conflicting identities cannot partially import | Transactional import service | Version/content and existing-identity rollback assertions | PASS |
| Imported barcode resolves through tenant adoption to name, image, tenant price, and grade price | Catalog import plus existing scan/adoption/pricing/media services | End-to-end imported scan acceptance test across two tenants | PASS |
| Import performs no unlicensed bulk scrape or image copy | Versioned local snapshot; no runtime fetch; Open Food Facts images excluded | Source-contract validation and dataset inspection | PASS |

## Definition of Done

- [x] Customer phone lookup is deterministic and duplicate matches remain distinguishable.
- [x] Tenant isolation passes at the API and PostgreSQL RLS layers.
- [x] Master and tenant categories are usable and archive safely.
- [x] Master and tenant products are usable and remain distinct.
- [x] A known imported barcode immediately resolves.
- [x] An unknown barcode can become a manual tenant product.
- [x] Authenticated product images upload, re-encode, store, and retrieve correctly.
- [x] Piece/box packaging and calculations are correct.
- [x] Grades A+, A, B+, and B follow `pricing-v1` precedence and rounding.
- [x] No stock or availability state or behavior exists.

## Phase boundary

Phase 2 supplies customer, catalog, barcode, grade-pricing, media, and draft-invoice foundations.
It does not claim confirmed invoices, immutable customer ledgers, payment/refund processing,
storefront ordering, offline synchronization, supplier procurement, or delivery routing.

Conclusion: P2-M1 through P2-M5 and every Phase 2 Definition of Done item have implementation and
test evidence. Phase 2 is complete without implying that Phase 3 financial behavior exists.
