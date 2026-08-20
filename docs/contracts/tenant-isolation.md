# Tenant isolation and lifecycle contract

Business access is authorized through authentication, session validation, active-tenant resolution, membership/role checks, tenant-scoped services, and PostgreSQL RLS. A client-provided tenant ID is never authority.

Platform admins review applications and manage tenant access without automatically becoming tenant members or gaining private commercial-data access. `SUSPENDED` blocks business access while preserving all data. Reactivation uses the same tenant. `CLOSED` is not temporary non-payment handling. An active tenant must retain an active usable owner.
