# PHASE_09.md — Production Hardening, Deployment, Multi-Tenant Pilot, Launch Readiness

## Authority and reconciliation status

This is the authoritative Phase 9 specification, reconciled on 2026-09-07 from the historical
planning copy in `docs/recovered-planning/PHASE_09.md`. D-027/D-028 already establish Supabase
PostgreSQL and Render for the current deployment; Phase 9 verifies/hardens that architecture and
may not silently replace it.

Whether password recovery is mandatory, exact SLO numbers, production worker/object-storage/
staging choices and retention periods remain `REVIEW_REQUIRED` before their affected milestone.

## Phase objective
Harden the deterministic Tawzeevo system built in Phases 1–8 for real multi-tenant production operation.

Phase 9 proves security, recovery, performance, observability, deployment, data lifecycle, and real operating workflows. It does not redesign product behavior.

## Start condition
- Phases 1–8 COMPLETE with validation evidence.
- Architecture gates A–G passed where applicable.
- No critical domain ambiguity hidden inside hardening.

---

# A. Public GitHub repository constraint

The existing Tawzeevo GitHub repository remains public.

Never commit:
- `.env` secrets;
- credentials/tokens;
- production DB dumps;
- real customer/supplier private data;
- Google OAuth secrets;
- KEKs/DEKs;
- deployment secrets;
- private backup payloads.

Use environment/secret manager/GitHub secret facilities.

Do not change repo visibility, delete/recreate it, force-push, transfer ownership, or add a software license without explicit approval.

Committed demo/seed data must remain fictional.

---

# B. Security hardening

Required:
- exhaustive authorization matrix:
  `system role × tenant role × resource × action × ownership/assignment`;
- RLS suite;
- session rotation/revocation;
- refresh reuse detection;
- rate limiting;
- login brute-force controls;
- guest checkout abuse controls;
- public token abuse/enumeration tests;
- CSP;
- enforce locked CORS/CSRF/Origin contract;
- upload security;
- secret management;
- dependency/security scanning;
- penetration-style object authorization tests;
- tenant suspension/closure access checks;
- last-owner invariant;
- driver least-privilege API/cache checks.

Platform admin remains lifecycle manager, not silent tenant-private data viewer.

---

# C. Password recovery

Implement:
- forgot password;
- one-time reset token;
- token hash storage;
- short expiry;
- single-use;
- rate limit;
- enumeration-safe response where practical;
- security-version/session invalidation after reset;
- audit/security event.

Whether this complete recovery workflow is mandatory for the Phase 9 launch gate is
`REVIEW_REQUIRED` before P9-M1. If approved, every security property above is mandatory.

---

# D. Database hardening

Review:
- constraints/FKs;
- unique invariants;
- indexes;
- query plans;
- connection pooling;
- transaction contention;
- invoice sequence/refund/payment concurrency;
- RLS;
- migration history.

Rehearse/test:
- migration from zero;
- production-like upgrade;
- invoice sequence race;
- refund concurrency;
- checkout/payment idempotency;
- backup/PITR according to hosting;
- restore drill.

Favor expand/migrate/contract and forward fixes over blindly destructive down migrations.

---

# E. Data lifecycle

Run controlled lifecycle drill:
- tenant export;
- temporary suspension/reactivation preserving all data;
- deliberate CLOSED/deactivation path;
- membership revocation;
- local cache purge;
- public token revocation;
- sync device revocation;
- backup retention/deletion handling;
- financial/audit retention.

Temporary non-payment uses `SUSPENDED`, not deletion.

---

# F. Performance SLOs

Candidate initial staging targets — exact SLOs are `REVIEW_REQUIRED` before P9-M3:
- phone lookup p95 < 250 ms;
- barcode lookup p95 < 250 ms;
- core authenticated CRUD p95 < 400 ms;
- storefront checkout server transaction p95 < 750 ms;
- sync push 100 lightweight operations p95 < 2.5 s;
- critical API 5xx < 1% in normal load test.

