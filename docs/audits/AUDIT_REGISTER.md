# Continuity audit register

Implementation audit baseline: `2248c137e43c6c043725830c1303756da1d210ee`.
Audit date: 2026-09-06. Tier E. All reviewer inferences/recommendations are DERIVED / CANDIDATE.
This is continuity/authority reconstruction, not the financial/security/architecture-hardening audit.

Current disposition: the subsequent narrow requirements/decision reconciliation is complete.
Its input documentation commit is `f4bb7fd7f1ba86821b87b6c15b17a7694ed0328b`; application
evidence still refers to the implementation baseline above. Authorized read-only inspection of
eight preserved future-guide/manifest blobs is explicitly separated from approved authority below.
The original continuity result was CONDITIONAL PASS; the narrow reconciliation result is PASS
under its criteria allowing explicit REVIEW_REQUIRED/CANNOT VERIFY dispositions.

## Register conventions

P0 = immediate catastrophic issue established; P1 = blocks a material continuation/workflow or
required provenance; P2 = scoped gap/risk requiring review; P3 = low-impact clarification.
Severity is reviewer triage, not a new product invariant. No P0 was established; absence of a P0
in this bounded audit is not proof no P0 exists.

Counts: 10 meaningful findings: 0 P0, 3 P1, 7 P2, 0 P3. No findings were created to fill severity buckets.
These are retained finding severities, not an open-only count. CT-001 is now reconciled as
documentation-only; the three P1 findings remain open, as do six other P2 findings.
Each record includes the requested schema, including unknown/not-run fields rather than invented
independent verification. Source/model attribution is neutral under D-025; no model brand is made
part of public project authority.

## Findings

### CT-001 — Governance

| Field | Record |
|---|---|
| ID | CT-001 |
| Audited commit | `2248c137e43c6c043725830c1303756da1d210ee` |
| Area | Governance |
| Claim | The requested A–E tier ordering is not identical to AGENTS.md's existing source precedence. The ledger ranks above the project contract in AGENTS.md, while a simple A-contract/B-ledger reading would invert that order. |
| Evidence | AGENTS.md Source-of-truth precedence; 04_DECISIONS.md opening approval rule; docs/contracts/README.md explicit subordination. The audit governance document records the collision without changing AGENTS.md. |
| Affected requirement/invariant | B25; T61; handling of conflicting hard constraints and later approved decisions. |
| Severity | P2 |
| Confidence | HIGH for source ordering; MEDIUM for future conflict impact |
| Source/model | Repository-only continuity reviewer; model identifier not recorded; not product authority. |
| Origin / Authority | DERIVED / CANDIDATE |
| Independent verification | Both texts and continuity commit rechecked: SOURCE_OF_TRUTH expressly preserves AGENTS.md and denies an independently effective second order. No current source-order contradiction is established. No second independent reviewer. |
| Disagreement | Not independently assessed; user disposition not yet recorded. |
| Resolution | RECONCILED — explanatory classification only; wording clarified without changing AGENTS.md precedence. |
| Resolution rationale | A classification document cannot silently amend the operating contract. |
| Decision impact | No new decision is needed to follow existing precedence. Only a future proposal to replace that order would be CANDIDATE / REVIEW_REQUIRED. Tier labels never settle a conflict independently. |
| Regression-test reference | N/A — governance provenance, not an application test. |
| Fix commit | None (no application fix). Documentation-only clarification, if any, is recorded by this audit commit. |
| Verification commit | Implementation evidence at 2248c137e43c6c043725830c1303756da1d210ee; no independent fix-verification commit. |
| Status | RECONCILED_DOCUMENTATION_ONLY |

### CT-002 — Future delivery continuity

| Field | Record |
|---|---|
| ID | CT-002 |
| Audited commit | `2248c137e43c6c043725830c1303756da1d210ee` |
| Area | Future delivery continuity |
| Claim | At the immutable implementation baseline, a repository-only successor could not safely execute through Phase 10 because PHASE_04.md–PHASE_10.md were absent. |
| Evidence | Baseline inventory and preservation report; later authorized inspection of exactly PHASE_04–10 and their manifest from stash parent 068bb2ec38e66c1143b87d7f766cf38b9d896c2b. The manifest calls them generated consolidated guides and cites an absent frozen roadmap. Per-file blobs, added-detail examples and Phase 8 cost conflict are recorded below. |
| Affected requirement/invariant | B24/B25; T57; required current-phase specification before implementation. |
| Severity | P1 |
| Confidence | HIGH |
| Source/model | Repository-only continuity reviewer; model identifier not recorded; not product authority. |
| Origin / Authority | DERIVED / CANDIDATE |
| Independent verification | Original continuity pass did not open the stash. This reconciliation read only the eight allowlisted planning/manifest paths; no study content or other stash payload was read. No independent second reviewer or original approval transcript is available. |
| Disagreement | Owner supplied the historical set, approved the remaining current decisions, and directed creation of reconciled authoritative specifications without promoting the historical copies. |
| Resolution | CLOSED. Root PHASE_04.md–PHASE_10.md now preserve compatible requirements, apply later approved authority and mark remaining phase-specific choices `REVIEW_REQUIRED`. |
| Resolution rationale | The historical set remains provenance only. D-031/D-034 supersede Phase 8 later-cost historical-profit logic; D-035–D-043 and the reconciliation wrapper govern other corrections. Root specifications and phase gates no longer depend on the missing frozen roadmap. |
| Decision impact | Future work uses root phase specifications only, after explicit `Start Phase N` and satisfaction of each gate. Historical copies never override later decisions. |
| Regression-test reference | N/A — file-presence/preservation check. |
| Fix commit | None (no application fix). Documentation-only clarification, if any, is recorded by this audit commit. |
| Verification commit | Implementation evidence at 2248c137e43c6c043725830c1303756da1d210ee; no independent fix-verification commit. |
| Status | CLOSED — FUTURE SPECIFICATIONS FORMALIZED; PHASE GATES STILL APPLY |

### CT-003 — New-tenant finance workflow

| Field | Record |
|---|---|
| ID | CT-003 |
| Audited commit | `2248c137e43c6c043725830c1303756da1d210ee` |
| Area | New-tenant finance workflow |
| Claim | Supplier/cost schema and selection work with test fixtures, but the baseline lacks a supported owner-facing or documented CLI path to create supplier identities/cost entries/preferred-supplier defaults. A newly onboarded tenant cannot complete the described normal confirmation flow from setup alone. |
| Evidence | services/invoice_editor.py::_prepare_cost requires an existing supplier even for an override; services/invoice_finance.py::_validate_confirmable_costs rejects absent supplier/cost; routes/invoices.py exposes cost-options GET, not cost creation. InvoiceEditor.tsx shows cost controls only when options exist; seed_demo has no supplier/cost setup. Corrected fixture anchor: _attach_latest_cost and the dedicated cost-prefill test insert prerequisites directly; _catalog itself uses catalog/customer APIs. test_supplier_ledger.py::_supplier_context also inserts directly. |
| Affected requirement/invariant | D-034; PHASE_03.md B/D/L; T32–T34/T60. |
| Severity | P1 |
| Confidence | HIGH for missing surface and D-041 Phase 3 ownership |
| Source/model | Repository-only continuity reviewer; model identifier not recorded; not product authority. |
| Origin / Authority | DERIVED / CANDIDATE |
| Independent verification | Route, schema, CLI, UI and fixture inventory inspected. No new end-to-end or hosted reproduction performed. No second independent reviewer has verified this finding. |
| Disagreement | Not independently assessed; user disposition not yet recorded. |
| Resolution | PARTIAL overall: minimum schema/selection/override exists; supported fresh-tenant provisioning remains MISSING. D-041 resolves the owner-facing surface and Phase 3 ownership. No workaround implemented. |
| Resolution rationale | D-034 plus PHASE_03 B require minimum cost-entry foundation and usable confirmed-line provenance in Phase 3; Phase 6 may append automatically, not supply an explicitly authorized prerequisite deferral. Specific supplier CRUD screen/endpoint placement is not prescribed by a current approved milestone. |
| Decision impact | Required remediation, when authorized: make the existing tenant-private supplier/cost/preference foundation establishable through a supported authorized workflow and prove fresh-tenant invoice confirmation and explicit new-cost saving without direct fixture writes. Confirm the minimum surface/milestone boundary first; preserve D-034 validation and do not pull full procurement forward. |
| Regression-test reference | test_invoice_editor.py::test_editor_prefills_latest_tenant_cost_and_keeps_reasoned_override_revision_only; test_financial_schema.py::test_supplier_costs_are_tenant_private_append_only_and_independently_priced. No cold-start provisioning regression found. |
| Fix commit | None (no application fix). Documentation-only clarification, if any, is recorded by this audit commit. |
| Verification commit | Implementation evidence at 2248c137e43c6c043725830c1303756da1d210ee; no independent fix-verification commit. |
| Status | PARTIAL / MISSING_PROVISIONING — BLOCKS_AFFECTED_WORKFLOW; DECISION RESOLVED |

### CT-004 — Financial formula provenance — no financial audit performed

