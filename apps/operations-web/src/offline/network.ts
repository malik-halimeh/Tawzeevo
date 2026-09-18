/**
 * Offline queueing happens only when the browser reports no connection. A request that fails
 * while the browser is online (a lost response after the server committed) keeps the D-044/D-045
 * stable command so the owner retries the same intent and the server replays it.
 */
export function browserOffline(): boolean {
  return typeof navigator !== "undefined" && navigator.onLine === false;
}

export function isOfflineFailure(error: unknown): boolean {
  return error instanceof TypeError && browserOffline();
}
