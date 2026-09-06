# Source-of-truth governance

Implementation audit baseline: `2248c137e43c6c043725830c1303756da1d210ee`.
Audit/reconciliation date: 2026-09-07. This document is Tier E audit/navigation material. It does
not approve new product behavior or supersede AGENTS.md. The original continuity audit used
baseline material only. The later authorized reconciliation inspected exactly eight preserved
future-guide/manifest paths as supplemental CANDIDATE evidence, not baseline authority.

## Existing precedence — preserve, do not silently replace

AGENTS.md explicitly orders: (1) exact Phase 1 program requirements in PHASE_01.md;
(2) user-approved decisions in 04_DECISIONS.md; (3) 00_PROJECT_CONTRACT.md;
(4) current PHASE_XX.md; (5) 01_TECH_STACK.md; (6) compliant existing implementation;
(7) mechanical choices. Its no-invention and stop-on-conflict rules govern execution.

The requested A–E taxonomy below is explanatory classification, not a second precedence rule.
No source may silently override approved authority by invoking a tier label. For example, a
project-contract clause labelled A does not outrank an approved ledger decision labelled B;
AGENTS.md still places that decision above the project contract. An actual source conflict must
be recorded and affected implementation stopped under AGENTS.md, including conflicts within
one tier. Do not claim that naming a document a contract makes it binding.

The A–E labels do not establish a second, independently effective conflict-resolution order.
The approved AGENTS.md order remains in force. Any proposal to use tier ordering to change
that order remains CANDIDATE / REVIEW_REQUIRED; this audit does not reconcile it by fiat.
CT-001 is reconciled as documentation/provenance only: the continuity version already expressly
preserved this order, and this wording removes the potential misreading. No precedence-change
decision is needed to continue using AGENTS.md unchanged.

## Tier inventory and provenance

Paths in this inventory are repository-root-relative. Root contracts and implementation sources
are baseline inputs. New audit/navigation artifacts are Tier E outputs, not files claimed to have
existed at the implementation baseline. Recovered historical guides are explicitly identified separately.

| Tier | Actual sources | Why this authority / limitation applies |
|---|---|---|
| A — normative hard constraints | PHASE_01.md exact program requirements; non-negotiable clauses in 00_PROJECT_CONTRACT.md; approved invariant clauses in 04_DECISIONS.md such as D-008/010/011/019/031/034 | AGENTS.md explicitly binds the first two; the ledger explicitly records approved/locked decisions. A hard-constraint clause can be classified A even if its containing ledger is generally B. Do not upgrade untraced summaries. |
| B — approved product/architecture decisions | 04_DECISIONS.md D-001–D-042; locked technology clauses in 01_TECH_STACK.md; approved architecture clauses in 00_PROJECT_CONTRACT.md | The operating contract names these sources and their order. Approval provenance is the recorded repository ledger/contract, not independently recovered transcripts. |
| C — delivery intent | Current PHASE_03.md; PHASE_02.md; non-program delivery sections of PHASE_01.md; 02_PHASE_INDEX.md | Phase files define milestones, acceptance and gates under higher sources. Mandatory current-phase instructions remain requirements; C does not mean optional. Future phase summaries do not supply missing milestone specifications. |
| D — implementation evidence | apps/api/tawzeevo_api, apps/api/alembic, apps/operations-web, tests, compose.yaml, render.yaml, package manifests/locks, data/master-catalog | These show what exists and how it is configured. Code/tests/schema cannot independently approve product decisions; a test conflicting with an invariant is a finding, not an override. |
| E — derived operational state | 03_IMPLEMENTATION_STATUS.md; README files; docs/architecture.md; docs/folder-responsibilities.md; docs/future-phases.md; GUIDE_MANIFEST.md; RUN_TESTS.md; UNIT_TEST_STRATEGY.md; phase evidence and audit documents; AGENT_START_HERE.md | Status and reports are navigation/evidence. Frozen phase reports describe their dated state, not current implementation authority. Proposed test templates are not executed tests. |
| E — derived contract summaries | docs/contracts/README.md and its 15 linked summaries | Their own index explicitly says they restate root sources and lose conflicts. A sentence is binding only by its traceable higher source; the folder name does not grant independent authority. |
| E — historical/supporting | IMPLEMENTATION_MASTER_PROMPT.md, CHANGELOG_PLATFORM_ADMIN.md, demo-gallery docs, study HTML, and `docs/recovered-planning/` | Historical materials are not a current execution cursor. The recovered Phase 4–10 set is owner-supplied historical planning evidence, not authoritative specifications; its wrapper records compatibility, supersession and deferred gates. D-029 governs the demo, not its illustrative future screens. |

