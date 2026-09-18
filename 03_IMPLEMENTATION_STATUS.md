# 03_IMPLEMENTATION_STATUS.md — Persistent Implementation State

> The implementation agent updates this file at the end of every milestone. Keep it concise. Do not turn it into a diary.

## Current execution

- Current workstream: `Phase 4 — Offline-First Operations, Synchronization, Encrypted Backup`
- Current phase: `4`
- Current phase status: `IN_PROGRESS`
- Current milestone: `P4-M6 — Offline property/E2E hardening and freeze`
- Current milestone status: `NOT_STARTED`
- Last completed milestone: `P4-M5`
- Next required user command: `continue`
- Blocking decision: `none; a live Google backup run needs the owner's OAuth client (OWNER_ACTIONS.md § I), all backup behaviour is verified against the in-memory Drive double`

The user explicitly authorized `Start Phase 3`. Phase 2 is complete and its requirements audit,
test report, and demo guide are frozen under `docs/phase-2`. Gate C verification confirms the Phase 2
pricing, Decimal/NUMERIC, rounding, immutable ledger/payment/allocation, sequencing, cancellation,
and refund contracts. D-033 locks one optional order to at most one invoice header. D-034 locks
tenant-private supplier/product costs, latest-eligible prefilling, reasoned owner override, and
immutable confirmed-line cost provenance. P3-M5 is complete; P3-M6 remains not started.

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
| 4 | IN_PROGRESS | Gate D decisions D-052–D-057 recorded 2026-09-18; owner issued `Start Phase 4` |
| 5 | AUTHORIZED | Gate E decisions D-046–D-049, D-051, D-062 recorded; owner issued `Start Phase 5`; begins after Phase 4 DoD |
| 6 | LOCKED | Phase 5 DoD |
| 7 | LOCKED | Gate F |
| 8 | LOCKED | Gate G |
| 9 | LOCKED | Phases 1–8 DoD |
| 10 | LOCKED | historical-data gate |

## Current milestone evidence

- Code areas changed (P4-M1–M5, 2026-09-18): encrypted Google backup (`services/backup*.py`, `routes/backup.py`, `cli/backup_jobs.py`, `docs/runbooks/backup-key-recovery.md`, Backup tab `BackupPanel.tsx`, Google callback page); sync device registry, authorized paginated bootstrap, idempotent per-operation push with version conflicts, ordered pull with tombstones and retention floor, server-side device revocation on membership revoke/tenant suspend; offline invoice/payment commands through push reusing the Phase 3 financial services (`services/sync_push.py`); sha256 upload dedupe for image retries (`services/media.py`); PWA local database per tenant membership (Dexie), resumable bootstrap, outbox with exactly-once dispatch and conflict/dead-letter handling, incremental pull and re-bootstrap, offline draft/confirm/receipt queueing in the invoice editor with pending local references, offline media queue (`apps/operations-web/src/offline/`), Offline tab (`SyncPanel.tsx`)
- Migrations: `20260918_0014_sync_foundation`, `20260918_0015_sync_retention_floor`, `20260918_0016_backup_connections` (connections, wrapped keys, backups, restores; RLS); head `20260918_0016`; from-zero upgrade and downgrade verified on disposable PostgreSQL 18
- Tests run (2026-09-18): backend `185 passed` on disposable PostgreSQL 18 (sync bootstrap 6, push 5, pull 4, financial push 2, backup 4 added); frontend `67 passed` (sync 4, outbox 4, pull 4, commands 2, media 2, backup panel 1 added); Ruff and strict mypy PASS (60 source files); ESLint, strict TypeScript and production build PASS
- Security/invariants: bootstrap and push require an active membership and a registered device; forced RLS on all sync tables; per-operation transactions with advisory locks and request fingerprints (a replay with a different body is rejected); official invoice numbers and revision numbers are only ever assigned by the server; offline financial commands carry the same idempotency keys as the online editor so a replay never double-charges; offline queueing only when the browser reports no connection (a lost response while online keeps the D-044/D-045 stable command); backups are AES-256-GCM with per-tenant keys wrapped by an environment master key (D-057), `drive.file` scope only (D-055), 30 daily/12 monthly retention (D-056); tampered files, wrong keys and swapped manifests fail closed; restore drills never touch live rows and the controlled import refuses a non-empty tenant; OAuth codes/tokens redacted from logs
- Known defects: none open for P4-M1–M4. Media bytes are stored as `ArrayBuffer` rather than `Blob` in IndexedDB (some WebViews fail to persist Blobs)
- Contract deviations: none. The Google Drive client is exercised only through the in-memory double until the owner supplies an OAuth client; the HTTP client follows the documented Drive v3 endpoints and is not yet run against Google

## Latest completed milestone summary

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
