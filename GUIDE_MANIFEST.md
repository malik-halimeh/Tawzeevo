# GUIDE_MANIFEST.md — File Map

| File | Purpose | Read frequency |
|---|---|---|
| `AGENTS.md` | implementation-agent operating rules | every run / repository instructions |
| `00_PROJECT_CONTRACT.md` | locked product and architecture invariants | every implementation run |
| `01_TECH_STACK.md` | technology contract | every implementation run |
| `02_PHASE_INDEX.md` | phase/gate navigation | phase transitions |
| `03_IMPLEMENTATION_STATUS.md` | persistent milestone state | every run; update every milestone |
| `04_DECISIONS.md` | user-approved decisions only | when needed |
| `05_DESIGN_REFERENCES.md` | user-provided visual direction | design/UI milestones |
| `PHASE_01.md` ... `PHASE_10.md` | current phase contract and milestones | current phase only |
| `IMPLEMENTATION_MASTER_PROMPT.md` | initial implementation prompt | execute once |
| `ROOT_GUIDE_README.md` | human usage instructions | user-facing |

## Context rule

The implementation agent must not read all phase files at once. `AGENTS.md` defines the exact read order.
