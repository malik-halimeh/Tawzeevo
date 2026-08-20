# Folder responsibilities

## Root

- `AGENTS.md` defines the milestone operating contract.
- `00_PROJECT_CONTRACT.md` and `04_DECISIONS.md` contain approved product and architecture rules.
- `01_TECH_STACK.md` locks technology choices.
- `02_PHASE_INDEX.md`, `03_IMPLEMENTATION_STATUS.md`, and `PHASE_XX.md` files control phased execution.
- `compose.yaml` defines isolated local PostgreSQL development and test services.
- `package.json` coordinates frontend workspace checks and development commands.

## Applications

- `apps/api/tawzeevo_api/routes` owns thin HTTP handlers.
- `apps/api/tawzeevo_api/schemas` owns validated request/response contracts.
- `apps/api/tawzeevo_api/services` owns authoritative business rules and transactions.
- `apps/api/tawzeevo_api/repositories` owns reusable persistence queries where needed.
- `apps/api/tawzeevo_api/cli` owns non-public operational commands such as safe administrator bootstrap and synthetic demo seeding.
- `apps/api/alembic` owns ordered PostgreSQL schema migrations.
- `apps/api/tests` owns unit, API, authorization, RLS, migration, and integration regressions.
- `apps/operations-web/src/api` owns the typed HTTP boundary and in-memory access token.
- `apps/operations-web/src/auth` owns browser session state.
- `apps/operations-web/src/pages` owns route-level screens.
- `apps/operations-web/src/components` owns shared semantic interface components and route guards.
- `apps/operations-web/src/i18n.ts` owns Phase 1 English/Arabic strings and direction changes.
- `apps/storefront-web` is a documented future boundary and contains no implemented Phase 1 storefront.

## Shared boundaries

The directories under `packages` are placeholders for API clients, contracts, UI, localization, and configuration that later phases may share. They do not contain invented future behavior.

## Documentation and operations

- `docs/contracts` summarizes approved contracts without superseding the authoritative root files.
- `docs/phase-1` contains frozen completion evidence and the demo guide.
- `docs/architecture.md` explains current system boundaries and security flow.
- `docs/future-phases.md` summarizes only the approved phase sequence.
- `infra` documents local service infrastructure.
- `scripts` documents repository-safe automation policy.
