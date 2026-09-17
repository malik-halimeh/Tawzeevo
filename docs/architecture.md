# Tawzeevo architecture and current implementation

Implementation audit baseline: `2248c137e43c6c043725830c1303756da1d210ee`.
Reconstructed 2026-09-06 from repository material only. This is Tier E, DERIVED / CANDIDATE
implementation description, not approval of new requirements. The [governance index](governance/SOURCE_OF_TRUTH.md)
identifies binding sources; [traceability](TRACEABILITY_MATRIX.md) qualifies evidence and gaps.
This existing document also serves as current-state documentation; no parallel architecture or
CURRENT_STATE file is necessary.

## Implemented boundaries

```text
React/Vite operations browser
  api/client.ts (fetch, memory token, one refresh retry)
    -> FastAPI root evaluator APIs and /api/v1 business APIs
       -> Pydantic schemas + auth/session/tenant-owner dependencies
          -> synchronous transactional services
             -> SQLAlchemy models / small shared repositories
                -> PostgreSQL constraints, triggers and RLS

Unauthenticated invoice-link browser (not a storefront)
  FastAPI-served public_invoice.html
    -> fragment secret removed from address bar
       -> X-Invoice-Capability -> restricted current-invoice projection

/demo -> synthetic frontend memory only; no production API/data/auth
Future Next.js storefront and shared packages -> README placeholders only
```

`apps/api/tawzeevo_api/main.py` assembles routes, credentialed explicit-origin CORSMiddleware,
PublicInvoicePrivacyMiddleware, application-error responses and health/OpenAPI endpoints.
Role checks are FastAPI dependencies, not CORS middleware. CORS does not grant tenant access.
Services own authoritative calculations and transactions; several query ORM models directly.
There is not a repository class for every domain table.

`apps/operations-web/src/ApplicationRoot.tsx` isolates the demo; App.tsx, pages, route guards,
AuthContext and TenantWorkspace compose real operations. InvoiceEditor owns the production
finance UI, InvoiceSharing the link controls. TanStack Query is used on several pages; invoice
components also use explicit local state and apiRequest. TypeScript response interfaces are
hand-maintained, not generated from OpenAPI. React Hook Form/Zod support forms; i18next supports
EN/AR; some invoice-link translations live inline in the component and public HTML.

## Request and data flows

| Flow | Actual baseline path and boundary |
|---|---|
| Register/login | Root auth route -> normalization/validation -> users/auth service -> Argon2id and AuthSession -> access JWT + opaque refresh cookie. Public registration forbids role input. |
| Protected request | get_db -> get_auth_context validates JWT claims/session/user/security versions -> current user -> system-admin OR tenant context/owner dependency. Current system role comes from User, not a stale role claim. |
| Refresh/logout | Server hashes refresh tokens, rotates sessions, detects reuse and revokes sessions; client keeps access token in memory and refreshes once on an authenticated 401. D-026 governs policy. |
| Tenant application | Client submits -> platform admin approves/rejects -> approval creates one tenant + applicant owner + audit transactionally; suspension/reactivation preserves rows, not billing or admin ownership. |
| Tenant business | Requested tenant path/query ID -> active membership + ACTIVE tenant + owner check -> explicit tenant predicates -> transaction-local RLS context -> mutation/commit. |
| Catalog scan | Tenant barcode first, master fallback -> tenant adoption or manual product -> tenant/grade price and authenticated image references. Publication is not stock. |
| Draft/edit | Customer/catalog/calculator/parser inputs -> server pricing/cost resolution -> immutable revision/items -> current header pointer. Legacy tenant-nested draft routes adapt to this schema, not a second invoice engine. |
| Confirm/edit | Invoice/current predecessor locks -> complete cost requirement -> server tenant/year number + one charge; later confirmed edit adds revision and ledger delta, reconciling excess allocations. |
| Receipt/cancel/refund | Immutable receipt + ledger effect + allocations; corrections append compensating rows. Cancellation preserves payments; refund separately locks/rechecks available credit. PHASE_03.md H/I is authority. |
| Public invoice | Owner issues for a CONFIRMED invoice only; at most one active link (issuing/rotating revokes earlier links; cancellation revokes) -> hash + safe audit -> one-time URL -> browser fragment to header -> token + active tenant + confirmed check -> current revision allowlist (D-042). No account login, debt history, supplier cost or profit. |
| Supplier foundation | Owner creates suppliers and appends effective-dated product costs through `/api/v1/suppliers` (D-041); preferred supplier preloads invoice entry. Opening payable -> ordinary payment capped at payable (D-039) or explicit prepayment credit -> compensating reversal, per-currency aggregate. No purchase allocation/procurement. |
| Debt display | Read computes positive per-currency debt, oldest unpaid age on the Asia/Beirut calendar (D-040), threshold flag and stable alert key. UI displays it; no job worker or persistent notification queue (cadence remains a later operational policy). |

