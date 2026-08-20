# Phase 1 test report

Freeze date: 2026-08-20

## Automated results

| Gate | Result | Evidence |
|---|---:|---|
| PostgreSQL-backed backend suite | 70 passed | `apps/api/tests` |
| Backend statement coverage | 94% | `pytest-cov` over `apps/api/tawzeevo_api` |
| Frontend unit/integration suite | 10 passed | `apps/operations-web/src/App.test.tsx` |
| Python lint and formatting | PASS | Ruff check and format check |
| Python static typing | PASS | strict mypy over `tawzeevo_api` |
| Frontend lint | PASS | ESLint with zero warnings allowed |
| Frontend static typing | PASS | strict TypeScript build mode |
| Frontend production build | PASS | Vite production build |
| Alembic schema drift | PASS | no new upgrade operations detected |
| Migration from an empty database | PASS | isolated database upgraded to `20260820_0003` |
| PostgreSQL RLS | PASS | non-superuser tenant read isolation and cross-tenant write rejection |
| OpenAPI contract | PASS | required routes, unique operation IDs, bearer security, safe schemas |
| Live Arabic smoke | PASS | `lang=ar`, RTL layout/text, LTR phone input, no horizontal overflow |
| Public-repository safety | PASS | no secret signatures or prohibited external-assistant branding in the staged tree |

## Test ownership

- `test_auth.py` covers registration, validation, login, JWT, refresh rotation/reuse, logout, soft-delete authentication, and production configuration.
- `test_users.py` covers profiles, administrator CRUD, filters, pagination, statistics, soft deletion, and concurrent last-owner protection.
- `test_platform.py` covers tenant applications, transactional approval, replay rejection, access periods, suspension/reactivation, retained data, and audit events.
- `test_cash_van.py` covers approved-owner tenant access, customer/category/barcode product/draft invoice behavior, cross-tenant blocking, lifecycle blocking, money, and RLS policy presence.
- `test_hardening.py` covers protected-route denial, platform negative authorization, complete OpenAPI shape, migrations from zero, and real non-superuser RLS enforcement.
- `test_admin_cli.py` and `test_seed_demo.py` cover credential-safe administrator bootstrap and owner-scoped synthetic demo data.
- `App.test.tsx` covers registration, login/session storage boundaries, protected routing, user administration, application approval, suspension/reactivation, loading, failures, and RTL.

## Reproduction

Use a disposable PostgreSQL database that has been migrated to the current head, set `DATABASE_URL`, `TEST_DATABASE_URL`, and a local test-only `JWT_SECRET`, then run the commands in the root `README.md` validation section. The migration-from-zero test creates and removes its own uniquely named disposable database and therefore requires database-create permission in the test environment.

No known critical or high-severity Phase 1 defect remains at freeze.
