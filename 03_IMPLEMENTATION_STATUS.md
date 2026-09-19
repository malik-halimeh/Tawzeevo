# 03_IMPLEMENTATION_STATUS.md — Persistent Implementation State

> The implementation agent updates this file at the end of every milestone. Keep it concise. Do not turn it into a diary.

## Current execution

- Current workstream: `Phase 9 — Production hardening, CI/CD, staging, multi-tenant pilot`
- Current phase: `9`
- Current phase status: `IN_PROGRESS`
- Current milestone: `P9-M3 — Performance + observability`
- Current milestone status: `NOT_STARTED`
- Last completed milestone: `P9-M2`
- Next required user command: `continue` (the owner authorized Phases 6–9 on 2026-09-19; Phase 10 stays locked)
- Blocking decision: `none; a live Google backup run needs the owner's OAuth client (OWNER_ACTIONS.md § I), all backup behaviour is verified against the in-memory Drive double`

The owner authorized `Start Phase 4` and `Start Phase 5` on 2026-09-18 and, on 2026-09-19, every
phase up to and including Phase 9 (Phase 10 is not authorized). Phases 1–8 are complete and their
requirements audits, test reports and demo guides are frozen under `docs/phase-1` … `docs/phase-8`.
Phase 9 starts with P9-M1 (D-077 password recovery approved; D-078 targets; D-079 in-process jobs).

## Demo workstream status

| Milestone | Status | Scope |
|---|---|---|
| DRG-M1 | COMPLETE | Isolated pre-auth gallery shell and live registration regression proof |
| DRG-M2 | COMPLETE | Guest and customer perspectives |
| DRG-M3 | COMPLETE | Owner perspective |
| DRG-M4 | COMPLETE | Driver perspective and least privilege |
| DRG-M5 | COMPLETE | Cross-role hardening, deployment, and teardown proof |

## Phase status

| Phase | Status | Gate |
|---|---|---|
| 1 | COMPLETE | DoD PASSED |
| 2 | COMPLETE | Definition of Done PASSED; P2-M1 through P2-M5 complete |
| 3 | COMPLETE | Definition of Done PASSED 2026-09-17; P3-M1 through P3-M6 complete; evidence in `docs/phase-3/` |
| 4 | COMPLETE | Frozen 2026-09-18 (P4-M6): `docs/phase-4/requirements-audit.md`, `test-report.md`, `demo-guide.md`; live Google run deferred to the owner's OAuth client |
| 5 | COMPLETE | Frozen 2026-09-19 (P5-M6): `docs/phase-5/requirements-audit.md`, `test-report.md`, `demo-guide.md`; D-071/D-072/D-075/D-076 implemented (LINK assurance only) |
| 6 | COMPLETE | Frozen 2026-09-19 (P6-M5): `docs/phase-6/requirements-audit.md`, `test-report.md`, `demo-guide.md` |
| 7 | COMPLETE | Frozen 2026-09-19 (P7-M4): `docs/phase-7/requirements-audit.md`, `test-report.md`, `demo-guide.md` |
| 8 | COMPLETE | Gate G decisions D-064–D-070; P8-M1–P8-M4 complete 2026-09-19; `docs/phase-8/{requirements-audit,test-report,demo-guide}.md`; four storefront presentation items (favicon, featured presentation, promotional banners, homepage layout) left for the owner's decision |
| 9 | IN_PROGRESS | owner authorization of 2026-09-19; P9-M1, P9-M2 complete 2026-09-19 |
| 9-old | LOCKED | Phases 1–8 DoD |
| 10 | LOCKED | historical-data gate |

## Current milestone evidence

