# Remediation of audit run 20260920-1922-7a7596 — owner action register

Everything below needs the owner, a hosted system or a product decision. Nothing here was
executed by the remediation: no production or staging system was connected to or mutated, no
secret was read or written, no external service was called. Each item says why local
verification is insufficient, the exact action, the expected safe result, how to record the
evidence, and which verdict it changes.

## A. Before the next live deploy of the remediation branch

These are consequences of fail-closed rules added on 2026-09-21. The live service keeps running
as it is until a deploy; the deploy must not happen before they are done.

| # | Finding | Why local verification is insufficient | Exact action | Expected safe result | Record evidence | Verdict change afterwards |
|---|---|---|---|---|---|---|
| A1 | F-009 | The production OTP provider is the owner's launch-gate decision (item 2); the API now refuses `CUSTOMER_OTP_PROVIDER=dev` in production. | Decide the provider; set `CUSTOMER_OTP_PROVIDER=<provider>` in the API service environment (dashboard). No adapter exists yet for any production provider, so `VERIFIED` stays unselectable on the live service until one is implemented. | The next deploy boots (startup logs no settings error); `/health` 200. | Note the provider name in `docs/phase-9/requirements-audit.md` § P9-M5. | F-009 → FIXED_VERIFIED once the service boots with the value set. |
| A2 | F-007 | Dashboard values are not visible from the repository. | Confirm `EMAIL_PROVIDER`, `EMAIL_API_KEY`, `REFRESH_COOKIE_SAMESITE=none`, `PASSWORD_RESET_URL` exist in the API service environment (render.yaml now declares them; a blueprint sync prompts for the `sync:false` ones). | Deploy boots; login and reload keep the session; forgot-password sends. | Screenshot-free note in the Phase 9 test report ("values present, date"). | F-007 → FIXED_VERIFIED. |
| A3 | F-005 | The hosting proxy topology is not visible from the repository. | Confirm in the hosting provider's documentation/dashboard that exactly one proxy hop sets `X-Forwarded-For` for the API service. `render.yaml` declares `TRUSTED_PROXY_HOPS=1`; change it if the hop count differs (0 = ignore the header). | Ten failed logins from one address throttle only that address (`/health/metrics` `auth_login_throttled` rises by one). | Note in the Phase 9 test report. | F-005 → FIXED_VERIFIED. |
| A4 | F-010 | The dashboard auto-deploy setting of a manually created service is independent of `render.yaml`. | For the three live services, confirm auto-deploy is **off** (deploys come from the "Deploy live after green CI" workflow). Staging keeps auto-deploy. | A push to `main` does not deploy live by itself; the workflow deploys after green CI and waits for the exact migration head. | Note in the Phase 9 test report. | F-010 → FIXED_VERIFIED. |

## B. Hosted database role (F-002)

| Why local verification is insufficient | The hosted role's `rolsuper`/`rolbypassrls` attributes exist only on the hosted database; the remediation never connects to it. |
|---|---|
| Exact action | On the hosted database, as the role in the API's `DATABASE_URL`: `select rolname, rolsuper, rolbypassrls from pg_roles where rolname = current_user;` — or, after deploying this branch, read `GET /health/database` on the live API and look at `database_role_rls_enforced`. |
| Expected safe result | `false | false` (or `"database_role_rls_enforced": true`). |
| If not | Provision a `LOGIN NOSUPERUSER NOBYPASSRLS` role with the grants in `docs/runbooks/database-role.md`, point `DATABASE_URL` at it, redeploy, confirm the flag, then set `DB_ROLE_REQUIRE_RLS_SUBJECT=true` so a later change cannot regress silently. |
| Record evidence | Role name and the two flags (never the connection string) in `docs/phase-9/requirements-audit.md` § D. |
| Verdict change afterwards | F-002 → FIXED_VERIFIED (row A-002 fully closed); with `true` the API refuses to start with a bypassing role. |

## C. Product decisions still pending (deferred findings)

