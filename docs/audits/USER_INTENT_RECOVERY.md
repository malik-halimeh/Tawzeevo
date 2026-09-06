# Narrow user-intent reconciliation

Date: 2026-09-06. Result: **LIMITED CORROBORATION — material findings remain open**.
Recovered explicit intent remains `RECOVERED_USER_INTENT — FORMALIZATION_REQUIRED`.
This derived report creates no BINDING authority and changes no decision/specification.
Existing [AGENTS.md](../../AGENTS.md) precedence remains in force.

## Evidence verification and historical checkpoint

Starting HEAD: `41c5af0790cc36d37a9cffb3248d3e46fef51086`, clean.
Immutable implementation baseline: `2248c137e43c6c043725830c1303756da1d210ee`.
The previous report at starting HEAD correctly found zero quotations in its guard-only packet.
The current follow-up replaces that inconclusive report using the corrected evidence packet.

- Packet: `.tmp/tawzeevo-user-intent-evidence.md`, relative to the repository.
- SHA-256: `acba1090b591ba0bbfc9980b92f74e4ef26b523f69fc7790bd28282adc4fb2f7`.
- Size: 6,657 bytes. Opened/read completely before reconciliation: **PASS**.
- Three OWNER MESSAGE blocks contain actual wording plus session ID and timestamp/order.
  The packet's session index supplies the exact Tawzeevo working directory.
- All three cite session `01a01cc1-ade4-71f1-b5ef-eebc07eddc80`.
  Times below preserve the packet literally; no timezone or per-candidate segment mapping is supplied.
- INTENT-001 is excerpted; INTENT-002 lacks the antecedent of its opening approval.
  Original raw-history provenance is not independently revalidated in this task.
- The upstream 296-message scan count is not this task's review count. The earlier extraction
  found platform/reviewer envelopes among user-role records, so role alone does not prove authorship.

No raw history, extraction scripts, additional historical messages, assistant suggestions or
stash contents were accessed. The packet itself remains temporary and uncommitted.

## Message-level findings

| Evidence / timestamp and order | Classification | Wording and bounded interpretation |
|---|---|---|
| INTENT-001; 08/24/2026 23:16:00 / 6652 | RECOVERED_EXPLICIT_USER_DECISION | Requires "explicit grade price beats grade percentage discount", otherwise normal price, backend calculation, Decimal/NUMERIC and the existing pricing-v1 contract. Requests exact rounding tests. Gives no numeric scale/mode, intermediate invoice stages or manual-invoice grade policy. |
| INTENT-002; 08/25/2026 23:27:37 / 8332 | RECOVERED_EXPLICIT_USER_DECISION | Cost 2 then 2.2 USD at unchanged sale price 3 should leave respective weekly profits 1 and 0.8. Says "the system must then keep snapshots of the record at the time of when the invoice was made or add an option for the owner to control that price". Explicit historical-calculation protection; exact snapshot/owner-control mechanism left open. |
| INTENT-003; 08/26/2026 20:20:12 / 9936 | DISCUSSION_ONLY | Describes different owners' negotiated prices for the same supplier/product, then asks "is that what is implemented?" and says "i will be ready to approve your decisions". Relevant clarification, not approval of a workflow or all D-034 details. Packet's preliminary explicit-instruction label is not adopted. |

Counts: **3 messages reviewed; 2 explicit decisions; 0 explicit confirmations;
1 discussion-only; 0 wholly ambiguous messages; 0 conflicting instructions**.
One sub-item is **AMBIGUOUS**: what INTENT-002's initial "Approved." approves.
It supplies no recovered confirmation or blanket formula/decision approval.
Mechanism details left open are unresolved scope, not conflicting owner instructions.

INTENT-001 and INTENT-002 are recorded as
`RECOVERED_USER_INTENT — FORMALIZATION_REQUIRED`; no new authority is formalized.
The profit example is illustrative evidence, not a comprehensive profit formula.
INTENT-002's request to create a memory "if this is in the coming phases" requests plan
checking/documentation; it does not choose a phase or defer confirmation prerequisites.

## Four-way comparison of the 13 requested items

Sources: [04_DECISIONS.md](../../04_DECISIONS.md) D-019/D-030/D-031/D-034,
[PHASE_03.md](../../PHASE_03.md), and the existing derived code/test comparisons in
[AUDIT_REGISTER.md](AUDIT_REGISTER.md) F01–F15, C01–C08 and supplier-provisioning review.
E1–E13 retain that register's exact test mapping. Those comparisons are reused, not treated
as approval. Newly relevant catalog/cost source and test excerpts were inspected again;
no runtime tests or wider audit were performed.