Finance APIs use `?tenant_id=...` with /api/v1/invoices, /payments, /customer-ledger,
/supplier-ledger and /suppliers groups. Catalog APIs remain nested under /api/v1/tenants/{tenant_id}.
/api/v1/tenant-contexts discovers the caller's active memberships. Blanket tenant-nested wording
in the older API summary is not an accurate route map now. Public HTML is /api/v1/public/invoice;
its /data endpoint reads the secret header manually. OpenAPI describes the header but does not
declare a formal required header parameter.

## Database model and migration ownership

One PostgreSQL schema/model set, not one database per tenant. models.py defines the ORM shape;
Alembic additionally defines RLS, historical conversions and append-only triggers. Model metadata
alone misses these semantics. No production create_all workflow is prescribed.
repositories/tenancy.py sets transaction-local app.current_tenant_id / app.current_user_id;
commit_and_restore_tenant_scope restores scope for post-commit reads.

| Family | Current tables / scope |
|---|---|
| Platform identity | users, auth_sessions, tenants, tenant_applications; platform/session access differs from tenant business authority |
| Membership/audit | tenant_memberships, tenant_invitations, audit_events; invitations have schema but no flow; internal membership lifecycle service is not an HTTP management API |
| Global master identity | master_categories, master_products, master_barcodes, master_product_images, master_catalog_imports, master_product_sources; not tenant commercial pricing |
| Tenant customer/catalog | customers, categories, tenant_products, tenant_barcodes, tenant_grade_discounts, product_grade_prices, tenant_product_images |
| Tenant costs | tenant_suppliers (identity/name, owner CRUD), append-only tenant_product_cost_entries (owner append), preferred supplier reference; contacts/location and procurement remain Phase 6 |
| Invoice/history | invoices, invoice_sequences, invoice_revisions, invoice_revision_items; header pointers, revision financial snapshots; nullable order_id uniqueness is reserved, not a live order table |
| Money/events | customer_ledger_entries, supplier_ledger_entries, payments, payment_allocations, tenant_financial_settings; balances computed per currency |
| Public sharing | public_invoice_capabilities; mutable expiry/revocation/rotation metadata, hash-only secret, tenant/invoice composite relationship |

| Revisions | Actual purpose |
|---|---|
| 0001–0003 | Identity/session/tenant/application foundation; platform audit RLS; customer/category/product/draft slice |
| 0004 | Customer grades/coordinates, bilingual master/tenant categories and self-membership scope |
| 0005 | Master/tenant product and barcode separation |
| 0006 | Grade discounts/prices and media metadata |
| 0007 | Catalog import provenance |
| 0008 | Converts old draft rows to revisions/items; replaces invoice_items; financial/cost/capability tables, constraints, RLS and immutable triggers |
| 0009 | Revision-item line ordering |
| 0010 | Confirmation/debt/financial settings constraints, including zero adjustments |
| 0011 | Explicit zero-value confirmed-cancellation reversal; current head 20260827_0011 |

tawzeevo_reject_financial_mutation rejects UPDATE/DELETE on cost entries, revisions/items,
customer/supplier ledger entries, payments and allocations. Headers and capabilities are not
immutable financial records. 0009/0010 remain unchanged with exact Ruff exceptions and content
guards. Never expand these exceptions to conceal a new failure.

