# Remediation report — audit run 20260920-1922-7a7596

- **Audit:** run `20260920-1922-7a7596`, frozen ref `refs/audit/20260920-1922-7a7596` =
  `f00c39e9816f359879ccebfc8e0a72d5ddb9ec37`, audited owner HEAD `4d6ea0a9` on `main`. The audit
  evidence was neither modified nor rewritten; it stays preserved together with the ref.
- **Remediation:** branch `remediation/audit-20260920`, base `4d6ea0a9529999fb74aaa3d69bdbaa94b157de84`
  (the owner tree was clean at the audited HEAD apart from the untracked `docs/mentor-defense/`
  folder, which was left untouched), 21 commits, executed 2026-09-21. Not merged, not pushed.
- **Environment:** one disposable PostgreSQL 18 cluster on `127.0.0.1:55440` (`.tmp/`), two
  databases (`tawzeevo_remediation` for the project suite; `tawzeevo_audit_20260920_1922_7a7596`
  recreated with the audit's own `recreate_audit_db.py --alembic` from the remediated migrations
  for the re-audit). No hosted database, staging or production system was connected to or
  changed; every integration credential in tests is a sentinel; no e-mail/SMS/OAuth/Drive/routing
  call left the process.
- **Companion files:** `REMEDIATION_FINDINGS.json` (machine-readable ledger, one entry per
  finding), `REMEDIATION_OWNER_ACTIONS.md` (owner register), `REMEDIATION_TEST_RESULTS.md`
  (executed commands and outcomes). Re-audit artefacts (module hashes, junit files, logs):
  `../tawzeevo-audit/remediation-20260921/` outside the repository.

## 1. Summary

| | Count |
|---|---|
| Original findings | 33 (CRITICAL 0, HIGH 4, MEDIUM 9, LOW 20); 32 open, 1 refuted by the audit |
| Fixed locally and verified by runtime tests | **22** (`FIXED_VERIFIED`) |
| Fixed locally, hosted/dashboard confirmation still needed | **5** (`FIXED_OWNER_VERIFICATION_REQUIRED`: F-002, F-005, F-007, F-009, F-010) |
| Deferred pending an authoritative decision | **4** (`DEFERRED_PENDING_DECISION`: F-004 D-080 bucket/adapter, F-017 C-F04, F-022 D-055, F-024 D-029) |
| Owner/external only | **1** (F-032 hosted schedule/cold start) |
| Refuted (unchanged) | **1** (F-014) |
| Documentation-only corrections | F-003 (test added + doc), F-004, F-023, F-027, F-029 |
| New migrations | `20260921_0030` (tenant_applications RLS + platform audit SELECT policy), `20260921_0031` (supplier purchase immutability); `alembic check` clean, up/down/up verified from zero |
| Tests | backend 253 → 307 nodes (all passing, see § 6); operations client 82 → 86; storefront 9; lint/format/mypy/tsc/eslint/builds green |
| Targeted re-audit rows | A-001, A-002, A-042, A-055: preserved modules **PASS**; A-058 log regression **PASS**; 39/41 of all preserved adversarial tests pass, the 2 failures are explained consequences of intentional tightening (§ 5) |
| Defects found during remediation (not in the audit) | 1: platform audit inserts (`tenant_id IS NULL`) could never succeed under a non-bypass role (RETURNING needs a SELECT policy) — fixed in `20260921_0030` |

The launch gate remains **NOT PASSED**: the owner items of the audit are unchanged (backup
drill, P9-M5/M6 decisions, D-088, SLO) and two were added (D-080 object storage, hosted database
role). The two runtime-confirmed defects the audit added to the gate (F-001, F-028) are fixed and
re-proven with the audit's own modules.

## 2. Before / after by finding

