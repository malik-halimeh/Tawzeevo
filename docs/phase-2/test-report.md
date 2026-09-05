# Phase 2 test report

Freeze date: 2026-08-26

Status: PASS

This report records the Phase 2 completion run preserved in `RUN_TESTS.md` and
`03_IMPLEMENTATION_STATUS.md`. Commands assume execution from the repository root and a deliberately
disposable PostgreSQL database. No hosted or production database credentials are recorded here.

## Final automated results

| Gate | Result | Evidence |
|---|---:|---|
| PostgreSQL-backed backend suite | 92 passed | `apps/api/tests` |
| Backend statement coverage | 93% | pytest-cov over `tawzeevo_api` |
| Frontend unit/integration suite | 27 passed | operations client Vitest suite |
| Python lint | PASS | Ruff check |
| Python formatting | PASS | Ruff format check |
| Python static typing | PASS | configured strict mypy |
| Frontend lint and static typing | PASS | `npm run check` |
| Frontend production build | PASS | Vite build, 208 modules; non-blocking size advisory only |
| Alembic schema drift | PASS | no ungenerated model operations at revision `20260826_0007` |
| Migration from an empty database | PASS | empty PostgreSQL database upgraded through `0001`–`0007` |
| Latest migration reversibility | PASS | downgrade `0007` to `0006`, then upgrade to `0007` |
| PostgreSQL tenant isolation | PASS | non-bypass role read filtering and cross-tenant write rejection |
| `pricing-v1` financial arithmetic | PASS | precedence, fallback, Decimal rounding, and piece/box cases |
| Media security | PASS | decode/re-encode, type/size/dimension validation, authentication, tenant scope, traversal rejection |
| Catalog import quality and provenance | PASS | GTIN/duplicate gate, attribution, checksum/version idempotency, conflict rollback |
| Imported barcode acceptance | PASS | imported name to tenant-specific image, price, and grade pricing across isolated tenants |

## Milestone validation progression

| Milestone | Backend result | Frontend result | Important acceptance evidence |
|---|---:|---:|---|
| P2-M1 | Included in later aggregate runs | Included in later aggregate runs | Membership lifecycle, last-owner invariant, explicit tenant predicates, forced RLS |
| P2-M2 | 83 passed, 93% coverage | 24 passed | Customer disambiguation, grades/location, bilingual category/archive workflows |
| P2-M3 | 85 passed, 93% coverage | 26 passed | Master/tenant ownership, known adoption, unknown manual flow, package barcode, RLS |
| P2-M4 | 88 passed, 93% coverage after re-audit | 27 passed | Exact pricing ties, invoice selling-price provenance, safe media, migration `0006` |
| P2-M5 / phase acceptance | 92 passed, 93% coverage | 27 passed | Licensed import, provenance/idempotency/rollback, imported scan-to-price/image, migration `0007` |

## Test ownership

- `test_cash_van.py` covers tenant access, membership lifecycle, customers, grades, categories,
  products, barcodes, publication visibility, pricing, packaging, media, draft selling-price
  snapshots, and imported-catalog acceptance.
- `test_hardening.py` covers the protected-route matrix, migrations from zero, Alembic shape, and
  real non-superuser PostgreSQL RLS enforcement.
- `test_catalog_import.py` covers quality reporting, GTIN and duplicate rejection, source/license
  validation, persisted provenance, checksum/version idempotency, CLI check-only mode, and atomic
  conflict rollback.
- `test_users.py` retains concurrent last-owner and user-lifecycle regressions needed by tenant
  membership safety.
- `App.test.tsx` covers duplicate customer selection, bilingual categories, known and unknown
  barcode flows, publication, package barcodes, grade pricing, image upload, and RTL behavior.
- Earlier Phase 1 authentication, authorization, platform lifecycle, OpenAPI, and administrator CLI
  tests remain part of the full regression suite.

## Reproduction

Configure `DATABASE_URL`, `TEST_DATABASE_URL`, and a local test-only `JWT_SECRET` as described in the
root README. The test URL must identify a disposable PostgreSQL database and must never point to
shared, staging, or production data.

```powershell
.\.venv\Scripts\python.exe -m pytest apps/api/tests -q --cov=tawzeevo_api --cov-report=term-missing --cov-fail-under=80
.\.venv\Scripts\python.exe -m ruff check apps/api
.\.venv\Scripts\python.exe -m ruff format --check apps/api
.\.venv\Scripts\python.exe -m mypy --config-file apps/api/pyproject.toml apps/api/tawzeevo_api
.\.venv\Scripts\python.exe -m alembic -c apps/api/alembic.ini check
npm run check
```

The full per-test node commands and milestone execution log are maintained in `RUN_TESTS.md`.

## Known limitations at freeze

- The committed Open Food Facts snapshot is intentionally small and not comprehensive.
- The local media adapter is intended for local development and demonstrations, not durable
  production object storage.
- The frontend build emitted a size advisory, not a failure.
- Phase 2 does not test or claim the later confirmed-invoice, ledger, payment, refund, storefront,
  offline, supplier, or delivery engines.

No known critical or high-severity Phase 2 defect remained at freeze.
