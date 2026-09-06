# Recovered Phase 4–10 planning evidence

Status: **HISTORICAL OWNER PLANNING EVIDENCE — NOT AUTHORITATIVE PHASE SPECIFICATIONS**.

This directory preserves the complete recovered Phase 4–10 planning set supplied by the owner on
2026-09-07. The seven `PHASE_XX.md` files and `REMAINING_PHASE_GUIDE_MANIFEST.md` are preserved
byte-for-byte. Do not implement from them directly, copy them to the repository root, or use their
details to override [AGENTS.md](../../AGENTS.md), [approved decisions](../../04_DECISIONS.md), the
[project contract](../../00_PROJECT_CONTRACT.md), or the current phase specification.

## Provenance

The recovered manifest describes the phase files as newly generated consolidated guides derived
from the then-current project documents and a frozen `cash-van-production-roadmap-v2.1.1.md`; it
explicitly says they are not verbatim recovered originals. That cited frozen roadmap is not present
in this directory or the tracked repository. The owner has now identified this exact set as planning
created during earlier ChatGPT planning sessions and directed that it be retained as historical
evidence rather than automatically promoted.

The Git blob IDs below exactly match the eight objects previously inspected from the preserved
stash and recorded in CT-002. This proves content identity with the already inventoried guide set;
it does not prove approval of every clause.

| File | Lines | Git blob ID | Reconciliation status |
|---|---:|---|---|
| `PHASE_04.md` | 401 | `609a2085048dd9a587eb5c57b28ba769bf62579b` | Historical candidate |
| `PHASE_05.md` | 386 | `b658be6f3f2231fa189e90725dba9a6a96439d0f` | Historical candidate |
| `PHASE_06.md` | 326 | `ef1e59d7a68834861c276ad36f5e6ce4912543f0` | Historical candidate |
| `PHASE_07.md` | 290 | `a88d368a10a298e72a9174348c7c0c6a81cc518a` | Historical candidate |
| `PHASE_08.md` | 253 | `0319e5968a0e3a1dd2f38489c3c1d3d4fb1c4061` | Historical candidate; cost conflict superseded below |
| `PHASE_09.md` | 346 | `ec825132ef407a61ad2cd1032229540bd5efa45f` | Historical candidate |
| `PHASE_10.md` | 198 | `1853a75c73ae17f791fa3459da73bb8194e879e5` | Historical candidate |
| `REMAINING_PHASE_GUIDE_MANIFEST.md` | 39 | `73eba6ad075b3492cade9f7b872c8f2630289331` | Provenance evidence; not an authority grant |

The recovered set was read in full for this reconciliation. Current implementation remains through
P3-M5; none of these future features is treated as implemented.

## Preserved compatible planning

These historical requirements agree with later approved authority and should be carried into the
eventual authoritative phase specifications, with exact acceptance details reviewed at each gate:

| Phase | Compatible planning preserved |
|---|---|
| 4 | PostgreSQL remains authoritative; IndexedDB projection/outbox; idempotent/versioned sync; server-only official sequences; append-only finance; revocation/quarantine; encrypted Google backup as recovery/export rather than live DB; offline media; no early Phase 6/7 domain work. |
| 5 | One tenant storefront; only tenant-adopted/created and published products; guest checkout; immutable contact snapshot; idempotent retry; owner review/confirmation; owner-set delivery date; cancellation request decided by owner; owner-only operation works with zero drivers; no stock or tracking. |
| 6 | Tenant-private suppliers; append-only comparable price history; demand-driven procurement without inventory; owner/driver assignee with restricted driver projection; immutable purchase/payable/payment chain; currencies separate; no per-purchase supplier-payment allocation. |
| 7 | Owner may self-operate; neutral owner/driver membership assignment; least-privileged assigned driver; no customer tracking; no driver supplier costs/profit; offline fallback/manual route order; routing provider requires later approval. |
| 8 | Canonical revision/ledger/payment sources; current-state and event-flow reports distinguished; currencies separated; owner-only financial analytics; customer duplicates not merged; branding cannot change financial/security rules; public aggregates require privacy review. |
| 9 | Public-repository secret/privacy rules; authorization/RLS/session/concurrency/migration/recovery hardening; observability without sensitive logs; reproducible CI/CD; two-tenant isolation; one-owner and separate-driver pilots; no product redesign disguised as hardening. |
| 10 | Tenant-specific canonical confirmed/non-cancelled sales; deterministic statistical baseline first; insufficient-data behavior; backtesting without future leakage; ML only after measured improvement; no LLM, inventory or automatic purchasing. |

## Later authority that supersedes recovered details

Later approved decisions win while the older wording remains here for provenance:

1. **Phase 6 cost storage:** the historical `supplier_product_prices` instruction must not create a
   parallel cost truth. The eventual specification must extend/reuse D-034's tenant-private,
   append-only `TenantProductCostEntry` foundation and preserve quote/actual-purchase provenance.
2. **Phase 8 historical profit:** the recovered precedence of later linked actual purchase or latest
   comparable actual-purchase price cannot calculate historical invoice profit. D-031/D-034 and
   D-036 require immutable revision-specific sale-time quantity, revenue and cost snapshots. A later
   purchase-based estimate may exist only as a separately named metric after explicit approval.