Tenant-owned rows use forced RLS and predicates; tests exercise non-bypass roles. The connection
role is not proven by the DATABASE_URL variable name. Master/platform records have different
policies; do not replace them with a generic Supabase auth.uid() policy. D-027 specifies direct
PostgreSQL and Tawzeevo authentication, not Supabase Auth/Data API. Deployed grants/roles are
CANNOT VERIFY from the baseline.

## Runtime, setup and deployment evidence

| Input | Recorded configuration, not live-service certification |
|---|---|
| Development | README Windows PowerShell flow; Python 3.13+, Node 22+, hosted PostgreSQL or compose.yaml PostgreSQL 16 dev/test services |
| Backend locks | uv.lock was clean-checkout tested; requirements.lock is an older snapshot. README editable pip install and Render pip install . do not enforce either (CT-008). |
| Frontend | npm ci / package-lock.json -> npm run check -> Vite dist; VITE variables are build-time |
| Hosting | D-027/028 and render.yaml describe hosted PostgreSQL plus Render static operations/Python API services; live state not queried |
| API startup | Uvicorn binds PORT; Blueprint /health is not a schema/readiness gate. No Blueprint Alembic step; README migrations are manual. |
| Media | LocalObjectStorage under MEDIA_LOCAL_ROOT; opaque keys, validation and WebP re-encoding; no durable cloud provider |
| Offline | Manifest and small shell service worker only; no Dexie, business IndexedDB/outbox, sync APIs/devices/leases or Drive backup |

Environment **names**: DATABASE_URL, TEST_DATABASE_URL, APP_ENV, JWT_SECRET,
CORS_ALLOWED_ORIGINS, REFRESH_COOKIE_SECURE, ACCESS_TOKEN_TTL_MINUTES,
REFRESH_TOKEN_TTL_DAYS, REFRESH_COOKIE_NAME, REFRESH_COOKIE_PATH, JWT_ISSUER, JWT_AUDIENCE,
MEDIA_LOCAL_ROOT, MEDIA_MAX_UPLOAD_BYTES, MEDIA_MAX_DIMENSION, INVOICE_FUZZY_MATCH_THRESHOLD;
frontend VITE_API_BASE_URL and VITE_DEMO_PREVIEW; hosting PORT/runtime versions.
config.py owns defaults/production guards. Never use development placeholders in production.
Settings read .env relative to process working directory. Localhost and 127.0.0.1 are different
browser hosts: verify a consistent local host plan and credentialed refresh. CORS alone does not
certify deployed cookie compatibility. Actual environment values and database grants remain unverified.

## Testing structure and evidence limits

pytest/FastAPI TestClient use real PostgreSQL via dependency overrides. The autouse fixture
truncates business tables even for many apparently pure tests; missing TEST_DATABASE_URL can
skip tests. Migration/RLS tests create/drop temporary databases and roles, requiring disposable
test-only privileges. Two migration tests construct Alembic paths by Windows backslash replacement;
cross-platform execution is not evidenced.

Vitest/Testing Library use mocked fetch/jsdom. PublicInvoicePage tests execute the actual HTML
script, not a full real-browser flow. No committed Playwright suite or CI workflow was found.
UNIT_TEST_STRATEGY.md is a historical proposal, not proof of a no-database unit lane.
P3-M6 still owns phase-wide hardening/acceptance.

The frozen baseline report records 126 backend tests, 92.29% coverage, 34 frontend tests,
whole-backend Ruff, strict mypy, frontend lint/types/build and Alembic migration/drift success.
This continuity pass performs static source/document validation, not a new runtime rerun.
See [RUN_TESTS.md](../RUN_TESTS.md) and [baseline reproduction](phase-3/baseline-remediation.md).
Do not present prior executions as tests run by this audit.

## Status and future boundary

Use [persistent status](../03_IMPLEMENTATION_STATUS.md); no duplicate PHASE_STATUS document.
Phase 1/2 evidence is frozen; P3-M5 evidence is not a Phase 3 completion report. The
[phase index](../02_PHASE_INDEX.md) retains future gates. PHASE_04–10 were absent at the immutable
implementation baseline but are now reconciled authoritative root specifications; CT-002 is closed.
Their explicit `REVIEW_REQUIRED` sync/order/job/provider/metric details remain phase-gate blockers,
not approved defaults. Historical copies under `docs/recovered-planning/` are provenance only.
