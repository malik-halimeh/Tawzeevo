# Tawzeevo architecture

Tawzeevo is a monorepo with a FastAPI service, PostgreSQL as the live authority, a React/Vite operations PWA, and a later Next.js public storefront. Backend services own business rules. Tenant access follows authentication, session validation, active-tenant resolution, membership authorization, tenant-scoped data access, and PostgreSQL row-level security.

Phase 1 establishes durable boundaries; later phase features are not represented as implemented. The implemented vertical slice ends at approved-owner customer/category/barcode-product access and database-backed draft invoices. Confirmed financial history, storefront ordering, offline sync, procurement, routing, branding, analytics, and forecasting remain governed future work.

Platform administration is intentionally separate from tenant operations. A system administrator can review applications and control lifecycle/access metadata without tenant membership or private commercial-data access. An approved client becomes the tenant owner transactionally. Suspension blocks business context but retains the same tenant and all business rows for reactivation.

The contract index in `docs/contracts/README.md` is the navigation point for later milestones; authoritative precedence remains in `AGENTS.md`.