If hardware requires adjustment:
- measure;
- document;
- change through ADR/evidence;
- do not silently weaken.

---

# G. Observability

Implement:
- structured logs;
- request/correlation IDs;
- error tracking;
- metrics;
- app health;
- DB health;
- job health;
- sync failure metrics;
- backup failure metrics;
- auth anomaly metrics;
- alert levels.

Critical alerts:
- DB unavailable;
- repeated backup failure;
- auth failure spike;
- sync worker dead;
- dead-letter growth;
- object storage failure;
- elevated 5xx.

Never log secrets, raw capability tokens, or unnecessary sensitive payloads.

---

# H. CI/CD

Pipeline:
1. format/lint;
2. `tsc --noEmit`;
3. adopted Python static type check;
4. backend unit;
5. PostgreSQL integration;
6. financial property/invariant;
7. sync idempotency/property;
8. frontend unit/component;
9. E2E critical flows;
10. migration-from-zero;
11. reproducible locked-dependency build;
12. dependency/security checks;
13. staging deploy;
14. staging smoke/E2E subset;
15. controlled production release.

No production secret in public repo/artifacts.

---

# I. Deployment architecture

Before P9-M4, verify D-027/D-028 Supabase PostgreSQL and Render deployment against production
requirements. Any replacement or added paid provider requires explicit approval.

Do not silently choose paid providers if not approved.

Target shape, with worker/object-storage/staging choices `REVIEW_REQUIRED` before P9-M4:
- containerized FastAPI API;
- separate background worker process from same versioned image/code;
- managed PostgreSQL;
- S3-compatible/object storage;
- HTTPS ingress/reverse proxy;
- operations web separate deployable;
- storefront web separate deployable;
- pinned lockfiles;
- immutable release/container version.

Environments:
- local;
- automated test;
- staging;
- production.

Never test against production DB.

---

# J. Multi-tenant pilot

Even with one real pilot, maintain at least two synthetic tenants for isolation testing.

Pilot workflows:
- barcode;
- customer phone search;
- invoice;
- post-confirm edit;
- payment;
- debt/overdue;
- offline/reconnect;
- storefront guest order;
- owner review;
- delivery date/reminder;
- cancellation;
- procurement;
- supplier purchase/payment;
- route/delivery;
- analytics;
- backup/restore.

## One-person Cash Van
- one owner;
- zero drivers;
- owner gets order;
- confirms;
- self-operates delivery/route;
- no fake driver account.

## Larger business
- owner + separate driver;
- owner assigns/reassigns;
- driver least-privileged;
- driver no supplier price/profit/analytics.

No customer tracking.

---

# K. Product invariant regression

Prove system still has no:
- stock/inventory;
- product availability state;
- customer login requirement;
- direct customer cancellation;
- customer-selected delivery date;
- customer delivery tracking;
- driver-specific storefront catalog;
- automatic platform-admin tenant-private access;
- automatic customer merge;
- supplier per-purchase payment allocation;
- implicit FX;
- mutable financial history.

---

# L. Required Phase 9 tests/reviews

## Identity/security
- registration/login regression;
- password recovery tests if that scope is approved at P9-M1;
- session rotation/revocation/reuse;
- soft-delete;
- last-owner;
- tenant suspension/reactivation;
- RLS/cross-tenant;
- platform admin boundary.

## Public
- checkout abuse/idempotency;
- capability enumeration/rate limit/cache/log;
- phone privacy;
- suspended storefront.

## Financial
- pricing;
- revisions;
- ledger;
- allocations;
- payment/reversal;
- refund ceiling/concurrency;
- cancellation;
- D-043 strictly positive net sales for every confirmed revision;
- D-038 one signed nonzero historical opening per party/currency plus correction/reversal;
- D-039 ordinary supplier-payment ceiling and distinct supplier prepayment;
- mixed currency;
- invoice sequencing.

