# Tawzeevo Unit Test Strategy

## 1. Purpose and scope

This document is the blueprint for adding fast, deterministic unit tests to Tawzeevo without changing product behavior or weakening the existing PostgreSQL-backed verification. It is a plan only: no proposed unit-test file exists yet, and no application or test code is authorized by this document.

Phase 1 is complete and Phase 2 remains locked. The strategy therefore tests the behavior that is already implemented in Phase 1, including the reversible role-demo boundary, and does not introduce future storefront, inventory, financial-ledger, delivery, offline-sync, or procurement behavior.

### What “unit test” means here

A unit test exercises one small behavior with no network and, normally, no real database. Pure functions, Pydantic validation, token construction, role predicates, formatting, request construction, and React state/guard behavior are good unit-test subjects.

The following are **not** proven by mocked unit tests and must remain real PostgreSQL integration tests:

- SQLAlchemy query correctness and PostgreSQL-specific expressions;
- transactions, row locks, refresh-token reuse serialization, and concurrent owner deletion;
- RLS policies and tenant-session variables;
- migration-from-zero behavior and schema constraints;
- commit/rollback atomicity across several records;
- FastAPI/OpenAPI contract wiring and full request/response behavior.

### Present-state baseline

- `docs/phase-1/test-report.md` records a frozen Phase 1 result of 70 PostgreSQL-backed backend tests with 94% statement coverage.
- `apps/api/tests/` already covers authentication, users, tenant lifecycle, Cash Van behavior, RLS, migrations, CLIs, and OpenAPI primarily through API/integration tests.
- `apps/operations-web/src/App.test.tsx` contains 10 production-flow component/integration tests.
- `apps/operations-web/src/ApplicationRoot.test.tsx` contains 12 isolated demo-gallery tests.
- Backend database tests intentionally skip when `TEST_DATABASE_URL` is absent because their autouse fixture truncates a disposable database.
- There is no dedicated database-independent backend unit-test lane yet.

The purpose of the new lane is faster failure localization and exhaustive edge-case coverage, not replacing the existing suite or inflating test counts.

## 2. Project Structure Overview

```text
Tawzeevo/
├── AGENTS.md, 00_PROJECT_CONTRACT.md, 01_TECH_STACK.md
├── PHASE_01.md, 03_IMPLEMENTATION_STATUS.md, 04_DECISIONS.md
│   └── authoritative scope, architecture, decisions, and execution state
├── render.yaml, compose.yaml, .env.example
│   └── deployment/local infrastructure configuration; never test secret values
├── apps/
│   ├── api/
│   │   ├── pyproject.toml                 Python/test/tool configuration
│   │   ├── alembic/                      migration environment and revisions
│   │   ├── tawzeevo_api/
│   │   │   ├── main.py                   FastAPI assembly, CORS, error handlers, health
│   │   │   ├── config.py                 environment settings and production guards
│   │   │   ├── database.py               engine/session dependency
│   │   │   ├── models.py                 ORM entities, enums, and constraints
│   │   │   ├── phone.py                  phone parsing and E.164 normalization
│   │   │   ├── security.py               Argon2id, refresh hashing, JWT issue/decode
│   │   │   ├── dependencies.py           auth/session and system/tenant role checks
│   │   │   ├── errors.py                 application error types
│   │   │   ├── schemas/                  Pydantic request/response validation
│   │   │   ├── repositories/auth.py      locked auth/session lookups and revocation
│   │   │   ├── services/                 authoritative business/transaction rules
│   │   │   ├── routes/                   thin HTTP adapters and auth cookies
│   │   │   └── cli/                      admin bootstrap and synthetic demo seed
│   │   └── tests/                         existing PostgreSQL/API integration suite
│   ├── operations-web/
│   │   ├── src/api/                       typed API contracts and fetch client
│   │   ├── src/auth/                      in-memory access-token session lifecycle
│   │   ├── src/components/                route guards and shared semantic UI
│   │   ├── src/pages/                     forms, queries, mutations, and role surfaces
│   │   ├── src/demo/                      reversible, synthetic, memory-only gallery
│   │   ├── src/App.tsx                    production route tree
│   │   ├── src/App.test.tsx               production component/integration coverage
│   │   └── src/ApplicationRoot.test.tsx   isolated demo coverage
│   └── storefront-web/                    future placeholder; not a current target
├── packages/                              future shared-package placeholders
├── infra/, scripts/                       documented placeholders/support material
└── docs/                                  architecture, contracts, audits, and guides
```

