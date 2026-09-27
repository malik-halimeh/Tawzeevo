/**
 * A business name typed on the register form (D-096). It is handed to the client home in this tab,
 * which sends it as the tenant application once the new account is signed in; nothing else reads it.
 */
const KEY = "tawzeevo.pendingApplication";

export function keepPendingApplication(businessName: string): void {
  try { sessionStorage.setItem(KEY, businessName); } catch { /* storage unavailable: the owner applies by hand */ }
}

export function takePendingApplication(): string | null {
  try {
    const name = sessionStorage.getItem(KEY);
    sessionStorage.removeItem(KEY);
    return name && name.trim() ? name.trim() : null;
  } catch {
    return null;
  }
}
