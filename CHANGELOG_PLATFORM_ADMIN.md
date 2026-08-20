# Platform Admin / Tenant Access Change — Affected Files

Only these generated files are affected:

1. `00_PROJECT_CONTRACT.md`
   - Adds tenant application approval.
   - Defines manual access periods, suspension for non-payment, reactivation, and data preservation.
   - Clarifies platform admin does not become tenant owner or gain private tenant data automatically.
   - Changes out-of-scope billing wording: automatic payment-provider charging remains out of scope; manual access control is now in scope.
   - Preserves the previously approved owner-as-Cash-Van-operator rule.

2. `02_PHASE_INDEX.md`
   - Updates Phase 1 objective to include platform tenant approval/access control.
   - Preserves the previously approved owner/driver Phase 7 wording/gate.

3. `04_DECISIONS.md`
   - Adds D-021 owner-as-operator decision.
   - Adds D-022 platform admin tenant-application decision.
   - Adds D-023 non-payment suspension/data-retention/manual-access-period decision.

4. `PHASE_01.md`
   - Implements tenant applications and manual SaaS access control in Phase 1.
   - Adds DB fields/models, exact production routes, authorization, tests, UI requirements, milestone changes, and DoD.
   - Replaces direct production tenant self-onboarding with application → admin approval → tenant+owner creation.
   - Preserves every original academic Phase 1 requirement.
   - Preserves the owner-as-operator architecture lock.

5. `IMPLEMENTATION_MASTER_PROMPT.md`
   - Updates P1-M1 foundation schema/document expectations so the implementation agent creates the correct tenant application/access-control foundation from the first migration.

Unchanged because this product change does not alter their purpose:
- `AGENTS.md`
- `01_TECH_STACK.md`
- `03_IMPLEMENTATION_STATUS.md`
- `05_DESIGN_REFERENCES.md`
- `GUIDE_MANIFEST.md`