| Field | Record |
|---|---|
| ID | CT-004 |
| Audited commit | `2248c137e43c6c043725830c1303756da1d210ee` |
| Area | Financial formula provenance — no financial audit performed |
| Claim | The immutable baseline lacked approved complete invoice-adjustment and opening-boundary provenance; later owner decisions now supply it. |
| Evidence | D-030; PHASE_03 Gate C/A/B/D/E/F/H/I/N; components F01–F15 below distinguish explicit equations, actual code, test assertions and missing provenance. _prepare_items/_totals implement fixed amounts and intermediate rounding. confirm_invoice rejects initial zero net sales, while confirmed edits can reach zero. Tests establish examples, not approval. No recovered future authority supplies the missing formula. |
| Affected requirement/invariant | B09/B10/B11; T26/T35; no-invention rule for financial formulas. |
| Severity | P1 |
| Confidence | HIGH for catalog formula; MEDIUM for missing full invoice provenance |
| Source/model | Repository-only continuity reviewer; model identifier not recorded; not product authority. |
| Origin / Authority | DERIVED / CANDIDATE |
| Independent verification | Tracked normative Markdown searched for pricing-v1/formula/net_sales/discount/Q4; relevant service and test anchors inspected. No chat or study document treated as authority. No second independent reviewer has verified this finding. |
| Disagreement | Not independently assessed; user disposition not yet recorded. |
| Resolution | FORMULA AUTHORITY RESOLVED; IMPLEMENTATION CONTRADICTED for the identified zero-revision and opening-multiplicity paths. |
| Resolution rationale | D-035–D-037 lock manual price, fixed adjustments, Q4 stages and displayed due. D-038 locks one signed nonzero historical opening/corrections. D-043 locks positive confirmed net sales and nonnegative boundaries. |
| Decision impact | The financial audit can assess exact compliance without inventing these rules. Remediation remains separately unauthorized. |
| Regression-test reference | test_cash_van.py::test_pricing_v1_precedence_rounding_packaging_and_invoice_snapshot; test_invoice_editor.py::test_editor_recalculates_pricing_v1_calculator_adjustments_and_immutable_updates. |
| Fix commit | None (no application fix). Documentation-only clarification, if any, is recorded by this audit commit. |
| Verification commit | Implementation evidence at 2248c137e43c6c043725830c1303756da1d210ee; no independent fix-verification commit. |
| Status | AUTHORITY_RESOLVED / IMPLEMENTATION_REVIEW_REQUIRED |

### CT-005 — Implicit policy / P3-M5 post-hoc review

| Field | Record |
|---|---|
| ID | CT-005 |
| Audited commit | `2248c137e43c6c043725830c1303756da1d210ee` |
| Area | Implicit policy / P3-M5 post-hoc review |
| Claim | P3-M5 introduced observable policy/architecture choices that lacked approval at the baseline; later owner decisions now resolve the material supplier/overdue/public-link behavior. |
| Evidence | PHASE_03.md J/H/P3-M5; 04_DECISIONS.md; services/public_invoices.py; public_invoice_security.py; schemas/public_invoices.py; routes/public_invoices.py; services/supplier_ledger.py; schemas/supplier_ledger.py; templates/public_invoice.html; InvoiceSharing.tsx; candidate table C01–C08. |
| Affected requirement/invariant | B17/B18/B15; T41/T47–T52/T61. |
| Severity | P2 |
| Confidence | HIGH for code behavior; MEDIUM for absence of approval |
| Source/model | Repository-only continuity reviewer; model identifier not recorded; not product authority. |
| Origin / Authority | DERIVED / CANDIDATE |
| Independent verification | Governing text compared with current implementation and scoped tests. No external or independent reviewer approval inferred. No second independent reviewer has verified this finding. |
| Disagreement | Not independently assessed; user disposition not yet recorded. |
| Resolution | CORE DECISIONS RESOLVED through D-039–D-042; current contrary code is an implementation mismatch. Exact rate-limit constants and durable alert cadence remain explicitly deferred. |
| Resolution rationale | An architectural or business-policy choice needs traceable authority; some may prove acceptable mechanical details after review. |
| Decision impact | Audit current behavior against D-039–D-042 before remediation. Exact rate-limit constants and durable alert cadence remain gated; ordinary rendering/CSP/text mechanics need no product redesign. |
| Regression-test reference | test_public_invoices.py; test_supplier_ledger.py; InvoiceSharing.test.tsx; PublicInvoicePage.test.ts; overdue tests for C08. |
| Fix commit | None (no application fix). Documentation-only clarification, if any, is recorded by this audit commit. |
| Verification commit | Implementation evidence at 2248c137e43c6c043725830c1303756da1d210ee; no independent fix-verification commit. |
| Status | CORE_DECISIONS_RESOLVED / IMPLEMENTATION_REVIEW_REQUIRED |

### CT-006 — Stale/duplicate documentation

| Field | Record |
|---|---|
| ID | CT-006 |
| Audited commit | `2248c137e43c6c043725830c1303756da1d210ee` |
| Area | Stale/duplicate documentation |
| Claim | Baseline navigation and architecture contain stale Phase 1-only/current-phase claims and incomplete contract summaries. A cold reader could restart Phase 2 or miss the production revision model. |
| Evidence | Baseline docs/architecture.md ends at draft invoices and migration 0003; docs/future-phases.md says next Start Phase 2; UNIT_TEST_STRATEGY.md says Phase 2 locked; docs/contracts/pricing.md says no later grade/confirmed engine; tenant-isolation.md still names removed invoice_items; api-conventions.md says all tenant resources are nested despite PHASE_03.md K finance groups; GUIDE_MANIFEST.md lists absent ROOT_GUIDE_README.md/future guides. 03 status claims no blockers/deviations despite newly identified audit uncertainty. |
| Affected requirement/invariant | B25; T18/T56; delivery/implementation separation. |
| Severity | P2 |
| Confidence | HIGH |
| Source/model | Repository-only continuity reviewer; model identifier not recorded; not product authority. |
| Origin / Authority | DERIVED / CANDIDATE |
| Independent verification | Files compared against phase status, code/routes, migrations and baseline inventory. No second independent reviewer has verified this finding. |
| Disagreement | Not independently assessed; user disposition not yet recorded. |
| Resolution | PARTIAL DOCUMENTATION CLARIFICATION — existing architecture reconstructed, entry/governance links added, status overlay and historical future-summary warning added, manifest corrected. Frozen reports/contract summaries/unit strategy remain historical; no product contradiction silently resolved. |
| Resolution rationale | Reuse existing equivalents, annotate stale evidence, and retain the immutable baseline rather than rewrite history or duplicate every root document. |
| Decision impact | Use original sources and current traceability, not stale derived prose. Candidate/product conflicts remain open even after navigation improves. |
| Regression-test reference | Documentation path/status/marker checks; no application regression required for these prose-only changes. |
| Fix commit | None (no application fix). Documentation-only clarification, if any, is recorded by this audit commit. |
| Verification commit | Implementation evidence at 2248c137e43c6c043725830c1303756da1d210ee; no independent fix-verification commit. |
| Status | DOCUMENTED_WITH_REMAINDER |

### CT-007 — Test evidence and portability

