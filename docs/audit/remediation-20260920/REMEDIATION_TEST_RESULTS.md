# Remediation test results — 2026-09-21

All commands ran on the owner's workstation against a disposable PostgreSQL 18 cluster
(`127.0.0.1:55440`, data under `.tmp/pg-remediation-20260920`, trust auth on loopback only).
`DATABASE_URL`/`TEST_DATABASE_URL` were exported per process; no hosted database was used.
Backend commands run from `apps/api` with the repository virtual environment; frontend commands
from the repository root.

## 1. Static checks (final state, `41eb890`)

| Check | Command | Result |
|---|---|---|
| Lint | `python -m ruff check .` | All checks passed |
| Format | `python -m ruff format --check .` (after `ruff format`) | clean |
| Types | `python -m mypy tawzeevo_api` | Success: no issues found in 106 source files |
| Frontend | `npm run check` (eslint + tsc + vitest + build, both clients) | exit 0 — operations 25 files / 86 tests, storefront 3 files / 9 tests, both builds OK |

## 2. Migrations

| Step | Result |
|---|---|
| `alembic upgrade head` on an empty database | head `20260921_0031` |
| `alembic check` | "No new upgrade operations detected" |
| `alembic downgrade 20260921_0030` → `upgrade head`; `downgrade 20260920_0029` → `upgrade head` | both directions clean |
| `test_hardening.py::test_migrations_build_a_new_database_from_zero`, `test_lifecycle_drill.py` (upgrade from the Phase 7 head) | PASS |
| Immutable historical files (`test_immutable_migration_files.py`) | PASS (0009/0010 untouched) |

## 3. Finding-specific and subsystem runs (all PASS unless noted)

| Finding | Command (from `apps/api`) | Outcome |
|---|---|---|
| F-001 | `pytest tests/test_sync_driver_projection.py` | 5 passed; the same tests against the pre-fix service: 3 failed (200 with customer rows; SUPPLIER_PAYMENT row exposed) — the leak is reproduced by the tests |
| F-001 subsystem | `pytest tests/test_sync_bootstrap.py tests/test_sync_pull.py tests/test_sync_push.py tests/test_sync_hardening.py tests/test_sync_phase6.py tests/test_sync_financial_push.py tests/test_delivery_tasks.py tests/test_delivery_routes.py tests/test_security_matrix.py` | 34 passed |
| F-028 / F-015 | `pytest tests/test_tenant_applications_rls.py tests/test_platform.py tests/test_hardening.py` | 30 passed (first run of the lifecycle test under a NOBYPASSRLS role failed on the platform audit insert → SELECT policy added in 0030) |
| F-002 | `pytest tests/test_db_role_preflight.py tests/test_observability.py tests/test_health.py` | 10 passed |
| F-003 | `pytest tests/test_auth.py` | 29 passed |
| F-005 | `pytest tests/test_client_ip.py tests/test_password_recovery.py tests/test_phase5_freeze.py` | 20 passed |
| F-009 | `pytest tests/test_customer_verification.py tests/test_customer_access.py "tests/test_auth.py::test_production_settings_require_secure_cookie_and_real_secret"` | 7 passed |
| F-007 / F-010 | `pytest tests/test_migration_readiness.py tests/test_deployment_config.py tests/test_db_role_preflight.py tests/test_observability.py tests/test_health.py` | 13 passed |
| F-008 | `pytest tests/test_route_authorization.py` | 7 passed (185 route operations registered; deny cells probed with 5 actors) |
| F-011 | `npx vitest run src/pwaManifest.test.ts` (operations-web) | 2 passed |
| F-012 | `pytest tests/test_jobs.py tests/test_order_review.py tests/test_backup.py tests/test_storefront_signals.py tests/test_observability.py` | 17 passed |
| F-013 | `pytest tests/test_routing_chain.py tests/test_delivery_routes.py` | 14 passed |
| F-006 / F-016 | `pytest tests/test_observability.py tests/test_password_recovery.py tests/test_deployment_config.py` | 12 passed |
| F-018 / F-025 / F-026 | `pytest tests/test_users.py tests/test_delivery_tasks.py tests/test_sync_pull.py tests/test_memberships.py` | 27 passed |
| F-019 / F-020 | `pytest tests/test_fa009_create_command.py tests/test_fa010_legacy_draft_parity.py tests/test_sync_push.py tests/test_invoice_editor.py tests/test_fa008_obligations.py tests/test_opening_balances.py tests/test_sync_financial_push.py` | 3 + 34 passed (two runs) |
| F-021 | `pytest tests/test_supplier_purchases.py tests/test_supplier_profiles_prices.py tests/test_procurement.py tests/test_migration_readiness.py tests/test_financial_schema.py tests/test_sync_phase6.py tests/test_fa002_supplier_payment_cap.py` | 21 passed (after the finalize path was changed to write the header once) |
| F-030 / F-033 | `pytest tests/test_branding_public_stats.py tests/test_procurement.py tests/test_delivery_routes.py tests/test_sync_phase6.py` | 12 passed |
| F-031 | `npx vitest run src/utils/tenantCalendar.test.ts`; `npx eslint src`; `npx tsc -b` | 2 passed; clean |

