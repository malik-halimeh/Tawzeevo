# Sync protocol contract

The operations PWA will use an atomic local mutation plus outbox, server idempotency, entity versions, bootstrap/pull cursors, tombstones, registered devices, permission revocation, protocol versioning, and an offline media queue. A device ID identifies a device for deduplication; it never authorizes access. PostgreSQL remains authoritative.

Protocol details are locked at the Phase 4 gate.