| ID | Sev | Title (short) | Before | After | Status |
|---|---|---|---|---|---|
| F-001 | HIGH | Driver downloads owner-only sync snapshot collections | A-042/A-055 FAIL (runtime) | role allowlist gates `snapshot_page`; preserved A-042/A-055 modules PASS | FIXED_VERIFIED |
| F-002 | HIGH | Hosted DB role may bypass RLS | static, never queried | preflight + health flag + opt-in refusal + runbook; app proven under a NOBYPASSRLS role | FIXED_OWNER_VERIFICATION_REQUIRED |
| F-003 | HIGH | Evidence cites a nonexistent Origin-guard test | no test | `test_cookie_samesite_is_configurable_and_cross_site_origin_is_guarded` (lax + none) | FIXED_VERIFIED |
| F-004 | HIGH | S3 media storage claimed live; D-080 unimplemented | false PASS | evidence states local storage, media not durable, gate item added | DEFERRED_PENDING_DECISION |
| F-005 | MED | Rate limits keyed on the socket peer behind the proxy | shared bucket / spoofable | trusted-hop rule, `TRUSTED_PROXY_HOPS=1` declared | FIXED_OWNER_VERIFICATION_REQUIRED |
| F-006 | LOW | uvicorn access log records query strings (A-058 FAIL) | 253/443 lines | query strings stripped by filter; `--no-access-log` on the host | FIXED_VERIFIED |
| F-007 | MED | render.yaml omits production-mandatory settings | undeclared | declared (`sync:false` secrets), guarded by a test | FIXED_OWNER_VERIFICATION_REQUIRED |
| F-008 | MED | Authorization matrix covers 12/182 routes | 12 resources | 185 operations registered + deny cells probed; new/widened route fails CI | FIXED_VERIFIED |
| F-009 | MED | Dev OTP provider not refused in production | silent | refused in production; VERIFIED unselectable without a usable provider | FIXED_OWNER_VERIFICATION_REQUIRED |
| F-010 | MED | Deploy gate ignores the migration head; auto-deploy on commit | status-only wait | `/health` 503 on head mismatch; workflow waits for the exact head; auto-deploy off | FIXED_OWNER_VERIFICATION_REQUIRED |
| F-011 | MED | PWA manifest has no icons | not installable | 192/512 any + maskable icons, test | FIXED_VERIFIED |
| F-012 | MED | Rollup never scheduled; reminders never executed | backup timer only | in-process scheduler: backups, rollup, reminders (idempotent, isolated) | FIXED_VERIFIED |
| F-013 | MED | D-060 Google fallback missing | key unused | ORS → Google → offline chain, deterministic fallback | FIXED_VERIFIED |
| F-014 | LOW | Order/invoice uniqueness (refuted by the audit) | closed | re-run PASS | REFUTED |
| F-015 | LOW | RLS sweep covers 22/47 tables | fixed list | catalog-driven (49 tables) | FIXED_VERIFIED |
| F-016 | LOW | Forgot-password 503 vs 202 under mail outage | oracle | uniform 202, failure counted | FIXED_VERIFIED |
| F-017 | LOW | Sequence year UTC vs Beirut (C-F04 open) | open | unchanged — owner decision | DEFERRED_PENDING_DECISION |
| F-018 | LOW | User deletion leaves sync devices active | devices active | revoked (`USER_DELETED`) | FIXED_VERIFIED |
| F-019 | LOW | Draft-create fingerprint ignores money | silent replay | every monetary intent compared → 409 | FIXED_VERIFIED |
| F-020 | LOW | Payment replay ignores method/paid_at/allocations | silent replay | compared → 409 | FIXED_VERIFIED |
| F-021 | LOW | Supplier purchases immutable in code only; reversed purchase wins preload | code only | DB triggers; reversed purchases excluded from preload | FIXED_VERIFIED |
| F-022 | LOW | OAuth `userinfo.email` beyond D-055 | as is | unchanged — owner decision | DEFERRED_PENDING_DECISION |
| F-023 | LOW | Stale evidence statements | stale | corrected (Phase 3/4/8, index, status, RUN_TESTS) | FIXED_VERIFIED |
| F-024 | LOW | Demo gallery on the live client | as is | unchanged — owner decision | DEFERRED_PENDING_DECISION |
| F-025 | LOW | Scripts take the admin password on argv | argv | env/prompt; argv refused | FIXED_VERIFIED |
| F-026 | LOW | Task transitions without a row lock | optimistic only | `FOR UPDATE` on every transition; race test | FIXED_VERIFIED |
| F-027 | LOW | Assistant names in `.gitignore`; AGENTS.md private paths | present | per-clone exclude; AGENTS.md self-contained | FIXED_VERIFIED |
| F-028 | MED | `tenant_applications` without RLS (A-001/A-002 FAIL) | cross-tenant read/write | FORCE RLS + ownership-true policies; preserved A-001/A-002 PASS | FIXED_VERIFIED |
| F-029 | LOW | E08/RUN_TESTS cite a nonexistent test | wrong name | existing test cited | FIXED_VERIFIED |
| F-030 | LOW | Six tests use the UTC 'today' | fails 00–03 local | tenant-calendar day | FIXED_VERIFIED |
| F-031 | LOW | Client default demand range on the UTC date | wrong 00–03 local | Asia/Beirut day (Intl) | FIXED_VERIFIED |
| F-032 | LOW | Live services cold; schedule may not fire | observed | documented; owner check | OWNER_EXTERNAL_ONLY |
| F-033 | LOW | Tautological branding assertion | `x == x` | before/after money capture | FIXED_VERIFIED |