## 4. Targeted re-audit with the preserved, unmodified audit modules

Audit database recreated: `python <audit>/reproducibility/recreate_audit_db.py --alembic <repo>`
with `PGPORT=55440 PGUSER=postgres` → `{"database": "tawzeevo_audit_20260920_1922_7a7596", "identity": "tawzeevo_audit_20260920_1922_7a7596|127.0.0.1/32|55440|20260920-1922-7a7596"}`.
Module SHA-256 values equal the audit's `seed_manifest.json` (`remediation-20260921/modules/sha256.txt`).

| Command | Outcome | Evidence |
|---|---|---|
| `pytest tests/audit_adv_sync_driver.py tests/audit_adv_schema.py "tests/audit_adv_recon.py::test_a055_driver_snapshot_payments_page_after_supplier_payment"` | **11 passed** — A-042 (every collection 403), A-055 (`status 403, supplier_payment_rows 0`), A-001 (`RLS_SWEEP` 49 tables, 0 missing), A-002 (`leaks {}, writable {}, refusals {}`), A-019, A-026, A-038, A-039, A-040, A-043 | `remediation-20260921/junit/targeted_a001_a002_a042_a055.xml` |
| `pytest tests/audit_adv_recon.py tests/audit_adv_public.py tests/audit_adv_authz.py tests/audit_adv_finance.py` | **39 passed, 2 failed** (explained below) — includes A-058 (`test_a037_a058…`) PASS, A-052 PASS, A-003 sweep PASS, A-033 and A-027/28/32 finance replays PASS | `remediation-20260921/junit/preserved_modules_regression.xml` |

Explained failures: `audit_adv_recon.py::test_a008_production_settings_refuse_non_google_backup_provider`
constructs production settings without `CUSTOMER_OTP_PROVIDER`, which production now refuses
(F-009 rule; the backup-provider assertions it targets still hold);
`audit_adv_recon.py::test_a032_refund_replay_returns_original_and_conflicting_replay_is_refused`
regenerates `paid_at` in its `_refund` helper on every call, so its "replay" is a different
command under the tightened FI-32 rule (409, still exactly one refund; F-020). The audit modules
were then removed from the tree (they are untracked audit artefacts, copies kept in
`remediation-20260921/modules/`).

## 5. Full backend suite

| Run | Command | Outcome |
|---|---|---|
| First (at `f0f7e54`) | `pytest tests -q -p no:cacheprovider -W ignore` | 305 passed, 2 failed — `test_observability.py::test_uvicorn_access_log_never_records_query_strings` and `test_public_invoices.py::test_public_rate_limit_and_access_log_redaction`: the new query-string filter stripped `?token=%s` from a format string whose argument remained (logging error), and the new test's logger had been disabled by alembic's `fileConfig` in full-run order. Fixed in `41eb890` (filter strips arguments, message only when there are none; test restores its logger like the existing one). |
| Final (at `41eb890`) | same | **307 passed, 0 failed** in 972 s (`remediation-20260921/junit/backend_full_suite_final.xml`) |

## 6. Not executed

- Playwright real-browser lane (CI runs it on every push; the only client behaviour change,
  the procurement default range, is unit-tested and the API contract is unchanged).
- Anything against staging or production (never connected).
