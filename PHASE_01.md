# PHASE_01.md — Full Program Delivery + Production Foundation

## Phase objective

Complete **all** supplied FastAPI authentication/user-management requirements in one week, including the source-labeled frontend bonus which is mandatory for this project, while creating production-compatible tenant/auth foundations and a small real Cash Van vertical slice.

Nothing required below may be deferred to a later phase.

Future systems may be **contracted** now without being fully implemented now.

---

# A. Exact Phase 1 functional contract

## User model

Every user has:
- `id`
- `first_name`
- `last_name`
- `email`
- `phone`
- `city`
- `age`
- `type`
- `password_hash`
- soft-delete state (`is_deleted` and/or `deleted_at`)
- `created_at`
- `updated_at`

System type in Phase 1:
- `admin`
- `client`

Public registration never accepts authorization type and always creates `client`.

Never return password/hash.

## Validation

`first_name`
- required;
- trim;
- must contain non-whitespace.

`last_name`
- same.

`city`
- required;
- trim;
- non-empty.

`email`
- required;
- trim;
- Unicode NFC;
- lowercase canonical storage/login form;
- valid email;
- unique DB index on normalized value;
- do not remove dots or `+tags`.

`phone`
- required;
- normalize/validate using the shared phone utility;
- preserve raw form where schema allows;
- valid reasonable international format.

`age`
- required integer;
- `1..120` inclusive.

`password`
- required;
- 10–128 Unicode characters;
- not empty/all-whitespace;
- no arbitrary upper/lower/symbol composition requirement;
- never truncate;
- Argon2id hash before storage.

## Required root routes

These exact routes must remain available for evaluation:

```text
POST   /register
POST   /login
POST   /users
GET    /users
GET    /users/me
PUT    /users/me
PUT    /users/{id}
DELETE /users/{id}
GET    /stats/count
GET    /stats/average-age
GET    /stats/top-cities
```

Production-only auth/tenant routes may live under `/api/v1`.

## POST /register — public

Input:
- first_name
- last_name
- email
- phone
- city
- age
- password

Must:
- reject/ignore privileged type input according to schema validation;
- never allow public admin creation;
- validate;
- detect duplicate email;
- hash password;
- create `client`.

## POST /login — public

Input:
- email
- password

Must:
1. find normalized email;
2. verify hash;
3. reject soft-deleted user;
4. generate access JWT;
5. return access token;
6. use 401 for incorrect credentials/invalid auth state.

## Reusable authentication/authorization

Implement reusable logic for:
- current user;
- active user;
- system-role checks;
- tenant membership resolver foundation.

## POST /users — admin only

Admin can create:
- client;
- admin.

Client gets `403`.

Use same validation/hash/duplicate-email rules.

## GET /users/me — authenticated

Return own safe user profile.

## PUT /users/me — authenticated

User may update:
- first_name
- last_name
- email
- phone
- city
- age
- password.

Must:
- validate;
- duplicate-email check;
- re-hash changed password;
- never permit self-role change.

## GET /users — admin only

Must support:
- pagination;
- filtering;
- searching.

Mandatory filters:
- age;
- city;
- type;
- first_name;
- last_name;
- email.

Multiple filters work together.

Pagination:
- `page` default 1, minimum 1;
- `limit` default 10, minimum 1, maximum 100;
- filter first;
- calculate matching total;
- paginate;
- return `page`, `limit`, `total`, `total_pages`, `users`.

Search:
- case-insensitive normalized first name/last name/email;
- bounded/stable ordering.

## PUT /users/{id} — admin only

Admin may:
- update any user;
- change admin/client system role;
- update password safely.

Must:
- 404 if user does not exist;
- validate;
- prevent duplicate email;
- re-hash password.

## DELETE /users/{id} — admin only soft delete

Must:
- never physically delete;
- mark deleted;
- timestamp;
- remove from normal `/users`;
- block login;
- exclude from required statistics;
- leave DB record.

Production foundation invariant:
- if target is the last active usable owner of any active tenant, return `409 OWNER_TRANSFER_REQUIRED`;
- make no deletion/membership change in that failed transaction;
- if another usable owner exists, deletion may proceed and target active memberships are revoked atomically.

## Public statistics

`GET /stats/count`
- active users only;
- empty → `0`.

`GET /stats/average-age`
- active users only;
- empty → `null`.

`GET /stats/top-cities`
- active users only;
- at most top 3;
- count descending;
- normalized city ascending tie-break;
- empty → `[]`.

