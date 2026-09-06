# 04_DECISIONS.md — User-Approved Decision Ledger

Only record decisions explicitly approved by the user or already locked by the authoritative contract.

Do not use this file to invent decisions.

## Locked decisions

| ID | Decision | Status |
|---|---|---|
| D-001 | Phase 1 contains the complete supplied FastAPI program requirements; the source-labeled frontend bonus is mandatory for this project. | LOCKED |
| D-002 | PostgreSQL is the authoritative database. | LOCKED |
| D-003 | FastAPI is the backend framework. | LOCKED |
| D-004 | Operations client is React + TypeScript + Vite and becomes an offline-first PWA. | LOCKED |
| D-005 | Public storefront uses Next.js App Router + TypeScript. | LOCKED |
| D-006 | English and Arabic are supported from the foundation. | LOCKED |
| D-007 | Platform/system user roles include admin/client; tenant roles are separate owner/driver roles. | LOCKED |
| D-008 | Public registration cannot choose a privileged role and creates client. | LOCKED |
| D-009 | Customers are not required to be authenticated users. | LOCKED |
| D-010 | No inventory/stock quantities or product availability statuses. | LOCKED |
| D-011 | Confirmed invoices remain editable only through immutable revision/ledger history. | LOCKED |
| D-012 | Customer cannot directly cancel; owner approves/rejects cancellation. | LOCKED |
| D-013 | Owner sets estimated delivery date after confirmation. | LOCKED |
| D-014 | No customer-facing delivery tracking. | LOCKED |
| D-015 | Homepage featured-product advertising defaults to 7 days and is not availability. | LOCKED |
| D-016 | Recommendations are deterministic first and purchase weight is higher than view weight. | LOCKED |
| D-017 | Google Drive is encrypted backup/export, not the live database. | LOCKED |
| D-018 | AI/forecasting is deferred until the final phase. | LOCKED |
| D-019 | Supplier payments reduce aggregate supplier payable; no per-purchase allocation unless later approved. | LOCKED |
| D-020 | Automatic customer merging is not part of the project unless later approved. | LOCKED |
| D-021 | A tenant owner may personally operate the Cash Van and perform all delivery/route operational actions without a second driver account or duplicate membership. Delivery tasks may be assigned to an active owner or driver membership. If exactly one active usable owner exists and there are no active drivers, delivery work defaults to that owner; otherwise an owner selects the assignee. Drivers remain least-privileged and cannot reassign work unless later explicitly approved. | LOCKED |
| D-022 | Platform `admin` manages tenant applications and SaaS access without automatically becoming a tenant owner or gaining tenant-private business-data access. A registered client submits an application; admin approves/rejects it; approval creates/activates the tenant and owner membership transactionally. | LOCKED |
| D-023 | Temporary non-payment never deletes a tenant or its business data. Platform admin uses tenant `SUSPENDED` with reason `SUBSCRIPTION_OVERDUE`, may set/extend `access_until` and optional `grace_until`, and later reactivates the same tenant with retained data intact. Automated payment-provider charging is not required unless later explicitly approved. | LOCKED |
| D-024 | The public product/platform name and the single public GitHub repository name are `Tawzeevo`. “Cash Van” describes the operating model and is not the product name. | LOCKED |
| D-025 | Public repository files and history use neutral implementation-agent terminology and exclude external assistant branding. | LOCKED |
| D-026 | Session policy uses 15-minute access tokens and 30-day refresh tokens. The refresh cookie is HttpOnly, Secure in production, SameSite=Lax, and scoped to `/api/v1/auth`. Refresh tokens rotate on every refresh; reuse of a rotated token revokes all active sessions for that user. | LOCKED |
| D-027 | The current development database is the free hosted Supabase PostgreSQL project `Tawzeevo` in `eu-central-1`. Tawzeevo continues to use its own FastAPI authentication and direct PostgreSQL access; Supabase Auth and the Supabase Data API are not application dependencies. Docker Compose remains available for reproducible local PostgreSQL and disposable database tests. | LOCKED |
| D-028 | The public Tawzeevo deployment uses Render's free static-site hosting for the operations client and Render's free web-service hosting for the FastAPI service. The API continues to use the hosted Supabase PostgreSQL database directly. | LOCKED |
| D-029 | The guest, customer, owner, and driver role demonstration is an environment-gated, frontend-only synthetic gallery at `/demo`. It introduces no new login role, credential, backend behavior, migration, database row, persistence, API request, or dependency. Guest/customer remain unauthenticated storefront perspectives; owner/driver remain tenant membership roles. The gallery is not Phase 2 evidence and must be removable without database or migration cleanup. | LOCKED |
| D-030 | `pricing-v1` stores tenant grade discounts as `NUMERIC(7,4)` percentages from `0.0000` through `100.0000`. An explicit product-grade price uses the product's currency and PIECE/BOX basis and overrides the grade discount. Otherwise the backend applies `normal_basis_price × (1 − discount_percent ÷ 100)`; without either override it uses the normal basis price. The resolved basis price is quantized to four decimals with `ROUND_HALF_UP`, then the counterpart piece/box price is derived from that rounded basis price and independently quantized to four decimals. All authoritative calculations use Decimal/NUMERIC only. | LOCKED |
| D-031 | Historical profit must never be recomputed from a product's latest supplier price. Each confirmed invoice revision line must preserve an immutable unit-cost snapshot, its currency, package/basis context, and provenance sufficient to reproduce the profit known for that revision. Later supplier price changes affect only later eligible sales and never rewrite earlier invoice profit. Supplier cost and profit are owner-only and must not appear in driver or public/customer projections. The exact automatic cost-source selection and any owner override workflow must be locked before implementing the supplier/confirmed-invoice integration. | LOCKED |
| D-032 | P2-M5 may use a small curated Open Food Facts Lebanon-market subset containing product names, barcodes, and categories under the Open Database License (ODbL). Tawzeevo must provide attribution and share the imported catalog data under compatible ODbL terms, record source/retrieval/import-version provenance, enforce barcode and required-field quality checks with a duplicate/quality report, respect source API identification/rate limits, avoid unlicensed bulk scraping, and import no Open Food Facts product images. This is an initial catalog, not a claim of comprehensive Lebanese-market coverage. | LOCKED |
| D-033 | An order may have at most one production invoice header, and an invoice header may reference zero or one order. All immutable revisions belong to that single header. A tenant-scoped uniqueness constraint applies when `order_id` is non-null; split or multiple invoices for one order are not implemented unless later explicitly approved. | LOCKED |
| D-034 | Supplier identities, product-cost entries, preferred supplier selection, and negotiated prices are tenant-private. The same real supplier and master product may have different independent costs for different tenants. Product costs are append-only entries scoped by tenant, supplier, tenant product, currency, piece/box basis, and effective time. Invoice entry preloads the latest eligible cost for the current tenant/product and selected or preferred supplier; changing supplier reloads only that tenant's eligible cost. An owner may override the cost on the spot with a required reason. The override affects only that revision unless the owner explicitly saves it as a new product-cost entry. Every confirmed revision line must have and immutably snapshot the chosen cost, currency, basis, package context, supplier/source provenance, and override reason when applicable. Missing or currency-mismatched cost blocks confirmation; Tawzeevo performs no silent conversion. Phase 6 procurement may create these cost entries automatically but may never rewrite historical invoice snapshots. This is a latest-known-cost model, not stock, FIFO, weighted-average inventory, or a globally shared supplier price. | LOCKED |
| D-035 | For a manual invoice item that is not linked to a catalog product, the owner-entered unit price is the final effective customer price. Tawzeevo does not automatically apply the customer's catalog grade percentage or a product-grade price to that manual line. | LOCKED |
| D-036 | Invoice line discounts and markups are fixed currency amounts applied once to the whole line, not per-unit or percentage adjustments. Invoice-level discounts and markups are fixed currency amounts applied once to the invoice. Quantity is quantized to Q4 before multiplication; authoritative stored monetary stages use Q4 `ROUND_HALF_UP`. For each line: `base = Q(effective_unit_price × quantity)` and `line_total = Q(base − line_discount + line_markup)`. Invoice totals are `subtotal = Q(SUM(base))`, `discount_total = Q(SUM(line_discount) + invoice_discount)`, `markup_total = Q(SUM(line_markup) + invoice_markup)`, and `net_sales = Q(subtotal − discount_total + markup_total)`. Catalog grade savings are already reflected in effective unit price and are not also counted in `discount_total`. | LOCKED |
| D-037 | Preserve the immutable invoice-revision due snapshot `Q(prior_balance_snapshot + net_sales)` and present it distinctly from the customer's live current balance. Later payments or ledger events update the live balance but never rewrite the revision snapshot. User-facing labels must make the two meanings clear. | LOCKED |
| D-038 | Each customer or supplier may have at most one initial opening-balance event per currency. A later correction must use an explicit immutable correction/reversal event rather than another opening event or mutation of the original. Whether an initial opening may be negative remains pending explicit disposition. | LOCKED — PARTIAL; SIGN POLICY REVIEW_REQUIRED |
| D-039 | An ordinary supplier payment may not exceed the supplier's current positive aggregate payable in that currency. Any excess is recorded through a separate explicit supplier-prepayment action, producing clearly labelled supplier credit; it is not silently accepted as an oversized ordinary payment. Reversals remain immutable compensating events and supplier payments remain aggregate, never allocated per purchase. | LOCKED |
| D-040 | Customer overdue age uses the `Asia/Beirut` calendar boundary and the approved `age_days > customer_overdue_threshold_days` rule. If the tenant has no configured threshold, overdue detection is disabled. Durable notification cadence remains a later operational policy; it does not change the red-indicator calculation. | LOCKED |
| D-041 | Before Phase 3 can complete, owners receive a dedicated Suppliers and Product Costs setup API/UI where they can create suppliers, append effective-dated product costs, and select a preferred supplier. The Invoice Editor links to this setup when required cost input is missing. Full procurement remains Phase 6; direct fixture/SQL setup is not a supported owner workflow. | LOCKED |
| D-042 | Owner-issued public invoice sharing permits at most one active capability per invoice and only for a confirmed invoice. Issuing or rotating a link invalidates the previous active link; cancellation revokes public access. The raw capability remains in the URL fragment and is transported to the API in the private capability header, subject to the existing hash-only/no-log/security rules. Phase 5 must still present its required provisional checkout representation without weakening this confirmed-invoice sharing rule; the exact provisional presentation flow is a Phase 5 gate detail. | LOCKED |

## Pending decisions

- RP-NOW-01: invoice zero/sign admission boundaries, including whether initial confirmation may
  have zero net sales and whether any negative price/adjustment input is permitted.
- RP-NOW-02: whether the single initial customer/supplier opening per currency may be negative.

## Implementation procedure for a new decision

When a decision is needed:
1. do not implement it;
2. mark the current milestone blocked in `03_IMPLEMENTATION_STATUS.md`;
3. ask the user;
4. after explicit approval, add a row here:
   - ID
   - exact decision
   - phase/milestone
   - date if useful
   - what it supersedes, if anything;
5. resume only after the user says to continue.
