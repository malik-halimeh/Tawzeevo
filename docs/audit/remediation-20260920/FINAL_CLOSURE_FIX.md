# Final closure fix — Fable 5 final review findings (2026-09-22)

- **Branch:** `remediation/audit-20260920`. Not merged, not pushed, not deployed.
- **Start HEAD:** `aa5185edb493d0f3f3c779c64da337b28b21a7fe`
- **Final HEAD:** this documentation commit, whose parent
  `d3c58150c5295b2ac01ef39270eaa91419460539` carries the implementation and the regression test.
  Both commits are on the branch only.
- **Scope:** exactly the three findings of the final independent review — `FABLE-F-001`,
  `FABLE-F-002`, `FABLE-F-003` — plus the compatibility wording those findings name. Nothing
  else was changed; no new audit was run.
- **Environment:** one disposable PostgreSQL 18.4 cluster on `127.0.0.1:55442` under `.tmp/`,
  database `tawzeevo_closure`, migrated with `alembic upgrade head` to `20260921_0031`, backup
  provider `memory`. No hosted, staging or production system was connected to; no secret was
  read or written; the cluster was stopped and left behind as disposable data.
- **Review source (never modified):**
  `../tawzeevo-audit/fable5-final-review-20260922/`.

## 1. Result

| Finding | Severity | Status after this fix |
|---|---|---|
| FABLE-F-001 — scheduled jobs find no work under an RLS-subject role | MEDIUM | **FIXED_VERIFIED** (runtime-proven under a real `NOSUPERUSER NOBYPASSRLS` login role) |
| FABLE-F-002 — stale head / static-check references in Phase 9 evidence | LOW | **FIXED** |
| FABLE-F-003 — `TRUSTED_PROXY_HOPS` over-configuration hazard undocumented | LOW | **FIXED** |

## 2. FABLE-F-001 — root cause

Every tenant-owned table carries one policy,
`tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid`, and
`FORCE ROW LEVEL SECURITY`. The three scheduled jobs opened their work by scanning a
tenant-owned table **before any tenant scope was bound**:

- `services/jobs.py::run_due_delivery_reminders` — `SELECT` of due `delivery_reminders`;
- `services/backup.py::run_due_backups` — `SELECT` of `tenant_backup_connections`;
- `services/storefront_signals.py::rollup_views` — `GROUP BY` over `product_interactions`.

Under a role that is neither `SUPERUSER` nor `BYPASSRLS` — the role
`docs/runbooks/database-role.md` tells the owner to provision — that first scan returns no rows,
so each job silently did nothing: no error, no failure counter, no alert. The project's own
tests could not observe it because the suite connects as a superuser, for which the policies are
inert. No tenant data was ever exposed; the defect was availability/operational.

## 3. Implementation approach

The fix is at the job layer, not at the database layer. Nothing was granted `BYPASSRLS` or
`SUPERUSER`, no policy was widened, and no scheduler-bypass GUC was introduced. No migration was
needed.

New helper `repositories/tenancy.py::all_tenant_ids(db)` reads the tenant ids from the global
`tenants` table. That table has no `tenant_id` column and therefore no row-level policy: it is
the one legitimate unscoped enumeration source, and it yields identifiers only.

Each job now runs **tenant by tenant**: enumerate → `set_tenant_scope(db, tenant_id)` →
query that tenant's due work → process it with the existing idempotency and locking logic →
commit or roll back → next tenant.

- **Delivery reminders.** The due-id scan runs inside the tenant's scope and is wrapped so a
  failing tenant is counted (`reminder_failures`) and logged without blocking the rest. Each
  reminder is still its own transaction, the scope is re-bound before the
  `SELECT … FOR UPDATE SKIP LOCKED` (a transaction-local GUC does not survive the commit or
  rollback of the previous reminder), and the CANCELLED / SENT / replay behaviour is unchanged.
- **View rollup.** The grouping read, the `ON CONFLICT DO UPDATE` fold and the deletion of the
  folded raw rows now happen per tenant inside that tenant's scope, one transaction per tenant.
  D-051 semantics (raw views older than 90 days, monthly per-product counts, idempotent second
  run) are unchanged.
- **Backups.** The tenant list replaces the unscoped connection scan; the scope is bound before
  the connection lookup, the `ACTIVE`-tenant check, the due-kind check and the backup itself.
  One backup per connected active tenant per 24 h, monthly first, retention and per-tenant
  failure isolation are unchanged.

## 4. Changed files