Simple route forwarding, static configuration, styles, generated manifests, README placeholders, and empty package boundaries were inventoried but are intentionally not high-value unit targets.

## 3. High-Value Test Targets

### Priority definitions

- **P0:** security, authorization, money, tenant boundary, or destructive-state risk.
- **P1:** important validation, error mapping, lifecycle, or request-construction behavior.
- **P2:** useful regression localization with lower production risk.

### Backend targets

| Priority | Source and symbols | Behavior worth isolating | Recommended unit boundary | Keep in integration tests |
|---|---|---|---|---|
| P0 | `apps/api/tawzeevo_api/security.py` — `hash_password`, `verify_password`, `generate_refresh_token`, `hash_refresh_token`, `create_access_token`, `decode_access_token` | Password hashes verify without exposing plaintext; refresh hashes are deterministic SHA-256 while generated tokens are high-entropy; JWT claims, issuer, audience, security version, session ID, and time boundaries are correct. | Real cryptographic helpers with fixed `Settings`, fixed UUIDs, and fixed `now`; decode the issued token and assert claims. Patch only randomness when a deterministic `jti` assertion is necessary. | Database session validity, revocation, refresh rotation, and concurrency. |
| P0 | `apps/api/tawzeevo_api/dependencies.py` — `AccessClaims`, `get_current_user`, `require_system_admin`, `require_client`, `require_tenant_owner` | Invalid claim shapes are rejected; correct identities pass; incorrect system or tenant roles produce the exact `AppError` status/code. | Construct model/dataclass objects directly. Test the pure role gates without FastAPI or a database. | `get_auth_context` session lookup/expiry and `resolve_tenant_context` RLS/membership queries require focused service/integration coverage. |
| P0 | `apps/api/tawzeevo_api/services/auth.py` — `login`, `_create_session`, `rotate_refresh_token`, `logout` | Constant-work missing-user path, deleted-user rejection, session expiration, security-version mismatch, rotation/reuse states, and logout idempotence. | Isolate decision branches with controlled repository collaborators and a minimal session double only where SQL is not the behavior under test. Assert error codes and state transitions. | Lock acquisition, replay serialization, mass revocation, commit/rollback, and real session persistence must remain PostgreSQL tests. |
| P0 | `apps/api/tawzeevo_api/services/users.py` — `_email_conflicts`, `update_user_profile`, `soft_delete_user`, `list_users` | Email ownership logic; password/role changes increment `security_version` and revoke sessions; ordinary profile changes do not; normalized filters and page math; last-owner protection contract. | Directly test pure decisions and collaborator calls. Extract no new public behavior. Query-shape assertions may inspect compiled statements only when stable and useful. | Concurrent last-owner deletion, locks, atomic membership/session revocation, actual filter results, and rollback safety. |
| P0 | `apps/api/tawzeevo_api/services/platform.py` — `_access_state`, `tenant_response`, `_ensure_not_shortened`, `suspend_tenant`, `reactivate_tenant` | Exact current/grace/overdue boundary dates; response projection; access period cannot shorten; only valid lifecycle transitions; suspension reason cleared on reactivation; invalid grace/access ordering. | `_access_state` and `_ensure_not_shortened` are pure unit targets using fixed dates and lightweight model objects. Lifecycle decision branches can use a controlled `_tenant_for_update` collaborator. | Transactional approval, audit persistence, row locks, retained tenant data, and RLS. |
| P0 | `apps/api/tawzeevo_api/services/cash_van.py` — `_money`, `product_response`, `create_draft_invoice` | `ROUND_HALF_UP` to four decimals; piece/box conversion; missing box size failure; immutable response projection; line totals/subtotal; single-currency requirement; missing products. | Test `_money` and `product_response` directly with Decimal boundary cases. For invoice arithmetic, isolate a deterministic calculation seam only if implementation work is separately approved; do not mock a transaction and call that proof. | Tenant-scoped product/customer lookup, inserts, commits, RLS, and persisted invoice/item totals. |
| P1 | `apps/api/tawzeevo_api/phone.py` — `normalize_phone` | Whitespace handling, Lebanese default region, international input, E.164 output, impossible/invalid/blank numbers, and exception contract. | Call the real `phonenumbers` library with a small table of deterministic examples. | API/Pydantic error-envelope mapping. |
| P1 | `apps/api/tawzeevo_api/schemas/auth.py` — `normalize_required_text`, `RegisterRequest`, `LoginRequest` | NFC/trim/lowercase normalization; non-whitespace names/city; age limits; password 10–128 Unicode characters; invalid phone/email; extra-field rejection; no public `type`. | Instantiate Pydantic models directly and assert normalized values or validation locations/messages. | Full HTTP 422 envelope and duplicate database email. |
| P1 | `apps/api/tawzeevo_api/schemas/users.py` — `normalize_optional_text`, `ProfileUpdateRequest`, `AdminCreateUserRequest`, `AdminUpdateUserRequest` | Empty update rejected; explicitly null field rejected; partial values normalized; self-profile schema has no role field; admin schema accepts valid system roles. | Direct Pydantic validation, including `model_fields_set` cases. | Authorization and persisted profile/session changes. |
| P1 | `apps/api/tawzeevo_api/schemas/platform.py` — application/access/reactivation validators | Business/review text normalization; grace date never precedes access date; default suspension reason; optional reactivation fields preserve omitted-versus-explicit-null meaning. | Direct Pydantic construction with fixed dates. | Lifecycle persistence and audit rows. |
| P0 | `apps/api/tawzeevo_api/schemas/cash_van.py` — product/invoice validators | Currency uppercasing and three-letter validation; positive money/quantity; barcode/name trimming; BOX requires `pieces_per_box`; PIECE rules; non-empty bounded invoice items. | Direct Pydantic model tests using Decimal, UUID, and table-driven valid/invalid cases. | Foreign keys, unique barcodes, tenant visibility, and persisted invoices. |
| P1 | `apps/api/tawzeevo_api/config.py` — `Settings.validate_production_security` | Production rejects default/short secrets and insecure refresh cookies; development defaults remain usable. | Instantiate `Settings` with explicit non-secret dummy values and an isolated environment. Never read a developer `.env`. | Deployed provider configuration. |
| P1 | `apps/api/tawzeevo_api/routes/auth.py` — `set_refresh_cookie`, `clear_refresh_cookie` | Cookie name, path, max-age, HttpOnly, Secure, and SameSite attributes follow settings; clearing uses the same scope. | Use a FastAPI/Starlette `Response` and deterministic test settings. | Browser cross-origin cookie behavior and full login/refresh routes. |
| P2 | `apps/api/tawzeevo_api/cli/create_admin.py`, `cli/seed_demo.py` | Password confirmation and exit codes; no password argument; currency/phone normalization; replay and role failures map to safe output. | Patch argument/getpass/session boundaries; test parsers and return codes without a real production database. | Actual admin/demo inserts and tenant authorization remain existing PostgreSQL tests. |

