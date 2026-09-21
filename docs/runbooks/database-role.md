# Runbook — application database role and row-level security

Tenant isolation is enforced twice: every service filters by tenant, and PostgreSQL row-level
security (RLS) is forced on every tenant-owned table as defense in depth
(`docs/contracts/tenant-isolation.md`). The second layer only exists when the role the API
connects with (`DATABASE_URL`) is **neither `SUPERUSER` nor `BYPASSRLS`**. A hosted default
role (for example a managed provider's `postgres` role) may carry `BYPASSRLS`, in which case
`FORCE ROW LEVEL SECURITY` is inert for the application and isolation rests on application
predicates alone.

## Required role properties

| Attribute | Required value |
|---|---|
| `rolsuper` | `false` |
| `rolbypassrls` | `false` |
| privileges | `USAGE` on schema `public`; `SELECT, INSERT, UPDATE, DELETE` on all application tables; `USAGE` on all sequences |

Migrations create policies and alter tables, which requires table ownership. Either run
`alembic upgrade head` as the owning role and the API as the restricted role (two connection
strings), or let the restricted role own the tables — `FORCE ROW LEVEL SECURITY` applies the
policies to the owner too, so an owning `NOBYPASSRLS` role is still subject to RLS.

## How the API reports it

- Startup: the API reads `pg_roles` for `current_user` and logs
  `database role <name> is subject to row-level security` or a **warning**
  `database role <name> bypasses row-level security (...)`.
- `GET /health/database` answers `database_role_rls_enforced: true|false` (no role name).
- `DB_ROLE_REQUIRE_RLS_SUBJECT=true` makes the API **refuse to start** with a role that bypasses
  RLS. It is `false` by default so an existing deployment is never taken down by a redeploy; turn
  it on once the restricted role is in place, so a later configuration change cannot silently
  regress.

## Owner check on the hosted database (never run by automation)

Connect to the hosted database with the exact `DATABASE_URL` the API service uses and run:

```sql
select rolname, rolsuper, rolbypassrls from pg_roles where rolname = current_user;
```

Expected safe result: `false | false`. Record the output (role name and the two flags, no
connection string) in the Phase 9 evidence. Alternatively read the live
`GET /health/database` answer after a deploy that includes this runbook's code: it must show
`"database_role_rls_enforced":true`.

## Provisioning a restricted role (template, adapt the names)

```sql
create role tawzeevo_app login nosuperuser nobypassrls password '<set in the provider dashboard>';
grant usage on schema public to tawzeevo_app;
grant select, insert, update, delete on all tables in schema public to tawzeevo_app;
grant usage on all sequences in schema public to tawzeevo_app;
alter default privileges in schema public grant select, insert, update, delete on tables to tawzeevo_app;
alter default privileges in schema public grant usage on sequences to tawzeevo_app;
```

Then point the API service's `DATABASE_URL` at that role, redeploy, confirm
`database_role_rls_enforced` is `true`, and set `DB_ROLE_REQUIRE_RLS_SUBJECT=true`.

## What is verified under a restricted role, and what is not

Verified locally, against a disposable PostgreSQL database, with a real `NOSUPERUSER NOBYPASSRLS`
login role:

- the application lifecycle that platform administration depends on (tenant applications, audit
  events) — `apps/api/tests/test_tenant_applications_rls.py`;
- the three **scheduled jobs** — delivery reminders, the storefront view rollup and the encrypted
  backups — `apps/api/tests/test_jobs_rls_role.py`. Each job enumerates tenant ids from the
  global `tenants` table (no `tenant_id` column, therefore no policy) and binds the tenant scope
  before every statement that touches a tenant-owned table, so it finds the same work under a
  role that is subject to row-level security as under one that bypasses it.

Not verified here: the **hosted** role itself. Its `rolsuper`/`rolbypassrls` attributes and its
grants exist only on the hosted database; the owner check above is the only evidence for it. A
restricted role must hold the grants in the table above — including `SELECT` on `tenants`, which
the scheduled jobs enumerate — or the jobs cannot run.
