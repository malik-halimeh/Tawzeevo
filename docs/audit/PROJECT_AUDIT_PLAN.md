# Tawzeevo — Project Audit Plan (Phases 1–9 as built on 2026-09-20)

This plan tells an auditing agent exactly what to check, how to check it, what counts as
accepted, and how to report. It is self-contained: an agent who has never seen this repository
can start at § 1 and finish with a signed findings register. It audits what exists; it never
adds features, changes behaviour or "fixes on the way" — every finding goes into the register
and is decided by the project owner (D-081: the owner is the final authority; the Design &
Planning Agent reviews; the Implementation Agent fixes only what is approved).

Read before starting: `AGENT_START_HERE.md`, `AGENTS.md` (read order and no-invention rule),
`00_PROJECT_CONTRACT.md`, `04_DECISIONS.md` (every D-xxx cited below), `03_IMPLEMENTATION_STATUS.md`.

## 1. Ground rules for the auditor

1. **Never run anything against the hosted production database.** Use a disposable local
   PostgreSQL (`RUN_TESTS.md`), the CI database, or staging (`tawzeevo-staging-*`).
2. **Evidence over prose.** A check is PASS only when you executed the command or read the
   code/tests yourself in this repository state and recorded the exact command, file and line.
   "The docs say so" is not evidence; the phase evidence documents (`docs/phase-N/*.md`) are
   claims to verify, not proof.
3. **No changes.** Do not edit code, migrations, data, Jira, Render, GitHub settings or
   decisions. If a fix is obvious, write it as a recommendation with the smallest change.
4. **Secrets.** Never print, copy or commit secrets, tokens, passwords, cookies or private
   customer data; `private/` is git-ignored and out of the audit's write scope.
5. **Severity scale.** CRITICAL = money, identity, tenant isolation or data loss can be wrong
   today; HIGH = a locked invariant or launch-gate item is unmet; MEDIUM = contract deviation
   without customer impact; LOW = quality/documentation. Any CRITICAL or HIGH finding makes the
   audit verdict FAIL.
6. **Output.** One file: `docs/audit/findings-<date>.md` using the register format in § 6, plus
   a one-paragraph verdict at the top. Nothing else is produced.

## 2. Environment the auditor needs

| Need | How |
|---|---|
| Repository at the audited commit | `git log -1` — record the SHA in the register header |
| Python 3.13 venv with the API installed | `RUN_TESTS.md` (Windows) / `.github/workflows/ci.yml` (Linux) |
| Disposable PostgreSQL 16/18 | local cluster or the CI service container; `TEST_DATABASE_URL` set |
| Node 22 with workspaces installed | `npm ci` at the repository root |
| Chromium for Playwright | `npx playwright install --with-deps chromium` |
| Read access to CI runs | https://github.com/malik-halimeh/Tawzeevo/actions |
| Read access to staging | `https://tawzeevo-staging-api.onrender.com/health/database` (no credentials needed for health) |

Time budget: about 6 hours of agent time for a full audit; § 4 lists which items can be
skipped for a shorter one.

## 3. Verification procedure (run in this order)

### Step A — Baseline (30 min)
1. `python -m pytest apps/api/tests -q` on a fresh disposable database → record the count.
   Accepted: **every test passes**; count ≥ 253.
2. `python -m ruff check apps/api`, `python -m ruff format --check apps/api`,
   `python -m mypy apps/api/tawzeevo_api` → accepted: clean.
3. `python -m alembic -c apps/api/alembic.ini upgrade head && … check` → accepted: head is
   `20260920_0029` (or later), "No new upgrade operations detected".
4. `npm run check` → accepted: operations client ≥ 82 tests, storefront ≥ 9 tests, builds OK.
5. Start API, client, storefront (commands in `docs/phase-5/test-report.md` § Reproduction) and
   run `npx playwright test` in `apps/operations-web` → accepted: **8 passed**.
6. Open the latest CI run on `main` → accepted: all three jobs green on the audited SHA (or
   explain the difference).

