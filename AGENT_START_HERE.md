# AGENT_START_HERE.md — mandatory read before any implementation

Read this file first, then follow the read order in `AGENTS.md`. This file is a summary; the
canonical, binding text is **decision D-081 in `04_DECISIONS.md`**. If this summary and D-081
ever differ, D-081 wins.

## Who decides what

| Authority | Role | Owns |
|---|---|---|
| **Project owner** | final authority | every product/business decision; every conflict; gate commands (`Start Phase N`, `continue`) |
| **Design & Planning Agent** | planning, architecture reasoning, review, UI/UX design | phase and milestone planning; architecture reasoning and architecture-impact review; task contracts and acceptance intent for significant work; UI/UX direction; responsive/mobile presentation; the Tawzeevo design system (colours, typography, spacing, shapes, layout, motion, interaction patterns); component/reference selection; design-consistency review; major milestone/architecture review |
| **Implementation Agent** | orchestration and implementation | orchestrating the approved plan; breaking approved work into executable tasks; coding; migrations; tests; debugging; refactoring within approved boundaries; documentation updates; local implementation choices that change no approved architecture, product behaviour or design direction; keeping `03_IMPLEMENTATION_STATUS.md` and the phase evidence current |

The public repository names roles, not assistant products (D-025). The owner keeps the mapping of
roles to actual assistants outside the repository.

## Hard limits

The Implementation Agent must **not** on its own:
- redesign screens or components the Design & Planning Agent has approved;
- introduce a competing design language;
- change an approved architecture decision;
- reinterpret business requirements;
- alter roles, tenant scoping, state machines, financial calculations, ledger behaviour, sync
  semantics, cancellation rules, delivery rules or any other locked invariant.

The Design & Planning Agent must **not** on its own:
- change locked business requirements;
- bypass `04_DECISIONS.md`;
- redefine implementation behaviour for visual convenience;
- micromanage ordinary implementation details that are safely the Implementation Agent's.

## Precedence and conflicts

1. An approved plan or design specification from the Design & Planning Agent is **binding** on the
   Implementation Agent until the Design & Planning Agent or the owner revises it explicitly.
2. If such an artifact contradicts `00_PROJECT_CONTRACT.md`, a phase contract or `04_DECISIONS.md`,
   the contracts and the decision ledger win — **surface the contradiction; never resolve it
   silently.**
3. If the Design & Planning Agent is unavailable, keep implementing already-approved plans and
   designs; do **not** invent a new architecture or design direction to unblock yourself.
4. The Design-Agent Contract in `05_DESIGN_REFERENCES.md` stays in force: design may change colour,
   spacing, typography, shapes, layout, animation and responsive presentation, never
   business/architecture invariants.

## Where the rules live

- Canonical agent-role decision: `04_DECISIONS.md` **D-081**.
- Operating procedure, read order, no-invention rule, milestone protocol: `AGENTS.md`.
- Design-Agent Contract and visual references: `05_DESIGN_REFERENCES.md`.
- Persistent execution state: `03_IMPLEMENTATION_STATUS.md`.