### Frontend targets

| Priority | Source and symbols | Behavior worth isolating | Recommended unit/component boundary | Avoid duplicating |
|---|---|---|---|---|
| P0 | `apps/operations-web/src/api/client.ts` — `ApiError`, `setAccessToken`, `refreshAccessToken`, `apiRequest`, `loginRequest`, `clearSession` | Base URL normalization; JSON headers only when needed; bearer header only when authenticated/token exists; credentials included; structured/fallback errors; 204 handling; exactly one 401 retry; concurrent requests share one refresh; failed refresh clears memory token; token never enters browser storage. | Stub `fetch`, use real `Request`/`Response`/`Headers`, reset module state between tests, and assert calls/results. Do not render React. | Full form/route flows already covered by `App.test.tsx`. |
| P0 | `apps/operations-web/src/auth/AuthContext.tsx` — `AuthProvider`, `useAuth` | Startup refresh success/failure; login loads user after token; logout clears local state even if API fails; refreshUser transitions; unmount ignores late results; hook outside provider fails clearly. | Render a tiny consumer/harness with mocked API module functions. Test observable context state, not internal hooks. | Admin pages and full navigation journeys. |
| P0 | `apps/operations-web/src/components/RouteGuards.tsx` — `ProtectedRoute`, `AdminRoute`, `ClientRoute` | Loading state; unauthenticated redirect retains origin; admin/client allow and deny destinations. | MemoryRouter plus a controlled auth context/harness. | Backend authorization—frontend guards are usability only, never security proof. |
| P1 | `apps/operations-web/src/pages/UsersPage.tsx` — `userQueryString`, form payload behavior | Omit empty filters; encode Unicode/special characters; include page/limit/type/age correctly; reset page when applying filters; create versus update payload and optional password handling. | Prefer exporting a small pure serializer only if separately approved; otherwise verify observable fetch URLs/payloads through focused component tests. | The existing broad create-user flow and backend query correctness. |
| P1 | `apps/operations-web/src/components/Ui.tsx` — `ErrorState`, `Pagination` | `ApiError` versus unknown-error presentation; previous/next disabled boundaries and page callbacks. | Small RTL component tests. | Static headings, decorative markup, and CSS. |
| P2 | `apps/operations-web/src/demo/demoPath.ts` — `isDemoPath`; `demo/DemoGallery.tsx` | Exact `/demo` path matching and the isolation boundary. | Pure path table and only uncovered isolation cases. | The 12 existing gallery journey, accessibility, RTL, least-privilege, reset, and zero-network/storage tests. Demo-only behavior is not production evidence. |