### Step B — Invariants that must never regress (2 h)
For each row, open the named test, confirm it asserts what the column says, run it, and add one
adversarial variation of your own (a value or actor the test does not use). Record both.

| Invariant (source) | Where it is proven | Accepted when |
|---|---|---|
| Tenant isolation by forced RLS on every business table (`docs/contracts/tenant-isolation.md`) | `test_hardening.py::test_all_tenant_owned_tables_have_forced_rls_and_a_policy`, `::test_postgresql_rls_enforces_tenant_visibility_and_write_checks` | every table with `tenant_id` has FORCE RLS + a policy; a non-bypass role cannot read or write another tenant's rows |
| Authorization matrix system role × tenant role × resource (PHASE_09 B, D-022) | `test_security_matrix.py` | all cells match; admin never reads tenant-private data; add one resource not in `MATRIX` and check its behaviour matches its router family |
| Financial rows immutable; corrections are new rows (D-031…D-039, `financial-invariants.md`) | `test_financial_schema.py`, DB triggers `*_immutable` | UPDATE on `invoice_revision_items`/`customer_ledger_entries` fails at the database, not only in code |
| Official numbering per tenant/year, never reused, race-safe (FI-12) | `test_invoice_editor.py::test_invoice_sequence_is_serialized…` | two concurrent confirmations get consecutive numbers |
| Receipts allocate oldest-first, reversal compensates, refund ceiling (FI-19/21, D-039) | `test_invoice_editor.py`, `test_supplier_ledger.py`, `test_fa002…` | concurrent refunds cannot exceed the ceiling |
| Exactly-once sync push; replay returns the stored result; conflicts never double-apply (D-044/D-045, `sync-protocol.md`) | `test_sync_push.py`, `test_sync_hardening.py`, `test_sync_financial_push.py` | ×100 replay leaves one financial effect |
| Driver least privilege on API, bootstrap, pull, push and cache (PHASE_07 D) | `test_delivery_tasks.py`, `e2e/phase7-field-flow.spec.ts` | driver payloads contain no cost/profit/supplier price; bootstrap returns no owner collections |
| Public failure responses are constant; secrets never in URLs/logs/audit (PHASE_05 K, D-076) | `test_phase5_freeze.py`, `test_public_invoices.py`, `test_observability.py` | byte-identical bodies for rotated/revoked/absent secrets; access log has no query string |
| Customer access assurance vs policy (D-072/D-073) | `test_customer_access.py`, `test_customer_verification.py` | LINK never satisfies VERIFIED; a session is bound to one link and one customer; revocation/rotation/suspension end sessions |
| Analytics reconcile with ledgers; profit only from sale-time snapshots (D-064…D-067) | `test_analytics.py`, `test_customer_stats.py`, `e2e/phase8-analytics-branding.spec.ts` | dashboard = ledger balances = invoices; uncovered lines reported, never estimated |
| Branding never changes logic (PHASE_08 F) | `test_branding_public_stats.py` | public price and confirmed invoice unchanged after branding |
| No stock/availability/tracking anywhere (contract exclusion) | `test_procurement.py::test_no_inventory_columns_exist_anywhere`, storefront privacy tests | no column or public field names stock/availability/tracking |
| Tenant lifecycle: suspension preserves data, closure is terminal and retains rows (D-023, PHASE_09 E) | `test_lifecycle_drill.py` | export before/after suspension identical (except revoked devices) |
| Password recovery: hashed one-time token, session invalidation, enumeration-safe (D-077) | `test_password_recovery.py` | old access token dead after reset; unknown address indistinguishable |

### Step C — Decision ledger conformance (1 h)
Walk `04_DECISIONS.md` D-001…D-088. For every LOCKED decision that names behaviour, find the
code that implements it (grep the decision id or its key term) and record file:line. Accepted:
each decision maps to code or to an explicit "not yet implemented" note in
`03_IMPLEMENTATION_STATUS.md`; any decision implemented differently is a HIGH finding; any code
behaviour that no decision or contract authorises is a HIGH finding ("invention").
Special attention: D-081 (agent roles — check `AGENT_START_HERE.md`/`AGENTS.md` still point to
it), D-086/D-087 (Phase 10 must contain no forecasting code), D-088 (PENDING — check whether the
owner confirmed; if not, that is the expected state, not a finding).