AGENTS.md is the governing operating contract rather than a product-evidence tier. Its milestone,
approval, safety, and precedence rules remain in force. 05_DESIGN_REFERENCES.md is the designated
UI-reference input under AGENTS.md, not a new source for financial or authorization rules; this
task performs no visual redesign.

## Origin and authority labels

- EXPLICIT: stated directly in a cited source. It is not necessarily approved: code can explicitly implement an unapproved rule.
- DERIVED: reviewer reconstruction/inference from sources. Keep CANDIDATE.
- PROPOSED: a possible change/decision not present as approved behavior. Keep CANDIDATE.
- BINDING: traceable to the existing approved authority named below. Do not mark newly inferred/proposed rules BINDING.
- CANDIDATE: requires review; may document an existing implementation choice without approving it.

VERIFIED traceability means evidence matches the specific scoped claim; it is not approval,
complete test coverage, a fresh runtime execution, or a production certification.

## Binding-rule index (summaries, not replacements)

Every row is EXPLICIT / BINDING solely through the listed baseline authority. Consult that source
for exact wording. Rules not in this compact index can still be binding in their original sources;
absence here does not remove a requirement.

| ID | Rule summarized | Traceable approved authority |
|---|---|---|
| B01 | Exact training routes, validation, admin/client checks and mandatory real frontend | PHASE_01.md A–D; D-001 |
| B02 | Public register creates client; users and storefront customers are distinct | PHASE_01.md A; 00_PROJECT_CONTRACT.md Identity / Customers; D-007/008/009 |
| B03 | Argon2id, in-memory access token, rotating hashed refresh, 15m/30d session policy and scoped HttpOnly cookie | PHASE_01.md C; D-026; 01_TECH_STACK.md Backend / Operations |
| B04 | System admin is not tenant owner; active membership and tenant lifecycle precede business access | 00_PROJECT_CONTRACT.md Multi-tenancy / Platform administration; D-007/022 |
| B05 | Explicit tenant IDs, tenant predicates and RLS; active tenants retain a usable owner | 00_PROJECT_CONTRACT.md Multi-tenancy; PHASE_01.md A/C; PHASE_03.md A/M |
| B06 | Suspension preserves data; manual access control is not automatic billing | 00_PROJECT_CONTRACT.md Tenant lifecycle; D-023 |
| B07 | No stock, availability, automatic customer merging or per-purchase supplier payment allocation | 00_PROJECT_CONTRACT.md exclusions; D-010/019/020 |
| B08 | Customer duplicate-phone disambiguation; categories/master/tenant catalog and barcode separation | PHASE_02.md Required domain behavior; 00_PROJECT_CONTRACT.md Customers / Catalog |
| B09 | Grades A+, A, B+, B; explicit grade price before percentage before normal, round basis then counterpart | D-030; PHASE_02.md Pricing; 00_PROJECT_CONTRACT.md Grades |
| B10 | Backend Decimal, NUMERIC(20,4), Q4 HALF_UP, no silent currency aggregation/conversion | 01_TECH_STACK.md Money; PHASE_03.md A; D-030/034 |
| B11 | Header is identity; immutable revision is financial truth; confirmed edits append revision and ledger delta | PHASE_03.md A/B/E; D-011 |
| B12 | One optional order per invoice; at most one header per order | D-033; PHASE_03.md Gate C / B |
| B13 | Latest eligible tenant-private supplier cost and reasoned override; immutable historical cost provenance | D-031/034; PHASE_03.md B |
| B14 | Server tenant/year invoice numbering; replay does not duplicate charge or number | PHASE_03.md C/E |
| B15 | Per-currency ledger balance; opening balance is not sales; payments/allocations immutable, reversible and FIFO by default | 00_PROJECT_CONTRACT.md Financial truth; PHASE_03.md F/H |
| B16 | Cancellation preserves payment history; refunds are separate, credit-limited and serialized | PHASE_03.md I; 00_PROJECT_CONTRACT.md Financial truth |
| B17 | Public token >=256 random bits, SHA-256 only, 90-day default, expiry/revocation/rotation, privacy projection/headers/no logs/rate limiting | PHASE_03.md J; 00_PROJECT_CONTRACT.md Public invoice access |
| B18 | WhatsApp uses normalized phone, summary and capability URL; PDF not mandatory | PHASE_03.md J |
| B19 | Provider-neutral validated/re-encoded JPEG/PNG/WebP media; no SVG | PHASE_02.md Media; 01_TECH_STACK.md Media |
| B20 | Curated names/barcodes/categories only from approved ODbL subset; provenance, attribution, compatible catalog sharing, no imported source images | D-032; PHASE_02.md Master catalog import |
| B21 | FastAPI, sync SQLAlchemy, PostgreSQL, React/Vite now; Next.js storefront beginning Phase 5 | D-002–006; 01_TECH_STACK.md |
| B22 | Hosted PostgreSQL/direct API-owned auth, recorded Render deployment choice; no Supabase Auth/Data API dependency | D-027/028 |
| B23 | Future guest checkout, owner cancellation/delivery decisions, no tracking; owner-as-operator/driver least privilege | 00_PROJECT_CONTRACT.md Order / Location; D-009/012/013/014/021 |
| B24 | Future offline protocol, encrypted Drive backup not live DB, scope/provider approvals, analytics currency/timezone gate, forecasting last | 00_PROJECT_CONTRACT.md Offline / Google / Analytics / AI; 02_PHASE_INDEX.md Gates D/F/G; D-017/018 |
| B25 | One milestone per continuation; explicit phase transitions; immutable applied migrations; tests/evidence before completion; no unauthorized push | AGENTS.md execution/completion/safety rules; PHASE_03.md M |
| B26 | Synthetic frontend-only removable role gallery; no production role/API/data changes | D-029 |
| B27 | Manual non-catalog invoice price is final; fixed line/invoice adjustments and the exact Q4 invoice formula | D-035/036 |
| B28 | Immutable revision due snapshot is distinct from live customer balance | D-037 |
| B29 | One initial opening per party/currency; later changes use immutable correction/reversal; initial sign remains review-required | D-038 |
| B30 | Ordinary supplier payment is payable-capped; excess uses a separate labelled prepayment action | D-039 |
| B31 | Customer overdue uses the `Asia/Beirut` calendar, `age_days > threshold`, and unset disables detection | D-040 |
| B32 | Dedicated owner supplier/product-cost API/UI is required before Phase 3 completes | D-041 |
| B33 | One active confirmed-invoice public link; replacement invalidates the old link and cancellation revokes it; fragment/header transport remains | D-042 |

