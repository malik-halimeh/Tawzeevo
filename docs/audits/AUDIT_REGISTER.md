# Continuity audit register

Implementation audit baseline: `2248c137e43c6c043725830c1303756da1d210ee`.
Audit date: 2026-09-06. Tier E. All reviewer inferences/recommendations are DERIVED / CANDIDATE.
This is continuity/authority reconstruction, not the financial/security/architecture-hardening audit.

## Register conventions

P0 = immediate catastrophic issue established; P1 = blocks a material continuation/workflow or
required provenance; P2 = scoped gap/risk requiring review; P3 = low-impact clarification.
Severity is reviewer triage, not a new product invariant. No P0 was established; absence of a P0
in this bounded audit is not proof no P0 exists.

Counts: 10 meaningful findings: 0 P0, 3 P1, 7 P2, 0 P3. No findings were created to fill severity buckets.
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
| Independent verification | Both texts read; no specific current contradictory product decision is asserted here. No second independent reviewer has verified this finding. |
| Disagreement | Not independently assessed; user disposition not yet recorded. |
| Resolution | OPEN — preserve existing sources and stop an affected conflict; no replacement precedence approved. |
| Resolution rationale | A classification document cannot silently amend the operating contract. |
| Decision impact | Before using tier labels to settle a conflict, obtain an explicit precedence clarification; do not infer that a ledger-wide or folder-wide label decides it. |
| Regression-test reference | N/A — governance provenance, not an application test. |
| Fix commit | None (no application fix). Documentation-only clarification, if any, is recorded by this audit commit. |
| Verification commit | Implementation evidence at 2248c137e43c6c043725830c1303756da1d210ee; no independent fix-verification commit. |
| Status | CANDIDATE / REVIEW_REQUIRED |

### CT-002 — Future delivery continuity

| Field | Record |
|---|---|
| ID | CT-002 |
| Audited commit | `2248c137e43c6c043725830c1303756da1d210ee` |
| Area | Future delivery continuity |
| Claim | A successor with only this baseline cannot safely execute the detailed plan through Phase 10: PHASE_04.md–PHASE_10.md are absent. |
| Evidence | Baseline git ls-tree/git ls-files; 02_PHASE_INDEX.md lists phase filenames/gates; docs/phase-3/baseline-remediation.md identifies the seven future guides and REMAINING_PHASE_GUIDE_MANIFEST.md among nine preserved exclusions. |
| Affected requirement/invariant | B24/B25; T57; required current-phase specification before implementation. |
| Severity | P1 |
| Confidence | HIGH |
| Source/model | Repository-only continuity reviewer; model identifier not recorded; not product authority. |
| Origin / Authority | DERIVED / CANDIDATE |
| Independent verification | Baseline inventory and preservation report checked; stash contents deliberately not opened. No second independent reviewer has verified this finding. |
| Disagreement | Not independently assessed; user disposition not yet recorded. |
| Resolution | OPEN — no guides restored or recreated. |
| Resolution rationale | Broad roadmap/contract summaries cannot recover exact milestones, acceptance criteria or later approved refinements. |
| Decision impact | Future-phase implementation must wait for separately authorized recovery/review or approved replacement specifications. A local stash is not transported by clone and is not an audit source. |
| Regression-test reference | N/A — file-presence/preservation check. |
| Fix commit | None (no application fix). Documentation-only clarification, if any, is recorded by this audit commit. |
| Verification commit | Implementation evidence at 2248c137e43c6c043725830c1303756da1d210ee; no independent fix-verification commit. |
| Status | BLOCKS_FUTURE_IMPLEMENTATION |

### CT-003 — New-tenant finance workflow

