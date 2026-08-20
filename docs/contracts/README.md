# Architecture contracts

These concise contracts restate approved decisions from the authoritative root documents. They guide future milestones but do not unlock future functionality. When a summary conflicts with `PHASE_01.md`, `04_DECISIONS.md`, or `00_PROJECT_CONTRACT.md`, the root source-of-truth order in `AGENTS.md` wins.

- `locked-decisions.md` — approved product and architecture boundaries
- `api-conventions.md` — namespaces, error semantics, tenant resource conventions
- `auth-session.md` — access/refresh tokens, rotation, revocation, browser storage
- `tenant-isolation.md` — membership checks, lifecycle blocking, service scope, RLS
- `audit-events.md` — append-only security and lifecycle evidence
- `pricing.md` — grade precedence, decimal money, piece/box derivation
- `financial-invariants.md` — immutable financial history, balances, refunds
- `payment-allocation.md` — immutable customer allocation and supplier payable scope
- `order-state.md` — guest order review, confirmation, cancellation boundaries
- `public-access.md` — guest identity and capability-token rules
- `delivery-assignment.md` — owner-as-operator and driver least privilege
- `sync-protocol.md` — offline outbox, versions, cursors, devices, revocation
- `offline-authoritative-ids.md` — local UUIDs and server-assigned business sequences
- `jobs-reminders.md` — owner reminders, tenant/timezone/idempotency requirements
- `media-security.md` — accepted formats, validation, storage abstraction, access

Later phase gates must resolve any deliberately undecided state machine, provider, OAuth scope, or protocol detail before implementation.
