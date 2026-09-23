# Phase 9 test report

Report date: 2026-09-20 (P9-M8 launch-gate audit; Phase 9 not yet complete — see the
requirements audit for the open items)

Local runs used a disposable PostgreSQL 18 cluster on `127.0.0.1:55439`; CI uses a PostgreSQL 16
service container; staging uses its own Supabase database. The production database is never
used for tests.

## Final automated results

| Lane | Where | Result |
|---|---|---|
| Backend unit/integration | local | **253 passed** (9 min 04 s) |
| Backend static | local + CI | ruff / format / mypy clean (102 source files) and `alembic check` clean at `20260920_0029` — **historical, as of this 2026-09-20 report date**; the current branch ships head `20260921_0031` with mypy clean over 106 source files (`docs/audit/remediation-20260920/REMEDIATION_TEST_RESULTS.md`, `FINAL_CLOSURE_FIX.md`) |
| Operations client | local + CI | **82 passed**; lint/types clean; build OK |
| Storefront | local + CI | **9 passed**; lint/types clean; build OK |
| Real-browser E2E (Chromium) | local + CI | **8 passed**: Phase 3, Phase 4 offline, Phase 5 ×2, Phase 6, Phase 7, Phase 8, **Phase 9 verification** |
| Dependency audit | CI | `pip-audit` clean after raising `cryptography` ≥ 50 and `pytest` ≥ 9; `npm audit --omit=dev` 0 vulnerabilities |
| CI pipeline | GitHub Actions run on `83c6adb` | all three jobs green; gated live deploy ran and confirmed the migration head |
| Alert probe | GitHub Actions `Health and alerts` | simulated-failure run fails as designed (the alert path); the normal run's first version wrongly pinned a date prefix — fixed; the re-run is green |

Phase 9 test files: `test_password_recovery.py` (5), `test_security_matrix.py` (2),
`test_lifecycle_drill.py` (2), `test_observability.py` (4), `test_customer_verification.py` (3);
`App.test.tsx` recovery pages; `e2e/phase9-verification-flow.spec.ts`.

## Measured performance (D-078)

| Target | Local (Windows, local PG) | Staging from Beirut (client-side) |
|---|---:|---:|
| phone lookup p95 < 250 ms | 17 ms | 337 ms |
| barcode lookup p95 < 250 ms | 26 ms | 401 ms |
| CRUD p95 < 400 ms | 21 ms create / 17 ms read | 347 ms create / 561 ms read |
| storefront checkout p95 < 750 ms | 43 ms | 429 ms |
| sync push 100 operations < 2.5 s | 629 ms | 4 840 ms |

`/health` with no database work answers in ≈400 ms p50 from the same client, so ≈300 ms of every
staging number is the path Beirut → Cloudflare → Render Frankfurt and back. The sync-push figure
is the one genuine server-side finding (≈48 ms per operation on a 0.1-CPU free instance through
the Supabase pooler). Server-side durations are now written to the access log (`duration_ms`)
and can be read from the Render logs on the next measurement.

## Pilot drill (P9-M7)

`scripts/pilot_drill.py` against staging, 2026-09-20: **30/30 checks** — owner+driver business
with the owner's pilot accounts, sole-owner business, driver least privilege (one stop, no
cost/profit/supplier words, no owner collections in bootstrap, supplier desk 403), driver and
sole-owner completions, analytics reconciliation (50 invoiced / 35 outstanding / 35 payable each),
owner-B / driver / admin / anonymous boundaries, public catalogs without private words.

## Defects found and fixed during Phase 9

- Live sign-out on every reload: `SameSite=Lax` refresh cookie across two `onrender.com` sites →
  configurable SameSite with an Origin guard (D-088 pending confirmation).
- "Failed to fetch" on the first call after idle: free-tier wake-up returns a bare gateway error
  without CORS headers → one client-side retry for session calls and a translated hint.
- The application access log never reached stdout under uvicorn → `configure_logging()`.
- Error bodies must stay constant on public failure surfaces (a Phase 5 freeze test caught the
  request id in the body) → the id travels in the header only.
- CI: the production-settings test read the CI `BACKUP_DRIVE_PROVIDER=memory` from the
  environment → explicit fields in the test.
- Health probe pinned a migration-date prefix → any well-formed head.

## Reproduction

Backend, client and E2E commands are unchanged (`docs/phase-5/test-report.md` § Reproduction).
Phase 9 additions:

```powershell
# SLO probe against a running API (never the production database from a test)
$env:TAWZEEVO_ADMIN_PASSWORD = '<admin password>'   # never on the command line
.\.venv\Scripts\python.exe apps\api\scripts\slo_probe.py http://127.0.0.1:8011 admin-e2e@example.com
# pilot drill (two businesses, both operating models, boundaries)
.\.venv\Scripts\python.exe apps\api\scripts\pilot_drill.py http://127.0.0.1:8011 admin-e2e@example.com
```

CI runs on every push to `main` (`.github/workflows/ci.yml`); the alert probe can be dispatched
by hand with `simulate_failure=yes` to test the notification path.

## Known limitations at the audit

- P9-M6 (customer accounts) is not built — gate decisions pending.
- Only the development OTP adapter exists; production WhatsApp/SMS is an owner decision.
- The live encrypted backup has not run (owner action); Supabase free plan keeps no backups.
- The alert path is a failing GitHub workflow (e-mail to the repository owner), not a paging
  system; there is no external error-tracking service.
- Staging smoke (SLO probe, pilot drill) is run by hand, not by the pipeline.
- One Chromium project.