- Code areas changed (P9-M2, 2026-09-19): `database.py` + `config.py` (bounded pool: `DB_POOL_SIZE` 5, `DB_MAX_OVERFLOW` 5, recycle 1800 s, timeout 10 s, pre-ping); `services/platform.py::close_tenant` + `POST /api/v1/platform/tenants/{id}/close` (admin-only, terminal, retyped business name, reason audited, devices revoked, every row retained); admin Tenants screen "Close this business for good" (EN/AR); `tests/test_lifecycle_drill.py` (export → suspend: owner/driver/device/private link locked and storefront stops orders → reactivate: export identical except revoked device rows → close: confirmation mismatch 400, owner 403, terminal 409s, `TENANT_CLOSED`, storefront 404, counts unchanged; production-like upgrade from the Phase 7 head `20260919_0026` to head is expand-only)
- Migrations: none new
- Tests run (2026-09-19): full backend suite; concurrency invariants already in place and green (`test_invoice_editor` sequence race and refund ceiling, `test_fa009_create_command` same command twice, `test_supplier_ledger` payment cap, `test_public_invoices` capability issue, `test_sync_push` replay); migration from zero (`test_hardening`) and Phase-7-head upgrade rehearsal; restore drill (`test_backup` import into an empty tenant, tampered file and wrong key refused); RLS suite; ruff/format/mypy clean; operations client `82 passed`, lint/types clean
- Security/invariants: suspension and closure never delete; closure is deliberate (retyped name) and terminal; public storefront and private links stop at once; pool is bounded so one instance cannot exhaust the hosted connection cap
- Known defects: none open for P9-M2
- Contract deviations: hosted backup/PITR is a Supabase plan setting the owner must confirm (`private/OWNER_ACTIONS.md` § K3); the application-level encrypted Google Drive backup and restore drill are verified against the in-memory double until the owner's OAuth client exists (§ I)

## Latest completed milestone summary

P9-M2 (2026-09-19) delivered the bounded connection pool, the deliberate tenant closure path,
the lifecycle drill (suspend/reactivate preserves every row; close is terminal and retains data)
and the production-like migration rehearsal from the Phase 7 head.

### Previous (P9-M1)

P9-M1 (2026-09-19) delivered password recovery per D-077 (hashed one-time tokens, session
invalidation, Brevo/Resend adapter, EN/AR pages), login and recovery throttles, and the
authorization matrix suite.

### Earlier (P8-M4)

P8-M4 (2026-09-19) froze Phase 8: the reconciliation E2E (dashboard = ledgers = invoices,
lifetime drilldown, branding on storefront and invoice page), a broken customer picker fixed,
readable theme tokens, measured latency, and the Phase 8 evidence documents. Phase 8 COMPLETE.

### Earlier (P8-M3)

P8-M3 (2026-09-19) delivered tenant branding (owner desk, storefront theme/texts/pages, branded
customer invoice page with a safe QR) and the D-070 public platform aggregates; presentation only.

### Earlier (P8-M2)

P8-M2 (2026-09-19) delivered customer lifetime statistics per D-069 with a drilldown in the
owner analytics screen; duplicates are never merged and missing data is reported, not invented.

### Earlier (P8-M1)

P8-M1 (2026-09-19) delivered the trusted metric service: current-state and event-flow views by
currency on the tenant calendar, gross profit from sale-time snapshots with coverage, and the
owner analytics baseline screen.

### Earlier (P7-M4)

P7-M4 (2026-09-19) froze Phase 7: owner team management (add/revoke drivers), the real-browser
field flow (sole owner, driver least privilege, offline completion applied once, revocation), two
defects fixed, and the Phase 7 evidence documents.

### Earlier (P7-M3)

P7-M3 (2026-09-19) delivered location provenance with the D-061 precedence, the deterministic
offline stop-order heuristic with manual reorder, the OpenRouteService adapter with safe fallback
(D-060), and the role-projected nearby supplier reminder.

### Earlier (P7-M2)

P7-M2 (2026-09-19) delivered the assigned-only member API and the driver's least-privilege
projection, driver-scoped sync (empty bootstrap, filtered pull, completion-only push) and offline
completion applied exactly once, with a My Work screen for drivers and for the owner as operator.

### Earlier (P7-M1)

P7-M1 (2026-09-19) delivered delivery tasks with a neutral owner-or-driver assignee: sole-owner
default, owner-only audited reassignment, completion by the assigned member with the performer
recorded, terminal end states per D-063, and system cancellation from the invoice cancellation.

### Earlier (P6-M5)

P6-M5 (2026-09-19) froze Phase 6: Phase 6 commands on the Phase 4 sync protocol (supplier,
price append, procurement edit, purchase, supplier payment) with offline fallbacks in the owner
screens, the real-browser procurement chain, and the Phase 6 evidence documents.

### Earlier (P6-M4)

