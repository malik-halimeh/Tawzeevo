# IMPLEMENTATION MASTER PROMPT — Start the Tawzeevo Project

Run the prompt below from the repository root after placing all guide files in the root.

---

You are the implementation agent for this repository.

Your task is to implement Tawzeevo, the Cash Van + linked e-commerce SaaS, strictly from the repository's Markdown contracts.

## First instruction: use the repository instruction system

Before changing code, read:

1. `AGENTS.md`
2. `00_PROJECT_CONTRACT.md`
3. `01_TECH_STACK.md`
4. `02_PHASE_INDEX.md`
5. `03_IMPLEMENTATION_STATUS.md`
6. `PHASE_01.md`
7. `04_DECISIONS.md`

Read `05_DESIGN_REFERENCES.md` only when the current milestone includes UI/design work.

Do **not** preload `PHASE_02.md` through `PHASE_10.md`. The phase files intentionally divide context so you do not overload yourself or mix future requirements into current implementation.

Treat `AGENTS.md` as your operating contract.

## Source-of-truth rule

Phase 1 is non-negotiable: every program requirement documented in `PHASE_01.md`, including the frontend that the original source called a bonus, must be implemented in Phase 1.

Do not postpone a Phase 1 requirement because a later architecture would be cleaner.

At the same time, do not implement later-phase features early unless Phase 1 explicitly requires a foundation/skeleton for them.

## No invention

Do not invent product behavior, schema meaning, roles, permissions, APIs, financial rules, UX behavior, third-party provider choices, or new architecture.

If a needed decision is not explicitly defined:
- stop the affected work;
- ask me one focused question;
- offer at most three options;
- recommend one;
- wait for my decision;
- record the approved answer in `04_DECISIONS.md`;
- only then continue.

Mechanical private implementation details that do not change behavior are allowed as defined in `AGENTS.md`.

## Current objective

Begin **Phase 1, Milestone P1-M1 only**.

Do not implement P1-M2 in this run.

### P1-M1 expected work

Following `PHASE_01.md`:
- inspect the existing repository before editing;
- preserve existing compliant work if any;
- establish the monorepo boundaries;
- scaffold/configure the FastAPI API;
- scaffold/configure the React + TypeScript + Vite operations frontend;
- configure PostgreSQL development/test connection strategy;
- configure SQLAlchemy and Alembic;
- create Phase 1 foundation models/migration for users, auth sessions, tenants (including lifecycle/access fields), tenant memberships, tenant invitations, tenant applications, and audit events;
- configure environment handling and `.env.example` without secrets;
- create backend/frontend test harnesses;
- establish lint/type/test commands;
- create the required architecture-contract documentation skeletons, including platform-admin tenant lifecycle/access control and owner-as-operator rules, without implementing unrelated future-phase functionality;
- make migration-from-zero and application startup work.

Use the technologies locked in `01_TECH_STACK.md`.

Do not add stock, availability, customer login, customer tracking, early AI, or any other non-approved feature.

## Repository state

If the repository is not empty:
- audit what is present;
- do not replace valid work unnecessarily;
- report any conflict with the contracts before destructive changes.

If a required local tool such as Docker is unavailable and this changes the prescribed implementation path, ask before substituting a different infrastructure strategy.

## Validation

Before marking P1-M1 complete, run every check required by that milestone that the environment permits.

If a check cannot run because of environment/tooling, report the exact blocker and do not falsely mark it passed.

## Persistent progress

Update `03_IMPLEMENTATION_STATUS.md`:
- set P1-M1 IN_PROGRESS when you begin;
- on success mark P1-M1 COMPLETE;
- set current milestone to P1-M2 NOT_STARTED;
- record concise validation evidence.

Do not unlock a future phase.

## End-of-run behavior

At the end, respond using the exact concise milestone format from `AGENTS.md`.

Then stop.

My next command will normally be:

`continue`

When I say `continue`, execute exactly the next milestone in the current phase according to `AGENTS.md` and `03_IMPLEMENTATION_STATUS.md`, validate it, update status, report, and stop again.

When Phase 1 is complete, do not begin Phase 2 from a generic `continue`. Wait for my explicit `Start Phase 2`.

Begin now.
