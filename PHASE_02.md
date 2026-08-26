# PHASE_02.md — Tenant Business Core, Customers, Catalog, Barcodes, Grades, Pricing

## Start condition

Phase 1 is COMPLETE.

Do not start if Phase 1 has unresolved failing tests or migration defects.

## Locked outcomes

Build production catalog/customer/pricing foundation used by later invoice and storefront work.

No stock.
No product availability state.

## Required domain behavior

Customers:

- tenant-scoped;
- create/update/view/search;
- phone normalization;
- duplicate phone disambiguation;
- address;
- coordinates;
- grade assignment.

Do not implement automatic merge.

Categories:

- master categories and tenant categories are distinct;
- bilingual names;
- tenant ordering/slugs;
- archive/disable rather than destructive historical breakage.

Products:

- master product identity separated from tenant product;
- curated Lebanese barcode catalog;
- manual tenant product when missing;
- tenant product publication flag = visibility only;
- images;
- piece/box packaging;
- tenant price.

Barcodes:

- master and tenant barcode ownership remain explicit;
- support package-level barcode when needed;
- barcode scan resolves product image/name and tenant price.

Customer grades:

- A+, A, B+, B.

Pricing:

- explicit grade price beats grade percentage discount;
- otherwise normal price;
- backend owns calculation;
- Decimal/NUMERIC only;
- exact `pricing-v1` contract from project architecture docs must be used.

Media:

- provider-neutral object storage interface;
- safe local/dev adapter permitted;
- JPEG/PNG/WebP;
- validate/re-encode;
- no arbitrary SVG upload.

Master catalog import:

- provenance/source;
- import version;
- duplicate/quality report;
- no unlicensed bulk scrape.

## Milestones

### P2-M1 — Tenant security + membership lifecycle

- finish tenant-scoped repositories/policies;
- membership lifecycle;
- last-owner invariant coverage;
- cross-tenant/RLS integration tests.

### P2-M2 — Customers, grades, categories

- production customer model/API/UI;
- phone search/disambiguation;
- addresses/location data;
- grades;
- master/tenant category structures.

### P2-M3 — Master/tenant products + barcodes

- master products;
- tenant products;
- barcode tables/lookup;
- missing-product manual flow;
- publication visibility only.

### P2-M4 — Packaging, pricing, media

- piece/box;
- price basis;
- grade prices/discount;
- exact rounding tests;
- image/media abstraction and security.

### P2-M5 — Catalog import + acceptance

- initial legal/curated Lebanon-market dataset;
- import quality/provenance;
- full tenant isolation and pricing tests;
- scan-to-name/image/tenant-price demonstration.

## Definition of Done

- customer phone lookup deterministic;
- tenant isolation passes;
- categories usable;
- master/tenant products usable;
- known barcode immediately resolves;
- unknown barcode can become manual tenant product;
- images work;
- piece/box calculations correct;
- grades correct;
- no stock/availability logic exists.

Mark Phase 2 COMPLETE and STOP.
