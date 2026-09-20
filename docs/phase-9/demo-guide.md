# Phase 9 demo, release and operations guide

This guide covers what Phase 9 delivered so far: password recovery, the hardening suites,
observability and alerts, CI/CD with a gated live release, staging, customer verification, and
the pilot drill. Customer accounts (P9-M6) are not part of it. Use synthetic data only.

## Prepare the environment

1. Follow the root `README.md` local setup; confirm Alembic head `20260920_0029`.
2. For the live demonstration you need: the operations client URL, the API URL, one owner
   account, one driver account (the pilot accounts in the owner's private file).

## Recommended presentation route

### 1. Recovery and sessions
Sign-in page → *Forgot your password?* → enter an address → the same answer whether or not it
exists → the e-mail link opens *Choose a new password* → after the change every other device is
signed out. Say: tokens are hashed, single use, 30 minutes; failed logins are throttled per
address (10 per 15 minutes).

### 2. Where the guarantees are proven
Open `apps/api/tests/test_security_matrix.py`: 12 resources × 6 actors, one table. Open
`test_lifecycle_drill.py`: export → suspend → reactivate (identical rows) → close (terminal, rows
kept). These run in CI on every push.

### 3. Observability
`GET /health/database` → status and migration head; `GET /health/metrics` → counters (5xx ratio,
login throttling, sync rejections, backup and mail failures, OTP). Every response carries
`X-Request-ID`; the access log has one JSON line per request with the route template — never the
query string or a secret. GitHub → Actions → *Health and alerts*: a probe every 10 minutes; a
failing run is the alert (e-mail to the repository owner); run it with `simulate_failure=yes` to
show the path.

### 4. CI/CD and staging
GitHub → Actions → *CI*: backend on PostgreSQL, both clients, Playwright flows, dependency
audits. *Deploy live after green CI* only runs after a green CI on `main`. Staging
(`tawzeevo-staging-api`, `tawzeevo-staging-web`) deploys on every push against its own database
and is where `slo_probe.py` and `pilot_drill.py` run.

### 5. Customer verification
Owner desk → Customers → a customer → *Storefront link*: policy *Verified phone (one-time code)*
(business default under *Storefront*, or per customer). Open the personalized link in a private
window: the storefront offers verification, prices stay public; *Send me the code* → enter the
6-digit code → the customer's prices appear and orders carry their identity. Desk shows
"1 verified session"; *End verified sessions* drops it at once. Say: codes are hashed, 5 minutes,
5 attempts, 5 sends per hour; a provider outage never locks anyone in; rotating or revoking the
link ends every session; the production channel is an owner decision.

### 6. Pilot drill
`python apps/api/scripts/pilot_drill.py <staging api> <admin> <password>` → 30 checks: two
businesses, owner+driver and sole owner, driver least privilege, analytics reconciliation,
cross-tenant and admin boundaries.

## Release runbook (staging → live)

1. Push to `main`. Staging deploys automatically (Render). CI runs.
2. When CI is green, *Deploy live after green CI* triggers the three live services and waits
   until `/health/database` answers `ok`; the migration runs in the API start command
   (`alembic upgrade head`).
3. If a deploy must be rolled back: Render → service → *Manual Deploy* → pick the previous
   commit. Migrations are expand-only; a rollback of code never needs a downgrade.
4. Secrets live only in Render (per service) and in the GitHub Actions secret `RENDER_API_KEY`.
   Changing an env value in Render triggers a redeploy of that service.
5. Alerts: a failed *Health and alerts* run means DB down, 5xx ≥ 1 %, backup or mail failures,
   sync rejections or a login-throttling wave — read `/health/metrics` and the Render logs
   (search the `request_id` from the client's error).

## Security expectations (say them out loud)

- Every tenant table is under forced RLS; the matrix and the pilot drill prove the boundaries.
- Public failure responses are constant; secrets never appear in URLs, logs or audit rows.
- The platform admin manages lifecycle only and reads no tenant data.
- A verified session is bound to one link and one customer; a phone change never breaks identity.

## Limitations to state plainly

- P9-M6 customer accounts await gate decisions; `ACCOUNT_REQUIRED` cannot be selected.
- OTP delivery is the development adapter until the owner picks a provider.
- Hosted backups: Supabase free plan keeps none; the app's encrypted Google Drive backup must be
  run live by the owner before launch.
- SLOs are met locally; on the free two-region hosting the network floor exceeds the lookup
  target and sync push needs optimisation or an evidence-based adjustment.
