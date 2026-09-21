# Jobs and reminders contract

After order confirmation, the owner sets an estimated delivery date and Tawzeevo creates an owner reminder. Loan-delay and approved operational reminders must respect tenant scope, timezone, authorization, and idempotent execution.

The job runtime for the pilot is the in-process scheduler inside the API (D-079,
`apps/api/tawzeevo_api/services/jobs.py`, enabled by `BACKUP_SCHEDULER_ENABLED`): encrypted
backups (D-056/D-057), the storefront view rollup (D-051) and delivery reminders (D-049) run on
their own intervals, each in its own database session, with failures counted for the alert probe.
Every job works tenant by tenant: it reads the tenant list from the global `tenants` table (which
carries no `tenant_id` and therefore no row-level policy) and binds that tenant's RLS scope before
every statement against a tenant-owned table, so a job finds the same work under a database role
that is subject to row-level security as under one that bypasses it
(`docs/runbooks/database-role.md`, `apps/api/tests/test_jobs_rls_role.py`).
A due delivery reminder (tenant-local 09:00 stored as UTC `remind_at`) becomes exactly one in-app
owner notification of kind `DELIVERY_REMINDER` and is marked SENT under a row lock, so replays and
concurrent runs never notify twice; a reminder whose order is no longer confirmed is CANCELLED. No
SMS/e-mail/push channel exists for reminders (D-049). The same jobs are callable from
`python -m tawzeevo_api.cli.backup_jobs` for a hosting scheduler.
