# Phase 4 requirements audit

Audit date: 2026-09-18

Status: PASS (P4-M6 freeze)

This document freezes requirement-to-code/test evidence for `PHASE_04.md`. It does not supersede
the project contract, the decision ledger, or the phase contract. Backend paths are relative to
`apps/api/tawzeevo_api/`, tests to `apps/api/tests/`, frontend to `apps/operations-web/src/`.
Gate D decisions: D-052 (device lease 24 h, retirement 90 d), D-053 (tombstone retention 90 d with
a per-tenant floor), D-054 (manual merge on version conflicts), D-055 (`drive.file` scope, one app
folder per business), D-056 (30 daily / 12 monthly backups), D-057 (per-tenant keys wrapped by an
environment master key).

## A/C — Device security and registry

| Requirement | Implementation evidence | Test evidence | Result |
|---|---|---|---:|
| Device installation id is dedup identity only; registered during authenticated bootstrap | `services/sync.py::bootstrap/active_device`; `routes/sync.py` (owner dependency on every route) | `test_sync_bootstrap.py::test_device_id_is_never_authorization...`; `test_sync_hardening.py::test_a_device_id_alone_is_never_authorization` | PASS |
| No access/refresh token in localStorage/IndexedDB; only the installation id in localStorage | `offline/db.ts` (`getDeviceInstallationId`, no token stores); `offline/media.ts::setMediaTokenProvider` reads the in-memory token | `sync.test.ts` (database contents), review of `db.ts` stores | PASS |
| Unique active tenant+user+device; stale devices retire and re-bootstrap (D-052) | migration `0014` partial unique index; `sync.py::active_device` (90 d retirement → 410) | `test_sync_bootstrap.py::test_retired_device_must_rebootstrap` | PASS |
| Owner projection only (no driver role exists yet); minimum local projection per collection | `services/sync_changes.py::PROJECTIONS`; `sync.py::snapshot_page` role-filtered fields | `test_sync_bootstrap.py` snapshot field assertions | PASS |
| Documented browser security expectations; no custom IndexedDB encryption as authorization | `docs/phase-4/demo-guide.md` § Security expectations; `db.ts` header comment | — (documentation) | PASS |

## B/J — Suspension, closure and revocation

| Requirement | Implementation evidence | Test evidence | Result |
|---|---|---|---:|
| Membership revoke / tenant suspend revoke devices server-side; sync denied on next contact | `services/memberships.py`, `services/platform.py` → `sync.py::revoke_membership_devices/revoke_tenant_devices` | `test_sync_pull.py::test_membership_revocation_and_tenant_suspension_revoke_devices` | PASS |
| Reconnect purges/quarantines local cache; queued work from revoked devices never applies | `offline/pull.ts::syncNow/quarantineAndPurge` (`REVOCATION_CODES`) | `pull.test.ts::syncNow pushes then pulls, and a revoked device is quarantined and purged` | PASS |
| Physically offline browsers cannot receive revocation instantly (explicit limitation) | `docs/phase-4/demo-guide.md` § Limitations | — | PASS |

## D/E/H/I — Offline operations, outbox and conflicts

| Requirement | Implementation evidence | Test evidence | Result |
|---|---|---|---:|
| Read synced customers/products/categories; phone search from the projection | `offline/sync.ts::searchLocalCustomers/findLocalProductByBarcode`; `InvoiceEditor.tsx` offline fallbacks | `sync.test.ts`; `e2e/phase4-offline-flow.spec.ts` (real offline mode) | PASS |
| Create/edit customer, create/edit product offline with expected version | `offline/outbox.ts::createCustomerOffline/updateCustomerOffline/createProductOffline/updateProductOffline`; `TenantWorkspace.tsx` fallbacks | `outbox.test.ts`; `test_sync_push.py`; E2E offline customer creation | PASS |
| Create/edit invoice draft, confirm, post-confirmation edit, authorized payment offline | `offline/commands.ts`; `services/sync_push.py::_apply_financial` (reuses Phase 3 services) | `commands.test.ts`; `test_sync_financial_push.py`; E2E offline draft | PASS |
| Atomic local mutation + outbox command; restart preserves pending; states pending/sending/acknowledged/retryable/conflict/rejected/dead-letter | `offline/outbox.ts` (Dexie transactions, `MAX_ATTEMPTS`) | `outbox.test.ts` (four scenarios); `db.test.ts` restart persistence | PASS |
| Canonical 409 conflict envelope; manual merge (D-054); ledger/payment never merged; stale invoice branch rejected | `sync_push.py::_Conflict/_check_version`; `schemas/sync.py::ConflictEnvelope`; `SyncPanel.tsx` keep-server / resend-mine | `test_sync_push.py::test_stale_expected_version_returns_conflict_envelope...`; `test_sync_financial_push.py` stale confirmation | PASS |
| Client never fabricates official numbers, revision numbers, change_seq; pending local reference shown | `commands.ts::pendingReference`; `outbox.ts::applyResult` replaces pending rows with the server projection | `commands.test.ts`; `test_sync_financial_push.py` (server assigns `-000001`) | PASS |
| Offline queueing only when the browser is offline; lost responses online keep the D-044/D-045 stable command | `offline/network.ts::browserOffline`; `InvoiceEditor.tsx` | `InvoiceEditor.test.tsx` lost-response tests (unchanged) | PASS |
| Excluded: storefront checkout, membership/platform admin, Google connect offline, driver/supplier/procurement commands | not implemented offline by design | — | PASS |