| Field | Record |
|---|---|
| ID | CT-003 |
| Audited commit | `2248c137e43c6c043725830c1303756da1d210ee` |
| Area | New-tenant finance workflow |
| Claim | Supplier/cost schema and selection work with test fixtures, but the baseline lacks a supported owner-facing or documented CLI path to create supplier identities/cost entries/preferred-supplier defaults. A newly onboarded tenant cannot complete the described normal confirmation flow from setup alone. |
| Evidence | services/invoice_editor.py::_prepare_cost requires an existing supplier for override; services/invoice_finance.py::_validate_confirmable_costs rejects absent supplier/cost; routes/invoices.py exposes cost-options GET, not cost creation. TenantSupplier has minimum name/tenant fields. InvoiceEditor.tsx shows cost controls only when options exist. cli/seed_demo.py creates no suppliers/costs. test_invoice_editor.py::_catalog and test_supplier_ledger.py::_supplier_context insert prerequisites directly. P3-M5 demo assumes existing supplier IDs. |
| Affected requirement/invariant | D-034; PHASE_03.md B/D/L; T32–T34/T60. |
| Severity | P1 |
| Confidence | HIGH for missing surface; MEDIUM for exact intended milestone ownership |
| Source/model | Repository-only continuity reviewer; model identifier not recorded; not product authority. |
| Origin / Authority | DERIVED / CANDIDATE |
| Independent verification | Route, schema, CLI, UI and fixture inventory inspected. No new end-to-end or hosted reproduction performed. No second independent reviewer has verified this finding. |
| Disagreement | Not independently assessed; user disposition not yet recorded. |
| Resolution | OPEN — no direct-SQL workaround, API, UI, seed change or spec reinterpretation implemented. |
| Resolution rationale | Schema-level foundation does not establish a reproducible user workflow; assigning it to Phase 6 automatically would be an undocumented scope decision. |
| Decision impact | Clarify/confirm the approved minimum Phase 3 provisioning/save-cost workflow and milestone boundary before declaring fresh-tenant finance demonstrable. Preserve complete-cost confirmation checks. |
| Regression-test reference | test_invoice_editor.py::test_editor_prefills_latest_tenant_cost_and_keeps_reasoned_override_revision_only; test_financial_schema.py::test_supplier_costs_are_tenant_private_append_only_and_independently_priced. No cold-start provisioning regression found. |
| Fix commit | None (no application fix). Documentation-only clarification, if any, is recorded by this audit commit. |
| Verification commit | Implementation evidence at 2248c137e43c6c043725830c1303756da1d210ee; no independent fix-verification commit. |
| Status | BLOCKS_AFFECTED_WORKFLOW |

### CT-004 — Financial formula provenance — no financial audit performed

| Field | Record |
|---|---|
| ID | CT-004 |
| Audited commit | `2248c137e43c6c043725830c1303756da1d210ee` |
| Area | Financial formula provenance — no financial audit performed |
| Claim | D-030 explicitly locks catalog grade/basis rounding, but an approved complete invoice-adjustment pricing-v1 formula and numerical example set cannot be located in baseline authority. PHASE_03.md requires locked/tested examples; implementation/tests supply additional choices. |
| Evidence | D-030; PHASE_03.md Gate C/D/N; docs/contracts/pricing.md remains a Phase 1 summary. services/invoice_editor.py::_prepare_items rounds quantity/effective-price products and applies fixed line adjustments; _totals aggregates and applies fixed invoice adjustments. Test test_editor_recalculates_pricing_v1_calculator_adjustments_and_immutable_updates encodes expected values, not independent approval. |
| Affected requirement/invariant | B09/B10/B11; T26/T35; no-invention rule for financial formulas. |
| Severity | P1 |
| Confidence | HIGH for catalog formula; MEDIUM for missing full invoice provenance |
| Source/model | Repository-only continuity reviewer; model identifier not recorded; not product authority. |
| Origin / Authority | DERIVED / CANDIDATE |
| Independent verification | Tracked normative Markdown searched for pricing-v1/formula/net_sales/discount/Q4; relevant service and test anchors inspected. No chat or study document treated as authority. No second independent reviewer has verified this finding. |
| Disagreement | Not independently assessed; user disposition not yet recorded. |
| Resolution | OPEN — existing arithmetic not changed; no formula approved by this audit. |
| Resolution rationale | A plausible implementation and passing example test cannot prove that the complete formula was approved. This finding is provenance, not a claim of arithmetic loss. |
| Decision impact | Recover approved source or ask a focused product decision on exact adjustment units/order/rounding examples before extending financial behavior. Do not infer percentage discounts or alternative rounding. |
| Regression-test reference | test_cash_van.py::test_pricing_v1_precedence_rounding_packaging_and_invoice_snapshot; test_invoice_editor.py::test_editor_recalculates_pricing_v1_calculator_adjustments_and_immutable_updates. |
| Fix commit | None (no application fix). Documentation-only clarification, if any, is recorded by this audit commit. |
| Verification commit | Implementation evidence at 2248c137e43c6c043725830c1303756da1d210ee; no independent fix-verification commit. |
| Status | BLOCKS_AFFECTED_DECISION |

### CT-005 — Implicit policy / P3-M5 post-hoc review

