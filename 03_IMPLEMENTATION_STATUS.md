# 03_IMPLEMENTATION_STATUS.md — Persistent Implementation State

> The implementation agent updates this file at the end of every milestone. Keep it concise. Do not turn it into a diary.

## Current execution

- Current workstream: `Phase 2 — Tenant Business Core`
- Current phase: `2`
- Current phase status: `IN_PROGRESS`
- Current milestone: `P2-M5 — Catalog import + acceptance`
- Current milestone status: `NOT_STARTED`
- Last completed milestone: `P2-M4`
- Next required user command: `continue`
- Blocking decision: `none; pricing-v1 approved as D-030`

The user explicitly authorized `Start Phase 2`, the Phase 1 Definition of Done gate is passed, and
the authoritative `PHASE_02.md` contract has been supplied. P2-M1 through P2-M4 are complete. P2-M5
is the next milestone. Historical supplier-cost snapshot behavior is locked for later confirmed-invoice/
supplier integration as D-031 and was not prematurely pulled into Phase 2 pricing.

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
| 2 | IN_PROGRESS | P2-M1 through P2-M4 complete; P2-M5 not started |
| 3 | LOCKED | Gate C |
| 4 | LOCKED | Gate D |
| 5 | LOCKED | Gate E |
| 6 | LOCKED | Phase 5 DoD |
| 7 | LOCKED | Gate F |
| 8 | LOCKED | Gate G |
| 9 | LOCKED | Phases 1–8 DoD |
| 10 | LOCKED | historical-data gate |

## Current milestone evidence

- Code areas changed: tenant grade-discount and explicit product-grade-price models/APIs/UI; pricing-v1 Decimal resolution and draft-invoice snapshots; piece/box counterpart derivation; provider-neutral media interface, safe local adapter, image metadata/content APIs, and authenticated owner image UI
- Migration(s): `20260826_0006`; from-zero upgrade, Alembic drift check, and downgrade/upgrade PASS
- Tests run: backend `87 passed` with `93%` statement coverage on a disposable PostgreSQL 18 database; pricing precedence, exact half-up rounding, piece/box calculations, immutable selling-price snapshots, image re-encoding/type rejection, cross-tenant denial, and non-bypass PostgreSQL pricing RLS PASS; frontend `27 passed`
- Type/lint checks: Ruff lint and format PASS; strict mypy PASS; full `npm run check` PASS; production build PASS (`208` modules, non-blocking size advisory)
- Security checks: pricing and tenant-image tables use forced RLS, explicit tenant predicates, and same-tenant composite foreign keys; images are byte/dimension limited, decoded, re-encoded to WebP, and served only after owner authorization with `nosniff`; SVG is rejected
- Known defects: none
- Contract deviations: none; the local media adapter is development/demo storage and durable production object storage remains an explicit provider decision; no stock, availability, supplier-cost implementation, catalog import, or later-phase workflow was introduced

## Latest completed milestone summary

P2-M4 added the locked pricing-v1 precedence and rounding contract, customer-grade discount and explicit product-grade controls, invoice selling-price provenance snapshots, piece/box calculations, and secure provider-neutral product images. The high-priority historical supplier-cost/profit snapshot requirement is recorded as D-031 for the later supplier and confirmed-invoice implementation. P2-M5 is next and remains not started.

## Rules for updating this file

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
