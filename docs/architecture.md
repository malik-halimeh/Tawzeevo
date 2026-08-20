# Tawzeevo architecture

Tawzeevo is a monorepo with a FastAPI service, PostgreSQL as the live authority, a React/Vite operations PWA, and a later Next.js public storefront. Backend services own business rules. Tenant access follows authentication, session validation, active-tenant resolution, membership authorization, tenant-scoped data access, and PostgreSQL row-level security.

Phase 1 establishes durable boundaries; later phase features are not represented as implemented.
