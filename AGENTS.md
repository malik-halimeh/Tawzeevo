# AGENTS.md — Tawzeevo: Cash Van + Linked E-Commerce SaaS

## Purpose

This is the primary operating contract for the implementation agent in this repository.

The project is implemented **milestone by milestone**. Do not read every phase file at once. Keep context small, deterministic, and current.

## Mandatory read order at the start of every implementation run

Read only:

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
- produce the phase completion report;
- STOP.

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

## Final authority

If you are uncertain whether something is allowed, **ask before implementing it**.
