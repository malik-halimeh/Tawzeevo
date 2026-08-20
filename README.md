# Tawzeevo

Tawzeevo is a multi-tenant Cash Van operations platform with a linked bilingual customer storefront. This repository is the authoritative monorepo for the platform.

Phase 1 is in progress. The current milestone establishes the FastAPI, PostgreSQL/Alembic, and React/TypeScript/Vite foundations without implementing later product behavior.

## Repository layout

- `apps/api` — FastAPI service and PostgreSQL migrations
- `apps/operations-web` — React operations client
- `packages` — shared package boundaries reserved by the architecture
- `docs/contracts` — approved architecture contracts
- `infra` — local infrastructure configuration
- `scripts` — repository automation

## Local prerequisites

- Python 3.13+
- Node.js 22+
- Docker with Compose (preferred PostgreSQL development/test runtime)

Copy `.env.example` to `.env`, use development-only values, then follow the component READMEs.

No license has been granted for this repository.
