# Phase 9 requirements audit (launch-gate audit, P9-M8)

Audit date: 2026-09-20

Status: **NOT YET COMPLETE — one milestone (P9-M6) is blocked on owner gate decisions; every
other milestone is done and evidenced.** The launch gate is therefore **NOT PASSED**; the exact
open items are listed at the end. Nothing here claims behaviour beyond what runs and is tested.

Backend paths are relative to `apps/api/tawzeevo_api/`, tests to `apps/api/tests/`, workflows to
`.github/workflows/`. Decisions used: D-026/D-088 (sessions, cookie), D-073 (verification),
D-074 (accounts — gate open), D-077 (recovery), D-078 (SLOs), D-079 (jobs), D-080 (object
storage, staging), D-081 (agent governance), D-086/D-087 (Phase 10 gate).

## A — Public repository constraint

| Requirement | Evidence | Result |
|---|---|---|
| No secrets, dumps, private data, OAuth secrets, keys or deployment secrets committed; visibility unchanged; demo data fictional | secrets only in Render env, GitHub Actions secret `RENDER_API_KEY`, and the git-ignored `private/`; `.gitignore` covers `.env*`, keys, `private/`, local agent loader; `test_hardening` and CI `pip-audit`/`npm audit`; demo seed is fictional (`cli/seed_demo.py`) | PASS |

## B — Security hardening

| Requirement | Evidence | Result |
|---|---|---|
| Authorization matrix system role × tenant role × resource | `test_security_matrix.py` (12 resources × 6 actors, all cells; suspension/reactivation); every earlier per-feature denial test | PASS |
| RLS suite | `test_hardening.py::test_postgresql_rls_enforces_tenant_visibility_and_write_checks`, `::test_all_tenant_owned_tables_have_forced_rls_and_a_policy` (catalog-driven: every `tenant_id` table, 47+ tables; `tenant_applications` under forced RLS since `20260921_0030`), `test_tenant_applications_rls.py` (application lifecycle under a `NOBYPASSRLS` role) | PASS |
| Session rotation/revocation, refresh reuse detection | `test_auth.py` (rotation, reuse revokes all sessions, security version) | PASS |
| Rate limiting; login brute-force; public token abuse | `routes/auth.py` limiters (10 failed logins / 15 min per IP, 10 recovery calls / 15 min), `test_password_recovery.py`; public limits D-076 (`test_phase5_freeze.py`); OTP throttles (`test_customer_verification.py`) | PASS |
| Guest checkout abuse controls | idempotency key, rate limit on private surfaces, constant failure responses (`test_checkout.py`, `test_phase5_freeze.py`) | PASS |
| CSP; locked CORS/CSRF/Origin | invoice page CSP (`test_branding_public_stats.py`); CORS with explicit origins; Origin guard on cookie routes, exercised under both `lax` and `none` (`test_auth.py::test_cookie_samesite_is_configurable_and_cross_site_origin_is_guarded`, added 2026-09-21 — the row previously cited this test before it existed) — **D-088 pending owner confirmation** | PASS (decision pending) |
| Upload security | product/logo images re-encoded to WebP (`test_branding_public_stats.py`, Phase 2 tests) | PASS |
| Secret management | Render env; production settings refuse to start without real secrets (`test_auth.py::test_production_settings_require_secure_cookie_and_real_secret`) | PASS |
| Dependency/security scanning | CI `pip-audit` (raised `cryptography` ≥ 50, `pytest` ≥ 9) and `npm audit --omit=dev` — green on `83c6adb` | PASS |
| Object-authorization tests; suspension/closure; last-owner; driver least privilege | matrix + `test_lifecycle_drill.py` + `test_memberships.py` + `test_delivery_tasks.py`; pilot drill on staging (30/30) | PASS |
| Platform admin is lifecycle manager, not tenant-private viewer | matrix (`admin` column 403 on every tenant resource); pilot drill "admin reads no tenant …" | PASS |

