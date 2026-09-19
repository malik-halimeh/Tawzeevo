# AGENTS.md — Tawzeevo: Cash Van + Linked E-Commerce SaaS

## Purpose

This is the primary operating contract for the implementation agent in this repository.

The project is implemented **milestone by milestone**. Do not read every phase file at once. Keep context small, deterministic, and current.

## Agent roles

Two agents work under the project owner: a **Design & Planning Agent** (planning, architecture
reasoning, review, UI/UX design) and an **Implementation Agent** (orchestration and
implementation). The canonical, binding definition is decision **D-081** in `04_DECISIONS.md`;
`AGENT_START_HERE.md` summarises it and must be read before any implementation. Nothing in this
file overrides D-081.

## Mandatory read order at the start of every implementation run

Read only:

0. `AGENT_START_HERE.md` (agent roles and limits; canonical text is D-081)
1. `AGENTS.md`
2. `00_PROJECT_CONTRACT.md`
3. `01_TECH_STACK.md`
4. `03_IMPLEMENTATION_STATUS.md`
5. the current `PHASE_XX.md`
6. `04_DECISIONS.md` only if the current task depends on a recorded decision
7. `05_DESIGN_REFERENCES.md` only for UI/design work

Use `02_PHASE_INDEX.md` only to locate the current/next phase and its gate.

**Do not preload future phase files.** Read a future phase only when a current architectural question cannot be answered by the project contract and the future dependency is directly affected.

## Source-of-truth precedence

Highest to lowest:

1. The exact Phase 1 program requirements embedded in `PHASE_01.md`.
2. User-approved decisions recorded in `04_DECISIONS.md`.
3. `00_PROJECT_CONTRACT.md`.
4. The current `PHASE_XX.md`.
5. `01_TECH_STACK.md`.
6. Existing implementation that is already compliant with the above.
7. Mechanical implementation choices.

If two instructions conflict, stop before implementing the conflicting behavior and ask the user.
An approved plan or design specification from the Design & Planning Agent is binding on the
Implementation Agent but sits below items 1–4 of this list: when it contradicts them, surface the
contradiction (D-081).

## No-invention rule

You MUST NOT invent or silently change:

- product behavior;
- business rules;
- roles/permissions;
- database meaning;
- API behavior;
- state transitions;
- financial formulas;
- security behavior;
- offline conflict behavior;
- third-party providers/scopes;
- new dependencies that materially affect architecture;
- new features;
- new product fields presented as business requirements;
- future scope.

If a required decision is not defined:

1. stop the affected work;
2. ask one focused question;
3. state the exact ambiguity;
4. provide at most 3 options;
5. recommend one option with a brief reason;
6. do not implement the disputed choice until the user approves it;
7. after approval, record it in `04_DECISIONS.md`.

### What is NOT considered invention

You may choose ordinary mechanical details that do not change behavior, such as:

- local variable names;
- private helper names;
- test fixture names;
- obvious file placement inside the prescribed structure;
- refactoring that preserves contracts;
- exact patch/minor dependency versions compatible with the locked technology major versions.

If a mechanical choice introduces a new public contract or dependency category, it is no longer mechanical: ask first.

## Milestone execution protocol

`03_IMPLEMENTATION_STATUS.md` is persistent execution state.

When the user gives the initial project prompt:
- inspect repository state;
- verify instruction files;
- start the current milestone only.

When the user says **`continue`**:
- read `03_IMPLEMENTATION_STATUS.md`;
- if a milestone is `IN_PROGRESS`, resume it;
- otherwise execute the next milestone in the current phase;
- complete exactly ONE milestone;
- run its required checks;
- update `03_IMPLEMENTATION_STATUS.md`;
- stop.

Do not execute two milestones from one `continue`.

### Phase boundary

