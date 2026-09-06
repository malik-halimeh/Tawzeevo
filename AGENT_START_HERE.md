# Tawzeevo — repository-only continuation entry point

Implementation audit baseline: `2248c137e43c6c043725830c1303756da1d210ee`.
This is a derived navigation document, not a replacement project contract.

## Start safely

1. Read [AGENTS.md](AGENTS.md), then its prescribed project contract, stack, status and current-phase read order. Do not execute the historical initial prompt in `IMPLEMENTATION_MASTER_PROMPT.md`.
2. Inspect `git status --porcelain=v1` and `git rev-parse HEAD`. A later documentation commit is not a new implementation baseline. Preserve unexplained changes.
3. Read [source governance](docs/governance/SOURCE_OF_TRUTH.md), [current architecture](docs/architecture.md), and [persistent status](03_IMPLEMENTATION_STATUS.md). These distinguish approved intent, observed implementation, and remaining uncertainty.
4. Use [traceability](docs/TRACEABILITY_MATRIX.md) to find requirement/code/test anchors. Use [the audit register](docs/audits/AUDIT_REGISTER.md) for unresolved findings and candidate decisions. Tests and successful gates do not authorize undocumented product rules.
5. Follow the user's current task. This continuity pass does not authorize P3-M6, a financial audit, fixes, deployment, or future phase work. Do not treat the milestone pointer as permission to implement during an audit.

## Actual stopping point

Phases 1 and 2 are recorded complete. P3-M1 through P3-M5 are recorded complete; Phase 3 is
still in progress and P3-M6 is NOT_STARTED. The earlier baseline gate passed, but this continuity
audit identifies gaps in cold-start usability and approved provenance; it is not a renewed
certification that every Phase 3 requirement is satisfied. See CT-003 and CT-004 before finance work.

Implemented: account/session/admin foundation, tenant onboarding/access controls, owner-only
customer/catalog/pricing/media operations, immutable invoice/ledger/payment foundations, and
capability-based invoice sharing. The role gallery is synthetic, not a storefront or driver backend.
There is no implemented guest checkout, offline business sync, procurement, delivery routing,
analytics, or forecasting. Supplier/cost tables are not a complete supplier management workflow.

## Preserved work — do not mix it into this baseline

The prior [preservation report](docs/phase-3/baseline-remediation.md) identifies nine excluded paths:
`PHASE_04.md` through `PHASE_10.md`, `REMAINING_PHASE_GUIDE_MANIFEST.md`, and changes to
`docs/Tawzeevo-Python-FastAPI-Study-Journey.html`. They were preserved in local stash
`9050d544791b5e22d15c2ff1a1acdbd503b40418`.

This audit neither opens nor applies/pops/modifies/drops that stash. A clone does not receive local
stashes. Do not reconstruct the absent phase specifications from memory or summaries. Before
future implementation, obtain explicit authorization to recover/review the preserved guides (or
obtain approved replacements), retain their provenance, and resolve conflicting requirements.
This is preservation information, not restoration authorization. CT-002 blocks an autonomous
repository-only continuation all the way through Phase 10.

## Run and verify without hidden history

- Normal application setup and API activation: [root README](README.md#local-setup).
- Exact tested locked-install workflow and results: [baseline reproduction](docs/phase-3/baseline-remediation.md#clean-checkout-reproduction--2026-09-06).
- Individual test commands and dated runs: [RUN_TESTS.md](RUN_TESTS.md). Its initial `tests/unit` examples are proposed templates, not existing tests.
- Test infrastructure: disposable PostgreSQL only. The autouse fixture truncates business tables; migration/RLS tests additionally create/drop temporary databases and roles. Do not point tests at the hosted application database.
- Supply `DATABASE_URL` and `TEST_DATABASE_URL` to the same disposable migrated database. Backend settings resolve `.env` from the process working directory; use explicit process environment variables for audit tests. Never copy secrets into reports.
- Backend lock reconciliation, deployment migration procedure and runtime-role verification are open continuity items (CT-008/009); a green Windows/local gate does not prove deployed behavior.

## How to continue later

The next implementation milestone is P3-M6 only after the user authorizes it and affected open
questions are addressed. Do not advance Phase 3 to COMPLETE from this audit. At eventual phase
completion, automatically produce the three evidence reports required by AGENTS.md.
Future phases still require explicit `Start Phase N`, their approved detailed specification and gate.
For the next task, recommend a focused requirements/decision reconciliation review, not automatic
implementation or the financial audit.
