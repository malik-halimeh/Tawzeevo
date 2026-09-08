# Graphify structural-evidence policy

Graphify is local development and audit tooling. It is supplemental structural evidence, not an
application dependency, a source of product truth, or a replacement for the authority order in
`AGENTS.md` and `docs/governance/SOURCE_OF_TRUTH.md`. Generated output lives in `graphify-out/` and
is intentionally ignored by Git.

## Evidence rules

1. Graphify is supplemental evidence only.
2. For every material finding, verify graph relationships against source code, schema/migrations
   where relevant, and tests.
3. `EXTRACTED` relationships can guide structural analysis, but critical findings still require
   direct source verification.
4. `INFERRED` and `AMBIGUOUS` relationships are investigation leads only.
5. No P0 or P1 finding may be established solely from an `INFERRED` or `AMBIGUOUS` relationship.
6. Absence of a Graphify edge is not proof that a runtime or code path does not exist.
7. Directly inspect dynamic behavior, dependency injection, reflection/configuration-driven wiring,
   framework behavior, ORM behavior, and runtime dispatch.
8. A stale graph must not be used as current structural evidence.

## Mandatory freshness workflow

Refresh and verify the graph:

- after every completed milestone;
- before an audit, dependency scan, blast-radius analysis, or architectural review that materially
  relies on graph structure; and
- after material database schema/migration, financial, authentication, authorization, tenant,
  domain-service, repository-boundary, public-API-boundary, or major module movement/refactoring
  changes, even before a milestone finishes.

Before relying on Graphify, identify the commit being examined as `CURRENT_INTENDED_SHA`. It must
equal the `GRAPH_SOURCE_SHA` in the freshness record below. On mismatch, stop using graph results,
rebuild for the intended committed state, verify the refresh, and only then continue. A graph that
still returns results is not necessarily current.

Run from the repository root:

```powershell
pwsh -NoProfile -File scripts/refresh_graphify.ps1 -IntendedSha <full-commit-sha>
pwsh -NoProfile -File scripts/refresh_graphify.ps1 -IntendedSha <full-commit-sha> -CheckOnly
```

The rebuild requires `HEAD` to equal the intended commit and refuses tracked working-tree changes.
It performs structural, code-only extraction with no clustering or deep semantic analysis, runs
representative queries, and updates this record. The check-only mode does not alter files. Commit an
updated freshness record deliberately; the script never stages or commits.

## Freshness record

<!-- GRAPHIFY_STATE_START -->
GRAPH_SOURCE_SHA=868bf1c5d4d49e755c74a6dd2c75a9a78f6ca6e6
GRAPH_REFRESHED_AT_UTC=2026-09-07T06:18:37Z
GRAPHIFY_VERSION=0.9.55
GRAPH_MODE=structural-code-only-no-cluster
GRAPH_VALIDATION=PASS
GRAPH_NODES=1400
GRAPH_EDGES=6783
<!-- GRAPHIFY_STATE_END -->

## Baseline validation evidence

The graph above was built from a clean checkout at the recorded SHA. Each representative result was
then checked directly in the cited source.

| Category | Graphify result | Direct source confirmation |
|---|---|---|
| API route | `confirm_invoice_editor()` resolves to the invoice editor route | `apps/api/tawzeevo_api/routes/invoices.py` |
| Service/domain | `confirm_invoice_editor()` calls `confirm_invoice()` through an `EXTRACTED` edge | `apps/api/tawzeevo_api/services/invoice_finance.py` |
| Repository/database | `set_tenant_scope()` resolves to the tenant repository and its PostgreSQL `set_config` statement | `apps/api/tawzeevo_api/repositories/tenancy.py` |
| Financial/invoice | `confirm_invoice()` resolves ledger posting and transaction work | invoice finance service and invoice/customer-ledger models |
| Test | `test_confirmation_is_idempotent_assigns_official_number_and_posts_one_charge()` resolves its confirmation workflow | `apps/api/tests/test_invoice_editor.py` |

Structural queries worked for all five categories. Broad natural-language queries were noisy and
could be truncated; focused symbol queries and paths were more reliable. Some ORM/test relationships
were inferred rather than extracted. FastAPI dependency injection, SQLAlchemy runtime behavior, RLS,
and other dynamic wiring therefore still require source, migration, and test inspection.