## HTTP behavior

Use:
- 400 business-invalid/malformed where appropriate;
- 401 unauthenticated/invalid/expired JWT/incorrect credentials/soft-deleted auth;
- 403 authenticated but unauthorized;
- 404 not found;
- 409 duplicate email/state conflict;
- FastAPI/Pydantic 422 validation semantics.

Application errors follow the project error envelope where it does not break evaluator compatibility.

## Code organization

Do not place everything in `main.py`.

Separate:
- routes;
- schemas;
- models;
- configuration;
- database;
- security/JWT;
- dependencies;
- repositories;
- services/business logic;
- tests.

## Swagger

FastAPI Swagger/OpenAPI must be functional and usable to test the API.

---

# B. Mandatory Phase 1 frontend

Build a real React/Vite frontend consuming the FastAPI API.

Required:
- registration;
- login;
- JWT authentication;
- protected routes;
- client profile;
- edit profile;
- admin dashboard;
- user management;
- admin create client/admin;
- admin update;
- soft delete;
- pagination;
- filters/search;
- statistics dashboard;
- platform tenant-application review;
- platform tenant access/lifecycle management (set/extend access period, suspend, reactivate).

Foundation:
- English/Arabic;
- LTR/RTL;
- accessible navigation/forms;
- tenant context shell.

Use a functional neutral visual system until user design references are supplied.

---

# C. Phase 1 production foundation

## Authentication/session foundation

In addition to the evaluator routes, implement production-compatible session support under `/api/v1`:
- session record;
- short-lived access JWT;
- opaque refresh token hash;
- secure HttpOnly refresh cookie;
- refresh rotation;
- reuse/session revocation;
- logout;
- protected-request session/security-version validation;
- explicit allowed-origin/credentialed CORS policy for the local frontend.

Do not store refresh token in JavaScript storage.

## Initial DB/migrations

At minimum:
- users;
- auth_sessions;
- tenants;
- tenant_memberships;
- tenant_invitations;
- tenant_applications;
- audit_events.

Tenant foundation must include:
- `status` = `ACTIVE | SUSPENDED | CLOSED`;
- `access_until` nullable;
- `grace_until` nullable;
- `suspension_reason` nullable;
- lifecycle timestamps needed to audit activation/suspension/reactivation.

Use Alembic from the start.

RLS architecture is documented and enabled for tenant-owned Phase 1 business tables.

## Tenant application and onboarding

Production path after user becomes authenticated `client`:

```text
registered/authenticated client
→ submit tenant application
→ platform admin reviews
→ approve
→ create tenant
→ create applicant owner membership
→ activate tenant
→ set/resolve active tenant
```

A client does not self-activate a production tenant.

Tenant-application states in Phase 1:
- `PENDING`
- `APPROVED`
- `REJECTED`

Application approval is one transaction:
- validate application is `PENDING`;
- create tenant;
- create applicant `owner` membership;
- mark application `APPROVED`;
- set tenant `ACTIVE`;
- apply optional `access_until` / `grace_until`;
- append audit event.

Rejection:
- leaves applicant user intact;
- creates no tenant/membership;
- retains review history.

System `admin` and tenant `owner` remain separate.

### Owner-as-operator architecture lock

This is a Phase 1 architecture contract, not a requirement to implement the Phase 7 driver workflow now.

- a tenant owner may personally operate the Cash Van;
- an owner does not need a separate driver account or duplicate membership;
- `owner` includes the operational permissions that a driver would need for delivery/route work, while retaining full owner permissions;
- a separate `driver` role remains least-privileged for employees/other workers;
- later delivery tasks may be assigned to an active owner or driver membership;
- a single-owner tenant with no drivers must be able to operate without driver setup.

## Safe platform-admin bootstrap

Provide a safe local/dev/admin bootstrap mechanism (CLI/script or equivalent) that:
- never exposes public admin registration;
- never embeds a default production password;
- is documented.


## Platform-admin tenant applications and manual access control

Phase 1 implements the manual commercial-access control needed to operate the SaaS without requiring an automatic billing provider.

Production-only routes under `/api/v1`:

```text
POST /api/v1/tenant-applications
GET  /api/v1/platform/tenant-applications
POST /api/v1/platform/tenant-applications/{application_id}/approve
POST /api/v1/platform/tenant-applications/{application_id}/reject
GET  /api/v1/platform/tenants
PUT  /api/v1/platform/tenants/{tenant_id}/access-period
POST /api/v1/platform/tenants/{tenant_id}/suspend
POST /api/v1/platform/tenants/{tenant_id}/reactivate
```