| File | Change |
|---|---|
| `apps/api/tawzeevo_api/repositories/tenancy.py` | new `all_tenant_ids()` helper (global tenant enumeration, documented as the only unscoped source) |
| `apps/api/tawzeevo_api/services/jobs.py` | reminders run per tenant inside the tenant scope; new `_send_due_reminders()`; module and function docstrings corrected |
| `apps/api/tawzeevo_api/services/storefront_signals.py` | `rollup_views()` folds per tenant inside the tenant scope (new `_rollup_tenant_views()`) |
| `apps/api/tawzeevo_api/services/backup.py` | `run_due_backups()` enumerates tenants and binds the scope before the connection lookup |
| `apps/api/tests/test_jobs_rls_role.py` | **new** — the three jobs under a real `NOSUPERUSER NOBYPASSRLS` login role |
| `apps/api/tawzeevo_api/client_ip.py` | docstring: the over-configuration hazard (FABLE-F-003) |
| `render.yaml` | `TRUSTED_PROXY_HOPS` comment: never higher than the real hop count (FABLE-F-003) |
| `docs/audit/remediation-20260920/REMEDIATION_OWNER_ACTIONS.md` | owner action A3 wording (FABLE-F-003) |
| `docs/runbooks/database-role.md` | what is and is not verified under a restricted role |
| `docs/contracts/jobs-reminders.md` | how jobs bind the tenant scope |
| `docs/phase-9/demo-guide.md`, `docs/phase-9/requirements-audit.md`, `docs/phase-9/test-report.md` | stale head / static-check references (FABLE-F-002) |
| `docs/audit/remediation-20260920/FINAL_CLOSURE_FIX.md` | this record |

## 5. Restricted-role runtime proof

`apps/api/tests/test_jobs_rls_role.py` creates a throw-away login role with
`NOSUPERUSER NOBYPASSRLS` on the disposable database, asserts that the role really is subject to
row-level security (`rolsuper OR rolbypassrls` is `false`), opens a second engine as that role
and runs the jobs through it. Each test first asserts that the restricted session sees **zero**
rows without a bound scope, so the property under test cannot be satisfied by an inert policy.

| Test | Proves |
|---|---|
| `test_delivery_reminders_run_under_an_rls_subject_role` | two tenants, one due reminder each → 2 sent, both SCHEDULED→SENT, exactly one `DELIVERY_REMINDER` notification per tenant pointing at that tenant's order; a replay sends nothing and duplicates nothing |
| `test_view_rollup_runs_under_an_rls_subject_role_without_mixing_tenants` | raw views of two tenants (3 and 1) folded once, 4 in total, into each tenant's own monthly row for its own product; raw rows dropped; the second run folds 0 |
| `test_backup_discovery_runs_under_an_rls_subject_role` | the connected tenant's backup connection is discovered and its encrypted backup is UPLOADED under the restricted role; within one bound scope only that tenant's connection is readable; the unconnected second tenant has no backup; a second run inside 24 h is not due |

All three fail on the pre-fix code (verified by stashing the service changes and re-running) and
pass on the fixed code — `3 passed`.

## 6. Fable's own probe (reproduction check)

Fable's probe was copied unchanged into `apps/api/tests/` for the run
(sha256 `8240d477cbbefe190e2aa9b898e16979e4ab794e50bbb88dad3f53b183b9cafe`, identical to the
review copy) and deleted afterwards; the review directory was not modified.

The two observation lines it prints, before and after the fix, on the same disposable database:

| Observation | Before (matches `logs/jobs_rls_probe_rerun.log`) | After |
|---|---|---|
| `rls_role_visible_reminders` | 0 | 0 (correct: nothing is visible without a bound scope) |
| `rls_role_sent` | 0 | **1** |
| `status_after_rls_run` | `SCHEDULED` | **`SENT`** |
| `notifications_after_rls_run` | 0 | **1** |
| `rls_role_folded_views` | 0 | **1** |
| `rollup_rows_after_rls_run` | 0 | **1** |
| `raw_views_after_rls_run` | 1 | **0** |
| `rls_role_backup_tenants` | `[]` (no connection discovered) | `[]` with a logged `scheduled backup failed … BACKUP_KEY_UNAVAILABLE` — the connection **is** discovered and attempted; the probe's synthetic connection row (`wrapped_refresh_token=b"probe"`, no key material) cannot produce a real backup |

**The reproduction is gone:** both assertions that carried the finding
(`sent_restricted == 1`, `folded_restricted == 1`) now hold.

The probe file as a whole nevertheless still exits non-zero, and it can no longer do otherwise.
Its two contrast assertions, `assert sent_super == 1` and `assert folded_super == 1`, measure a
superuser run that happens **after** the restricted run, and they are written to expect that the
restricted run left the work untouched. Now that the restricted role sends the reminder and
folds the view, the later superuser run correctly finds nothing due (`0`), so those two lines
fail. That failure is a consequence of the fix, not a regression: the probe's contrast
assertions are only satisfiable while the defect exists. `test_jobs_rls_role.py` carries the
same property as a permanent product regression, with the contrast taken in an order that stays
valid.

