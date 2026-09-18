# Encrypted backup: keys, rotation and restore

Tawzeevo places a complete, encrypted copy of each business in one app-created folder of the
owner's own Google Drive (OAuth scope `drive.file` only). This runbook covers the keys that make
those files readable, how to rotate them, and how a backup is restored without ever overwriting
live data.

## Key model

| Key | Where it lives | Purpose |
|---|---|---|
| Master key (KEK), one per environment | Hosting-provider secret `BACKUP_MASTER_KEY` (base64 of 32 random bytes) **and** the owner's password manager | Wraps every tenant data key and every stored Drive refresh token |
| Tenant data key (DEK), one per business | `tenant_backup_keys.wrapped_key`, stored only wrapped by the KEK | AES-256-GCM encryption of that business's backup files |
| Drive refresh token, one per connection | `tenant_backup_connections.wrapped_refresh_token`, stored only wrapped by the KEK | Lets the server upload to, list and delete files in the app folder |

Plaintext keys exist only in process memory. Nothing in the repository, the database or the logs
holds a usable key; OAuth codes and tokens are redacted from access logs.

Generate a master key:

```bash
python -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode())"
```

Set `BACKUP_MASTER_KEY` and `BACKUP_KEK_ID` (a label such as `kek-prod-1`) as environment secrets.
Each environment (development, staging, production) uses its own master key.

## Backup file and manifest

- File name: `tawzeevo-<tenant id>-<UTC timestamp>-<daily|monthly|manual>.tzb`
- Content: one byte format version, a 96-bit nonce, then AES-256-GCM ciphertext and tag.
- The manifest (schema version, business id, timestamps, application and migration versions,
  encryption metadata, SHA-256 checksum, row counts per table) is stored in the database and is
  bound to the ciphertext as authenticated data. A manifest swapped between files, a flipped byte
  or a wrong key makes decryption fail closed.
- Schedule: one backup per business per 24 hours; the first backup of a month is the monthly one.
  Retention keeps the newest 30 daily/manual and 12 monthly backups; expired files are deleted
  from Drive and marked `DELETED`.
- Scheduling: run `python -m tawzeevo_api.cli.backup_jobs run-due` from the hosting scheduler, or
  set `BACKUP_SCHEDULER_ENABLED=true` for the in-process hourly timer.

## Master key rotation

1. Generate the new key and store it in the password manager as the next key.
2. Set `BACKUP_MASTER_KEY_NEXT=<new key>` next to the current `BACKUP_MASTER_KEY`.
3. Run `python -m tawzeevo_api.cli.backup_jobs rotate-master-key --new-kek-id kek-prod-2`.
   Every tenant data key and refresh token is unwrapped with the old key and re-wrapped with the
   new one in a single transaction; existing backup files stay readable because the data keys
   themselves do not change.
4. Move the new value into `BACKUP_MASTER_KEY`, set `BACKUP_KEK_ID=kek-prod-2`, remove
   `BACKUP_MASTER_KEY_NEXT`, restart the API.
5. Keep the previous key in the password manager for 30 days, then retire it.

## Restore

Restore never writes into a live business. The steps, in order:

1. **Drill (owner, any time).** Backup tab → *Run restore drill*. The server downloads the file,
   checks the checksum, unwraps the key, authenticates and decrypts the payload, and reconciles
   the row counts with the manifest. The result is recorded; live data is untouched.
2. **Recovery environment (platform team).** Create an empty environment with the same migration
   version as the manifest (`migration_version`) and the same master key.
3. **Verify there (platform team).** Run the drill again in the recovery environment.
4. **Owner approval.** The owner confirms, in writing, which backup is to be imported.
5. **Controlled import (platform administrator).**
   `POST /api/v1/platform/tenants/{tenant_id}/backups/{backup_id}/import` with
   `{"confirm_tenant_id": "<tenant id>"}`. The import is refused unless the business has no
   business rows at all (`BACKUP_TARGET_NOT_EMPTY`); ids are preserved; devices that synchronized
   against the lost data are forced to re-bootstrap.
6. **Reconciliation.** Compare the import report with the manifest counts and spot-check invoices
   and balances with the owner.
7. **Audit.** The import is recorded as an audit event and as a `tenant_backup_restores` row.

Platform users, memberships and sessions are platform data: they are restored from the platform
database backup (for example the hosted PostgreSQL point-in-time recovery), not from the
business backup.

## Losing things

| Lost | Effect | Recovery |
|---|---|---|
| Master key | No backup of any business can be decrypted | Restore it from the password manager; this is why the copy there is mandatory |
| Database, master key intact | Business data | Recovery runbook above, one business at a time |
| Owner's Google account | Files in Drive | Reconnect a new account; the next backup starts a new folder. Older files stay in the old account |
| Drive file deleted by the owner | That backup | The next scheduled run creates a new one; deleted rows are marked when the drill fails |