P6-M4 (2026-09-19) delivered actual supplier purchases: immutable purchases whose finalization
appends the price history, charges the supplier payable and advances the procurement list in one
transaction, replay-safe and fully rolled back on failure; compensating reversals; and customer
outstanding / supplier payable totals by currency.

### Earlier (P6-M3)

P6-M3 (2026-09-19) delivered demand-driven procurement: lists built from confirmed customer
demand with separate required/target/purchased/remaining quantities, owner edits that preserve
demand history, the D-058 lifecycle with waive/carry-forward/cancel reasons, labelled cost
estimates, print/CSV export, a neutral owner-or-driver assignee and a price-free pickup view.

### Earlier (P6-M2)

P6-M2 (2026-09-19) delivered the deterministic comparable-supplier recommendation with
explanations, exclusions with reasons, and the owner override recorded with its reason.

### Earlier (P6-M1)

P6-M1 (2026-09-19) extended suppliers into full profiles (contact, address, saved location,
notes, row version) and the D-034 cost history into a provenance-aware, append-only price history
with derived per-supplier insights and the D-059 invoice preload order.

### Earlier (P5-M6)

P5-M6 (2026-09-19) froze Phase 5: freeze tests for abuse limits, link lifecycle and public leakage,
configurable rate limits (D-076), the real-browser storefront E2E in English and Arabic on a phone,
three defects fixed (stale confirm revision, RTL skip-link overflow, hard-coded limits), and the
Phase 5 evidence documents.

### Earlier (P5-M5)

P5-M5 (2026-09-19) delivered owner order review: an order inbox, explicit customer linking (the
personalized-link hint is a suggestion only) that re-prices the draft, confirmation through the
Phase 3 confirmation, decline, delivery date with a reminder job, and customer cancellation
requests decided by the owner with Phase 3 reversal accounting.

### Earlier (P5-M4)

P5-M4 (2026-09-19) delivered guest checkout: cart and checkout without an account, one RECEIVED
order per idempotency key with an immutable contact snapshot, a draft invoice and first provisional
revision priced by the server, a short-lived provisional order page, one owner notification per
order, and the intended-customer hint from a personalized link that never becomes financial truth.

### Earlier (P5-M3)

P5-M3 (2026-09-19) established the personalized customer context: owner-issued opaque links
bound to the exact customer, one active per customer with atomic rotation and revocation, no
automatic expiry, hash-only storage, assurance `LINK`, current customer pricing on the storefront
through the identity, a 30-day-maximum HttpOnly cookie re-resolved on every request, and policy
fields that later assurance levels (Phase 9) will enforce. No OTP, sessions, accounts or providers.

### Previous (P5-M2)

P5-M2 (2026-09-18) added the storefront signals: pseudonymous views de-duplicated per session and
product within 30 minutes, valid purchases from confirmed non-cancelled sales weighing ten times
a view, a fixed deterministic ranking, monthly rollups after 90 days, and owner-managed featured
campaigns (7-day default, priority then newer then id) shown first on the storefront.

### Previous (P5-M1)

P5-M1 (2026-09-18) opened Phase 5: every approved business now has a public address
(`/<slug>`), an audited rename with a kept redirect, and a bilingual mobile-first storefront that
shows only its published assortment at public prices, with deterministic search and pagination.
No stock or availability concept exists anywhere in the public payload.

### Previous (P4-M6)

P4-M6 (2026-09-18) froze Phase 4: property-style replay (×1/×10/×100) and crash-between-commits
recovery on the server, device-id-alone denial, protocol-mismatch safety and an explicit IndexedDB
schema upgrade on the client, offline fallbacks for customer/product creation, barcode scan and
invoice edits, a real-browser offline E2E (download, offline customer + invoice, reconnect,
exactly-once sync), the sha256 upload dedupe, and the three phase evidence files. Phase 4 is
COMPLETE. Phase 5 was authorized by the owner and starts with P5-M1.

### Previous (P4-M5)

P4-M5 (2026-09-18) delivered the encrypted Google Drive backup: owner OAuth connection with the
narrowest scope and one app folder per business, per-tenant data keys wrapped by an environment
master key, daily/monthly scheduled backups with a clear-text manifest bound to the ciphertext,
30/12 retention, owner restore drills (download, checksum, decrypt, reconcile), a platform-only
controlled import into an empty recovery tenant, master-key rotation, and the key-recovery
runbook. Only P4-M6 (hardening, offline E2E, evidence, freeze) remains before Phase 4 is COMPLETE.