## 4. Lower-value or inappropriate unit targets

Do not add tests merely to execute lines in:

- thin route functions that only pass validated data to a service;
- `main.py` router registration or static OpenAPI metadata already covered by API tests;
- ORM declarations without behavior—assert database constraints through migrations/integration tests instead;
- Alembic revision text—run migrations from zero and schema/RLS checks;
- `styles.css`, manifests, static HTML, translation dictionaries, and decorative components;
- placeholder `apps/storefront-web`, `packages/*`, `infra`, or `scripts` README files;
- generated build output or lockfiles;
- synthetic demo copy already protected by the isolated gallery tests.

Avoid tests that assert private implementation trivia such as exact SQLAlchemy call order, React hook call count, CSS class names, or a hash string that is intentionally salted.

## 5. Recommended Testing Stack

No new dependency is required for the planned work.

### Backend

- **pytest** for unit discovery, fixtures, parameterization, and exception assertions.
- **pytest-cov** for visibility into newly tested branches; coverage is evidence, not the objective.
- **`unittest.mock` / pytest `monkeypatch`** for time, randomness, repository, and CLI boundaries.
- **Real Pydantic, PyJWT, pwdlib/Argon2id, phonenumbers, Decimal, and Starlette Response objects** rather than reimplementing their behavior in fakes.
- **Ruff and strict mypy** for every future test milestone.

Proposed layout:

```text
apps/api/tests/
├── unit/
│   ├── test_phone_unit.py
│   ├── test_security_unit.py
│   ├── test_schema_validation_unit.py
│   ├── test_dependency_roles_unit.py
│   ├── test_auth_service_unit.py
│   ├── test_user_rules_unit.py
│   ├── test_platform_rules_unit.py
│   ├── test_cash_van_rules_unit.py
│   ├── test_auth_cookies_unit.py
│   └── test_cli_unit.py
└── existing PostgreSQL/API files remain unchanged
```

Before the first unit test is added, Milestone 0 must make `apps/api/tests/conftest.py` bypass its destructive `clean_database` fixture for tests explicitly marked `unit`, and `apps/api/pyproject.toml` must register that marker. Existing database tests must continue to use the disposable PostgreSQL fixture. This is a future reviewed harness change, not part of this documentation task.

Proposed commands after that harness exists:

```powershell
.\.venv\Scripts\python.exe -m pytest apps/api/tests/unit -m unit -q
.\.venv\Scripts\python.exe -m pytest apps/api/tests/unit -m unit -q --cov=apps/api/tawzeevo_api --cov-report=term-missing
.\.venv\Scripts\python.exe -m ruff check apps/api/tawzeevo_api apps/api/tests/unit
.\.venv\Scripts\python.exe -m mypy apps/api/tawzeevo_api
```

The existing integration lane continues to require an explicitly disposable `TEST_DATABASE_URL`:

```powershell
.\.venv\Scripts\python.exe -m pytest apps/api/tests -q
```

Never point that command at shared, staging, or production PostgreSQL because `clean_database` truncates application tables.

### Frontend