## F/G — Server sync: idempotency, versions, change log, pull, tombstones, bootstrap

| Requirement | Implementation evidence | Test evidence | Result |
|---|---|---|---:|
| Per-operation transaction, advisory lock, request fingerprint; replay returns the stored result | `sync_push.py::_apply_one/_lock/_fingerprint/_record` | `test_sync_push.py` (replay, per-operation isolation, concurrent identical pushes); `test_sync_hardening.py` replay ×1/×10/×100 | PASS |
| Crash between the financial commit and the result commit is recovered with one effect | `sync_push.py::_apply_one` (completes a staged record) | `test_sync_hardening.py::test_crash_between_the_financial_commit_and_the_result_commit_is_recovered` | PASS |
| Monotonic entity versions; change log appended in the same flush; operation/device attribution | migration `0014`; `services/sync_changes.py::_before_flush` | `test_sync_bootstrap.py::test_mutations_append_ordered_change_records_and_bump_versions` | PASS |
| Ordered pull with cursor acknowledgement, `has_more`; tombstones via delete changes | `sync.py::pull_changes`; `offline/pull.ts::pullChanges` | `test_sync_pull.py` (order, tombstones); `pull.test.ts` | PASS |
| Retention floor (D-053): purge below the floor forces re-bootstrap (410); outbox survives re-bootstrap | migration `0015`; `sync.py::purge_sync_changes`; `pull.ts` 410 handling | `test_sync_pull.py::test_purge_keeps_what_active_devices_need...`; `pull.test.ts` re-bootstrap keeps outbox | PASS |
| Paginated, resumable bootstrap of the authorized projection | `sync.py::snapshot_page`; `offline/sync.ts::bootstrapLocalProjection` (meta cursors) | `test_sync_bootstrap.py`; `sync.test.ts` interruption/resume | PASS |
| Protocol mismatch rejected server-side; client keeps pending work and blocks sending | `sync.py::_protocol_check`; `sync_push.py`; `outbox.ts::flushOutbox` (whole-request refusals restore `pending`) | `test_sync_bootstrap.py::test_protocol_mismatch...`; `outbox.test.ts::a protocol mismatch blocks sending but keeps every queued command intact` | PASS |
| Explicit, versioned, tested IndexedDB schema migrations | `db.ts` versions 1 → 2 with upgrade | `db.test.ts::a device on the first schema upgrades in place and keeps its queued work` | PASS |

## K — Offline media

| Requirement | Implementation evidence | Test evidence | Result |
|---|---|---|---:|
| Persist local media id, bytes, checksum, MIME/size, upload state, entity association, retry metadata | `offline/media.ts`; `db.ts::LocalMedia` (bytes, not Blob: some WebViews fail to store Blobs) | `media.test.ts` | PASS |
| Idempotent upload retry (identical bytes map to the existing asset) | `services/media.py::upload_tenant_product_image` sha256 lookup | `test_cash_van.py::test_product_image_upload_reencodes_and_scan_returns_tenant_image` (retry returns the same id); `media.test.ts` retry ladder | PASS |
| Object URLs render-only, never persisted | `media.ts` header; `TenantWorkspace.tsx` image rendering via blob requests | review | PASS |

## L — Google encrypted backup