## 3. Security findings — attack path and what now prevents it

- **F-001.** A driver's bearer token plus a registered device could `GET
  /api/v1/sync/bootstrap/{collection}` for every owner collection (customers with phones and
  grades, invoices with prices, revisions/items, ledger entries = debt, payments including
  SUPPLIER_PAYMENT rows with amount and supplier id): `snapshot_page` verified the device and the
  tenant but never the membership role. Now `permitted_collections(membership)` is the single
  source for both the bootstrap answer and the snapshot gate; the gate runs before any device or
  data access and answers `403 TENANT_OWNER_REQUIRED`; a registry/route-type pairing test makes a
  future collection fail CI if it is reachable but unregistered.
- **F-028.** Any SQL under the application role while scoped to tenant B could read, update and
  delete tenant A's `tenant_applications` row (business name, applicant, review notes, tenant
  link): the table had no RLS. Now FORCE RLS with policies that follow the real ownership:
  platform-admin scope (bound by `require_system_admin` for the request transaction) reviews all;
  an applicant inserts a PENDING application for themselves and reads their own rows; a tenant
  scope reads the application that created it; nothing else. The sweep test is catalog-driven so
  no tenant table can be forgotten again.
- **F-002.** Not provable locally. Code now reports the role attributes at startup and on
  `/health/database`, refuses to start with a bypassing role when the owner opts in, and the
  platform lifecycle is proven to work under an RLS-subject role (so provisioning one is safe).
- **F-003.** The CSRF guard for the two-site deployment had no regression; a forged `Origin` on
  `/refresh` and `/logout` is now proven refused under both SameSite values, cookie cleared, token
  not consumed.
- **F-005.** Behind the hosting proxy every visitor shared one throttle bucket (ten failed logins
  anywhere blocked login platform-wide), and any naive trust of `X-Forwarded-For` would let a
  caller pick its key. The trusted-hop rule keys on the n-th address from the right, which a
  trusted proxy appends and a caller cannot move.
- **F-006 / A-058.** Query strings (tenant/device ids, cursors, filters, any secret a client
  puts in a URL) no longer reach the access log: a filter strips them from uvicorn records and the
  host runs `--no-access-log` (the structured line with route template and request id remains).
- **F-008.** A future route could widen access unnoticed; now every route operation must carry
  an explicit authorization expectation matching its resolved dependency, and deny cells are
  probed for all of them.
- **F-009.** Production could start with the development OTP adapter and let owners lock
  customers out; production refuses it and VERIFIED is unselectable without a usable provider.
- **F-016.** Under a mail outage the forgot endpoint revealed which addresses exist; both cases
  answer the identical 202 and the outage is counted for the alert probe.
- **F-018 / F-026 / F-025.** Devices are revoked on user deletion; task transitions lock the
  row so concurrent completions cannot both win; the probe/drill scripts refuse a password on
  the command line.

## 4. Financial changes — which invariant protects correctness

- **F-019 / F-020 (idempotent replays).** D-045 (one draft header per command) and FI-32 (a
  replay returns the original result without a second financial effect) are unchanged; only the
  definition of "the same request" was widened to every monetary intent the request carries
  (discounts, markups, manual prices, cost overrides, method, reference, payment time, selected
  allocation targets). A differing retry now answers 409 instead of silently returning the earlier
  draft/payment. No stored financial row is created, changed or deleted by these checks; the
  identical payload still replays. The operations client re-sends the stored command payload on
  retry, so real retries keep every field.
- **F-021 (supplier purchases).** Append-only history is now enforced at the database with the
  same trigger family as revisions, ledgers, payments and allocations: purchase lines reject any
  update/delete; a header accepts exactly one reversal transition (the three reversal columns
  written once from NULL with every other column unchanged) and is frozen afterwards. The header
  is written once with its final total. The D-059 preload order (latest actual purchase → latest
  quote → manual) is unchanged; entries of a reversed purchase are excluded because a reversed
  purchase never happened commercially — the entry stays as history with its provenance.
- **F-012 (jobs).** No financial rows are touched: a reminder becomes one owner notification; the
  view rollup folds pseudonymous view counts (D-051).
- **No tenant-isolation rule, financial invariant or driver projection was weakened**; every
  change is a tightening. No inventory/stock concept was introduced. No AI functionality was
  added.

## 5. Targeted re-audit (audit modules unmodified)

Audit database recreated from the remediated migrations
(`recreate_audit_db.py --alembic`, identity `tawzeevo_audit_20260920_1922_7a7596|127.0.0.1/32|55440|20260920-1922-7a7596`);
module hashes equal the audit's `seed_manifest.json`.

| Row | Module / test | Audit verdict | Re-run |
|---|---|---|---|
| A-042 | `audit_adv_sync_driver.py::test_a042_driver_cannot_download_owner_snapshot_collections` | FAIL | **PASS** (every collection 403) |
| A-055 | `audit_adv_recon.py::test_a055_driver_snapshot_payments_page_after_supplier_payment` | FAIL | **PASS** (`status 403, supplier_payment_rows 0`) |
| A-001 | `audit_adv_schema.py::test_a001_rls_sweep_over_every_table_with_a_tenant_id` | FAIL | **PASS** (49 tables, 0 exceptions) |
| A-002 | `audit_adv_schema.py::test_a002_cross_tenant_select_update_delete_are_empty_under_rls` | FAIL | **PASS** (`leaks {}, writable {}`) |
| A-058 | `audit_adv_public.py::test_a037_a058_public_failures_are_byte_identical_and_secrets_stay_out_of_logs` | FAIL (challenge) | **PASS** (plus the new query-string regression) |
| A-052 | `audit_adv_recon.py::test_a052_branding_change_leaves_confirmed_invoice_and_public_price_untouched` | PASS | PASS |
| all others | sync_driver 5/5, schema 5/5, public 10/10, authz 13/13, finance 11/11, recon 5/7 | | 39/41 |

Explained failures (both caused by intentional tightening, not regressions):
`audit_adv_recon.py::test_a008` builds production `Settings` without `CUSTOMER_OTP_PROVIDER`,
which production now refuses (F-009); `audit_adv_recon.py::test_a032`'s `_refund` helper
regenerates `paid_at` on every call, so its "replay" is a different command under the tightened
FI-32 rule and answers 409 while still producing exactly one refund (F-020).

## 6. Verification executed

See `REMEDIATION_TEST_RESULTS.md` for the command log. In short: per-finding tests → subsystem
suites → preserved adversarial modules on the recreated audit database → full backend suite
(twice; the first run exposed an ordering interaction of the new access-log filter, fixed in
`41eb890`) → frontend `npm run check` (lint, types, 86 + 9 unit tests, both builds) → ruff,
ruff format, mypy (106 files) clean → `alembic upgrade head`, `alembic check`, downgrade/upgrade
of both new migrations, migration from zero (`test_hardening`) and the Phase 7 upgrade rehearsal
(`test_lifecycle_drill`).

## 7. Known residual risks

- Hosted facts remain unverified until the owner acts (section A/B of the owner register):
  database role attributes, dashboard values, proxy hop count, auto-deploy setting, Actions
  schedule.
- Media on the API instance filesystem are lost on restart until D-080 is implemented against
  the owner's bucket.
- The next live deploy needs `CUSTOMER_OTP_PROVIDER` set (fail-closed); until an adapter for the
  chosen provider exists, VERIFIED is unselectable in production.
- Forgot-password timing differs for known vs unknown addresses (no padding); accepted as low.
- The Playwright real-browser lane was not re-run locally (CI runs it); the client change is
  unit-tested.
- The re-audit was executed by the same tooling that performed the remediation; it is not an
  independent review.