Authorization:
- `POST /api/v1/tenant-applications` requires an authenticated non-deleted `client`;
- all `/api/v1/platform/...` routes require system `admin`;
- system admin manages lifecycle/access metadata but does not automatically become a tenant member or gain tenant-private commercial-data access.

Application submission minimum:
- applicant user identity comes from authentication;
- business name;
- server timestamp;
- initial status `PENDING`.

Platform-admin application list:
- pagination;
- status filter;
- stable ordering.

Approve:
- only `PENDING`;
- creates tenant and owner membership transactionally;
- tenant begins `ACTIVE`;
- optional `access_until` / `grace_until`;
- application becomes `APPROVED`;
- audit event required.

Reject:
- only `PENDING`;
- application becomes `REJECTED`;
- applicant user is retained;
- no tenant/membership is created;
- review/audit history retained.

Tenant list:
- search/filter by tenant name/status;
- identify access as current/grace/overdue from dates;
- never infer that overdue means deleted.

Access period:
- platform admin may set or extend `access_until`;
- optional `grace_until` must not precede `access_until` when both exist;
- date changes are audited;
- Phase 1 does not automatically charge a card or payment provider.

Suspend:
- default temporary non-payment reason is `SUBSCRIPTION_OVERDUE` when that is the cause;
- set tenant `SUSPENDED`;
- preserve tenant row and all tenant-owned data;
- business access is blocked;
- sessions may remain valid at platform-account level but suspended tenant context is unusable;
- sync/offline revocation follows the locked tenant lifecycle contract.

Reactivate:
- use the same tenant;
- do not recreate customers/products/invoices or owner account;
- set tenant `ACTIVE`;
- optionally update access/grace dates;
- retain all existing business data;
- audit the transition.

`CLOSED` is not used as the normal temporary non-payment state.

## Small Cash Van vertical slice

Implement real DB-backed foundation:
- approved tenant onboarding/owner membership;
- customer create/view;
- customer phone search;
- category create/view;
- tenant product with barcode;
- basic draft invoice using customer/product.

This is deliberately not the final financial invoice engine.

Do not add stock/availability.

## Architecture contract docs

Before Phase 1 ends, create concise repository docs under `docs/` for:
- locked decisions;
- order state;
- pricing rules;
- auth/session;
- tenant isolation and platform-admin tenant lifecycle/access control;
- financial invariants;
- sync protocol;
- public access;
- owner/driver delivery assignment and owner-as-operator rules;
- jobs/reminders;
- media security;
- payment allocation;
- offline authoritative IDs;
- audit events;
- API conventions.

These documents summarize already-approved contracts. They do not authorize implementing later phases early.

---

# D. Mandatory Phase 1 test matrix

Automate all:

## Registration
- success;
- invalid email;
- invalid phone;
- invalid age;
- empty first name;
- empty last name;
- duplicate email;
- attempt `type=admin`;
- verify registration always client.

## Login
- success;
- wrong password;
- nonexistent email;
- soft-deleted user.

## Authentication
- no JWT;
- invalid JWT;
- expired JWT.

## Authorization
- admin admin-route access;
- client denied;
- client cannot modify another user;
- client cannot change own role.

## Profile
- get own info;
- update own info;
- update password;
- attempt own role change.

## Admin
- create client;
- create admin;
- list users;
- pagination;
- filtering;
- pagination + filtering;
- update user;
- change role;
- soft delete.

## Soft delete
- missing from normal list;
- cannot login;
- excluded stats;
- record still exists.

## Tenant-owner safety
- cannot soft-delete only usable owner;
- failed delete leaves user/membership unchanged;
- delete succeeds when another usable owner exists;
- successful delete revokes memberships atomically.

## Platform tenant applications/access
- authenticated client can submit application;
- application starts `PENDING`;
- client cannot approve/reject;
- admin can list/filter applications;
- admin approval creates exactly one tenant and owner membership;
- duplicate approval/replay cannot create another tenant;
- rejection retains user and creates no tenant;
- admin can set/extend access period;
- admin can suspend tenant without deleting tenant-owned data;
- suspended tenant cannot use business context;
- admin can reactivate same tenant;
- reactivation preserves existing tenant-owned data;
- non-admin cannot suspend/reactivate tenant;
- platform admin does not automatically become tenant member/owner;
- access-period and lifecycle transitions are audited.