## 7. Verification

| Check | Command | Result |
|---|---|---|
| Restricted-role jobs regression | `pytest tests/test_jobs_rls_role.py` | **3 passed** |
| Jobs suite | `pytest tests/test_jobs.py` | PASS (inside the run below) |
| Directly affected: backups, storefront signals | `pytest tests/test_jobs.py tests/test_backup.py tests/test_storefront_signals.py tests/test_jobs_rls_role.py` | **13 passed** (55 s) |
| Fable probe reproduction | `pytest tests/fable5_jobs_rls_probe.py -s` | reproduction gone — see § 6 |
| Full backend suite | `python -m pytest tests -q -p no:cacheprovider -W ignore` | **310 passed** (19 min 34 s) — 307 at the start HEAD plus the 3 new regressions |
| ruff | `python -m ruff check .` | **All checks passed** |
| ruff format | `python -m ruff format --check .` | **202 files already formatted** |
| mypy | `python -m mypy tawzeevo_api` | **Success: no issues found in 106 source files** |

No migration was introduced, so no migration cycle was run. No frontend code was changed, so no
frontend check was run. No material regression was encountered: every test that passed at the
start HEAD passes now.

## 8. Documentation corrections

**FABLE-F-002** — `docs/phase-9/demo-guide.md` step 1 and `docs/phase-9/requirements-audit.md`
§ D now cite the head the branch actually ships, `20260921_0031`. `docs/phase-9/test-report.md`
is dated frozen evidence of the 2026-09-20 run, so its `20260920_0029` / 102-source-file numbers
are kept but explicitly labelled **historical**, with the current head and the current
106-source-file mypy evidence named beside them.

**FABLE-F-003** — the owner register A3, the `render.yaml` comment and the `client_ip.py`
docstring now state that the value must never exceed the number of proxies that really append to
`X-Forwarded-For`; that a too-high value selects caller-controlled header content as the
rate-limit key; that a too-low value is the safe failure mode (a shared bucket, never a
caller-chosen one); and that `0` ignores forwarded client-IP headers. The resolution algorithm
itself was reviewed as correct and is unchanged.

**Compatibility wording** — `docs/runbooks/database-role.md` no longer claims compatibility in
general. It now separates what is verified locally under a real `NOSUPERUSER NOBYPASSRLS` role
(the platform application lifecycle **and** the three scheduled jobs) from what is not verified
(the hosted role itself), and states that a restricted role needs `SELECT` on `tenants`.
`docs/contracts/jobs-reminders.md` and the `jobs.py` docstring describe the actual mechanism
instead of the former "RLS scope is set per row".

## 9. Remaining owner actions

Unchanged from `REMEDIATION_OWNER_ACTIONS.md` and `FABLE5_OWNER_ACTIONS_REVIEW.md`, with one
blocker released:

1. Before the next live deploy: **A1** `CUSTOMER_OTP_PROVIDER` (the service will not boot in
   production without it), **A2** environment variables, **A3** `TRUSTED_PROXY_HOPS` with the
   corrected guidance above, **A4** dashboard auto-deploy off for the three live services.
2. **B** hosted database role: the read-only `rolsuper` / `rolbypassrls` check (or the live
   `database_role_rls_enforced` flag after a deploy) can be done now. The follow-up step —
   pointing `DATABASE_URL` at a `NOSUPERUSER NOBYPASSRLS` role and setting
   `DB_ROLE_REQUIRE_RLS_SUBJECT=true` — **was blocked by FABLE-F-001 and is no longer blocked by
   it**, subject to the usual deploy order and to the restricted role holding the grants in the
   runbook. The hosted role itself remains unverified until the owner performs the check.
3. Product decisions still open: D-080 object storage, C-F04 invoice-number year, D-055 OAuth
   scope, D-029 demo gallery, D-088 confirmation.
4. Hosted observation D (F-032): health-probe schedule and cold start.
5. Launch gate remains **NOT PASSED**: items (1) live encrypted backup + restore drill,
   (2) P9-M5/P9-M6 decisions, (3) D-088, (4) SLO measurement, (5) D-080 and (6) hosted database
   role. Item (6) no longer depends on FABLE-F-001.
6. Jira: the closeout manifest is still unapplied; the owner rule requires a findings task with
   the remediation report attached. This record and the Fable 5 review artifacts belong on the
   same task.