- **Vitest** for module and component tests.
- **React Testing Library + jest-dom** for observable user behavior.
- **jsdom** for browser APIs.
- **Vitest mocks** for `fetch` and module boundaries; reset globals/module state after each test.
- **ESLint, strict TypeScript, and Vite build** as milestone gates.

Proposed layout:

```text
apps/operations-web/src/test/unit/
├── api-client.unit.test.ts
├── auth-context.unit.test.tsx
├── route-guards.unit.test.tsx
├── users-query.unit.test.tsx
├── ui-errors-pagination.unit.test.tsx
└── demo-path.unit.test.ts
```

Proposed commands:

```powershell
npm exec --workspace @tawzeevo/operations-web -- vitest run src/test/unit
npm run lint:operations
npm run typecheck:operations
npm run build:operations
```

### Naming, fixtures, and determinism

- Name tests by observable outcome: `test_<condition>_<expected_result>` in Python and plain behavior sentences in Vitest.
- One test should have one primary failure reason; parameterization is preferred for equivalent boundary cases.
- Use fixed UUIDs, UTC timestamps, dates, Decimal values, and dummy secrets created inside tests.
- Do not use wall-clock sleeps, network calls, random ordering, production data, or developer environment values.
- Reset `get_settings` caches, module token state, mocks, globals, and document direction where applicable.
- Prefer simple builders/factories over large shared fixtures. A fixture must not silently grant admin/tenant authority.
- Mock at an architectural boundary, not inside the logic being tested.

### Coverage policy

- Record unit-only coverage per milestone and compare it to the previous milestone.
- Require every listed security, authorization, lifecycle, money, normalization, and error branch to have an explicit test, regardless of percentage.
- Do not lower the frozen integration coverage or replace integration assertions with mocks.
- Do not introduce a global `fail-under` threshold until the dedicated unit lane has a stable baseline; any threshold change requires review.

## 6. Sequential Milestone Plan

Only one testing milestone should be implemented and reviewed at a time. Every test function/case created must immediately receive one row in `RUN_TESTS.md`.

### UT-M0 — Harness separation and baseline

**Objective:** establish a database-independent unit lane without weakening the PostgreSQL suite.

**Proposed edits later:** `apps/api/tests/conftest.py`, `apps/api/pyproject.toml`, unit directories, and the smallest frontend test setup adjustment only if required.

**Actions:**

1. Register `unit` and `integration` markers.
2. Ensure unit tests never request or trigger the truncating database fixture.
3. Preserve current behavior for every existing backend test.
4. Establish exact unit, integration, lint, type, and frontend commands.
5. Record baseline counts/coverage honestly, including skips.

**Acceptance:** a zero/placeholder unit collection can execute without `TEST_DATABASE_URL`; existing database tests still skip safely without it and pass with a disposable database; no test is silently reclassified.

### UT-M1 — Pure normalization, schemas, dates, and money

**Proposed files:** `test_phone_unit.py`, `test_schema_validation_unit.py`, `test_platform_rules_unit.py`, `test_cash_van_rules_unit.py`.

**Targets:** phone E.164 normalization; auth/user/platform/Cash Van Pydantic validators; `_access_state`; `_ensure_not_shortened`; `_money`; `product_response` piece/box derivation.

**Acceptance:** all boundary values and exact error categories are covered; tests require no database/network; Decimal/date behavior uses fixed inputs; no product rule is invented.

### UT-M2 — Security, authentication decisions, and cookies

**Proposed files:** `test_security_unit.py`, `test_dependency_roles_unit.py`, `test_auth_service_unit.py`, `test_auth_cookies_unit.py`.

**Targets:** password/refresh hashes; JWT claims and validation; claim parsing; system/client/owner gates; login invalid states; refresh state-machine branches; cookie attributes and clearing.

**Acceptance:** 401-versus-403 and error codes are explicit; token tests fix time/settings; no token or secret is logged; locking/replay atomicity remains covered by PostgreSQL integration tests.

### UT-M3 — User and tenant lifecycle decisions

**Proposed files:** `test_user_rules_unit.py`, expanded `test_platform_rules_unit.py`.

**Targets:** email conflict ownership, profile security changes/session revocation decisions, filter normalization/page math, last-owner decision branches, lifecycle transition guards, access-period preservation, and response mapping.