### Previous (P4-M4)

P4-M4 (2026-09-18) completed offline financial commands: the invoice editor queues drafts,
confirmations and receipts on the device when the browser is offline, shows a clearly pending
local reference (never an official number), and the outbox pushes them once; the server applies
them through the unchanged Phase 3 services and returns the assigned header id, official number and
ledger effects, which replace the local rows. P4-M1 (device registry, bootstrap, push), P4-M2
(outbox) and P4-M3 (ordered pull, tombstones, revocation, re-bootstrap) were completed the same day.
P4-M5 (encrypted Google backup) and P4-M6 (hardening, offline E2E, phase evidence) remain.

### Previous (P3-M6)

P3-M6 (2026-09-17) froze Phase 3: full backend regression (161 tests, 93% coverage), frontend
checks (49 tests, lint, types, build), Alembic drift and from-zero/Phase 2 migration checks, RLS and
public-capability sweeps, a real-browser Playwright E2E of the critical owner flow (sign-in, supplier
cost setup, invoice by barcode, confirm, receipt, private link privacy, Arabic/RTL, cancellation
revoking the link), OpenAPI/docs reconciliation, and the three phase evidence files
(`docs/phase-3/requirements-audit.md`, `test-report.md`, `demo-guide.md`). Phase 3 is COMPLETE.
FA-009 was closed afterwards under D-045 (migration `20260917_0013`, head now `20260917_0013`).
Phase 4 and Phase 5 remain LOCKED until the owner records their gate decisions and issues
`Start Phase N`.

### Previous (P3-M5)

P3-M5 delivers 90-day owner-managed private invoice links, a restricted current-invoice customer view, EN/AR WhatsApp sharing controls, and tenant-private aggregate supplier payable/payment/reversal services. Tests cover invalid/internal-ID access, token lifecycle and rotation races, projection privacy, log safety, forced RLS, supplier replay/reversal concurrency, and UI interactions. Demo and operational boundaries are in `docs/phase-3/p3-m5.md`. P3-M6 is next; Phase 3 is not yet complete.

## Baseline remediation (not a new milestone)

The user authorized baseline remediation only. Whole-backend Ruff lint/format, strict mypy,
126 backend tests (92.29% coverage, including two migration-content guards), 34 frontend tests,
TypeScript/ESLint/build and Alembic upgrade/drift checks pass. Required earlier uncommitted
implementation is included; nine future/study paths are safely preserved in a verified local stash.
The path classification and checkpoint validation are recorded in
`docs/phase-3/baseline-remediation.md`. P3-M6 remains NOT_STARTED; no production deployment occurred.
On 2026-09-06, all results were reproduced from implementation checkpoint
`1097593b00c1773e70d1df783fa6dca4322f3ed5` in a separate clean checkout with fresh locked
dependencies, no copied `.env`, unchanged locks and a clean post-validation working tree.
The final checkpoint only adds this documentation evidence; tested runtime content is unchanged.

## Rules for updating this file

### Continuity audit overlay — 2026-09-06

Implementation audit baseline remains `2248c137e43c6c043725830c1303756da1d210ee`.
The phase/milestone rows above are recorded state, not authorization to start P3-M6 during an
audit. This documentation-only task does not implement a milestone or certify Phase 3 complete.
See `AGENT_START_HERE.md`, `docs/TRACEABILITY_MATRIX.md` and `docs/audits/AUDIT_REGISTER.md`.
Earlier "Blocking decision: none" / "Contract deviations: none" entries are historical milestone
claims, not a disposition of newly recorded provenance and cold-start findings. Await the next
explicit audit/work request; no candidate rule is approved by this status update.

