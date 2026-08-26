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

## Pending decisions

None.

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