## Statistics
- active count;
- average age;
- top 3 cities;
- empty/tie behavior.

---

# E. Milestones

## P1-M1 — Repository, database, migrations, contracts

Implement:
- inspect current repo;
- create monorepo boundary;
- API project;
- operations-web project shell;
- PostgreSQL local/test setup;
- SQLAlchemy/Alembic;
- configuration and `.env.example`;
- initial user/tenant/session/application/access-control/audit models/migration;
- test harness;
- contract-doc skeletons;
- lint/type/test commands.

Acceptance:
- API boots;
- frontend boots;
- DB migration from zero succeeds;
- health/smoke connection works;
- no secrets committed.

STOP after report.

## P1-M2 — Registration, login, JWT, sessions

Implement:
- user normalization/validation;
- Argon2id hashing;
- `/register`;
- `/login`;
- JWT current-user dependencies;
- session/refresh/logout foundation;
- soft-deleted auth rejection;
- auth tests;
- Swagger auth usability.

Acceptance:
- all registration/login/authentication cases pass.

STOP.

## P1-M3 — User/admin/profile/stats

Implement:
- `/users/me`;
- profile update/password;
- admin create;
- admin list/filter/search/pagination;
- admin update/role change;
- soft delete;
- last-owner protection;
- public stats;
- safe admin bootstrap;
- tenant application submit/review/approve/reject APIs;
- platform tenant list/access-period/suspend/reactivate APIs;
- application/lifecycle/audit tests;
- complete backend evaluator tests.

Acceptance:
- mandatory backend matrix passes;
- last-owner transaction tests pass;
- tenant approval creates tenant+owner atomically;
- suspension/reactivation preserves tenant data.

STOP.

## P1-M4 — Mandatory frontend

Implement:
- register/login;
- session/auth flow;
- protected routing;
- profile/edit;
- admin dashboard;
- users management;
- create/update/delete;
- filters/search/pagination;
- public stats dashboard;
- platform applications review UI;
- platform tenant access/status management UI;
- EN/AR and RTL;
- basic accessibility.

Acceptance:
- frontend uses real API, no mocks for required flow;
- TypeScript/lint/unit checks pass;
- critical manual flows work.

STOP.

## P1-M5 — Tenant foundation + real Cash Van slice

Implement:
- approved tenant onboarding;
- owner membership/active tenant;
- tenant RLS/scoping for new business rows;
- customer create/view/search phone;
- category create/view;
- tenant product/barcode;
- basic draft invoice.

Acceptance:
- an unapproved/rejected applicant has no usable tenant business context;
- a suspended tenant cannot use the Cash Van business slice;
- tenant A cannot access tenant B slice data;
- draft invoice uses real customer/product data;
- no stock/availability fields exist.

STOP.

## P1-M6 — Full hardening/test pass

Implement/fix:
- remaining tests;
- negative authorization;
- platform application/suspension/reactivation regression tests;
- migration from zero;
- RLS tests;
- API/OpenAPI cleanup;
- frontend loading/error states;
- RTL smoke;
- seed/demo data;
- contract docs finalized enough to guide later phases.

Acceptance:
- full Phase 1 automated suite passes;
- no known critical/high Phase 1 defect.

STOP.

## P1-M7 — Freeze and presentation readiness

Do not add new scope.

Produce/update:
- README;
- architecture overview;
- folder responsibilities;
- test report;
- demo seed/run instructions;
- presentation demo checklist;
- future-phase summary;
- final Phase 1 audit against this file.

Acceptance:
- every requirement in sections A–D has evidence;
- Phase 1 DoD below passes.

Mark Phase 1 COMPLETE and STOP. Do not start Phase 2.

---

# F. Phase 1 Definition of Done

All must be true:
- every exact program route exists;
- every mandatory program test passes;
- mandatory frontend is complete;
- PostgreSQL + Alembic used;
- passwords hashed;
- JWT auth works;
- production session foundation works;
- admin/client controls work;
- soft delete works;
- public required stats work;
- Swagger works;
- EN/AR foundation works;
- tenant foundation exists;
- tenant application approval/rejection works;
- platform admin can set/extend access, suspend, and reactivate without deleting tenant data;
- suspended tenant business access is blocked;
- last-owner protection works;
- real customer/category/barcode/draft-invoice slice works;
- migrations build DB from zero;
- architecture docs committed;
- no stock/availability;
- no throwaway Phase 1 architecture.
