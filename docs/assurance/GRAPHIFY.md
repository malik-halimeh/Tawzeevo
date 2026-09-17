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
GRAPH_SOURCE_SHA=e6786543eaba17297253ccf0b316bf4168383531
GRAPH_REFRESHED_AT_UTC=2026-09-17T03:54:31Z
GRAPHIFY_VERSION=0.9.55
GRAPH_MODE=structural-code-only-no-cluster
GRAPH_VALIDATION=PASS
GRAPH_NODES=2683
GRAPH_EDGES=8746
<!-- GRAPHIFY_STATE_END -->

## Baseline validation evidence

FA-008 obligation-remediation checkpoint (2026-09-10): the current freshness record refers to
`65b571488fc05247fad6f405f8d5733b597d98ef`. Refresh and check-only both passed. Direct review of
the opening/correction, obligation, receipt/allocation, debt and balance paths plus PostgreSQL-backed
regressions establishes the behavior; graph structure remains supplemental. Earlier evidence below
describes historical checkpoints and does not substitute for the current direct proof.

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

### FA-008 material-refresh verification ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â 2026-09-10

This refresh follows application commit `65b571488fc05247fad6f405f8d5733b597d98ef`.
Refresh and check-only passed with Graphify 0.9.55, 2,577 nodes and 8,180 edges. Focused paths
resolved these extracted relationships:

- `correct_customer_opening_balance()` ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ `correct_opening_balance()`;
- `record_customer_receipt()` ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ `_selected_allocations()` ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ `_obligations()` ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢
  `opening_obligation_positions()`;
- `record_customer_receipt()` ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ `PaymentAllocation` and `CustomerLedgerEntry` (model uses include
  inferred edges and were verified directly);
- `record_customer_receipt()` ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ `commit_and_restore_tenant_scope()`;
- `record_customer_receipt()` ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ `_payment_response()` ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ `_customer_balance()`;
- `customer_obligations()` ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ `_obligations()` ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ `opening_obligation_positions()`; and
- `customer_debts()` ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ `opening_obligation_positions()`.

Direct source and test review confirmed that immutable opening/correction rows are combined before
the signed position is interpreted; invoice groups retain their existing canonical aggregation;
receipt reversals and refunds are not standalone obligations; allocations continue to target the
original opening row; and tenant/currency filters remain explicit. Graphify does not prove Decimal
results, ORM runtime string values, transactionality, allocation conservation, RLS, or database
history immutability, so those conclusions rely on source, schema and the executed PostgreSQL suite.

### FA-007 material-refresh verification ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â 2026-09-08

This refresh follows application commit `ac9bbdb9b10f1dd09010bf4c1bd2ab56e44d85fd`.
Focused navigation returned EXTRACTED paths from `InvoiceEditor()` to both `financialIntent()` and
`apiRequest()`, and from `create_customer_receipt()` to `record_customer_receipt()`. The affected
query for `record_customer_receipt()` identified the mounted route and main router. Graphify also
resolved the new PostgreSQL-backed regression test and its direct helper calls; its ORM model uses
were marked INFERRED and were therefore treated only as navigation leads.

Direct source review confirmed the complete material path:

```text
InvoiceEditor recordReceipt / recordRefund
ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ financialIntent stable pending payload
ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ apiRequest (including same-body 401 replay)
ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ routes/payments.py::create_customer_receipt
ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ services/payments.py::record_customer_receipt
ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ Payment + CustomerLedgerEntry + PaymentAllocation + AuditEvent
```

Graphify does not index the nested `recordReceipt` callback as a standalone node, so the stable-key
creation, failure retention, successful retirement, ledger/allocation constructors, database
constraints and both regression tests were verified directly. No absence claim relies on the graph.

### FA-001 material-refresh verification ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â 2026-09-09

This refresh follows application commit `431a984898484ab132acb11089ecb6dd3a7e406a`.
Refresh and check-only both passed with Graphify 0.9.55, 2,562 nodes and 8,086 edges. Focused
`explain` results resolved extracted route-to-service calls for customer and supplier opening
creation and correction, plus extracted ledger and audit constructors in both correction services.

Direct review of D-038, the models, migration 0012, routes, schemas, services and PostgreSQL-backed
tests established the invariant. Graphify did not establish database uniqueness, row-lock behavior,
migration abort semantics, immutable-trigger behavior or resulting balances; those conclusions use
the directly inspected source, migration execution and regression tests.