## Candidate decisions and conflicts

CT-004 and CT-005 in [the register](../audits/AUDIT_REGISTER.md) distinguish resolved decisions
now recorded as D-035–D-042 from remaining candidates. The remaining zero/sign admission rules,
initial-opening sign, exact rate-limit constants, durable notification cadence and later-phase gate
details are not approved merely because code or historical planning contains them. Approval must
follow the existing user-decision process. Same-tier disagreement is left open; implementation
evidence is not used as the deciding vote.

The register's narrow reconciliation distinguishes approved facets, ordinary mechanics, and
material policy questions. Classifying a detail as mechanical does not create a BINDING product
rule. Most formula, supplier-provisioning, public-link, overpayment and overdue policy questions
are now explicitly decided in D-035–D-042. RP-NOW-01 and RP-NOW-02 remain review-required,
while named future-phase details safely wait for their phase gates.

The tracked recovered manifest describes generated consolidated guides, cites an absent frozen
roadmap, and supplies no independently traceable approval of their added details. All seven
future guides remain historical CANDIDATE / REVIEW_REQUIRED evidence, not authoritative root
phase files.
In particular, the preserved Phase 8 profit-cost precedence cannot supersede D-031/D-034.
See CT-002's per-file blob/provenance inventory; recovering a file is not approving its contents.

## Implementation baseline versus documentation HEAD

The immutable implementation reference remains `2248c137e43c6c043725830c1303756da1d210ee`.
The original continuity documentation commit is
`f4bb7fd7f1ba86821b87b6c15b17a7694ed0328b` (`docs(audit): establish Tawzeevo continuity baseline`).
The later narrow reconciliation is a separate documentation commit identified by Git history
(`docs(audit): reconcile continuity requirements and decisions`) and its handoff. Obtain current
HEAD using `git rev-parse HEAD`; do not substitute it for the implementation reference. A document
cannot truthfully embed its own final commit hash before that commit exists.
