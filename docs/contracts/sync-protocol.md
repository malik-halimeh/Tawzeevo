# Sync protocol contract

The operations PWA will use an atomic local mutation plus outbox, server idempotency, entity versions, bootstrap/pull cursors, tombstones, registered devices, permission revocation, protocol versioning, and an offline media queue. A device ID identifies a device for deduplication; it never authorizes access. PostgreSQL remains authoritative.

Protocol details are locked at the Phase 4 gate.

Snapshot collections are role-scoped: the bootstrap answer advertises exactly the collections the membership role may page, and the snapshot endpoint enforces the same list server-side (403 `TENANT_OWNER_REQUIRED`) before any device or data access. The owner projection is the full snapshot; a driver device receives no snapshot collection and is fed only by the assigned-task change feed.