Narrow requirements reconciliation followed continuity commit
`f4bb7fd7f1ba86821b87b6c15b17a7694ed0328b`. CT-001 is explanatory/no effective precedence
conflict. CT-002 remains P1: eight preserved planning/manifest files were read under explicit
authorization, but none qualified for authoritative restoration. CT-003 remains P1/PARTIAL:
minimum cost/supplier provisioning is missing despite tested snapshot/override behavior.
CT-004 remains P1/CANNOT VERIFY for complete formula approval; component-level evidence and
CT-005's material policy requests are recorded in `docs/audits/AUDIT_REGISTER.md`. The narrow
documentation task passes its stated reconciliation criteria; it does not close product decisions,
start any larger audit/P3-M6, or change the original implementation baseline or preserved stash.

Owner disposition and future-specification formalization followed on 2026-09-07. D-035–D-043 now
resolve the current formula, historical-opening, supplier-payment, overdue, supplier-setup and
public-link decisions. CT-002 is closed because reconciled root `PHASE_04.md`–`PHASE_10.md` now
exist with later authority applied and unresolved future details explicitly gated. CT-003–CT-005
identify application mismatches still requiring later audit/remediation. No application code was
changed, P3-M6 was not started, and the next recommended work is the separately authorized
financial audit—not automatic remediation.

FA-007 online-recovery extension (2026-09-09): owner decision D-044 requires ordinary same-browser
reload/remount safety now, while the full offline/outbox lifecycle remains Phase 4. The bounded
test-first extension persists exact pending receipt/refund payloads before send, preserves commands
when responses arrive after unmount, and retires them only on observed success. Validation and
limitations are recorded in the FA-007 follow-up in `docs/audits/AUDIT_REGISTER.md`. Independent
post-remediation verification against D-044 classified the fix `VERIFIED_FIXED`; FA-007 is CLOSED.
This is not P3-M6; its status remains NOT_STARTED.

FA-001 bounded remediation (2026-09-09): D-038/FI-16 now have application and database enforcement
at `431a984898484ab132acb11089ecb6dd3a7e406a`. Customer and supplier openings are unique per
tenant/party/currency, signed nonzero historical credits are explicitly classified, and later
changes use linked immutable correction/reversal entries. Migration 0012 aborts without rewriting
history when duplicate initial openings exist. Full backend, frontend, static, migration and
Graphify checks pass. Independent financial verification supplied on 2026-09-10 classifies FA-001
as `CLOSED — VERIFIED_FIXED` against D-038/FI-16; no FA-001 application behavior changed during
closure, no other finding changed, and P3-M6 remains NOT_STARTED.

FA-008 bounded remediation (2026-09-10): application commit
`65b571488fc05247fad6f405f8d5733b597d98ef` interprets customer obligations by approved economic
origin. Opening plus its optional correction is one signed historical position targeted to the
original immutable opening; invoice aggregation remains unchanged; receipt reversals and refunds
are not independent obligations. The string-backed ledger type no longer has an enum-only
dereference in the obligation path. Eleven focused PostgreSQL regressions, the preserved opening and
payment/debt suites, 142 backend tests, Ruff, formatting, strict mypy, Alembic drift and Graphify
refresh/check-only pass. FA-008 is `FIXED_PENDING_FINANCIAL_REGATE`; FA-001 remains CLOSED, other
findings are unchanged, the overall audit is not GO, and P3-M6 remains NOT_STARTED.

Sprint 1 remediation batch (2026-09-17): FA-002, FA-003, FA-004, FA-005, FA-006, FA-010, FA-011 and
FA-012 are fixed with permanent regressions and FA-008 is closed after regate; see the dated section
in `docs/audits/AUDIT_REGISTER.md`. HEAD `4bdbd88a9b719bedc94f1949278a816a9917666e`: 161 backend tests / 93% coverage, 49 frontend
tests, Ruff, strict mypy, ESLint, strict TypeScript, Vite build and Graphify refresh all PASS. New
API group `/api/v1/suppliers` and `/api/v1/payments/supplier-prepayments`; no migration added.
P3-M6 hardening/freeze is now IN_PROGRESS. FA-009 remains open pending an owner decision.

At milestone start:
- set milestone status `IN_PROGRESS`.

At successful milestone end:
- set milestone `COMPLETE`;
- record only the important validation evidence;
- advance `Current milestone` to the next milestone and set it `NOT_STARTED`;
- if phase ended, set phase `COMPLETE` and do not unlock/start next phase automatically.

If blocked:
- set milestone `BLOCKED`;
- record one concise blocking decision;
- do not advance.
