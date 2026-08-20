# Tawzeevo

Tawzeevo is a multi-tenant Cash Van operations platform with a linked bilingual customer storefront. This repository is the authoritative monorepo for the platform.

Phase 1 is in progress. The repository currently includes the FastAPI/PostgreSQL platform foundation and a bilingual React operations client for authentication, profiles, public statistics, user administration, tenant application review, and tenant lifecycle controls.

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

Run the operations client from the repository root with `npm run dev:operations`. It uses `VITE_API_BASE_URL` for the API origin and defaults to `http://localhost:8000`.

No license has been granted for this repository.
