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
| `PHASE_01.md` ... `PHASE_03.md` | phase contracts present at the implementation audit baseline | current phase only during implementation |
| `PHASE_04.md` ... `PHASE_10.md` | reconciled authoritative future phase specifications; explicit `REVIEW_REQUIRED` details remain gated | read only the phase being started, under AGENTS.md |
| `docs/recovered-planning/` | byte-matched historical Phase 4–10 planning and manifest plus reconciliation provenance | historical evidence only; never overrides root phases or later decisions |
| `docs/phase-<number>/` | frozen requirements audit, test report, and safe demo guide for each completed phase | phase completion and review |
| `IMPLEMENTATION_MASTER_PROMPT.md` | initial implementation prompt | execute once |
| `README.md` | human setup/run instructions; formerly listed ROOT_GUIDE_README.md is absent | user-facing |
| `AGENT_START_HERE.md` | repository-only continuation entry point | new reviewer/implementer |
| `docs/governance/SOURCE_OF_TRUTH.md` | authority/provenance classification without overriding AGENTS.md | interpreting evidence |
| `docs/architecture.md` | reconstructed architecture and current state | system orientation |
| `docs/TRACEABILITY_MATRIX.md` | requirement evidence and qualified gaps | targeted verification |
| `docs/audits/AUDIT_REGISTER.md` | findings, resolved provenance and remaining gated decisions | before affected work |

## Context rule

The implementation agent must not read all phase files at once. `AGENTS.md` defines the exact read order.