| Finding | Decision needed | Options (recommendation first) | What changes after the decision |
|---|---|---|---|
| F-004 (D-080 object storage) | Provision the S3-compatible bucket (D-080 named Backblaze B2) and its credentials; schedule the adapter. | 1. Provision the bucket now and have the Design & Planning Agent plan the adapter milestone (recommended: media are lost on every restart today). 2. Explicitly accept non-durable media for the pilot and record it in the launch gate. | The adapter is implemented behind the existing storage Protocol and verified against the bucket; evidence row § I becomes PASS. |
| F-017 (C-F04, invoice numbering year) | Which calendar decides the numbering year: UTC (current) or Asia/Beirut (every other business-day rule)? | 1. Asia/Beirut (recommended: consistent with D-040). 2. Keep UTC and record it as the rule. | One-line change in `invoice_finance.py` plus a boundary test; existing numbers are never renumbered. |
| F-022 (D-055 scope) | The Google OAuth request asks for `userinfo.email` in addition to `drive.file` (used for the "connected as {e-mail}" display). | 1. Amend D-055 to name the identity scope (recommended: it only identifies which account holds the backup folder). 2. Drop the scope and the connected-as display. | Ledger entry, or a small code + UI change. |
| F-024 (VITE_DEMO_PREVIEW) | Should the live operations client show the demo gallery? | 1. Keep (allowed by D-029). 2. Set `VITE_DEMO_PREVIEW="false"` in `render.yaml` and rebuild the client. | Presentation only. |
| D-088 (F-003) | Confirm D-088 (configurable SameSite with the Origin guard). | Confirm, or refuse and choose a custom domain. | Launch-gate item 3; the regression test exists either way. |

## D. Hosted observations (F-032)

| Why local verification is insufficient | GitHub Actions schedule history and the hosting instance state need the owner's accounts. |
|---|---|
| Exact action | GitHub → Actions → *Health and alerts*: does the schedule fire every 10 minutes? If it is disabled (inactive-repository rule) or delayed, re-enable it or move the probe to an external uptime monitor. Then, after ~15 idle minutes, `GET /health/metrics` twice 8 minutes apart and compare `uptime_seconds`. |
| Expected safe result | Uptime keeps increasing across the two probes (the service did not spin down), or the pilot documentation states the expected cold start (already added to the demo guide). |
| Record evidence | Note in the Phase 9 test report. |
| Verdict change afterwards | F-032 → FIXED_VERIFIED or ACCEPTED (documented cold start). |

## E. Launch-gate items unchanged by this remediation

Still owner-only, exactly as the audit listed them: (1) live encrypted backup run + restore
drill; (2) P9-M5 provider / remembered-browser and the P9-M6 gate decisions; (3) D-088
confirmation; (4) SLO adjustment or sync-push optimisation, measured with
`apps/api/scripts/slo_probe.py` against staging (password now from `TAWZEEVO_ADMIN_PASSWORD` or a
prompt, never argv). Added by the remediation: (5) D-080 object storage; (6) hosted database role
(section B).

## F. Repository housekeeping

- Other clones: add the three local loader-file lines to `.git/info/exclude`
  (`docs/runbooks/local-agent-files.md`) before staging anything; the names are no longer in
  `.gitignore` (D-025 neutrality, F-027).
- Jira: the audit's idempotent closeout manifest (`evidence/g13/jira_closeout_manifest.json`,
  1 run issue + 4 HIGH finding issues) is still unapplied; when a channel exists, apply it and add
  a findings task with this report attached, per the owner's rule (neutral wording).
- The audit ref `refs/audit/20260920-1922-7a7596` and the audit directory stay preserved; the
  re-audit evidence of 2026-09-21 is in `../tawzeevo-audit/remediation-20260921/` (outside the
  repository, outside the original audit's evidence).
- Merging: the remediation branch `remediation/audit-20260920` was not merged or pushed; review
  it, then merge to `main` and push when items A1–A4 are done (a push to `main` no longer deploys
  live by itself once the dashboard setting matches `render.yaml`).
