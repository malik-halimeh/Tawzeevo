# PHASE_04.md — Offline-First Operations, Synchronization, Google-Linked Encrypted Backup

## Phase objective
Make Tawzeevo's operations PWA resilient to unreliable/no internet while preserving server authority, tenant security, financial correctness, and replay safety.

PostgreSQL remains authoritative.
IndexedDB is the authorized local operational projection/outbox.
Google Drive is encrypted disaster-recovery/export backup, not operational synchronization.

## Start gate — Gate D
Do not begin until these are locked and verified:
- local schema/outbox protocol;
- local mutation + outbox atomicity;
- outbox states;
- server idempotency;
- entity versions;
- bootstrap/pull cursor;
- `sync_devices`;
- tombstone retention/device retirement;
- conflict envelope;
- protocol/app schema versions;
- revocation cleanup;
- offline official invoice/revision authority;
- local UUID/temp refs vs server-only sequence values;
- offline media queue.

Before the Google milestone, exact Google OAuth scope must be explicitly approved and the backup Drive folder model confirmed. Do not guess a broader scope.

---

# A. Device/local security

`device_installation_id` is dedup/sync identity only, never authentication.

Device registers only during authenticated bootstrap.

Do not claim browser storage is tamper-proof.

Required:
- no access/refresh token persistence in localStorage/IndexedDB;
- minimum role-specific local projection;
- owner/driver projections remain distinct;
- strict CSP/no arbitrary third-party scripts;
- pinned dependencies;
- local cache purge/lock on logout/revocation;
- documented device/browser security expectations.

Do not introduce custom IndexedDB encryption as an authorization boundary unless later approved.

---

# B. Tenant suspension/closure offline behavior

Server transition is authoritative immediately.

For `SUSPENDED`/`CLOSED`:
- revoke registered sync devices;
- invalidate offline leases server-side;
- reject refresh/tenant API/sync;
- on reconnect purge/lock local tenant cache;
- queued commands from revoked devices become rejected/quarantined;
- never silently apply them.

A physically offline browser cannot receive remote revocation instantly; keep this limitation explicit.

---

# C. Sync device registry

`sync_devices`:
- id;
- tenant_id;
- user_id;
- membership_id;
- device_installation_id;
- created_at/last_seen_at;
- last_acknowledged_change_seq;
- protocol_version;
- app_schema_version;
- revoked_at/reason.

Unique active tenant+user+device installation.

Stale/retired devices re-bootstrap rather than forcing infinite tombstone retention.

---

# D. Required offline operation matrix

| Operation | Offline |
|---|---|
| read synced customers/products/categories | yes |
| customer phone search in projection | yes |
| create customer | yes |
| edit customer | yes, expected version |
| create/edit tenant product | yes |
| create/edit invoice draft | yes |
| confirm invoice | yes owner, pending local reference |
| post-confirm invoice edit | yes owner |
| authorized customer payment | yes |
| set delivery date when allowed | yes owner |
| storefront guest checkout | no |
| membership/security/platform admin | no |
| Google connect/restore | no |
| driver task update | supported once Phase 7 exists |
| supplier price append | supported after Phase 6 |
| procurement edit | supported after Phase 6 |

Do not implement Phase 6/7 domain features early merely because sync can later transport them.

---

# E. IndexedDB and outbox

Use Dexie/locked thin abstraction.

Local stores:
- tenant/user/device scoped;
- authorized projection only;
- explicit schema version;
- restart-safe.

Local entity mutation + outbox record must commit in one IndexedDB transaction.

Outbox states:
```text
pending
sending
acknowledged
retryable_failed
conflict
rejected
dead_letter
```

Record:
- operation UUID;
- tenant/user/device;
- entity type/id;
- operation type;
- expected version;
- payload;
- client timestamp;
- protocol version;
- state/attempt/error.

Never silently discard conflicts/rejections/dead letters.

---

# F. Server sync

## Idempotency
Unique:
```text
(tenant_id, device_installation_id, operation_id)
```

Domain mutation + idempotency result + change records + required audit/job effects commit in one PostgreSQL transaction.

Replay returns original canonical result.

## Entity versions
Mutable conflict-sensitive rows use monotonic `version`.
Client sends `expected_version`.
Stale write never silently overwrites.

