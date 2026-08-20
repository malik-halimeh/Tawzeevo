# Tawzeevo architecture

Tawzeevo is a monorepo with a FastAPI service, PostgreSQL as the live authority, a React/Vite operations PWA, and a later Next.js public storefront. Backend services own business rules. Tenant access follows authentication, session validation, active-tenant resolution, membership authorization, tenant-scoped data access, and PostgreSQL row-level security.

```text
Operations browser
  → FastAPI routes and typed schemas
  → authentication / authorization dependencies
  → transactional services and repositories
  → SQLAlchemy
  → PostgreSQL constraints + row-level security
```

The access token remains in browser memory. The opaque refresh token is stored only as a server-side hash and sent through an HttpOnly cookie. Protected calls validate the JWT, session, user deletion state, and security versions before role or tenant checks.

Tenant business requests carry a tenant identifier as requested context, never as authority. An authenticated user must have an active membership with the required role, the tenant must be active, service queries retain explicit tenant predicates, and PostgreSQL RLS provides defense in depth. Platform administrators manage applications and access metadata through a separate authorization path.

Multi-record invariants use explicit PostgreSQL transactions. Application approval creates the tenant and owner membership while recording the approval atomically. User deletion locks affected tenants so concurrent requests cannot orphan an active tenant. Business money uses `NUMERIC(20,4)` and backend `Decimal` arithmetic.

Alembic owns schema evolution from an empty database. The Phase 1 chain is:

```text
20260820_0001 initial foundation
→ 20260820_0002 platform audit RLS
→ 20260820_0003 Cash Van slice
```

Phase 1 establishes durable boundaries; later phase features are not represented as implemented. The implemented vertical slice ends at approved-owner customer/category/barcode-product access and database-backed draft invoices. Confirmed financial history, storefront ordering, offline sync, procurement, routing, branding, analytics, and forecasting remain governed future work.

Platform administration is intentionally separate from tenant operations. A system administrator can review applications and control lifecycle/access metadata without tenant membership or private commercial-data access. An approved client becomes the tenant owner transactionally. Suspension blocks business context but retains the same tenant and all business rows for reactivation.

The contract index in `docs/contracts/README.md` is the navigation point for later milestones; authoritative precedence remains in `AGENTS.md`.
