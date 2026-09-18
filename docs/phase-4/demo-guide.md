# Phase 4 demo and presentation guide

This guide demonstrates only completed Phase 4 behavior: working with no connection, exactly-once
synchronization, conflict handling, revocation, and the encrypted Google Drive backup with its
restore drill. Use synthetic data only.

## Prepare the environment

1. Follow the root `README.md` local setup. Never demonstrate against production data.
2. Apply migrations and confirm revision `20260918_0016` is the current Alembic head.
3. Start the API with `BACKUP_DRIVE_PROVIDER=memory` (no Google account needed for the demo) and a
   `BACKUP_MASTER_KEY` generated as in `docs/runbooks/backup-key-recovery.md`.
4. Sign in as the active owner of an approved synthetic tenant with one category, one product
   with a barcode, one supplier cost entry and one customer.
5. Open the browser developer tools: the Network panel has an *Offline* switch you will use.

## Recommended presentation route

### 1. Download the business, then lose the connection

1. Open the **Offline** tab and press *Download for offline use*. Show the local counts
   (customers / products / invoices) and the sync position.
2. Switch the browser to *Offline*. The connection badge changes and *Sync now* is disabled.

### 2. Work offline

1. **Customers**: add a new customer. The notice says it was saved on this device and will be sent
   once when the connection returns.
2. **Invoices**: search that customer by phone (the match comes from the device), scan the product
   barcode (the line comes from the device catalog), and save the draft. Point at the reference
   `PENDING-XXXXXXXX`: the client never invents an official invoice number.
3. Back in **Offline**, show both commands as *Waiting to send*. Reload the page: they are still
   there (restart persistence).

### 3. Reconnect and synchronize exactly once

1. Switch the browser back online and press *Sync now*: "2 change(s) sent". Press it again:
   "0 change(s) sent". Explain the operation id and request fingerprint on the server: the same
   command replayed 100 times has one effect (`test_sync_hardening.py`).
2. Open **Invoices** and look the customer up online: the draft exists once, with the same line.
   Confirm it online to show the server-assigned `YYYY-000001`.

### 4. Conflicts are never merged silently

1. Edit the customer's address in a second browser (or through the API) while the first browser
   is offline; then edit the same customer offline in the first browser and reconnect.
2. The Offline tab shows *Conflict* with both versions and two explicit choices: keep the server
   version or resend mine. Nothing was overwritten.

### 5. Revocation

1. As the platform administrator, suspend the tenant while the owner's browser is offline.
2. When the owner reconnects and syncs, the device is refused, the local business data is removed
   and queued changes are set aside. Reactivate the tenant to continue.

### 6. Encrypted backup and restore drill

1. Open the **Backup** tab. Explain the permission: only files the app creates (`drive.file`), in
   one folder named after the business.
2. Press *Connect Google Drive*. With the memory double the connection completes immediately; with
   a real client the owner passes through Google's consent screen and returns to the app.
3. Press *Back up now*. Show the manifest facts in the history: kind, size, row count, checksum
   prefix, and that the file is ciphertext (AES-256-GCM with a per-business key wrapped by the
   environment master key).
4. Press *Run restore drill*: the server downloads, verifies the checksum, unwraps the key,
   decrypts and reconciles the row counts. Live data is untouched; the result is recorded.
5. Explain the real restore path from `docs/runbooks/backup-key-recovery.md`: an empty recovery
   tenant, owner approval, platform-administrator import, reconciliation, audit. A live business
   can never be overwritten by a restore.

## Security expectations (say them out loud)

- The device installation id is a de-duplication identity, never a credential. Every sync request
  carries the owner's short-lived session and is checked against the membership.
- No access or refresh token is stored in localStorage or IndexedDB. Anyone with physical access
  to an unlocked device can read the local business data; browser storage is not tamper-proof and
  the app does not claim otherwise.
- Sign-out, membership revocation and tenant suspension purge the local data on the next contact.

## Limitations to state plainly

- A device that is physically offline cannot learn about a revocation until it reconnects.
- Official numbers, revision numbers and change sequence numbers exist only on the server.
- Google connect and restore are online-only actions.
- No stock or availability tracking was introduced; "published" still means visible.