| Field | Record |
|---|---|
| ID | CT-005 |
| Audited commit | `2248c137e43c6c043725830c1303756da1d210ee` |
| Area | Implicit policy / P3-M5 post-hoc review |
| Claim | P3-M5 introduces several observable policy/architecture choices beyond the explicit capability and supplier-foundation requirements. The candidate inventory below records them without making them binding; a related earlier overdue-policy gap is separately labeled. |
| Evidence | PHASE_03.md J/H/P3-M5; 04_DECISIONS.md; services/public_invoices.py; public_invoice_security.py; schemas/public_invoices.py; routes/public_invoices.py; services/supplier_ledger.py; schemas/supplier_ledger.py; templates/public_invoice.html; InvoiceSharing.tsx; candidate table C01–C08. |
| Affected requirement/invariant | B17/B18/B15; T41/T47–T52/T61. |
| Severity | P2 |
| Confidence | HIGH for code behavior; MEDIUM for absence of approval |
| Source/model | Repository-only continuity reviewer; model identifier not recorded; not product authority. |
| Origin / Authority | DERIVED / CANDIDATE |
| Independent verification | Governing text compared with current implementation and scoped tests. No external or independent reviewer approval inferred. No second independent reviewer has verified this finding. |
| Disagreement | Not independently assessed; user disposition not yet recorded. |
| Resolution | OPEN — no candidate entered into 04_DECISIONS.md and no behavior changed. |
| Resolution rationale | An architectural or business-policy choice needs traceable authority; some may prove acceptable mechanical details after review. |
| Decision impact | Review candidates individually, distinguishing implementation mechanics from externally visible policy. Do not retroactively label all code as approved. |
| Regression-test reference | test_public_invoices.py; test_supplier_ledger.py; InvoiceSharing.test.tsx; PublicInvoicePage.test.ts; overdue tests for C08. |
| Fix commit | None (no application fix). Documentation-only clarification, if any, is recorded by this audit commit. |
| Verification commit | Implementation evidence at 2248c137e43c6c043725830c1303756da1d210ee; no independent fix-verification commit. |
| Status | OPEN_CANDIDATE |

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
| Independent verification | Exact Git diff and config/guard inspection; no stash parent/untracked payload accessed. Earlier fingerprint assertions are evidence from the report, not independently recreated here. No second independent reviewer has verified this finding. |
| Disagreement | Not independently assessed; user disposition not yet recorded. |
| Resolution | OPEN EVIDENCE LIMIT — retain supplied immutable baseline; do not rewrite history or infer additional approval. |
| Resolution rationale | Practical verification supports the narrow treatment but cannot manufacture a missing historical snapshot. |
| Decision impact | Audit existing behavior against authority, not an assumed clean P3-M5-only diff. This does not change AUDIT_BASE_SHA or alone invalidate the prior test results. |
| Regression-test reference | test_immutable_migration_files.py; prior baseline test report; exact documentation-only tree comparison. |
| Fix commit | None (no application fix). Documentation-only clarification, if any, is recorded by this audit commit. |
| Verification commit | Implementation evidence at 2248c137e43c6c043725830c1303756da1d210ee; no independent fix-verification commit. |
| Status | CANNOT_VERIFY_FULL_HISTORY |

## Candidate rules — never binding from this audit

All rows are DERIVED / CANDIDATE observations. The general requirement cited may be binding;
the specific implementation choice is not promoted with it. No row authorizes a change.

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

## Preservation and scope checks

The stash reference `9050d544791b5e22d15c2ff1a1acdbd503b40418` was read only as an object ID.
No stash content was opened, applied, popped, modified, dropped, or incorporated. Exclusion details
come exclusively from the existing baseline-remediation report. Future guides are not audit inputs.

The implementation baseline was not amended/rebased/rewritten. Only documentation changes are
permitted in this audit commit. Existing phase specifications, decision ledger, applied migrations,
application/tests, dependency/configuration files and frozen phase reports are not edited.
This commit does not start P3-M6 or approve any candidate decision.

## Documentation verification

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

## Final continuity assessment

CONDITIONAL PASS for this documentation handoff: reference, metadata, provenance and scope
checks pass, and the complete documentation diff has been reviewed. This is not an unqualified
pass for autonomous continuation through Phase 10, nor a renewed implementation acceptance gate.
CT-002 blocks detailed future-phase implementation; CT-003 blocks the affected fresh-tenant
finance workflow; CT-004 blocks claiming complete invoice-formula approval. Governance and
implicit policy candidates remain review-required. No finding is implemented or approved here.
Existing architecture/status documents were reused; authoritative history and the implementation
baseline were not rewritten. No independent second-reviewer or new runtime validation is claimed.

## Next audit recommendation only

A focused requirements/decision reconciliation review of CT-001–CT-005, especially the supplier-cost
cold-start boundary and full invoice-formula provenance. Obtain source/approval rather than implement
solutions. Resolve access to approved future specifications before future phases. Do not begin the
financial audit or P3-M6 automatically.