| Requirement | Implementation evidence | Test evidence | Result |
|---|---|---|---:|
| `drive.file` scope only; one app-created folder per business (D-055) | `services/backup_drive.py::SCOPES/ensure_folder`; `backup.py::folder_name` | `test_backup.py::test_connect_backup_verify_and_status` (scope in the authorization URL) | PASS |
| Per-tenant DEK wrapped by an environment KEK; refresh tokens stored wrapped only; KEK rotation re-wraps (D-057) | `services/backup_crypto.py`; `backup.py::_current_key/rotate_master_key`; `cli/backup_jobs.py` | `test_backup.py::test_scheduled_backups_and_master_key_rotation`; wrapped-token assertion | PASS |
| AES-256-GCM payload; manifest (schema, tenant, timestamps, app/migration versions, encryption metadata, checksum, counts) bound as associated data | `backup_crypto.py::encrypt_payload`; `backup.py::_manifest_core` | manifest assertions; ciphertext contains no customer name/phone/invoice number | PASS |
| Daily schedule; first of month monthly; retention 30/12 (D-056) | `backup.py::run_due_backups/apply_retention`; in-process timer in `main.py`; CLI `run-due` | retention and schedule tests in `test_backup.py` | PASS |
| Tamper / wrong key / swapped manifest fail closed | `backup_crypto.py::_open` (`BackupIntegrityError`) | `test_backup.py::test_tampered_file_and_wrong_master_key_fail_safely` | PASS |
| Restore never overwrites live data: drill (download, checksum, decrypt, reconcile) then controlled import only into an empty tenant by a platform administrator, audited | `backup.py::verify_backup/import_backup`; `backup_export.py::import_tenant` (`BACKUP_TARGET_NOT_EMPTY`); `routes/backup.py` | `test_backup.py::test_import_fills_only_an_empty_tenant_and_devices_rebootstrap` | PASS |
| No secrets in repository or logs | `.env.example` placeholders; `public_invoice_security.py` OAuth code/token redaction | `test_public_invoices.py::test_public_rate_limit_and_access_log_redaction` (filter installed); repository review | PASS |
| Key-recovery and restore runbook | `docs/runbooks/backup-key-recovery.md` | — | PASS |
| Live Google Drive run | `GoogleDriveClient`/`GoogleOAuthClient` (httpx) | not executed: needs the owner's OAuth client (OWNER_ACTIONS.md § I) | DEFERRED (owner action) |

## M/N — API, PWA scope, migrations, EN/AR/RTL

| Requirement | Implementation evidence | Test evidence | Result |
|---|---|---|---:|
| `/api/v1/sync/bootstrap`, `/push`, `/pull`; every request revalidates session and membership | `routes/sync.py` | sync test files | PASS |
| PWA: service worker shell, sync state, pending/conflict/rejected/dead-letter UI, safe retry, re-bootstrap, restart persistence, pending local reference, media queue, revoked state, owner backup status | `public/sw.js`; `public/manifest.webmanifest` (192/512 px `any` + `maskable` PNG icons under `public/icons/`, added 2026-09-21 — the manifest previously declared no icons, so Chromium's installability criteria were not met); `SyncPanel.tsx`; `BackupPanel.tsx`; `InvoiceEditor.tsx` | `pwaManifest.test.ts` (manifest members, icon files and PNG dimensions); `BackupPanel.test.tsx`; offline unit suites; E2E | PASS |
| EN/AR/RTL for every new string | `i18n.ts` (`sync.*`, `backup.*`, `invoiceEditor.*Offline`, `tenantWorkspace.*QueuedOffline`) | Phase 3 E2E Arabic/RTL switch still passes | PASS |
| Alembic revisions `0014`, `0015`, `0016`; forced RLS on every new tenant-owned table; from-zero upgrade; drift check | migrations; `test_hardening.py` | `test_hardening.py::test_migrations_build_a_new_database_from_zero`; `alembic check` | PASS |

## Q — Definition of Done walk-through

`authenticate/bootstrap → disconnect → create customer → work with products → build invoice →
restart-safe queue → reconnect → synchronize exactly once` is executed in a real Chromium with
network emulation off in `apps/operations-web/e2e/phase4-offline-flow.spec.ts` (customer creation,
customer search, barcode scan and invoice draft offline; one sync sends both commands; a second
sync sends nothing; the server shows one customer and one draft with no official number).
Confirmation and authorized payments offline are covered at the command/push level
(`commands.test.ts`, `test_sync_financial_push.py`, `test_sync_hardening.py`).

No stock or availability concept was introduced. PostgreSQL remains the only financial truth.
