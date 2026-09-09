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
GRAPH_SOURCE_SHA=7c6b46a895bd26fc93426942ce70b627acd771ac
GRAPH_REFRESHED_AT_UTC=2026-09-09T05:23:25Z
GRAPHIFY_VERSION=0.9.55
GRAPH_MODE=structural-code-only-no-cluster
GRAPH_VALIDATION=PASS
GRAPH_NODES=1412
GRAPH_EDGES=6825
<!-- GRAPHIFY_STATE_END -->

## Baseline validation evidence

FA-007 D-044 extension checkpoint (2026-09-09): the current freshness record refers to
`7c6b46a895bd26fc93426942ce70b627acd771ac`. Refresh and check-only both passed. Direct review of
`api/financialIntent.ts`, the receipt/refund callers, their tests and unchanged backend replay path
establishes the recovery behavior; graph structure remains supplemental. Earlier evidence below
describes its historical checkpoints and does not substitute for the new reload/remount tests.

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

### FA-007 material-refresh verification — 2026-09-08

This refresh follows application commit `ac9bbdb9b10f1dd09010bf4c1bd2ab56e44d85fd`.
Focused navigation returned EXTRACTED paths from `InvoiceEditor()` to both `financialIntent()` and
`apiRequest()`, and from `create_customer_receipt()` to `record_customer_receipt()`. The affected
query for `record_customer_receipt()` identified the mounted route and main router. Graphify also
resolved the new PostgreSQL-backed regression test and its direct helper calls; its ORM model uses
were marked INFERRED and were therefore treated only as navigation leads.

Direct source review confirmed the complete material path:

```text
InvoiceEditor recordReceipt / recordRefund
→ financialIntent stable pending payload
→ apiRequest (including same-body 401 replay)
→ routes/payments.py::create_customer_receipt
→ services/payments.py::record_customer_receipt
→ Payment + CustomerLedgerEntry + PaymentAllocation + AuditEvent
```

Graphify does not index the nested `recordReceipt` callback as a standalone node, so the stable-key
creation, failure retention, successful retirement, ledger/allocation constructors, database
constraints and both regression tests were verified directly. No absence claim relies on the graph.