### Step D — Phase evidence documents (1 h)
For each `docs/phase-N/requirements-audit.md` (N = 1…9): pick five rows at random, verify the
cited test exists and asserts the claim, and verify the "Known limitations" are still true.
Accepted: no row claims a test that does not exist or does not assert the claim. For Phase 9,
confirm the verdict is still "NOT PASSED" unless the open items have evidence of closure.

### Step E — Deployment and operations (45 min)
1. `https://tawzeevo-staging-api.onrender.com/health/database` → `status ok` and a migration
   head equal to the repository head.
2. GitHub Actions: `CI` green on the audited SHA; `Deploy live after green CI` ran after it;
   `Health and alerts` scheduled runs exist and the last normal run is green; one
   `simulate_failure=yes` run exists and failed (proves the alert path).
3. `apps/api/scripts/slo_probe.py` against **staging** with the staging admin (credentials from
   the owner) → record the numbers next to D-078; accepted: numbers recorded and compared with
   `docs/phase-9/test-report.md`; a miss is a finding only if the report did not already record
   and explain it.
4. `apps/api/scripts/pilot_drill.py` against staging → accepted: 30/30.
5. Secrets scan: `git log -p | grep -iE "xkeysib|rnd_|sk_live|BEGIN PRIVATE"` and a read of
   `.gitignore` → accepted: nothing found; `private/`, `.env*` and the local agent-loader files are ignored.
6. Public-repository naming (D-025): grep the tracked files, case-insensitively, for the names of
   the assistant products and vendors the owner uses (the list is in the owner's private role
   mapping, not here) → accepted: matches only in `.gitignore` file names.

### Step F — Accessibility, bilingual and mobile (30 min)
Run the two Playwright storefront flows (Phase 5 Arabic-on-phone, Phase 8 branding) and the
Phase 9 verification flow; then open the operations client in Arabic and tab through the invoice
editor with the keyboard. Accepted: RTL layout, visible focus, labelled controls, no colour-only
meaning, numbers `dir="ltr"`; findings are LOW unless a flow is unusable.

## 4. Short audit (2 hours)
Steps A, B rows 1–6 and 9, C for D-081/D-086/D-087/D-088 only, E items 1–2 and 5–6.

## 5. Acceptance — what "the project passes the audit" means

PASS requires all of: Step A green; every Step B row PASS with its adversarial variation;
no HIGH/CRITICAL in Step C; Step D without false claims; Step E items 1, 2, 5, 6 PASS. The
launch gate itself (Phase 9 `requirements-audit.md` verdict) is a separate question: the audit
may PASS while the launch gate stays NOT PASSED because of owner items (live backup run,
decisions). State both verdicts separately.

## 6. Findings register format

```
# Tawzeevo audit findings — <date> — commit <sha> — auditor <role/agent>

Verdict (repository audit): PASS | FAIL — one paragraph.
Launch gate (Phase 9): PASSED | NOT PASSED — the open items, verbatim from docs/phase-9/requirements-audit.md.

| ID | Severity | Step/row | Claim checked | Evidence (command / file:line / run URL) | Result | Finding and smallest recommended change | Owner decision needed? |
|----|----------|----------|---------------|-------------------------------------------|--------|------------------------------------------|------------------------|
| F-01 | HIGH | B-3 | … | … | FAIL | … | yes/no |
```

Every row needs evidence; every FAIL needs a recommendation; "owner decision needed" is
"yes" whenever the fix would change a locked decision, a contract, a role, a state machine or a
financial rule. Close with the list of decisions the owner must make, in priority order.

## 7. Out of scope for this audit
Phase 10 (gated, D-086), P9-M6 customer accounts (blocked on decisions), visual design
direction (Design & Planning Agent's authority, `05_DESIGN_REFERENCES.md`), the historical-sales
subsystem (D-087, direction only), any paid provider or infrastructure change.
