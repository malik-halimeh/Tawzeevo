# Lean continuous-assurance gates

These are derived completion checks. They do not alter the authority order, milestone protocol,
acceptance criteria, or phase rules in `AGENTS.md`. Candidate and inferred rules remain non-binding
until approved through existing governance.

## Milestone gate

A milestone is complete only after recording evidence that:

1. Governing requirements and approved decisions were identified.
2. Every milestone acceptance criterion is satisfied.
3. Relevant tests pass.
4. No unapproved product or architecture decision was silently introduced.
5. Important new behavior maps to tests.
6. Material code, schema, authorization, authentication, tenant, and financial changes are identified.
7. Graphify was refreshed and verified against the completed milestone commit.
8. The Graphify source SHA was recorded.
9. The blast radius of each material change was reviewed against direct repository evidence.
10. Relevant binding-invariant tests pass.
11. A relevant real-user workflow/E2E path is tested when such a workflow exists.
12. Documentation and implementation status are updated only where genuinely affected.
13. The working tree is clean at the milestone checkpoint.

Because a commit supplies the immutable SHA, refresh Graphify immediately after the completed
milestone commit. If the recorded freshness file changes, make a deliberate documentation/tooling
checkpoint; never let the script commit automatically.

## Phase gate

At phase completion, verify:

- a full Graphify refresh against the phase checkpoint;
- requirement-to-code/test traceability;
- architecture boundaries;
- binding-invariant regression coverage;
- the full relevant integration and E2E suite;
- static and security tooling appropriate to that phase;
- all open P0 and P1 findings are documented;
- forward dependencies against later approved phase specifications; and
- a `GO`, `CONDITIONAL GO`, or `NO-GO` decision under the existing project rubric.

No next phase may begin with an unresolved confirmed P0. A confirmed P1 that materially blocks the
next phase must be resolved or explicitly dispositioned under approved governance.

## Optional future assurance tools

Do not install a tool without a concrete failure class it addresses.

| Tool | Activation point |
|---|---|
| Hypothesis | After financial invariants are established, for suitable property-based tests. |
| Semgrep or equivalent static security enforcement | After binding tenant/authentication/authorization rules are established. |
| Schemathesis | When API contracts and workflows are stable enough for useful stateful API testing. |
| Import Linter | Only if an architecture audit identifies enforceable Python module-boundary contracts. |
| Playwright/E2E | Increase coverage as user-facing workflows mature, especially from Phase 5 onward; do not add new browser tooling merely for setup. |

CodeQL, additional agent frameworks, and third-party prompt/skill bundles are not part of this
foundation and have no approved activation here.