3. **Phase 5 public links:** D-042 now permits one active owner-issued link for a confirmed invoice;
   issuing/rotating replaces the old link and cancellation revokes it. The recovered automatic
   provisional capability and cancelled-link presentation cannot be copied unchanged. Phase 5 must
   design its provisional checkout representation within its gate without weakening D-042.
4. **Phase 3 supplier setup:** recovered P6-M1 supplier CRUD does not defer the minimum setup.
   D-041 requires a dedicated supplier/product-cost API/UI before Phase 3 completion. Phase 6 builds
   full contacts, analytics and procurement on that foundation.
5. **Supplier money:** D-039 replaces implicit ordinary-payment overage with a separate supplier
   prepayment action. Phase 6 must preserve this distinction and aggregate/no-allocation rules.
6. **Overdue/period calendar:** D-040 uses the `Asia/Beirut` calendar for overdue. Phase 8 reporting
   must use the approved timezone unless a later explicit decision changes it.
7. **Deployment:** D-027/D-028 already record current Supabase PostgreSQL and Render deployment.
   Phase 9 may select still-missing production services or propose a change, but cannot pretend no
   provider decision exists or silently replace the approved deployment.
8. **Routing ADR reference:** recovered Phase 7's `ADR-027` reference is not valid current provenance;
   D-027 concerns PostgreSQL hosting. A new correctly numbered routing-provider decision/ADR is
   required immediately before Phase 7.

## Genuine conflicts and current review status

| ID | Conflict/ambiguity | Status |
|---|---|---|
| RP-NOW-01 | Current invoice validation rejects initial zero net sales but permits a confirmed edit to reach zero. | **RESOLVED by D-043:** every confirmed revision requires strictly positive net sales; quantity is positive and monetary inputs/totals are nonnegative. Cancellation/reversal handles zero economic effect. |
| RP-NOW-02 | Whether the one initial opening per party/currency may represent negative credit. | **RESOLVED by completed D-038:** signed nonzero initial openings are allowed and clearly historical; multiplicity remains one and operational payments/prepayments remain distinct. |
| RP-P4-01 | Exact sync page size 500, 90-day tombstone minimum, 24-hour offline lease and retirement rules lack final approval. | Record at Gate D; safely wait until Phase 4 |
| RP-P4-02 | Google OAuth scope/folder model, retention, backup schedule, KEK provider/recovery and exact AES/DEK/KEK deployment need explicit security/provider review. | Required before P4-M5; safely wait |
| RP-P5-01 | D-042 confirmed-only sharing supersedes provisional capability issuance. The customer still needs the contracted provisional checkout representation; exact session/receipt/revisit behavior is undefined. | Resolve at Gate E before P5-M3 |
| RP-P5-02 | Exact tenant slug/rename redirect, recommendation ratio, view-dedup window and interaction retention are generated details beyond the approved high-level rules. | Resolve/configure during Phase 5 specification |
| RP-P6-01 | Procurement terminal/waive/carry-forward transitions and the precise relationship between quote, actual-purchase and D-034 cost entries need a final state/data contract. | Resolve before Phase 6 |
| RP-P7-01 | Delivery task terminal/reopen behavior, location replacement rules and online routing/geocoding provider are not approved. | Resolve immediately before Phase 7 |
| RP-P8-01 | Exact metric formulas, period/event dates, cost-coverage definition, lifetime/favorite/late metrics and small-cohort privacy thresholds remain undefined. | Gate G before Phase 8 |
| RP-P8-02 | Whether to offer a separately labelled later-purchase-based margin estimate in addition to immutable sale-time historical profit is a new product decision. | Safely wait until Phase 8; default is omit |
| RP-P9-01 | Mandatory password recovery, exact SLO numbers, worker/object-storage/staging providers and data-retention details are not fully sourced by current authority. | Resolve from security evidence before their Phase 9 milestone |
| RP-P10-01 | Minimum data threshold, season definition, confidence meaning and evaluation/adoption threshold for optional ML are data-dependent. | Resolve at Phase 10 gate |

## Questions requiring owner answer now

None for specification formalization. RP-NOW-01 and RP-NOW-02 are resolved by D-043 and completed
D-038. The phase-specific questions below remain gated rather than silently approved.

## Questions that safely wait

RP-P4-01 through RP-P10-01 are recorded for their named phase gates. They must not be silently
copied into authoritative root phase files. The relevant phase specification should present only
the remaining material owner choices at that time; technical defaults may be selected as ordinary
implementation detail when they do not change product, security, financial or provider behavior.

## CT-002 closure condition

CT-002 is closed by the 2026-09-07 formalization: RP-NOW-01/RP-NOW-02 are recorded in D-043/D-038;
reconciled authoritative root `PHASE_04.md` through `PHASE_10.md` preserve compatible planning,
apply later supersessions and explicitly gate deferred items; and navigation/governance/traceability
identify this directory as historical provenance only. Future implementation still requires the
normal explicit `Start Phase N`, completed prior phase and satisfaction of each root file's gate.
