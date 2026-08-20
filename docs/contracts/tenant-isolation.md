# Tenant isolation and lifecycle contract

Business access is authorized through authentication, session validation, active-tenant resolution, membership/role checks, tenant-scoped services, and PostgreSQL RLS. A client-provided tenant ID is never authority.

Phase 1 business routes use `/api/v1/tenants/{tenant_id}/...`. The path identifies the requested context; `resolve_tenant_context` independently verifies an active membership and an `ACTIVE` tenant before the route runs. The initial commercial slice is owner-only so the future restricted driver role is not accidentally granted broad customer, catalog, or invoice access.

`customers`, `categories`, `tenant_products`, `invoices`, and `invoice_items` all carry explicit `tenant_id`, use same-tenant composite foreign keys where records reference one another, and have forced PostgreSQL RLS policies bound to the transaction-local `app.current_tenant_id` setting. Services also include explicit tenant predicates. Transaction-local scope is restored after commits before any tenant-row refresh or follow-up read.

Platform admins review applications and manage tenant access without automatically becoming tenant members or gaining private commercial-data access. `SUSPENDED` blocks business access while preserving all data. Reactivation uses the same tenant. `CLOSED` is not temporary non-payment handling. An active tenant must retain an active usable owner.