## Offline
- bootstrap;
- replay;
- tombstones;
- conflicts;
- crash resume;
- revocation purge;
- protocol mismatch;
- media retry.

## Driver
- sole owner self-operation;
- separate driver assignment;
- unrelated data denied;
- owner secrets absent payload/cache;
- no tracking.

## Jobs/backup
- dedup;
- retry/lease reclaim;
- dead letter;
- backup alert;
- encrypted restore.

## Performance/data lifecycle/accessibility
- SLO report;
- query plans;
- export/suspend/reactivate/close;
- cache/token/device revocation;
- backup retention;
- keyboard/focus/semantics;
- automated accessibility;
- screen-reader critical smoke;
- Arabic/RTL/mixed script/phone/currency/date.

---

# M. Milestones

## P9-M1 — Security matrix and recovery decision
Resolve the password-recovery launch requirement, then implement the approved scope alongside
authorization/RLS, sessions, rate limits, brute-force/public abuse, CSP/CORS/CSRF/Origin and
upload/dependency security.

Acceptance:
- security regression passes;
- if password recovery is approved, reset invalidates sessions;
- no object authorization leak;
- public repo secret-safe.

STOP.

## P9-M2 — Database, concurrency, backup/restore, data lifecycle
Implement/harden constraints/indexes/query plans/pooling, concurrency, migration rehearsal, hosting backup/PITR, restore, tenant lifecycle/export/retention.

Acceptance:
- zero/upgrade migrations;
- concurrency invariants;
- suspension/reactivation preserves same data;
- restore verified.

STOP.

## P9-M3 — Performance + observability
Implement load harness, SLO measurement, logs/request IDs, metrics/health, alerts, sync/job/backup/auth monitoring.

Acceptance:
- staging-like SLO evidence;
- critical alerts testable;
- sensitive values redacted.

STOP.

## P9-M4 — CI/CD + staging deployment rehearsal
PRECONDITION: D-027/D-028 deployment verified and any added worker/object-storage/staging choices recorded.

Implement full pipeline, builds, staging deployment, worker/API/web separation, secrets, staging smoke/E2E, release/rollback-forward-fix runbook.

Acceptance:
- clean checkout builds/tests/deploys staging;
- no production DB tests;
- no secret in public repo;
- release traceable to Git commit.

STOP.

## P9-M5 — Multi-tenant pilot
Execute synthetic two-tenant security plus real pilot where available, including one-owner/zero-driver and owner+driver workflows, offline, procurement, analytics, backup.

Acceptance:
- both operating models succeed;
- no tenant/driver leak;
- no critical/high pilot defect.

STOP.

## P9-M6 — Production launch gate audit + freeze
No new product scope.

Produce launch/security/migration/restore/performance/observability/CI/pilot/data-lifecycle/risk evidence and run final full regression.

Acceptance:
- all production launch gates pass;
- no unresolved critical/high blocker.

Mark Phase 9 COMPLETE and STOP. Do not start Phase 10 automatically.

---

# N. Definition of Done

- all Phase 1 coursework still passes;
- Phases 1–8 regressions pass;
- auth/session hardened; password recovery hardened if approved at P9-M1;
- tenant lifecycle secure;
- RLS/two-tenant suite;
- owner/driver matrix;
- public abuse tests;
- financial/refund concurrency;
- offline/revocation;
- backup/restore;
- reliable jobs;
- EN/AR/accessibility;
- performance SLOs or approved evidence-based adjustment;
- observability/alerts;
- CI/CD E2E;
- staging/release runbook;
- one-person + separate-driver pilot;
- data lifecycle drill;
- no stock/availability/tracking regression;
- no critical/high launch blocker.

## Explicit exclusions
Do not add Phase 10 forecasting without its gate, automatic subscription payment provider, tax/VAT/full accounting/warehouse ERP, new roles, or new business behavior disguised as hardening.

First milestone to implement: **P9-M1 — Security matrix and recovery decision**
