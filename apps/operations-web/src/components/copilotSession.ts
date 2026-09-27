import type { CopilotResponse } from "../api/intelligence";

/**
 * The assistant conversation kept for this browser tab only (D-095): it survives moving between
 * workspace sections, and is gone when the tab closes, on sign-out or with "New conversation".
 * Nothing is stored on the server (D-089). A blocked storage simply keeps nothing.
 */
export interface StoredTurn { question: string; response: CopilotResponse }

const PREFIX = "tawzeevo.copilot.";
const key = (tenantId: string) => `${PREFIX}${tenantId}`;

export function readConversation(tenantId: string): StoredTurn[] {
  try {
    const raw = sessionStorage.getItem(key(tenantId));
    const parsed: unknown = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? (parsed as StoredTurn[]).filter((turn) => typeof turn.question === "string" && turn.response !== undefined) : [];
  } catch {
    return [];
  }
}

export function writeConversation(tenantId: string, turns: StoredTurn[]): void {
  try {
    if (turns.length) sessionStorage.setItem(key(tenantId), JSON.stringify(turns));
    else sessionStorage.removeItem(key(tenantId));
  } catch { /* storage unavailable: nothing kept */ }
}

/** Every business's conversation on this tab (sign-out). */
export function clearAllConversations(): void {
  try {
    for (const name of Object.keys(sessionStorage)) if (name.startsWith(PREFIX)) sessionStorage.removeItem(name);
  } catch { /* storage unavailable */ }
}