A = REPOSITORY ALREADY CORRECT only for the named corroborated facet.
F = STILL CANNOT VERIFY the unresolved detail or alleged later change.
A partial A does not close an entire finding. Absence of approval from this small packet
does not by itself establish C. CODE IMPLEMENTS UNAPPROVED BEHAVIOR.

| Item | Existing authority | Recovered intent classification | Actual implementation compared | Existing tests compared | Reconciliation result |
|---|---|---|---|---|---|
| 1. Formula/rounding boundaries | D-030 catalog rounding; Phase 3 A/D Decimal/calculator | RECOVERED_EXPLICIT_USER_DECISION: INTENT-001 Decimal and rounding-test requirement; NO_RELEVANT_USER_EVIDENCE for missing exact invoice boundaries | F01/F03/F05/F07 Q4 HALF_UP; quantity pre-rounding; positive quantity; initial positive net sales versus later zero edit | E1/E3 examples; E9 edit-to-zero, not full boundary matrix | A for backend Decimal principle; F for intermediate/sign/zero rules |
| 2. Manual price / grade | D-030 catalog precedence; Phase 3 manual entry | RECOVERED_EXPLICIT_USER_DECISION: INTENT-001 catalog order; NO_RELEVANT_USER_EVIDENCE for manual-invoice grade policy | resolve_product_pricing follows explicit-grade/percentage/normal order; F04 manual effective price bypasses automatic grade reduction and catalog manual-price input is rejected | E1 explicit grade wins; E2 manual 3 × 2 with grade-A customer | A for catalog order; F for manual semantics |
| 3. Discounts / markup / displayed due | Phase 3 B/D/F/L adjustments and old balance outside sales | NO_RELEVANT_USER_EVIDENCE for invoice units/display; catalog percentage mention does not specify them | F06 fixed amounts aggregate to net sales, grade savings outside discount total; F08 Q(prior + net sales) saved on revision acceptance | E2 net 27.7500/display 32.7500; E4 revision example | F for units/order/reporting/equation/inclusion set/timing |
| 4. Opening-event semantics | Phase 3 F/H ledger rules, opening not sales | NO_RELEVANT_USER_EVIDENCE | F10/F13 signed nonzero openings; multiple different keys admitted | E12 customer opening/replay; E10 supplier opening/balance; no complete admission matrix | F for signed/multiple/zero admission |
| 5. Supplier overpayment/credit | D-019/Phase 3 H aggregate payable reduction | NO_RELEVANT_USER_EVIDENCE | F13/C06 no payable ceiling; payments may create negative supplier balance | E10 payment/reversal/currency, no explicit overpayment assertion established | F for ceiling/credit meaning |
| 6. Overdue | Phase 3 G oldest unpaid obligation, positive balance, age > owner X, red/dedup alert | NO_RELEVANT_USER_EVIDENCE | F15/C08 date difference, unset means not overdue, read-time stable key, no persisted notification lifecycle | E12 aged debt/repeated key | F for day/timezone/unset/cadence/dedup |
| 7. Supplier/cost provisioning or deferral | D-034/Phase 3 B minimum foundation; Phase 6 may append automatically | DISCUSSION_ONLY: INTENT-003 tenant price clarification; INTENT-002 history-protection direction supplies no provisioning/deferral approval | _prepare_cost selects eligible tenant/product/supplier cost or reasoned override; confirmation requires snapshot; CT-003 missing supported provisioning remains | E11 directly inserts supplier/cost/preference; tests preload/override, not fresh-tenant creation | F for recovered workflow/deferral; PARTIAL foundation / MISSING provisioning unchanged |
| 8. Multiple links/regeneration/retries | Phase 3 J expiry/revoke/rotate | NO_RELEVANT_USER_EVIDENCE | C04 multiple active links, non-idempotent creation, rotation replaces selected capability only | Existing public-invoice tests cited by register | F for cardinality/retry/old-link scope |
| 9. Draft/cancelled sharing | Phase 3 J current representation/privacy ceiling | NO_RELEVANT_USER_EVIDENCE | C05 draft/cancelled issuance/read and post-cancellation behavior | Existing public-invoice backend/frontend tests | F for lifecycle approval |
| 10. Rate limit | Phase 3 J requires rate limiting | NO_RELEVANT_USER_EVIDENCE | C01 60/IP/60s, 4096-client fail-closed cap, per-process public-path bucket, shell/data both count, Retry-After 60 | Existing public-invoice tests; constants do not establish approval | F for exact service/policy scope |
| 11. Capability transport | Phase 3 J secret/hash-only/no raw logging/no internal-ID authorization | NO_RELEVANT_USER_EVIDENCE | C02 tenant-prefixed bearer, fragment to X-Invoice-Capability header, fixed paths, fragment clearing/reopen behavior | Existing public-invoice backend/frontend tests | F for public transport/reload contract |
| 12. Phase 4–10 guide/roadmap approval | Current-phase specification gate and approved ledger | NO_RELEVANT_USER_EVIDENCE: INTENT-001 concerns Phase 2; INTENT-002's conditional memory request adopts no exact future guide | CT-002 prior absent tracked guides/candidate versions/missing roadmap provenance; no new stash inspection | Existing file/provenance checks only | F; future gap and candidate Phase 8 conflict unchanged |
| 13. Later D-031/D-034 snapshot/profit change | D-031/D-034 immutable revision costs/no later-price historical rewrite | NO_RELEVANT_USER_EVIDENCE of override; RECOVERED_EXPLICIT_USER_DECISION: INTENT-002 supports history protection; INTENT-003 is tenant-price discussion | F14 immutable costs/revision override; no current profit-report algorithm established by prior review | E13 preserves 2.0000 after later 2.2000 entry; E11 retains prior revision cost | A for documented historical-cost protection; F for alleged supersession/full future profit behavior |