## C — Password recovery (D-077)

| Requirement | Evidence | Result |
|---|---|---|
| Forgot password, one-time hashed token, short expiry, single use, rate limit, enumeration-safe, session invalidation, audit | `services/password_reset.py`, `services/mailer.py` (Brevo/Resend/memory), `routes/auth.py`; `test_password_recovery.py` (5); client `/forgot-password`, `/reset-password` (`App.test.tsx`); live: production settings accept the Brevo variables; the owner's live send test is pending (`private/OWNER_ACTIONS.md` § L2) | PASS (live mail delivery unverified) |

## D — Database hardening

| Requirement | Evidence | Result |
|---|---|---|
| Constraints/FKs/indexes/RLS/migration history; pooling; contention | `database.py` bounded pool; `alembic check` clean at `20260921_0030`; migration from zero and upgrade from the Phase 7 head (`test_lifecycle_drill.py`) | PASS |
| Application database role subject to RLS (no `SUPERUSER`/`BYPASSRLS`) | Startup preflight logs the role attributes and refuses to start when `DB_ROLE_REQUIRE_RLS_SUBJECT=true`; `/health/database` reports `database_role_rls_enforced`; `test_db_role_preflight.py`; runbook `docs/runbooks/database-role.md`. The **hosted** role's attributes are an owner check on the hosted database and were not verified here | OPEN (owner action) |
| Invoice sequence race, refund concurrency, checkout/payment idempotency | `test_invoice_editor.py` (sequence, refund ceiling), `test_fa009_create_command.py`, `test_supplier_ledger.py`, `test_checkout.py`, `test_sync_push.py` | PASS |
| Backup/PITR according to hosting; restore drill | app-level encrypted backup + restore verified against the in-memory double (`test_backup.py`); Supabase plan is **free — no hosted backups** (owner, 2026-09-20) → the Google Drive backup is mandatory before launch and its live run is pending (§ L4) | OPEN (owner action) |

## E — Data lifecycle

| Requirement | Evidence | Result |
|---|---|---|
| Export; suspend/reactivate preserving data; deliberate CLOSED; membership, link, device revocation; retention | `test_lifecycle_drill.py` (export equality across suspension, close is terminal and retains rows), `test_memberships.py`, `test_customer_access.py`, `test_sync_hardening.py`; admin "Close this business" | PASS |

## F — Performance SLOs (D-078)

| Requirement | Evidence | Result |
|---|---|---|
| Targets measured | `scripts/slo_probe.py`: local run PASS on every target (lookup p95 17 ms, checkout 43 ms, sync 100 ops 629 ms); staging run from Beirut: lookups 337–561 ms p95, checkout 429 ms, sync 100 ops 4.8 s — the ≈300 ms network floor to Frankfurt dominates the lookups; sync push at ≈48 ms/op on the 0.1-CPU free instance is the one server-side miss | PARTIAL — evidence recorded, adjustment not yet approved (§ F "measure, document, change through evidence") |

## G — Observability

| Requirement | Evidence | Result |
|---|---|---|
| Structured logs, request ids, metrics, app/DB health, sync/backup/auth metrics, alert levels; no secrets in logs | `observability.py` (JSON access log, `X-Request-ID`, `configure_logging`), `metrics.py` + `/health/metrics`, `/health/database` with migration head, capability redaction filter; `health-alerts.yml` probes every 10 minutes and fails on DB down, 5xx ≥ 1 %, backup/mail failures, sync rejections, login throttling — a failed run e-mails the repository owner; `test_observability.py` (4) | PASS (no separate error-tracking SaaS; job health = backup counters) |

## H — CI/CD