| Field | Record |
|---|---|
| ID | CT-007 |
| Audited commit | `2248c137e43c6c043725830c1303756da1d210ee` |
| Area | Test evidence and portability |
| Claim | The passing Windows baseline gate is not a full Phase 3 real-browser E2E/accessibility/CI certification. Backend tests have hidden disposable-database/role privileges and Windows-specific migration-test path construction. |
| Evidence | No tracked Playwright suite/config or .github CI workflow found; Vitest tests mock fetch/jsdom. tests/conftest.py autouse TRUNCATE; test_hardening.py::test_migrations_build_a_new_database_from_zero and test_financial_schema.py::test_phase2_draft_rows_upgrade_to_revisions_and_round_trip create/drop databases and use __file__.replace with Windows backslashes; RLS tests create roles. PHASE_03.md P3-M6 owns phase-wide evidence. |
| Affected requirement/invariant | PHASE_03.md N/P3-M6; 01_TECH_STACK.md Testing; T17/T55. |
| Severity | P2 |
| Confidence | HIGH for files inspected; MEDIUM for unexecuted cross-platform outcome |
| Source/model | Repository-only continuity reviewer; model identifier not recorded; not product authority. |
| Origin / Authority | DERIVED / CANDIDATE |
| Independent verification | Static test/command inspection and existing dated gate record; no cross-platform or new runtime suite run in this audit. No second independent reviewer has verified this finding. |
| Disagreement | Not independently assessed; user disposition not yet recorded. |
| Resolution | OPEN / PLANNED PHASE WORK — no tests, privileges, CI or path construction changed. |
| Resolution rationale | A generic test command may skip with no DB or fail on inadequate privileges; an absent future acceptance lane is not newly invented scope. |
| Decision impact | Documented here for safe execution; separately authorize P3-M6 and its portability/E2E checks. Never grant test cleanup privileges to production to make a run pass. |
| Regression-test reference | test_hardening.py; test_financial_schema.py; apps/operations-web/src/*test*; RUN_TESTS.md. |
| Fix commit | None (no application fix). Documentation-only clarification, if any, is recorded by this audit commit. |
| Verification commit | Implementation evidence at 2248c137e43c6c043725830c1303756da1d210ee; no independent fix-verification commit. |
| Status | PLANNED_NOT_STARTED |

### CT-008 — Dependency reproducibility

| Field | Record |
|---|---|
| ID | CT-008 |
| Audited commit | `2248c137e43c6c043725830c1303756da1d210ee` |
| Area | Dependency reproducibility |
| Claim | The audited locked environment is reproducible, but normal README/Render backend install commands are not tied to it, and the two backend lock artifacts differ. |
| Evidence | render.yaml buildCommand pip install .; root/API README pip install -e apps/api[dev]; pyproject.toml ranges; requirements.lock older snapshot lacks Pillow/python-multipart and has Ruff 0.16.3, whereas uv.lock includes current dependencies/Ruff 0.16.4. baseline-remediation.md used uv sync --locked --extra dev. npm ci uses package-lock.json. |
| Affected requirement/invariant | 01_TECH_STACK.md Dependencies and versions; T58. |
| Severity | P2 |
| Confidence | HIGH |
| Source/model | Repository-only continuity reviewer; model identifier not recorded; not product authority. |
| Origin / Authority | DERIVED / CANDIDATE |
| Independent verification | Committed manifest/lock/command comparison. No package upgrade, installation or external package lookup performed. No second independent reviewer has verified this finding. |
| Disagreement | Not independently assessed; user disposition not yet recorded. |
| Resolution | OPEN — lockfiles and deployment commands unchanged. |
| Resolution rationale | Do not silently choose a new dependency source or rollout policy during continuity documentation. |
| Decision impact | Reconcile supported install/deploy lock policy before relying on deployment equivalence. Current audit reproduction should use the recorded locked workflow. |
| Regression-test reference | Prior clean-checkout gate only; no deployed install parity regression exists. |
| Fix commit | None (no application fix). Documentation-only clarification, if any, is recorded by this audit commit. |
| Verification commit | Implementation evidence at 2248c137e43c6c043725830c1303756da1d210ee; no independent fix-verification commit. |
| Status | OPEN_CANDIDATE |

### CT-009 — Hosted runtime and media evidence

| Field | Record |
|---|---|
| ID | CT-009 |
| Audited commit | `2248c137e43c6c043725830c1303756da1d210ee` |
| Area | Hosted runtime and media evidence |
| Claim | Repository topology is reconstructable, but deployed database roles/grants, migration application, cookie/origin behavior, token telemetry and durable media cannot be certified from the baseline. |
| Evidence | D-027/028 record direct hosted PostgreSQL and Render choices. render.yaml has pip install/start, /health probe and no migration step. config.py validates production JWT/cookie settings; README uses several localhost/127.0.0.1 examples. services/media.py is local storage; media-security.md warns about ephemeral hosting. RLS tests use special non-bypass roles but actual application role/grants are external. |
| Affected requirement/invariant | B03/B05/B17/B19/B22; T27/T50/T59/T60. |
| Severity | P2 |
| Confidence | HIGH for configuration; CANNOT VERIFY live state |
| Source/model | Repository-only continuity reviewer; model identifier not recorded; not product authority. |
| Origin / Authority | DERIVED / CANDIDATE |
| Independent verification | Static files only; no hosted dashboard, secrets, live SQL, logs, messaging or network verification. No second independent reviewer has verified this finding. |
| Disagreement | Not independently assessed; user disposition not yet recorded. |
| Resolution | OPEN / CANNOT VERIFY — no runtime/provider/configuration changes. |
| Resolution rationale | Local tests and intended env names do not prove actual deployed security or persistence. Supabase Auth/Data API are not application dependencies; their live exposure settings still cannot be inferred. |
| Decision impact | A separately authorized deployment/security verification must establish actual role/grants/migration/readiness/cookie/log/media behavior before production assurance. No provider choice made here. |
| Regression-test reference | test_auth.py::test_production_settings_require_secure_cookie_and_real_secret; local RLS/public log/media tests; no live verification. |
| Fix commit | None (no application fix). Documentation-only clarification, if any, is recorded by this audit commit. |
| Verification commit | Implementation evidence at 2248c137e43c6c043725830c1303756da1d210ee; no independent fix-verification commit. |
| Status | CANNOT_VERIFY |

### CT-010 — Baseline-remediation provenance

| Field | Record |
|---|---|
| ID | CT-010 |
| Audited commit | `2248c137e43c6c043725830c1303756da1d210ee` |
| Area | Baseline-remediation provenance |
| Claim | The final documentation checkpoint changes no runtime code relative to 1097593, and the documented Ruff/content-guard treatment is non-domain. However, Git cannot independently isolate all remediation from the earlier uncommitted implementation bundled into 1097593. |
| Evidence | git diff 1097593..2248c13 lists exactly 03_IMPLEMENTATION_STATUS.md, RUN_TESTS.md and docs/phase-3/baseline-remediation.md. Commit 1097593 includes prerequisite/P3-M5 implementation and remediation together; parent dac294a is Phase 2 core, not a pre-remediation P3-M5 snapshot. pyproject.toml exceptions and tests/test_immutable_migration_files.py inspected. Report records before/after fingerprints; an independently committed pre-remediation application tree is absent. |
| Affected requirement/invariant | T53; baseline report 'no application behavior changed' claim; reproducible provenance. |
| Severity | P2 |
| Confidence | HIGH for committed diff; LIMITED for pre-remediation uncommitted state |
| Source/model | Repository-only continuity reviewer; model identifier not recorded; not product authority. |
| Origin / Authority | DERIVED / CANDIDATE |
| Independent verification | Original continuity investigation: exact Git diff and config/guard inspection, without stash parent/untracked payload access. The later narrow guide inspection does not reconstruct pre-remediation application history. Earlier fingerprints remain report evidence, not independently recreated. No second independent reviewer. |
| Disagreement | Not independently assessed; user disposition not yet recorded. |
| Resolution | OPEN EVIDENCE LIMIT — retain supplied immutable baseline; do not rewrite history or infer additional approval. |
| Resolution rationale | Practical verification supports the narrow treatment but cannot manufacture a missing historical snapshot. |
| Decision impact | Audit existing behavior against authority, not an assumed clean P3-M5-only diff. This does not change AUDIT_BASE_SHA or alone invalidate the prior test results. |
| Regression-test reference | test_immutable_migration_files.py; prior baseline test report; exact documentation-only tree comparison. |
| Fix commit | None (no application fix). Documentation-only clarification, if any, is recorded by this audit commit. |
| Verification commit | Implementation evidence at 2248c137e43c6c043725830c1303756da1d210ee; no independent fix-verification commit. |
| Status | CANNOT_VERIFY_FULL_HISTORY |

## Initial continuity candidate inventory — historical, never binding from this audit

All rows are DERIVED / CANDIDATE observations. The general requirement cited may be binding;
the specific implementation choice is not promoted with it. No row authorizes a change.
The later C01–C08 disposition table below is the current review status; it resolves some facets
as ordinary mechanics without deleting the original observation or approving new product rules.

| ID | Existing choice | Governing explicit requirement versus unapproved detail | Evidence and review question |
|---|---|---|---|
| C01 | 60 requests/IP/60s, 4,096 clients, fail-closed map, per-process shell+data counting | PHASE_03 J requires rate limiting, not these thresholds/topology | PublicInvoiceRateLimiter and middleware. Are these operational limits approved, and what deployment assumptions govern them? No new provider proposed. |
| C02 | Tenant UUID prefix plus 256-bit secret; fragment-to-X-Invoice-Capability transport; secret cleared on load | J requires secret authorization/no logs, not token format or reload behavior | issue_capability/resolve_public_invoice and public HTML. Review URL/header/tenant-hint public contract; prefix alone never authorizes. |
| C03 | FastAPI serves public bilingual HTML with hashed-script CSP; secret header manually read and absent as formal OpenAPI parameter | J requires safe customer invoice; D-005/stack specify later Next.js storefront, not this interim page's renderer | routes/public_invoices.py, package template data, PublicInvoicePage tests. Not automatically a Next.js violation; clarify integration/documented public contract. |
| C04 | Repeated create allows multiple active links; rotation replaces one selected link; create has no idempotency key | J requires expiry/revocation/rotation but gives no active-link cardinality/retry rule | issue_capability; PublicInvoiceCapability uniqueness only for hash/rotation parent. Review create retry/cardinality policy without inventing single-link behavior. |
| C05 | Draft and cancelled invoices remain shareable; links resolve current revision, not issuance snapshot or payment state | J explicitly allows current invoice representation; lifecycle eligibility is not explicitly locked | No status check in issue/resolve; template labels DRAFT/CANCELLED; current-revision test. Current revision is traceable; draft/cancelled eligibility and post-cancel link policy require review. |
| C06 | Signed supplier opening entries; payments may exceed/no-match payable and create negative balance; full compensating reversal only | D-019/J/H require aggregate payable/payment foundation, not supplier prepayment/refund ceiling or opening-entry multiplicity | record_supplier_payment never compares balance; SupplierOpeningRequest accepts nonzero signed amount; reverse_supplier_payment preserves amount. Existing test pays 7 of 20, not overpayment. Review business semantics, do not infer customer refund rules for suppliers. |
| C07 | Public projection selects business/customer names, current line prices/totals but no phone/address/payment status; missing phone permits link, disables WhatsApp; summary bilingual | J lists permissible safe categories and normalized phone/summary/link; exact minimum projection/summary is not fully enumerated | PublicInvoiceResponse, issue_capability, InvoiceSharing. Privacy omissions fit upper-bound allowlist; review any expected customer-facing minimum, not permission to add private fields. |
| C08 | Earlier P3-M3 debt alerts are read-time stable keys, threshold unset means no overdue, UTC-date calculation, no persisted scheduling | PHASE_03 G requires deduplicated in-app alert according to policy; jobs summary mentions timezone without selecting runtime | customer_debts and debt desk; not introduced by P3-M5. Clarify cadence/persistence/timezone policy before any worker/job work. |

The fixed invoice-adjustment units/order/rounding in CT-004 are also DERIVED / CANDIDATE beyond
the explicitly approved D-030 catalog rule. C01–C08 are review questions, not a list of compulsory
changes. No customer accounts, stock, supplier per-purchase allocations or other new scope is proposed.

## Original continuity preservation and scope checks (historical)

The stash reference `9050d544791b5e22d15c2ff1a1acdbd503b40418` was read only as an object ID.
No stash content was opened, applied, popped, modified, dropped, or incorporated. Exclusion details
come exclusively from the existing baseline-remediation report. Future guides are not audit inputs.

The implementation baseline was not amended/rebased/rewritten. Only documentation changes are
permitted in this audit commit. Existing phase specifications, decision ledger, applied migrations,
application/tests, dependency/configuration files and frozen phase reports are not edited.
This commit does not start P3-M6 or approve any candidate decision.

## Original continuity documentation verification (historical)

Executed 2026-09-06:

- PASS: the final expanded check resolves 190 unique explicit traceability file/symbol references against baseline paths, including named authority/evidence documents and referenced Python functions/classes. The temporary extractor recognizes digits in identifiers and uses the documented frontend manifest path; no project code was changed.
- PASS: all 33 local Markdown links in the nine audit documents resolve to existing files or directories. This checks local targets, not browser-rendered heading fragments.
- PASS: 62 unique traceability rows; 51 VERIFIED, 5 PARTIAL, 3 CANNOT VERIFY, 2 MISSING, 1 CONTRADICTED.
- PASS: all 10 findings carry the 18 requested register fields; severity counts are 0 P0 / 3 P1 / 7 P2 / 0 P3.
- PASS: no conflict markers in audit documents; `git diff --check` passed.
- PASS: current pre-commit HEAD equals the implementation baseline; `git rev-parse refs/stash` still returns the preserved object ID. Only nine explicitly selected Markdown paths changed; no source/tests/migrations/configuration or dependency inputs changed.
- Reviewed: each BINDING summary has a cited approved baseline source; all new inferences/decisions remain CANDIDATE. The governance ordering conflict remains explicit; no decision-ledger amendment occurred.

Application tests were not rerun for this prose-only task. The prior baseline gate is evidence,
not a claimed new execution. Reproduce the repository boundary checks with:

```powershell
git diff 2248c137e43c6c043725830c1303756da1d210ee HEAD --check
git diff 2248c137e43c6c043725830c1303756da1d210ee HEAD --name-only
git status --porcelain=v1
git rev-parse refs/stash
```

After the documentation commit, the named diff must contain only the nine Markdown files listed
in the handoff. The implementation reference remains the full SHA above, not the documentation
HEAD. Use Git history/handoff for the documentation commit ID, avoiding self-reference.

## Original continuity assessment (historical)

CONDITIONAL PASS for this documentation handoff: reference, metadata, provenance and scope
checks pass, and the complete documentation diff has been reviewed. This is not an unqualified
pass for autonomous continuation through Phase 10, nor a renewed implementation acceptance gate.
CT-002 blocks detailed future-phase implementation; CT-003 blocks the affected fresh-tenant
finance workflow; CT-004 blocks claiming complete invoice-formula approval. Governance and
implicit policy candidates remain review-required. No finding is implemented or approved here.
Existing architecture/status documents were reused; authoritative history and the implementation
baseline were not rewritten. No independent second-reviewer or new runtime validation is claimed.

## Narrow reconciliation — 2026-09-06

Scope: CT-001–CT-005 only. Initial HEAD was the clean continuity documentation commit
`f4bb7fd7f1ba86821b87b6c15b17a7694ed0328b`. Implementation remains
`2248c137e43c6c043725830c1303756da1d210ee`. No financial invariant, tenant/security, runtime,
or P3-M6 audit was performed. Static requirements/code/test comparisons below are not new
runtime test executions or independent approval evidence.

### CT reconciliation and P1 before/after

The exact claims/evidence/severity remain in the individual records above; this table gives their
current disposition. Classifications and remediation recommendations are DERIVED / CANDIDATE.
Only explicitly cited approved requirements have EXPLICIT / BINDING authority.

| Item | Governing sources | Classification and current disposition | Before → after |
|---|---|---|---|
| CT-001 | AGENTS.md precedence/no-invention; 04_DECISIONS opening rule | Documentation/provenance only. SOURCE_OF_TRUTH already denied a second effective order; wording now makes the ledger-over-project-contract example explicit. No actual policy conflict requiring a decision remains. | P2 candidate → P2 historical finding, RECONCILED_DOCUMENTATION_ONLY |
| CT-002 | AGENTS.md current-phase gate; 02_PHASE_INDEX; baseline-remediation exclusions | Future-continuity gap + CANNOT VERIFY complete guide approval. Eight real planning blobs found, but no authoritative restoration justified. | P1 missing guides → P1 CANNOT_VERIFY_AUTHORITY / REVIEW_REQUIRED; normal-version-control availability still MISSING |
| CT-003 | D-034; 00_PROJECT_CONTRACT Suppliers/procurement; PHASE_03 B/D/L/O/P | Implementation integration gap + unresolved surface/milestone attribution. Foundation and fixture-backed overrides exist; fresh-tenant provisioning is missing. | P1 workflow gap → P1 PARTIAL overall / MISSING supported provisioning; remediation not implemented |
| CT-004 | D-030/031/034; stack Money; PHASE_03 A–I/N | Provenance gap + unresolved product formula/boundary decisions. Approved catalog, ledger, delta, allocation/refund rules are separable from code-only invoice choices. | P1 incomplete provenance → P1 CANNOT VERIFY full approval, exact unresolved components identified |
| CT-005 | PHASE_03 G/H/J/P3-M5; D-005/006/019; stack Storefront; AGENTS mechanics rule | Mixed approved facets/mechanics/material decisions. Classification complete; material candidates remain review-required, not accidental by assumption. | P2 candidates → P2 scoped material candidates; no blanket approval |

### Controlled future-specification inspection

The baseline-remediation group-E classification supplied the exact eight-path allowlist. Read-only
Git inspection used the stash commit's parent metadata and explicit paths only. The untracked
payload parent is `068bb2ec38e66c1143b87d7f766cf38b9d896c2b`; commands had the form
`git show '9050d544791b5e22d15c2ff1a1acdbd503b40418^3:PHASE_04.md'`, individually for the
seven phase files and manifest. No blanket stash diff/show/apply/pop/restore was used.

All eight files are legitimate Tawzeevo planning/provenance documents. The seven guides contain
phase objectives, gates, domain scope, tests, milestones and DoD; their counts match the baseline
index. No accidental implementation files, generated build output, credentials or unrelated study
content appear in the inspected documents. Their manifest explicitly calls them newly generated,
derived, consolidated guides, not verbatim originals. They were intended to act as specifications,
but intent is not proof of approval for their additional requirements.

The cited `cash-van-production-roadmap-v2.1.1.md` is absent from the baseline and current tracked
tree. No baseline approval record for these exact generated versions was found. The phase index
approves broad objectives/counts/gates, not every unpublished body clause. The current task's
conditional recovery authorization does not itself approve those clauses.

| Exact inspected path | Git blob ID (immutable content reference) | Authority result / evidence needing review |
|---|---|---|
| PHASE_04.md | 609a2085048dd9a587eb5c57b28ba769bf62579b | CANNOT VERIFY full approval. Gate D matches; exact 500-change page, 90-day tombstones, 24h lease and AES/DEK/KEK details lack independently recovered normative provenance. |
| PHASE_05.md | b658be6f3f2231fa189e90725dba9a6a96439d0f | CANNOT VERIFY full approval. Guest/tenant-publication intent matches; exact 10:1 weights, 30-minute dedup, 90-day retention, slug/cancellation/API details are added specifications, not all locked by root summaries. |
| PHASE_06.md | ef1e59d7a68834861c276ad36f5e6ce4912543f0 | CANNOT VERIFY full approval. Supplier CRUD at P6-M1 is declared in this candidate only; it does not authorize deferring Phase 3 minimum costs. Proposed supplier_product_prices must be reconciled with D-034's existing cost foundation before adoption. |
| PHASE_07.md | a88d368a10a298e72a9174348c7c0c6a81cc518a | CANNOT VERIFY full approval. Owner/driver and provider gate match roots; ADR-027 reference has no matching routing ADR in baseline (D-027 instead records hosted DB choice); exact terminal task states/nearest-neighbor + 2-opt detail need source/adoption. |
| PHASE_08.md | 0319e5968a0e3a1dd2f38489c3c1d3d4fb1c4061 | REVIEW_REQUIRED with a concrete conflict: A/J prefer later linked actual purchase, then latest comparable actual_purchase cost for profit. D-031/D-034 require immutable revision-specific sale-time cost, not historical profit recomputed from later purchase/latest prices. The guide does not define a separately approved alternate metric. |
| PHASE_09.md | ec825132ef407a61ad2cd1032229540bd5efa45f | CANNOT VERIFY full approval. Hardening/pilot intent matches; mandatory password recovery and exact performance targets are not independently sourced by available root summaries. Provider gates do not approve a new deployment today. |
| PHASE_10.md | 1853a75c73ae17f791fa3459da73bb8194e879e5 | CANNOT VERIFY full approval. Statistical-first/last-phase intent matches D-018/contract; detailed output/evaluation/data-gate requirements are consolidated additions without the cited full source. |
| REMAINING_PHASE_GUIDE_MANIFEST.md | 73eba6ad075b3492cade9f7b872c8f2630289331 | Provenance description VERIFIED; approval authority CANNOT VERIFY. Its self-description cannot make its derived guides BINDING. |

Recovery result: **zero files restored, zero specification-recovery commits**. Detailed approved
Phase 4–10 specifications are still not available in normal version control. These files are
retrievable, not lost; authority is the blocker. Preserve all blobs intact. R-G below states the
exact next action. No corrective rewrite of the Phase 8 candidate was made or approved here.

### Supplier/cost provisioning — eight required answers

| Question | Evidence-based answer |
|---|---|
| 1. Supplier creation already required? | Supplier identities/tenant-private selection are required by D-034 and PHASE_03 B/O P3-M1; full contacts/address/location management is required by the product contract. A particular Phase 3 supplier CRUD screen/endpoint is not specified. |
| 2. Cost creation/assignment required? | Yes: D-034 defines append-only effective-dated entries, selected/preferred supplier, preload and an explicit save-as-new-entry path; PHASE_03 B requires the minimum cost-entry foundation. Revision-only override is not that saved entry. |
| 3. Exact phase/milestone? | P3-M1 names supplier/product-cost foundation; P3-M2 requires the real editor; P3-M3 requires confirmation; B/L/P require Phase 3 confirmation/cost behavior. Exact provisioning API/UI/CLI delivery milestone is not individually enumerated: CANNOT VERIFY. The candidate P6-M1 is not current approved scheduling authority. |
| 4. Expected by P3-M5? | A supported prerequisite path is necessary for the already delivered fresh-tenant confirmation workflow; none exists. This is an integration gap against Phase 3's minimum foundation/usable workflow, not proof that the four explicit P3-M5 public-link acceptance bullets require a new supplier screen. The original P3-M5 test gate is not rerun/reversed by inference. |
| 5. Missed supported workflow? | None found in production route/service/schema/CLI/UI inventory. Cost-options is GET-only. Invoice requests can select an existing supplier or use a reasoned override; no supplier/cost creation or preferred-supplier-setting mutation exists. Supplier-ledger opening/payment APIs require an existing supplier and do not create one. |
| 6. Tests inject otherwise unavailable state? | Yes. _attach_latest_cost inserts TenantSupplier/TenantProductCostEntry and sets preferred_supplier_id. The dedicated prefill test does likewise. _supplier_context inserts a supplier directly. Correction to the original audit: _catalog itself creates category/product/customer via supported APIs. |
| 7. Intentional later-phase prerequisite? | No authoritative deferral found. PHASE_03 B expressly establishes minimum costs now; D-034 says Phase 6 MAY create costs automatically later. A procurement-only path beginning with confirmed demand would not establish the first confirmation's prerequisite. |
| 8. Contradictory to approved workflow? | Missing-cost rejection conforms to D-034. The absent way to supply that cost makes the fresh-tenant workflow incomplete; PARTIAL overall / MISSING provisioning. Do not weaken confirmation to conceal the gap, invent a direct-SQL setup, or treat the candidate Phase 6 schedule as approval. |

An existing supplier plus a reasoned override can supply snapshot cost without an existing cost
entry; therefore the narrower indispensable prerequisite is supplier identity, not always an
existing cost row. Latest-cost preload and explicit save-as-new-default still require cost-entry
creation. A truly fresh tenant has neither supported path. The UI also hides cost controls when
cost-options is empty. No new runtime reproduction was needed to classify the missing surfaces;
full user-flow verification remains unexecuted.

Affected paths: `apps/api/tawzeevo_api/models.py` (existing foundation),
`apps/api/tawzeevo_api/services/invoice_editor.py` (_prepare_cost/product_cost_options),
`apps/api/tawzeevo_api/services/invoice_finance.py` (_validate_confirmable_costs/confirm_invoice),
`apps/api/tawzeevo_api/routes/invoices.py`, `apps/api/tawzeevo_api/schemas/invoice_editor.py`,
`apps/api/tawzeevo_api/services/supplier_ledger.py`, `apps/api/tawzeevo_api/cli/seed_demo.py`,
`apps/operations-web/src/components/InvoiceEditor.tsx`, and the existing invoice-editor/supplier
tests. These are impact/evidence paths, not an approved edit plan. R-S requires a supported
minimal foundation workflow and a fresh-tenant regression without fixture-created prerequisites;
it does not require importing full procurement, stock, or a new supplier cost model into Phase 3.

### Invoice-formula provenance matrix

Notation: Q(x) = Decimal quantization to 0.0001 using ROUND_HALF_UP. Source requirements in
column A are EXPLICIT / BINDING only through the cited roots. Observed equations/details in B
are DERIVED / CANDIDATE unless A explicitly establishes the same rule. Tests in C are evidence,
never approval. D identifies the actual provenance difference, not a financial correctness verdict.
Backend paths below are relative to `apps/api/tawzeevo_api/`; backend tests to `apps/api/tests/`.

Test anchors (all existing; inspected, not rerun):

- E1: `test_cash_van.py::test_pricing_v1_precedence_rounding_packaging_and_invoice_snapshot`.
- E2: `test_invoice_editor.py::test_editor_recalculates_pricing_v1_calculator_adjustments_and_immutable_updates`.
- E3: `test_invoice_editor.py::test_editor_rejects_mixed_currency_package_mismatch_and_unsafe_calculator`.
- E4: `test_invoice_editor.py::test_post_confirmation_revision_posts_exact_delta_and_keeps_old_balance_out_of_sales`.
- E5: `test_invoice_editor.py::test_confirmation_is_idempotent_assigns_official_number_and_posts_one_charge`.
- E6: `test_invoice_editor.py::test_receipt_fifo_owner_allocation_partial_multi_obligation_and_reversal_are_immutable`.
- E7: `test_invoice_editor.py::test_downward_confirmed_edit_releases_excess_allocation_without_mutating_payment`.
- E8: `test_invoice_editor.py::test_cancellation_preserves_payment_releases_credit_and_refund_ceiling_is_concurrent`.
- E9: `test_invoice_editor.py::test_zero_value_confirmed_cancellation_keeps_an_explicit_immutable_reversal`.
- E10: `test_supplier_ledger.py::test_supplier_payment_aggregate_balance_replay_reversal_and_currency`.
- E11: `test_invoice_editor.py::test_editor_prefills_latest_tenant_cost_and_keeps_reasoned_override_revision_only`.
- E12: `test_invoice_editor.py::test_opening_balance_balance_api_overdue_alert_dedup_and_owner_security`.
- E13: `test_financial_schema.py::test_invoice_order_cardinality_and_cost_snapshot_survive_later_cost_change`.

| ID / component | A: explicitly approved requirement (EXPLICIT / BINDING) | B: actual implementation | C: test assertions | D: provenance status / unresolved detail |
|---|---|---|---|---|
| F01 Precision/currency | 01_TECH_STACK Money; PHASE_03 A: Decimal, NUMERIC(20,4), Q4 HALF_UP, one invoice currency/no FX mixing | services/pricing.py::quantize_money; services/invoice_editor.py::money; schema Decimal fields; mixed-currency checks | E1 tie/counterpart cases; E3 mixed currency rejected | VERIFIED for these explicit rules; exact additional intermediate quantization stages belong to F03/F05/F06, not automatically binding. |
| F02 Catalog grade/basis price | D-030: explicit grade price first, otherwise normal basis × (1 − percent/100), otherwise normal; round basis then separately round counterpart | services/pricing.py::resolve_product_pricing and derive_counterpart_prices follow that order | E1 precedence/rounding/packaging; E2 12.5000 at 10% → 11.2500 | VERIFIED provenance. No new formula decision needed for D-030 itself. |
| F03 Calculator/quantity | PHASE_03 D requires calculator-style numbers/operators; A requires Decimal/Q4 | services/invoice_editor.py::_Calculator: Arabic digits, + − * / parentheses/unary signs, standard precedence, local precision 38, Q of final expression; quantity expression Q applied before multiplication; q > 0 | E3 (٢ + ٣)/2 → 2.5000, unsafe expression rejected; E2 1+1 → 2 | PARTIAL: arithmetic grammar is ordinary mechanics, but quantity pre-rounding/positive boundary and full tie examples are DERIVED / CANDIDATE within R-F. Tests do not lock those stages as product truth. |
| F04 Manual line pricing | PHASE_03 D/L requires manual entry and grade-pricing support; D-030 locks catalog grade prices | schemas/invoice_editor.py::InvoiceEditorItemRequest requires manual price for manual lines and rejects it for catalog lines; _prepare_items uses manual price directly, source NORMAL, no automatic grade discount | E2 manual 3 × 2 = 6 with grade A customer; no dedicated catalog-manual-price rejection assertion cited here | PARTIAL: manual-entry support is binding; caller-specified manual price and no automatic manual grade rule are DERIVED / CANDIDATE semantics. R-F must state whether the manual input is the final effective price. |
| F05 Line multiplication | PHASE_03 B/D requires quantity, effective unit price, line total and backend recalculation; not an explicit complete stage-by-stage equation | _prepare_items: q_i = calculate_expression(quantity_expression), already Q-rounded; base_i = Q(q_i × effective_unit_price); line_i = Q(base_i − line_discount_i + line_markup_i) | E2 grade-priced base 22.5000, adjusted line 22.2500 | PARTIAL: exact equation/intermediate rounding is DERIVED / CANDIDATE; quantity × unit price is ordinary arithmetic, but exact rounding/order belongs to R-F. |
| F06 Discounts/markup/totals | PHASE_03 B/D requires line/invoice discounts and markup, subtotal/net sales; D-030 applies only catalog-grade percentages | _totals: subtotal = Q(sum base_i); discount_total = Q(sum line_discount_i + invoice_discount); markup_total likewise; net_sales = Q(subtotal − discount_total + markup_total). Expressions evaluate to absolute currency amounts, not percentages or per-unit adjustments. Grade savings already reduce effective price, not discount_total. | E2 subtotal 28.5000; discount_total 1.5000; markup_total 0.7500; net_sales 27.7500 | CANNOT VERIFY full approval. Fixed amount units, aggregation/order and grade-savings reporting are DERIVED / CANDIDATE; no competing approved full equation located. |
| F07 Zero/sign boundaries | PHASE_03 defines lifecycle and adjustments but does not explicitly lock these invoice admission boundaries | Quantity > 0; line/invoice discount and markup >= 0; manual price/cost override >= 0; line and invoice totals >= 0. confirm_invoice additionally requires initial net_sales > 0; update_confirmed_invoice can reduce net_sales to 0 | E9 confirms a positive invoice, edits to zero, then cancels with a zero reversal. It does not test initial zero confirmation rejection; no complete boundary matrix found | CANNOT VERIFY full approval. All those exact invoice boundaries are DERIVED / CANDIDATE; signed expressions are allowed internally but negative discount/markup results are rejected. Signed ledger deltas are a different, approved concept (F09). |
| F08 Old balance/display | PHASE_03 B/D/F/L: prior-balance snapshot/display, total due, old balance not current sales | Draft prior = current customer/currency ledger sum; confirmed-edit prior excludes this invoice's source_type INVOICE entries but retains payment events. amount_due_display = Q(prior + net_sales), persisted at revision acceptance; not recalculated by later payment | E2 prior 5 + net 27.75 = display 32.75; E4 prior stays 10 across invoice revisions, final display 21.75 | PARTIAL: excluding old balance from sales is BINDING; exact display equation, snapshot timing and payment/revision exclusion set are DERIVED / CANDIDATE. Do not confuse this display with current invoice outstanding or live customer debt. |
| F09 Confirmation/edits | PHASE_03 E: one +net_sales charge; delta = new_net_sales − old_net_sales, one immutable adjustment | services/invoice_finance.py::confirm_invoice/update_confirmed_invoice use those signed effects | E5 one 24.2500 charge; E4 effects 24.2500, −12.5000, 0.0000 | VERIFIED explicit equation provenance, conditional on independently approved net_sales inputs; no concurrency/correctness certification is made here. |
| F10 Customer balance/opening | 00_PROJECT_CONTRACT Financial truth; PHASE_03 F: balance = sum signed ledger by currency; positive debt/negative credit; opening is a ledger event, not sales | services/customer_ledger.py::create_opening_balance/customer_balances; schemas/customer_ledger.py permits signed nonzero opening events, replay by key; different keys can add more openings | E12 +75 opening/replay/balance; E4 +10 opening; E8 negative credit after cancellation | VERIFIED for sum/sign/old-balance exclusion; repeated positive/negative opening-event admission and zero rejection are DERIVED / CANDIDATE input policy, not independently approved merely because ledger amounts are signed. |
| F11 Receipts/allocations | PHASE_03 H: positive receipt, negative ledger effect, FIFO or explicit owner allocation, allocations <= payment, remainder credit; outstanding = MAX(0, net_sales − effective allocation) | services/payments.py::record_customer_receipt/_effective_allocation_amounts/_obligations; apply minus reversal, positive outstanding obligations only; reversal appends +original amount; excess allocations released after downward edit | E6 30 allocated; explicit receipt 10 allocates 7 and leaves 3 unallocated; E7 preserves original payment after release | VERIFIED provenance for stated rules. Exact FIFO tie implementation is not a newly approved business rule; invariant execution audit remains later work. |
| F12 Cancellation/refunds | PHASE_03 I; contract: confirmed cancellation reverses invoice, preserves payments/releases credit; refund separate, 0 < amount <= MAX(0, −balance), same currency/serialized | cancel_invoice appends −current net_sales; record_customer_refund adds +amount; no automatic cash refund | E8 cancelled paid invoice leaves −10 credit, excess/no-credit checks and concurrent refunds; E9 explicit zero reversal | VERIFIED provenance for these equations; test inspection is not a new concurrency run. |
| F13 Supplier money | D-019; contract Financial truth; PHASE_03 H/P3-M5: payments reduce aggregate payable, immutable/reversible foundation, no purchase allocations | supplier_balances = currency sum; _write_payment_effect emits −payment/+full reversal. Signed nonzero opening events accepted; record_supplier_payment has no payable ceiling, so zero-payable/overpayment can yield negative balance | E10 +20 −7 = 13; reversal → 20, currencies separate/no allocations. No explicit overpayment or negative opening assertion found | PARTIAL: aggregate reduction and compensation are BINDING; opening admission/multiplicity, negative supplier balance meaning and overpayment ceiling/no ceiling remain DERIVED / CANDIDATE (C06). |
| F14 Cost/profit boundary | D-031/034; PHASE_03 B: tenant-private eligible cost or reasoned revision override; immutable cost/source/currency/package snapshot; no later-cost rewrite of historical profit | _prepare_cost preloads matching basis/currency or accepts override; confirmation requires snapshot. No current profit calculation/report service established by this scope | E11 8.2000 entry → 8.6000 revision-only override; E13 old snapshot survives new cost | VERIFIED snapshot requirement, PARTIAL user provisioning (CT-003). No new profit formula invented. Preserved Phase 8 latest/actual-purchase fallback is conflicting candidate material, not authority for existing invoices. |
| F15 Overdue | PHASE_03 G: oldest still-unpaid obligation by currency, age > owner X and positive balance → red + deduplicated in-app alert | customer_debts computes date difference, nullable threshold (unset = not overdue), stable read-time key; no persisted delivery/scheduling policy | E12 +75 aged >=40 days triggers red condition and repeated equal alert key | PARTIAL: threshold/comparison/obligation basis are BINDING; day boundary/timezone, unset behavior, notification cadence/dedup lifecycle remain DERIVED / CANDIDATE (C08). |

Concrete implemented example (E2, not an approval record): catalog 12.5 at grade discount 10%
becomes 11.25; quantity 2 gives 22.5; line discount .5 and markup .25 give 22.25. Manual 3 × 2
adds 6. Invoice discount 1 and markup .5 produce net sales 27.75. Opening balance 5 changes
displayed due to 32.75, not sales. Code and this asserted example agree. That agreement does
not supply missing approval of fixed adjustment units, rounding stages or boundary behavior.

No contrary approved complete invoice equation was located. Missing provenance is not proof
of wrong arithmetic; it prevents an unqualified assertion that the entire implemented formula is
the approved formula. There is no tax/VAT, currency conversion, stock valuation, or implemented
profit-report algorithm to add to this matrix. Payment/allocation/cancellation equations already
explicitly stated remain usable authority independently of the unresolved invoice input policy.

### C01–C08 policy dispositions

A = already explicit approved facet; B = ordinary implementation detail, no product approval
needed on current evidence; C = material product/architecture decision requiring approval;
D = demonstrably accidental behavior; E = cannot verify intent/approval. These are review
categories, NOT the governance tiers. All classifications are DERIVED / CANDIDATE judgments;
an A facet is BINDING only through its named existing source. No D classification is established
merely because a choice lacks approval.

| Candidate | Disposition | Material review scope / escalation |
|---|---|---|
| C01 Rate limit | A: rate limiting required (PHASE_03 J). B: lock/hashed client keys/bounded storage mechanics. C: exact 60/IP/60s, 4096 tracked clients/fail-closed admission, one per-process bucket for all /api/v1/public paths, shell + data both consume quota, Retry-After 60. | Security/public integration review must establish accepted service/proxy/rate-limit scope; no new provider requested. Do not label exact constants BINDING from tests. Not a blocker to purely financial equations. |
| C02 Capability transport | A: random secret/hash-only/no internal-ID authorization/no logs (J). B: internal token parsing/hash mechanics. C: tenant-prefixed bearer token, fragment-to-X-Invoice-Capability header and fixed resource paths are public integration contracts. E: intended tradeoff of clearing fragment/reload behavior cannot be proved. | Review bearer transport/reopen/reload contract before public-security/Phase 5 integration. The observed requirement to reopen the original link after refresh is documented, not called accidental or redesigned. |
| C03 Public renderer | B: serving the required interim Phase 3 invoice through the existing FastAPI app/template, safe text rendering and computed CSP hash adds no new architecture category. A: Next.js storefront remains locked (D-005/stack beginning Phase 5). | No product decision needed merely to keep this renderer/hash now. Hand-read header/OpenAPI declaration and future frontend reuse are evidence/integration work; C02 governs changes to the public contract. Not approval to replace Next.js storefront. |
| C04 Multiple links | C: create may issue several active links and is not idempotent; rotation replaces only one selected capability. | Decide active-link cardinality, create retry and rotation/revocation scope before public lifecycle/security acceptance or checkout reuse. No single-link requirement invented. |
| C05 Sharing lifecycle | A: current representation and privacy ceiling (J), not issuance-time snapshot. C: standalone draft/cancelled issuance/read eligibility and post-cancellation link behavior. | Review those statuses before public acceptance; draft checkout intent in the contract is not blanket approval for every standalone/cancelled invoice. Candidate Phase 5 provisional language does not retroactively approve P3-M5. |
| C06 Supplier payments/openings | A: aggregate payment reduction and immutable compensating reversal (D-019/PHASE_03 H). B: whole-payment reversal via existing reversal action is consistent compensation, not a demand for partial-reversal UI. C: signed/multiple opening admission, zero-payable/overpayment and negative supplier balance semantics. | Required before unqualified supplier financial audit. Customer refund ceiling must not be copied to suppliers without approval; no supplier-refund feature proposed. |
| C07 Projection/WhatsApp | A: safe allowlist, normalized phone/summary/URL, EN/AR (J/L). B: current conservative subset, bilingual wording, URL encoding and disabling WhatsApp without a valid phone. | No new product-level approval needed for formatting or omitting unrequired private fields. Future applicable checkout/delivery fields must follow their approved phase. No evidence mandates a phone requirement for link issuance itself; no new field/design request escalated. |
| C08 Overdue alerts | A: oldest unpaid obligation, owner X, positive balance/age > X, red/dedup (G). B: literal alert-key spelling. C: unset threshold, day/timezone boundary, read-time-only generation and dedup/notification lifecycle. | Resolve day/unset semantics before unqualified debt audit; notification lifecycle before alert/job work. No job runtime/provider chosen. This is P3-M3 behavior, not newly attributed to P3-M5. |

### Exact remaining source/decision requests

These entries are PROPOSED / CANDIDATE requests for disposition, not approved decisions or an
implementation plan. No new row was added to 04_DECISIONS.md.

- R-G (CT-002): provide the manifest's frozen roadmap and approval provenance for the exact
  eight blob versions, or explicitly review/adopt them with approved corrections. Phase 8 must
  use the locked revision cost for historical profit; an alternate metric would need a separate
  explicit definition/approval. Only after verification/adoption recover the exact approved files
  in a separate specification commit, leaving the stash and study work intact.
- R-S (CT-003): confirm the minimum supported Phase 3 supplier/cost/preference provisioning
  and explicit-save surface and its milestone ownership. The existing requirement is not optional;
  the surface/scheduling choice is unresolved. No direct fixture/SQL setup may masquerade as a
  demonstrated owner workflow. Full supplier contacts/procurement need not be pulled forward.
- R-F (CT-004): provide normative provenance or explicitly disposition F03–F08's quantity/input
  rounding, manual effective-price/grade handling, fixed line/invoice adjustment amounts and
  aggregation, grade-discount reporting, zero/sign boundaries, and prior-balance/display timing.
  Include F10's repeated/signed opening-event admission policy. Approve exact numerical examples
  and reject/accept boundaries, not merely the name pricing-v1. F01/F02/F09/F11/F12's cited
  explicit rules do not need to be reinvented. The current test example is a candidate only.
- R-P (CT-005): disposition C06 supplier signed openings/overpayment/negative balance and C08
  overdue day/unset/dedup policy for finance/debt acceptance; disposition C01/C02/C04/C05 for
  later public-security/lifecycle integration. C03/C07 ordinary mechanics are not escalated into
  new product decisions. Do not broaden this into a redesign.

Before a full financial audit can certify compliance without assumptions, R-F and the supplier
financial/overdue portions of R-P need authoritative disposition. The audit could later inspect
explicit subsets while labelling unresolved portions, but cannot call those portions approved.
R-S additionally blocks fresh-tenant end-to-end finance acceptance, not static examination of
existing ledger equations. R-G blocks future implementation; it does not block an audit confined
to approved Phase 3 requirements. CT-001 is no longer a blocker. No permission to start any of
those audits is granted by this classification.

### Reconciliation self-validation and checkpoint

Executed 2026-09-06, PASS:

- 10 findings each retain all 18 required fields; original severities and 62 trace rows/counts preserved.
- 15 formula-component rows have consistent columns; 92 explicit Python file/symbol references resolve.
- All 12 local Markdown link targets in the six edited files exist; heading fragments were not browser-tested.
- All eight recorded guide/manifest blob IDs match the allowlisted stash paths; zero files restored.
- The 26 binding-index rows are identical to the continuity commit; source comparison keeps new inferences/candidates separate from approved requirements.
- Exactly six selected continuity Markdown files changed; complete diff reviewed; whitespace/conflict/unmerged-index checks pass. No source/tests/config/migrations/dependencies, authoritative ledger/specifications, or study-document changes.
- Initial HEAD and original implementation ancestry are preserved; stash ref/object remains intact. No apply/pop/drop/restore or unrelated stash-content inspection occurred.

The final handoff records the separate commit and post-commit clean-tree/HEAD checks. No runtime
tests are claimed for this documentation-only task. The original implementation and continuity
SHAs remain distinct; this document cannot embed its own future commit SHA.

## Narrow owner-intent recovery follow-up — 2026-09-06

The first pass at `41c5af0790cc36d37a9cffb3248d3e46fef51086` correctly found zero owner
quotations in its guard-only packet. The corrected-packet follow-up in
[USER_INTENT_RECOVERY.md](USER_INTENT_RECOVERY.md) reviews three actual messages:
two explicit decisions corroborate catalog grade precedence/backend Decimal and historical-cost
protection; one supplier-pricing question anticipates later approval and is DISCUSSION_ONLY.
There are zero recovered explicit confirmations. The referent of the opening "Approved." in
INTENT-002 is ambiguous and supplies no blanket approval.

Recovered explicit intent remains `RECOVERED_USER_INTENT — FORMALIZATION_REQUIRED`.
CT-002 gains no guide approval or later D-031/D-034 override; CT-003 gains no provisioning
surface/deferral approval; CT-004 gains corroboration only for already documented principles;
CT-005 gains no policy approval. R-F and financial R-P remain open. Original finding statuses,
severities and requirement authority are unchanged. No application behavior or source-of-truth
file changed. The packet is temporary evidence and is not committed; no raw-history search,
extraction rerun, stash inspection or wider audit was performed in this follow-up.

## Current next action only

Obtain source/owner disposition of the narrowly scoped requests R-S, R-F and R-P above, prioritizing
the full formula and supplier financial semantics before the financial audit. Future specifications
need the separate R-G provenance/adoption step before future implementation. No larger audit,
workflow implementation, Graphify installation, financial audit or P3-M6 is started by this task.

## Owner decisions and recovered Phase 4–10 reconciliation — 2026-09-07

This section supersedes only the open-status statements above; it preserves their evidence and
historical classifications. The owner directly approved D-035–D-043 and supplied byte-identical
copies of the seven future guides plus manifest under `docs/recovered-planning/`. The supplied set
was read in full and remains historical planning evidence, not current phase authority.

| Finding/request | Updated status and evidence |
|---|---|
| CT-002 / R-G | **CLOSED.** All eight historical artifacts are available with matching inventoried blob IDs. The owner resolved the two current questions and directed formalization. Reconciled root `PHASE_04.md`–`PHASE_10.md` preserve compatible requirements, apply later authority and mark deferred material choices `REVIEW_REQUIRED`; the historical directory remains provenance only. |
| CT-003 / R-S | **PARTIAL; DECISION RESOLVED / IMPLEMENTATION MISSING.** D-041 establishes the exact owner-facing surface and Phase 3 boundary. Current code still lacks the dedicated supplier/product-cost creation/preference API/UI and fresh-tenant path; no workaround is authorized. |
| CT-004 / R-F | **DECISIONS RESOLVED; IMPLEMENTATION REVIEW REQUIRED.** D-035–D-037 approve manual-price, adjustment, rounding and display semantics. Completed D-038 approves one signed nonzero historical opening plus immutable correction/reversal. D-043 requires strictly positive net sales for every confirmed revision and nonnegative inputs/totals. Current zero-edit behavior conflicts. |
| CT-005 / R-P | **PARTIAL; CORE FINANCIAL/SHARING POLICY RESOLVED.** D-039 resolves supplier overpayment/prepayment, D-040 overdue calendar/boundary/unset behavior, and D-042 link cardinality/status/rotation/cancellation/transport. Existing contrary behavior is an implementation mismatch to be handled later, not in this reconciliation. Exact rate-limit constants and durable alert cadence safely wait as operational policy. |
| D-031/D-034 | **UNCHANGED / VERIFIED AUTHORITY.** No owner override exists. Recovered Phase 8 wording that would recompute historical profit from later actual/latest cost is superseded. A separately named later-purchase estimate would require a new Phase 8 decision. |

### Current implementation mismatches — do not fix in this task

- CT-003: supported owner supplier/cost/preference provisioning required by D-041 is absent.
- CT-004: current initial-confirmation versus confirmed-edit zero-total asymmetry lacks approval.
- CT-005: current supplier payment can overpay and supplier openings can repeat; public sharing can
  issue multiple links and expose draft/cancelled invoices; overdue uses a date basis not yet shown
  to be the D-040 Beirut boundary. These must be verified/fixed only in an authorized implementation
  or financial-audit task.

### Current owner-decision status

RP-NOW-01 is resolved by D-043. RP-NOW-02 is resolved by completed D-038. Opening multiplicity
was not inferred from Q2: it was already separately approved in D-038 as at most one initial event
per party/currency, with immutable correction/reversal thereafter. All other recovered-plan
questions safely wait for their named gates in the now-authoritative root Phase 4–10 specifications.
No application remediation is authorized by this formalization.

## Deep Phase 3 financial audit — executed 2026-09-07, finalized 2026-09-08

This dated overlay supersedes only financial implementation-review uncertainty above; historical
continuity evidence and unrelated findings remain intact. See
[PHASE_3_FINANCIAL_AUDIT.md](PHASE_3_FINANCIAL_AUDIT.md) for complete evidence, finding metadata,
reproduction procedures and limitations, and the
[financial invariant catalog](../contracts/financial-invariants.md) for 32 EXPLICIT/BINDING and
5 CANDIDATE rows. Neither artifact changes approved authority.

AUDIT_BASE_SHA=2248c137e43c6c043725830c1303756da1d210ee

AUDITED_SHA=868bf1c5d4d49e755c74a6dd2c75a9a78f6ca6e6

GRAPH_SOURCE_SHA=868bf1c5d4d49e755c74a6dd2c75a9a78f6ca6e6

| Finding | Severity | Independently traced implementation result |
|---|---|---|
| FA-001 | P1 | D-038: different commands admit multiple initial openings; correction workflow absent. |
| FA-002 | P1 | D-039: ordinary supplier payment accepts excess; distinct prepayment absent. |
| FA-003 | P1 | D-040: UTC date arithmetic disagrees with Beirut overdue boundaries. |
| FA-004 | P1 | D-041/D-034: supported owner supplier/cost/preference setup absent; manual-line cost UI inaccessible. |
| FA-005 | P1 | D-042: multiple draft links resolve; cancellation does not revoke access. Financial lifecycle scope only. |
| FA-006 | P1 | D-043: initial confirmation rejects zero, but a confirmed revision accepts zero net sales. |
| FA-007 | P0 | Lost receipt response plus actual UI retry changes command identity; real API accepts the second payment. |
| FA-008 | P1 | Positive opening/reversal obligations raise String.value errors and block receipt selection. |
| FA-009 | P2 | Identical draft-create command creates separate headers; exact current cross-header key scope remains CANDIDATE. |
| FA-010 | P2 | Mounted legacy draft creation hardcodes zero prior balance, unlike the modern editor. |
| FA-011 | P2 | Immutable due snapshot lacks the required snapshot distinction in the UI label. |
| FA-012 | P2 | Oversized calculator results produce uncontrolled server errors. |

All twelve remain OPEN. Counts: **1 P0, 7 P1, 4 P2, 0 P3**. Result under the requested rubric:
**NO-GO**, because FA-007 permits duplicate money during a normal lost-response retry. It is
established by an actual-component diagnostic plus a real PostgreSQL-backed API reproduction,
not an inferred graph edge or an assertion that production corruption occurred. Independent
verification and permanent regression coverage are required before closure.

CT-003/R-S now has direct fresh-tenant failure evidence (FA-004); D-041 remains a Phase 3 completion
requirement, not a claim that a later decision was part of original P3-M5 acceptance. CT-004/R-F
formula provenance remains resolved by approved decisions; actual mismatches are FA-001/006/010/011
and calculation robustness FA-012. CT-005/financial R-P contradictions are verified as FA-002/003/005.
CT-002 remains closed by the prior formalization. No broad security/rate-policy audit is claimed.
D-031/D-034 historical snapshots remain protected; no profit-report implementation exists to certify.

Existing validation: 126 backend tests passed, 34 frontend tests passed on an isolated rerun, and
clean disposable database migrations reached 0011. These do not discharge the focused defect probes.
A suspected edit/payment race was not established: FK locking blocked the receipt in the tested
interleaving. Wider concurrency/fault windows remain explicitly missing coverage.

Five non-binding questions remain in the catalog: cross-header create-command semantics, draft-cost
refresh timing, later use of unallocated credit, numbering-year timezone, and signed due versus
D-043's nonnegative-total wording. None is the sole basis of a P0/P1 finding. No decision was invented.

Application code, business tests, migrations, dependencies, phase specifications and decisions are
unchanged. The preserved stash was not read or changed. No P3-M6, remediation, deployment, push or
tenant/security audit began. The separate documentation commit is recorded in the audit handoff.

Next action only: independently verify FA-007, then seek authorization for a bounded remediation
plan starting with logical payment-retry identity and the confirmed P1 blockers.

## FA-007 bounded remediation follow-up — 2026-09-08

**Status: FIXED_PENDING_INDEPENDENT_VERIFICATION.** This section supersedes only FA-007's OPEN
implementation status above. It does not close FA-007, change its approved financial meaning, or
alter any other finding.

Independent verification at HEAD `f56750154b4d65bfaf77a12949fce9bdb31fbce6` first retraced the
authority, component, API, persistence and existing tests without relying on the original finding.
It reproduced one physical USD 10 receipt as two Payment rows, two ledger effects, two FIFO
allocations and a `-20.0000` payment-ledger sum when an unobserved committed response was manually
retried with a new key. Same-key replay returned the original Payment correctly. Classification was
independently confirmed as P0 under the existing materially-incorrect-money rubric.

The committed pre-fix frontend regression failed for the expected identity reason after its harness
was valid: the built-in 401 retry preserved A, while two manual retries produced B and C instead of
A. The production correction is application commit:

APPLICATION_FIX_SHA=ac9bbdb9b10f1dd09010bf4c1bd2ab56e44d85fd

GRAPH_SOURCE_SHA=ac9bbdb9b10f1dd09010bf4c1bd2ab56e44d85fd

`InvoiceEditor.tsx::financialIntent` now owns an exact first-attempt payload and UUID for each
unresolved tenant/customer/currency/direction command. Receipt and refund handlers retain it across
transport failures and manual retries. They retire it immediately after an API response is observed,
before follow-up balance/obligation refreshes, so the next completed form submission receives a new
UUID. Receipt and refund pending refs are separate, and the scope prevents reuse across tenant,
customer, currency or direction. Backend idempotency behavior and constraints are unchanged.

Regression evidence:

- `InvoiceEditor.test.tsx::lost financial responses retain one command while the next completed
  intent gets a new command`: 401 replay plus two lost-response retries all use A and one modeled
  payment/ledger/allocation/audit effect; a completed second receipt uses B; refund loss/retry uses C.
- `test_invoice_editor.py::test_customer_receipt_retries_one_command_and_a_new_intent_posts_again`:
  three real API submissions with A persist one Payment/effect/allocation/audit; B persists the valid
  second set; payment ledger sum is exactly `-20.0000` for two legitimate USD 10 intents and the
  customer balance matches confirmed sales minus USD 20.

Final validation at the fix SHA:

- backend: 127 passed, one existing Starlette/httpx deprecation warning, 458.32 seconds;
- frontend: 35 passed across five files, 19.59 seconds on the isolated full rerun;
- frontend ESLint, strict TypeScript and production Vite build: PASS (existing chunk-size warning);
- backend Ruff and strict mypy (52 source files): PASS;
- Graphify 0.9.55 refresh and check-only: PASS, 1,403 nodes / 6,800 edges;
- focused EXTRACTED navigation: InvoiceEditor→financialIntent/apiRequest and route→payment service;
  ledger/allocation persistence and tests were verified directly rather than accepted from inferred edges.

An earlier concurrent frontend run was not accepted as final evidence: the new 401 test mock initially
returned a synchronous Response incompatible with `refreshAccessToken().then`, and an existing sharing
test timed out while the full backend suite competed for resources. The mock was corrected; the focused
test and isolated full frontend suite then passed. No application behavior was changed for that harness fix.

Residual risk: pending identities are component-memory state and do not survive browser reload,
component destruction or device loss. Durable recovery belongs to the approved Phase 4 offline-command
design and was not invented here. There is still no full real-browser/network-proxy outage test; the
current evidence composes an actual React component failure simulation with a real FastAPI/PostgreSQL
persistence test. An unresolved command deliberately retains its original payload even if fields are
edited before retry; no new abandon workflow was introduced. These limits require the requested
post-fix independent verification before closure.

FA-001–FA-006 and FA-008–FA-012 retain their prior statuses. No P3-M6 work, specification/decision
change, backend-idempotency change, payment-architecture redesign or unrelated remediation occurred.

Next action only: independently verify application commit
`ac9bbdb9b10f1dd09010bf4c1bd2ab56e44d85fd` against the FA-007 post-fix regression and decide whether
the in-session remediation may be closed while durable reload/device recovery remains governed by Phase 4.

## FA-007 online reload/remount extension — 2026-09-09

**Status: FIXED_PENDING_INDEPENDENT_VERIFICATION.** D-044 was recorded before this extension and
committed separately as `6d6523c`. The owner explicitly requires ordinary same-browser online
receipt/refund recovery across reload/remount in Phase 3. This supersedes the preceding report's
blanket deferral of component destruction/reload to Phase 4. Full offline/outbox processing and
total device/storage loss are outside this bounded remediation. P3-M6 remains NOT_STARTED.

Relevant subsystem maturity: M2 (established typed API, scoped payment services and PostgreSQL
replay constraints with deterministic validation). Task class A0 (financial-command identity and
asynchronous lifecycle correctness); implemented and reviewed directly, without delegation.

Implementation:

- `src/api/financialIntent.ts` stores the exact first-attempt UUID/payload synchronously in
  `sessionStorage` before sending. The key includes tenant, authenticated membership, customer,
  currency and receipt/refund direction. Separate keys preserve interleaved unresolved scopes.
- `InvoiceEditor` retrieves this identity for manual retries, including after a real page reload
  or remount. Original amount, method, reference, paid_at and allocations remain unchanged even
  if fields are edited. No background dispatch, outbox states, device registry, sync protocol,
  IndexedDB/Dexie, dependency, backend API, migration or financial formula was added or changed.
- Success retires only the matching identity before subsequent read refreshes. A late successful
  response to an unmounted component does not retire it because the owner was not shown success.
  An old response cannot delete a newer command. Receipt/refund identities remain separate.
- Unavailable storage, unreadable records or invalid stored shape block submission instead of
  falling back to a new UUID. Failed retirement retains a replayable command. Errors are EN/AR.
  Stored data contains only the pending command and scope, no authentication credentials; the
  backend still validates session, membership, authorization and all financial rules.

Test-first evidence (2026-09-08, with final harness checks on 2026-09-09):

- The extended actual-component lost-response regression first failed on remount: expected
  A/A/A/A, observed A/A/B/C. The mounted case passed. Both now pass, including a genuine second
  receipt and refund response-loss/remount retry.
  The extended multi-remount scenario has a 20-second test budget: a full-suite run exceeded its
  original 10-second budget on the development machine. No assertion was removed or weakened.
- Separate receipt and refund regressions first failed when successful responses arrived after
  unmount (new UUID and timestamp on retry). Both pass after the mounted-lifecycle guard.
- Six storage tests cover discarding all module memory while retaining session storage, exact
  first payload despite edited fields, repeated replay, successful retirement/new identity,
  late retirement, interleaved scopes/directions, read/write failure, corrupt/mismatched records
  and removal failure. Two actual-component storage-failure cases verify zero financial POSTs.
- Existing PostgreSQL integration tests pass: three retries return one Payment; the separately
  keyed genuine receipt creates another set. Persisted Payment/ledger/allocation/audit counts
  and monetary sums are checked. Receipt replay/reversal and refund credit-concurrency tests
  also pass. Backend replay protections are unchanged.
- Actual in-app browser document reloads were exercised using the real InvoiceEditor and an
  ignored, synthetic fetch harness: USD 10 receipt (2026-09-08) and USD 5 refund (2026-09-09),
  simulated commit then lost response, reload, reselect customer/re-enter amount, retry. Each
  retained the exact UUID, timestamp and payload; each had one modeled effect and displayed
  success. This is browser reload evidence, not a live API/network-proxy outage test. Financial
  persistence evidence comes from the separate real PostgreSQL tests above.

Reproduction commands:

```powershell
npm run check
npm run test --workspace=@tawzeevo/operations-web -- src/components/InvoiceEditor.test.tsx src/api/financialIntent.test.ts
# Set DATABASE_URL and TEST_DATABASE_URL only to a migrated, explicitly disposable local database.
./.venv/Scripts/python -m pytest apps/api/tests/test_invoice_editor.py -k 'customer_receipt_retries_one_command or receipt_fifo_owner_allocation or cancellation_preserves_payment_releases_credit' -q --disable-warnings
```

PostgreSQL checks ran against the disposable local cluster on 127.0.0.1:55439, database
`fa007_final_verification`, migration head `20260827_0011`: **3 passed**, 14 deselected, one existing
Starlette/httpx warning. The full frontend suite has **46 passing tests**; ESLint, strict TypeScript
and production build pass (existing Vite chunk-size advisory). Application checkpoint and Graphify
source verification are recorded in `docs/assurance/GRAPHIFY.md` after the implementation commit.

Boundary: session storage survives ordinary reload/remount in the same tab/browser session.
There is no cross-tab/device deduplication, browser-session-close recovery, automatic replay,
offline queue, abandon-command workflow or guarantee after storage deletion/device loss. To retry,
use the same tab, membership, tenant, customer, currency and direction; the first payload is reused
until observed success. Broader restart-safe offline command recovery remains Phase 4 under D-044.
No other finding was remediated or reclassified. Next action: independent narrow FA-007 verification
against D-044 and this extension; do not start P3-M6 or claim Phase 3 completion.

Application extension checkpoint: `7c6b46a895bd26fc93426942ce70b627acd771ac`.
Final `npm run check` on 2026-09-09: PASS, 46 tests, 32.05 seconds for Vitest; build 211 modules.
Graphify refresh and check-only both PASS against that exact SHA: version 0.9.55, 1,412 nodes,
6,825 edges. No critical conclusion relies on graph inference. This follow-up documentation commit
does not change the tested application. Nothing was pushed or deployed.
