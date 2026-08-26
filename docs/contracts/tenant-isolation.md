# Tenant isolation and lifecycle contract

Business access is authorized through authentication, session validation, active-tenant resolution, membership/role checks, tenant-scoped services, and PostgreSQL RLS. A client-provided tenant ID is never authority.

Phase 1 business routes use `/api/v1/tenants/{tenant_id}/...`. The path identifies the requested context; `resolve_tenant_context` independently verifies an active membership and an `ACTIVE` tenant before the route runs. The initial commercial slice is owner-only so the future restricted driver role is not accidentally granted broad customer, catalog, or invoice access.

`customers`, `categories`, `tenant_products`, `invoices`, and `invoice_items` all carry explicit `tenant_id`, use same-tenant composite foreign keys where records reference one another, and have forced PostgreSQL RLS policies bound to the transaction-local `app.current_tenant_id` setting. Services also include explicit tenant predicates. Transaction-local scope is restored after commits before any tenant-row refresh or follow-up read.

Platform admins review applications and manage tenant access without automatically becoming tenant members or gaining private commercial-data access. `SUSPENDED` blocks business access while preserving all data. Reactivation uses the same tenant. `CLOSED` is not temporary non-payment handling. An active tenant must retain an active usable owner.

Phase 2 membership lifecycle mutations are implemented behind an internal service boundary. Creating,
reactivating, changing the role of, and revoking an existing `owner` or `driver` membership all retain
explicit tenant predicates and transaction-local RLS scope. Membership rows are never physically
deleted. Mutations lock the affected user and tenant before making a last-owner decision, so two
concurrent revocations or demotions cannot orphan an active tenant. A suspended tenant may have its
last owner revoked, but it cannot return to `ACTIVE` until an active, non-deleted owner exists.

P2-M1 intentionally adds no membership-management HTTP route or invitation behavior. Authorization
and invitation semantics for such a public surface are not defined by the current contract; adding
them here would invent product behavior. Later routes must perform authorization before calling the
membership lifecycle service.

P2-M2 adds an authenticated self-context read at `/api/v1/tenant-contexts` so the operations UI can
discover the caller's active memberships without trusting a tenant ID supplied by the browser. The
authentication dependency sets transaction-local `app.current_user_id`; the membership SELECT policy
permits only rows for that user when no tenant context is active. INSERT, UPDATE, and DELETE remain
bound exclusively to `app.current_tenant_id`. Customer and tenant-category mutations remain owner-only,
explicitly tenant-filtered, and protected by forced tenant RLS.

P2-M3 separates global master-product identity from tenant-owned catalog data. `master_products` and
`master_barcodes` have RLS enabled and no public policies, while the backend table owner remains the
controlled access path. `tenant_products` and `tenant_barcodes` use explicit tenant predicates; the
barcode table also has forced RLS and a same-tenant composite foreign key to its product. A tenant
barcode value is unique only inside its tenant, while a master barcode is globally unique. Barcode
lookup checks the tenant namespace first, then the master catalog, and never exposes another tenant's
adoption, price, or publication state.
