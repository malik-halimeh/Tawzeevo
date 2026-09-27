/** Browser events of the offline layer (kept dependency-free so the database module can use them). */
export const OUTBOX_CHANGED_EVENT = "tawzeevo:outbox-changed";
export const SYNC_COMPLETED_EVENT = "tawzeevo:sync-completed";

/** Called by the local database whenever a command is queued (see db.ts). */
export function announceOutboxChange(): void {
  if (typeof window === "undefined") return;
  // After the queuing transaction has committed, so a sync reads the new row.
  window.setTimeout(() => window.dispatchEvent(new Event(OUTBOX_CHANGED_EVENT)), 0);
}
