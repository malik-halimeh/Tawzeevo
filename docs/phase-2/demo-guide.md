# Phase 2 demo and presentation guide

This guide demonstrates only completed Phase 2 customer, catalog, barcode, grade-pricing, packaging,
media, and tenant-isolation behavior. Use synthetic data only.

## Prepare the environment

1. Follow the root `README.md` local setup using either hosted Supabase PostgreSQL or local Docker
   Compose PostgreSQL. Never demonstrate against production data.
2. Apply migrations and confirm revision `20260826_0007` is the current Alembic head.
3. Validate and import the bundled starter catalog:

   ```powershell
   .\.venv\Scripts\python.exe -m tawzeevo_api.cli.import_master_catalog --check-only --report data/master-catalog/open-food-facts-lebanon-v1.quality.json
   .\.venv\Scripts\python.exe -m tawzeevo_api.cli.import_master_catalog
   ```

4. Start the API and operations client using the commands in the root README.
5. Confirm `/health`, `/health/database`, `/docs`, and the operations client load.
6. Use a synthetic client whose tenant application has been approved. Sign in as that tenant's
   active owner. A platform administrator alone does not receive tenant-private access.

## Recommended presentation route

### 1. Establish tenant context and isolation

1. Sign in as an approved tenant owner.
2. Open the tenant workspace and show the selected tenant and owner membership.
3. Explain that the tenant ID selects context but does not grant access; membership and tenant
   lifecycle checks run before business access, with PostgreSQL RLS as a second boundary.

### 2. Demonstrate customer search and disambiguation

1. Create two synthetic customers with the same normalized Lebanese phone number.
2. Give them different names or addresses and assign different grades, such as A+ and B+.
3. Search for that phone number using different spacing.
4. Show that both matches remain separate with their IDs, addresses, and grades.
5. Select one result, update its address or grade, and show that the other record is unchanged.

State explicitly that Tawzeevo does not automatically merge customers.

### 3. Demonstrate bilingual category lifecycle

1. Open Categories and create a tenant category with English and Arabic names, a slug, and an
   explicit display order.
2. Create a second category and show deterministic ordering.
3. Archive one category and show that it remains historically retained rather than being deleted.
4. Switch the interface to Arabic and confirm RTL layout while slugs, phone numbers, prices, and
   barcodes remain readable left-to-right.

### 4. Resolve and adopt a known catalog barcode

1. Open Products and scan `5283003202007`.
2. Show the imported master identity “Hummus tahini” and its master-owned piece barcode.
3. Adopt it into the current tenant with a tenant category, currency, price basis, and tenant price.
4. Toggle publication and explain that publication means visibility only—not stock or availability.

The starter records are attributed to Open Food Facts contributors under ODbL 1.0. They include
names, barcodes, and categories only; no source images or prices were imported.

### 5. Demonstrate the missing-product flow and packaging

1. Scan a clearly synthetic unknown barcode, such as `DEMO-LOCAL-001`.
2. Create a manual tenant product from the unknown result.
3. Set piece or box as its price basis and, when appropriate, provide pieces per box.
4. Add a second tenant-owned barcode at the other package level.
5. Show that each barcode retains explicit ownership and piece/box package context.

### 6. Demonstrate grade pricing precedence

1. Give a product a normal tenant price.
2. Configure an A-grade percentage discount.
3. Resolve the price for an A customer and show the discounted result.
4. Add an explicit A-grade product price and resolve again.
5. Show that the explicit grade price wins over the percentage discount; removing it restores the
   discount fallback, and removing the discount restores the normal price.

Explain that the backend performs the calculation using Decimal/NUMERIC and four-decimal
round-half-up rules. The browser does not decide the authoritative price.

### 7. Demonstrate safe product media

1. Upload a small synthetic JPEG, PNG, or WebP image with useful alternative text.
2. Show the authenticated image in the tenant product card and barcode result.
3. If useful, demonstrate that an SVG or renamed non-image file is rejected.

Explain that uploads are decoded, validated, and re-encoded as WebP. Tenant-private image access is
authorized, and the local adapter is a development/demo implementation behind a provider-neutral
storage interface.

### 8. Optional isolation proof in Swagger

With two synthetic tenants and their separate owner accounts:

1. Create or adopt the same master product independently at different tenant prices.
2. Upload an image only for the first tenant.
3. Scan as each owner and show that each receives only their own tenant price and image.
4. Attempt to address the other tenant's product ID and show the request is denied or hidden.

Do not copy access tokens into screenshots or presentation material.

## Phase boundary to state aloud

Phase 2 completes the production customer/catalog/barcode/grade-pricing/media foundation. It has no
stock or availability model. Draft invoices exist as a foundation, but confirmed immutable invoice
revisions, customer ledgers, payments, debt, refunds, and cancellation reversals belong to Phase 3
and must not be presented as completed here.

## Pre-presentation checklist

- [ ] The full backend suite and `npm run check` pass.
- [ ] Alembic reports `20260826_0007 (head)` and no schema drift.
- [ ] The catalog quality report says PASS with four accepted and zero rejected records.
- [ ] The API and operations-client origins match the configured CORS allowlist.
- [ ] The demonstration tenant is ACTIVE and the synthetic presenter has an active owner membership.
- [ ] Every customer, barcode, address, image, and price used in the demo is synthetic.
- [ ] English and Arabic layouts render correctly.
- [ ] No database URL, JWT secret, cookie, bearer token, or real customer data is visible.
- [ ] Publication is described as visibility, never inventory availability.
- [ ] No Phase 3 or later behavior is claimed as implemented.
