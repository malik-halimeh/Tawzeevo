# 04_DECISIONS.md — User-Approved Decision Ledger

Only record decisions explicitly approved by the user or already locked by the authoritative contract.

Do not use this file to invent decisions.

## Locked decisions

| ID | Decision | Status |
|---|---|---|
| D-001 | Phase 1 contains the complete supplied FastAPI program requirements; the source-labeled frontend bonus is mandatory for this project. | LOCKED |
| D-002 | PostgreSQL is the authoritative database. | LOCKED |
| D-003 | FastAPI is the backend framework. | LOCKED |
| D-004 | Operations client is React + TypeScript + Vite and becomes an offline-first PWA. | LOCKED |
| D-005 | Public storefront uses Next.js App Router + TypeScript. | LOCKED |
| D-006 | English and Arabic are supported from the foundation. | LOCKED |
| D-007 | Platform/system user roles include admin/client; tenant roles are separate owner/driver roles. | LOCKED |
| D-008 | Public registration cannot choose a privileged role and creates client. | LOCKED |
| D-009 | Customers are not required to be authenticated users. | LOCKED |
| D-010 | No inventory/stock quantities or product availability statuses. | LOCKED |
| D-011 | Confirmed invoices remain editable only through immutable revision/ledger history. | LOCKED |
| D-012 | Customer cannot directly cancel; owner approves/rejects cancellation. | LOCKED |
| D-013 | Owner sets estimated delivery date after confirmation. | LOCKED |
| D-014 | No customer-facing delivery tracking. | LOCKED |
| D-015 | Homepage featured-product advertising defaults to 7 days and is not availability. | LOCKED |
| D-016 | Recommendations are deterministic first and purchase weight is higher than view weight. | LOCKED |
| D-017 | Google Drive is encrypted backup/export, not the live database. | LOCKED |
| D-018 | AI/forecasting is deferred until the final phase. | LOCKED |
| D-019 | Supplier payments reduce aggregate supplier payable; no per-purchase allocation unless later approved. | LOCKED |
| D-020 | Automatic customer merging is not part of the project unless later approved. | LOCKED |
| D-021 | A tenant owner may personally operate the Cash Van and perform all delivery/route operational actions without a second driver account or duplicate membership. Delivery tasks may be assigned to an active owner or driver membership. If exactly one active usable owner exists and there are no active drivers, delivery work defaults to that owner; otherwise an owner selects the assignee. Drivers remain least-privileged and cannot reassign work unless later explicitly approved. | LOCKED |
| D-022 | Platform `admin` manages tenant applications and SaaS access without automatically becoming a tenant owner or gaining tenant-private business-data access. A registered client submits an application; admin approves/rejects it; approval creates/activates the tenant and owner membership transactionally. | LOCKED |
| D-023 | Temporary non-payment never deletes a tenant or its business data. Platform admin uses tenant `SUSPENDED` with reason `SUBSCRIPTION_OVERDUE`, may set/extend `access_until` and optional `grace_until`, and later reactivates the same tenant with retained data intact. Automated payment-provider charging is not required unless later explicitly approved. | LOCKED |
| D-024 | The public product/platform name and the single public GitHub repository name are `Tawzeevo`. “Cash Van” describes the operating model and is not the product name. | LOCKED |
| D-025 | Public repository files and history use neutral implementation-agent terminology and exclude external assistant branding. | LOCKED |
| D-026 | Session policy uses 15-minute access tokens and 30-day refresh tokens. The refresh cookie is HttpOnly, Secure in production, SameSite=Lax, and scoped to `/api/v1/auth`. Refresh tokens rotate on every refresh; reuse of a rotated token revokes all active sessions for that user. | LOCKED |

## Pending decisions

None.

## Implementation procedure for a new decision

When a decision is needed:
1. do not implement it;
2. mark the current milestone blocked in `03_IMPLEMENTATION_STATUS.md`;
3. ask the user;
4. after explicit approval, add a row here:
   - ID
   - exact decision
   - phase/milestone
   - date if useful
   - what it supersedes, if anything;
5. resume only after the user says to continue.