When the last milestone of a phase passes:
- mark the phase `COMPLETE`;
- create or update `docs/phase-<number>/requirements-audit.md` with requirement-to-code/test evidence and the phase Definition of Done;
- create or update `docs/phase-<number>/test-report.md` with the dated, actually executed validation results and reproduction commands;
- create or update `docs/phase-<number>/demo-guide.md` with a synthetic-data presentation workflow, phase boundary, and pre-demo checklist;
- produce the concise phase completion report;
- STOP.

The three phase evidence files are required completion artifacts. Generate them automatically when
the final milestone passes; do not wait for a separate user request. They are frozen evidence, not
new sources of truth, and must never claim behavior beyond the completed phase or contain secrets,
credentials, production data, or invented test results.

A generic `continue` must **not** cross into the next phase.

The user must explicitly say:

`Start Phase 2`
`Start Phase 3`
etc.

Before starting a phase with an architecture gate, verify the gate in that phase file. If any gate item is unresolved, ask before coding.

## Definition of milestone complete

A milestone is complete only when:

- required code is implemented;
- migrations are valid when applicable;
- relevant tests pass;
- type/lint checks for touched code pass;
- no known contract violation remains;
- documentation/status is updated;
- no unrelated feature was added.

Never mark a milestone complete with failing required tests.

## Repository safety

- Inspect before modifying.
- Preserve existing compliant work.
- Do not rewrite working modules merely for stylistic preference.
- Do not delete unexplained files.
- Do not perform destructive database operations outside disposable local/test databases.
- Do not modify applied shared migrations; create a new migration.
- Do not force-push or rewrite Git history.
- Do not push/merge/release unless the user explicitly asks.
- Never commit secrets, tokens, credentials, `.env` values, production data, or private customer data.
- Keep generated artifacts and temporary files out of source control unless required.

## Implementation style

- Backend owns authoritative business rules.
- Route handlers stay thin.
- Use explicit transactions for multi-record invariants.
- Validate authorization before business access.
- Make tenant scope explicit.
- Prefer small composable services over giant modules.
- Use typed schemas and strict TypeScript.
- Use database constraints for invariants that belong in the database.
- Write tests for each bug/invariant before calling it resolved.
- Avoid speculative abstractions.
- Avoid premature optimization.
- Do not add stock/availability behavior under another name.

## Required end-of-milestone response

Keep the report concise:

```text
Milestone: <ID> <name>
Status: COMPLETE | BLOCKED

Implemented:
- ...

Validation:
- test/check -> PASS/FAIL
- ...

Migrations:
- none | <revision>

Contract notes:
- none | ...

Next:
- <next milestone ID/name>

User command:
continue
```

If blocked, replace `Next` with the exact decision needed.

## Context discipline

The instruction system is intentionally layered. Do not summarize/rewrite all root docs into new duplicate files.

At the start of a milestone:
- read the minimum required files;
- inspect the relevant code;
- work from tests/contracts;
- update status.

Do not repeatedly reread all phase files.

## Lean continuous assurance

The authority order and milestone protocol above remain controlling. When structural graph evidence
is used, follow `private/docs/assurance/GRAPHIFY.md`; Graphify is supplemental and its recorded source SHA
must match the intended audited commit. Never establish a critical finding from an inferred or
ambiguous relationship without direct repository evidence.

Use `private/docs/assurance/ASSURANCE_GATES.md` at milestone and phase checkpoints. After each completed
milestone commit, and after the material change classes listed in the Graphify policy, run the
repository refresh script and verify its recorded SHA. The script and generated graph are development
tooling only and must not be required by the application at runtime.

## Final authority

If you are uncertain whether something is allowed, **ask before implementing it**.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, use the installed graphify skill or instructions before doing anything else.

Rules:
- Before relying on graph results, verify the recorded application source SHA and freshness under `private/docs/assurance/GRAPHIFY.md`; never use a stale graph as evidence.
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the local graph current (AST-only, no API cost), then follow the repository refresh/checkpoint process in `private/docs/assurance/GRAPHIFY.md` when it applies.