Append-only finance uses UUID/idempotency, not field merge.

## Change log
`sync_changes` contains server-assigned `change_seq BIGINT` plus tenant/entity/operation/version/time.

Clients apply ascending.

## Pull
Initial max:
```text
500 changes/page
```

Return changes, next cursor, high-water, protocol version.

Old cursor:
```text
410 SYNC_REBOOTSTRAP_REQUIRED
```

Controlled re-bootstrap preserves pending outbox then revalidates commands.

## Tombstones
Delete/archive creates delete change.

Minimum:
```text
90 days
```

Keep longer while active non-retired devices require it.

---

# G. Bootstrap

1. authenticate;
2. validate session;
3. resolve active tenant/membership;
4. register/update device;
5. capture server high-water;
6. download authorized paginated snapshot;
7. persist locally;
8. set cursor;
9. pull changes after high-water;
10. mark complete.

Must be resumable and version-aware.

Driver projection, once Phase 7 exists, is strictly less than owner projection.

---

# H. Conflict rules

Canonical 409 conflict includes safe:
- entity type/id;
- server version;
- client expected version;
- operation ID;
- manual merge strategy;
- role-filtered server projection;
- request ID.

Rules:
- customer/catalog mutable text → expected-version/manual retry;
- ledger/payment/allocation → append/idempotent, no merge;
- invoice revision → expected predecessor, reject stale branch;
- security/membership → online/server authoritative.

---

# I. Server-authoritative identifiers

Client may generate UUIDs for offline entities/commands.

Client must never fabricate:
- official invoice number;
- server revision number;
- change_seq;
- server accepted timestamp;
- job lease timestamps.

Offline confirmation shows a clearly pending local reference.
Server assigns official sequence exactly once on accepted sync.

---

# J. Revocation

After logout/user delete/membership revoke/tenant suspend:
- sync denied on next contact;
- offline lease invalidated;
- device revoked where appropriate;
- IndexedDB/Cache purged or locked;
- unauthorized pending commands rejected/quarantined.

Current offline lease default remains 24h unless later decision changes it.
Lease is never API authentication.

---

# K. Offline media

Persist:
- local media UUID;
- Blob;
- checksum;
- MIME/size metadata;
- upload state;
- entity association;
- retry/error metadata.

Object URL is transient/render-only.

Upload maps local UUID to canonical media asset.
Retry idempotent.

---

# L. Google encrypted backup

Operational sync and backup are separate.

Use approved application-managed Drive folder per tenant/connected owner.

Encryption:
- per-tenant DEK;
- AES-256-GCM payload;
- DEK wrapped by production KEK in secret manager;
- wrapped-key metadata in manifest;
- separate KEKs by environment;
- KEK rotation re-wraps DEKs.

Never commit OAuth/KEK credentials to public repo.

Manifest:
- schema version;
- tenant ID;
- created timestamp;
- app/migration versions;
- encryption metadata;
- checksum;
- row/entity counts.

Restore must never overwrite live tenant directly:
1. download/decrypt;
2. verify checksum/schema;
3. isolated recovery DB/tenant/environment;
4. integrity/reconciliation;
5. authorized cutover approval;
6. controlled import/replacement;
7. audit.

Retention policy finalized before production pilot.

---

# M. API/frontend scope

Canonical sync groups:
```text
/api/v1/sync/bootstrap
/api/v1/sync/push
/api/v1/sync/pull
```

Every sync request revalidates session + tenant membership.

Operations PWA provides:
- install/service worker;
- sync state;
- pending/conflict/rejected/dead-letter UI;
- safe retry;
- re-bootstrap;
- offline owner workflows;
- restart persistence;
- pending local invoice reference;
- media queue;
- revoked/session-expired state;
- owner backup status.

EN/AR/RTL/accessibility mandatory.

---

# N. Migration requirements

New Alembic revisions as needed for:
- sync devices;
- idempotency;
- change log;
- tombstone support;
- entity version columns;
- backup connection/metadata.

Never edit applied migrations.
RLS tenant-owned sync/backup data.
Zero migration + Phase 3 upgrade pass.

IndexedDB schema migrations explicit/versioned/tested.

---

# O. Test matrix