Rechecked source/test anchors:

- `apps/api/tawzeevo_api/services/pricing.py::resolve_product_pricing`.
- `apps/api/tawzeevo_api/services/invoice_editor.py::_prepare_cost`.
- `apps/api/tawzeevo_api/services/invoice_finance.py::_validate_confirmable_costs`.
- E1: `apps/api/tests/test_cash_van.py::test_pricing_v1_precedence_rounding_packaging_and_invoice_snapshot` (relevant catalog assertions).
- E11: `apps/api/tests/test_invoice_editor.py::test_editor_prefills_latest_tenant_cost_and_keeps_reasoned_override_revision_only` (fixture setup and override assertions).
- E13: `apps/api/tests/test_financial_schema.py::test_invoice_order_cardinality_and_cost_snapshot_survive_later_cost_change` (fixture-created revision retains 2.0000). This schema test is not a fresh-tenant confirmation or profit-report demonstration.

## Finding and request changes

| Finding/request | Evidence change | Remaining status |
|---|---|---|
| CT-002 | INTENT-002 corroborates historical protection; no guide approval or override | Future authority/availability gap and recorded Phase 8 candidate conflict stay open |
| CT-003 | INTENT-002 history-protection direction; INTENT-003 supplier-pricing clarification, not workflow approval | MISSING provisioning; surface/milestone/deferral provenance unresolved |
| CT-004 | INTENT-001 catalog precedence/backend Decimal and INTENT-002 historical-cost corroboration | Full invoice formula approval still CANNOT VERIFY |
| CT-005 | No new policy approval | Material sharing/supplier/overdue candidates remain REVIEW_REQUIRED |
| R-F | Corroboration of existing catalog principles only | Exact input/rounding/manual/adjustment/sign/display/opening requests unchanged |
| Financial R-P | No supplier overpayment/opening or overdue evidence | C06/C08 requests unchanged |

No B. LATER USER INTENT MISSING FROM DOCS, D. USER INTENT AND CODE DIFFER or
E. CONFLICTING USER INTENT is established. No new C classification is inferred from
missing evidence. The existing provisioning gap against existing authority remains; these
messages neither justify that gap nor demonstrate a new owner/code contradiction.

D-031/D-034 result: **NO LATER USER OVERRIDE FOUND** within this packet.
No wording changes/removes/replaces historical-cost protection. The packet does not establish
message dates relative to ledger approval events; timestamp alone cannot establish supersession.
Neither the initial "Approved." nor readiness to approve confirms all D-034 implementation details.

Supplier conclusion: no chosen supplier/cost/preference creation or save workflow, confirmation
setup, seeding or deliberate Phase 6 deferral is recovered. No workaround is approved.
Formula conclusion: corroboration improves provenance of existing catalog principles and
historical-cost intent; no new normative invoice equation, rounding stages, manual-price rule
or detailed profit formula has been recovered.

Existing owner requests remain R-S (minimum supported provisioning/save surface and milestone),
R-F (formula/boundary/display/opening policies), R-P (supplier/overdue and sharing policies),
and R-G (exact guide/roadmap adoption and cost conflict). Recovered explicit records themselves
await formalization. No new product requirement or authority tier is added.

## Validation and next action

Executed documentation checks passed: packet fingerprint/three message blocks, 13 numbered
comparison rows, two explicit/one discussion classification, links, six source/test symbols,
whitespace/conflict markers and two-file scope. The complete diff was reviewed. Runtime tests
were not rerun or claimed. Application files match the immutable baseline; only the two audit
documents differ from starting HEAD. Final commit/clean-tree results are supplied in the handoff;
raw history and the temporary packet remain uncommitted.

Recommended next action only: obtain owner disposition of the existing R-F invoice-formula
and financial R-P questions, using explicit numerical examples and acceptance boundaries.