**Acceptance:** unit tests prove decisions and collaborator calls; existing concurrent deletion, audit, transaction, and retained-data tests continue to pass against PostgreSQL.

### UT-M4 — Cash Van catalog and draft-invoice rules

**Proposed file:** expanded `test_cash_van_rules_unit.py`.

**Targets:** barcode/currency/packaging boundaries, missing product, mixed currencies, quantity and line rounding, subtotal rounding, and response snapshots.

**Acceptance:** all money uses Decimal/`ROUND_HALF_UP`; no stock or availability concept appears; persisted totals, RLS, and tenant lookup remain integration evidence. If arithmetic cannot be isolated without mocking transaction internals, first propose a behavior-preserving private calculation helper for review rather than forcing a brittle test.

### UT-M5 — Frontend API, authentication, and guards

**Proposed files:** `api-client.unit.test.ts`, `auth-context.unit.test.tsx`, `route-guards.unit.test.tsx`.

**Targets:** request headers/credentials/errors/204; single retry and shared refresh promise; memory-only token clearing; provider startup/login/logout states; protected/admin/client redirects.

**Acceptance:** no real network/storage writes; concurrent refresh is deterministic; logout clears local state on server failure; backend authorization remains the authority; existing production-flow tests still pass.

### UT-M6 — Frontend query/payload, errors, CLI, and residual gaps

**Proposed files:** `users-query.unit.test.tsx`, `ui-errors-pagination.unit.test.tsx`, `demo-path.unit.test.ts`, `test_cli_unit.py`.

**Targets:** encoded user filters and pagination reset; create/update payload differences; API error display; pagination boundaries; CLI confirmation/validation/exit behavior; only genuinely uncovered demo path boundaries.

**Acceptance:** tests assert user-visible or request-boundary behavior, not CSS/markup trivia; demo tests remain clearly labeled synthetic and do not count as production role evidence.

### UT-M7 — Final gap review and stable execution contract

**Objective:** remove duplication, verify traceability, and freeze reliable commands.

**Actions:**

1. Run unit-only backend and frontend commands.
2. Run Ruff, mypy, ESLint, TypeScript, and production build.
3. Run the full existing suite with disposable PostgreSQL.
4. Review uncovered branches by risk rather than chasing a percentage.
5. Remove brittle or duplicate tests.
6. Complete every `RUN_TESTS.md` row and add a validation-run entry.

**Acceptance:** every P0/P1 behavior has either unit evidence or an explicit integration-only justification; all required checks pass; no shared/production database was touched; no Phase 2 behavior was introduced.

## 7. Traceability and review rules

For every future test:

1. Identify the source contract or existing behavior being protected.
2. Name the exact source file/symbol and risk.
3. Choose unit or integration based on the real boundary—not convenience.
4. Add the test and immediately append its exact node command to `RUN_TESTS.md`.
5. Run that node, then its complete test file, then the milestone aggregate checks.
6. Record the last result honestly; skipped is not passed.
7. Review for secrets, production data, cross-tenant authority, and unrelated edits.

### Definition of done for one unit test

A unit test is complete only when:

- it protects an approved, currently implemented behavior;
- its name explains condition and outcome;
- its setup is deterministic and minimal;
- it fails for the intended regression and passes for the correct behavior;
- it does not use a real network or shared database;
- it does not mock away the behavior it claims to prove;
- it passes lint/type checks applicable to the test;
- its individual and file commands work from the repository root;
- its `RUN_TESTS.md` entry contains the exact node/function name, command, behavior, and latest status.

## 8. Key risks to guard throughout implementation

- The existing autouse database cleanup makes naïvely placed backend “unit” tests skip without `TEST_DATABASE_URL`; UT-M0 must solve this first.
- Mock-based tests must never be presented as evidence for RLS, locks, transaction atomicity, migration correctness, or concurrent refund/owner safety.
- Private helpers may be tested when they encode important behavior, but production code must not be refactored only to satisfy a coverage number.
- Frontend route guards are not security controls; every protected capability still requires backend dependency checks.
- Demo gallery tests remain reversible, synthetic, memory-only evidence and must stay separate from production roles.
- Unit fixtures must not contain credentials, hosted URLs, or copied production/customer records.
- Phase 2 remains locked; later financial, storefront, offline, delivery, and procurement tests belong to their approved implementation phases.