| Requirement | Evidence | Result |
|---|---|---|
| Pipeline steps 1–12 | `ci.yml`: ruff/format, mypy, `tsc`, backend unit + PostgreSQL integration (financial and sync properties are in the same suite), frontend unit, migration from zero + `alembic check`, Playwright critical flows (8), `pip-audit`, `npm audit`; green on `83c6adb` | PASS |
| 13–15 staging deploy, staging smoke, controlled production release | staging auto-deploys on push (own database); live deploys only after green CI (`deploy.yml`, waits for the migration head); staging smoke = `slo_probe.py` + `pilot_drill.py` run by hand (not yet in the workflow) | PASS (staging smoke manual) |

## I — Deployment architecture (D-027/D-028/D-080)

| Requirement | Evidence | Result |
|---|---|---|
| API, operations web, storefront as separate deployables; managed PostgreSQL; object storage; HTTPS; staging; never test against production | Render web service + two static/web sites; Supabase; S3-compatible media storage (`MEDIA_STORAGE_PROVIDER=s3` live); `tawzeevo-staging-api`/`-web` with `STAGING_DATABASE_URL`; tests run only on disposable or CI databases | PASS (no separate worker process — D-079 in-process scheduler for the pilot) |

## J — Multi-tenant pilot (P9-M7)

| Requirement | Evidence | Result |
|---|---|---|
| Two synthetic tenants for isolation; one-owner/zero-driver and owner+driver; barcode, phone search, invoice, payment, procurement, purchase, delivery, analytics | `scripts/pilot_drill.py` on staging: 30/30 (owner+driver "Pilot Van A" with the owner's pilot Gmail accounts, sole-owner "Pilot Van B"); Playwright flows cover post-confirm edit, offline/reconnect, storefront order, owner review, cancellation, delivery date, routes | PASS |
| Real pilot where available; backup/restore | live business "Bekaa Fresh Water" with the owner's two accounts created; real usage and the live backup run are the owner's next steps | OPEN (owner usage) |

## P9-M6 — Customer accounts and history claiming (D-074)

Precondition "Gate G decision on account identity (email/phone), recovery and session lifetime"
is **not yet decided**. Nothing was built; the assurance model already reserves `ACCOUNT` and the
`ACCOUNT_REQUIRED` policy stays unselectable (`test_customer_verification.py`). **BLOCKED.**

## Definition of Done (PHASE_09.md N) — line by line

| Item | Status |
|---|---|
| Phase 1 coursework and Phases 1–8 regressions pass | PASS — 253 backend, 82 + 9 client, 8 Playwright, CI green |
| Auth/session hardened; password recovery | PASS (D-088 confirmation, live mail test pending) |
| Tenant lifecycle secure; RLS/two-tenant suite; owner/driver matrix | PASS |
| Public abuse tests; financial/refund concurrency; offline/revocation | PASS |
| Backup/restore | PASS against the double; live run pending (owner § L4; Supabase free plan has no hosted backups) |
| Reliable jobs | PASS for the pilot scope (in-process scheduler, D-079; failure counters alerted) |
| EN/AR/accessibility | PASS (every new screen EN/AR; E2E in both directions) |
| Performance SLOs or evidence-based adjustment | PARTIAL — measured; adjustment for the two-region, free-tier setup not yet approved |
| Observability/alerts | PASS |
| CI/CD E2E | PASS |
| Staging/release runbook | PASS — `docs/phase-9/demo-guide.md` § Release |
| One-person + separate-driver pilot | PASS on staging; real pilot started |
| Data lifecycle drill | PASS |
| No stock/availability/tracking regression | PASS (`test_procurement.py` schema guard, Phase 5/7 privacy tests) |
| No critical/high launch blocker | one HIGH open: no hosted database backup until the live Google Drive backup runs (owner § L3/L4); P9-M6 gate decisions; OTP production provider decision |

**Launch gate verdict: NOT PASSED** until (1) the live encrypted backup has run and a restore
drill succeeded, (2) the owner decides the P9-M5 provider / remembered-browser items and the
P9-M6 gate items (or explicitly defers P9-M6 past launch), (3) D-088 is confirmed, (4) the SLO
adjustment for the hosted setup is approved or the sync push is optimised. Explicit exclusions
unchanged.