## Local/outbox
- atomic local mutation/outbox;
- restart preserves pending command;
- valid state transitions;
- retry/conflict/reject/dead-letter.

## Property/idempotency
- replay 1/10/100 = one effect;
- crash after send/before ack = one effect;
- independent reorder safe where commutative;
- stale conflict never overwrites.

## Pull/bootstrap
- initial/paginated bootstrap;
- interruption/resume;
- high-water catchup;
- tombstone;
- old cursor→410/rebootstrap;
- retired device.

## Financial offline
- offline confirm→one official invoice number;
- two devices no sequence collision;
- local revision UUID→one server number;
- stale predecessor conflict;
- offline payment replay one effect.

## Authorization/revocation
- membership revoked offline;
- tenant suspended offline;
- reconnect rejects/quarantines;
- cache purge;
- device ID alone denied;
- owner/driver projection separation.

## Protocol/media
- schema migration;
- protocol mismatch preserves pending work but blocks mutation;
- Blob survives restart;
- checksum/retry/idempotent upload.

## Backup
- encrypted backup;
- checksum/manifest;
- isolated restore;
- tamper/wrong-key failure;
- disconnect/reconnect;
- KEK rotation runbook.

## E2E
owner bootstrap→disconnect→customer edit→invoice confirm→payment→browser restart→reconnect→exactly-once sync.

---

# P. Milestones

## P4-M1 — PWA local schema, device registry, bootstrap foundation
Implement Gate D verification, PWA/service-worker baseline, IndexedDB schema/versioning, device registry, authorized bootstrap, local projections/search.

Acceptance:
- owner bootstrap works;
- device ID not auth;
- restart-safe;
- cross-tenant absent;
- migrations pass.

STOP.

## P4-M2 — Outbox, push idempotency, versions, conflicts
Implement atomic outbox, push, idempotency, versions, conflict envelope, audit/change-log atomicity.

Acceptance:
- replay one effect;
- stale conflict;
- crash/retry safe;
- no silent overwrite.

STOP.

## P4-M3 — Pull, tombstones, re-bootstrap, revocation
Implement ordered change log, pull pagination/high-water, tombstones/retirement, re-bootstrap, protocol checks, revoke/purge/quarantine.

Acceptance:
- deletions propagate;
- old cursor recovery;
- suspended tenant tests;
- revoked work never applies.

STOP.

## P4-M4 — Offline owner commands + media
Implement customer/product/invoice/payment/delivery-date commands, local pending invoice refs, media queue, conflict/dead-letter UX.

Acceptance:
- required current-domain offline matrix passes;
- official sequences server-only;
- restart/reconnect works;
- media persists/retries.

STOP.

## P4-M5 — Google encrypted backup + isolated restore
PRECONDITION: exact OAuth scope and Drive model recorded.

Implement OAuth, Drive connection, encrypted backup, manifest, scheduled job, status, restore drill, key-recovery docs.

Acceptance:
- encrypted backup/checksum;
- no direct live overwrite;
- tamper/wrong-key safe;
- no secrets in repo/logs.

STOP.

## P4-M6 — Offline property/E2E hardening and freeze
No new scope.

Complete two-device scenarios, property suite, revocation, protocol, media, backup, EN/AR/accessibility, migrations, OpenAPI/docs, final audit.

Acceptance:
- DoD passes;
- no critical/high offline integrity defect.

Mark Phase 4 COMPLETE and STOP. Do not start Phase 5.

---

# Q. Definition of Done

A real owner can:
```text
authenticate/bootstrap
→ disconnect
→ create/edit customer
→ work with tenant products
→ build/confirm invoice
→ record authorized payment
→ restart browser
→ reconnect
→ synchronize exactly once
```

Also:
- bootstrap/pull/tombstones work;
- conflicts safe;
- official sequences server-only;
- revocation purges/locks;
- suspended/closed queued work never silently applies;
- protocol mismatch safe;
- offline media works;
- Google backup encrypted/restored;
- PostgreSQL remains authoritative;
- no stock/availability introduced.

## Explicit exclusions
No offline storefront checkout, early Phase 6/7 domain implementation, continuous GPS, Google-as-live-DB, custom browser encryption as auth, unapproved OAuth scope, or AI.

First milestone to implement: **P4-M1 — PWA local schema, device registry, bootstrap foundation**
