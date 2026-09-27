import { useCallback, useEffect, useRef, useState } from "react";

import { OUTBOX_CHANGED_EVENT, SYNC_COMPLETED_EVENT } from "./events";
import { listOutbox } from "./outbox";
import { syncNow } from "./pull";

/**
 * Sends work queued on this device by itself (D-098): when the connection comes back, when the app
 * opens with something waiting, and a few seconds after something is queued. It runs the same
 * `syncNow` as the Sync now button — same commands, same idempotency — one run at a time, and waits
 * longer after each failure. Manual Sync now stays available.
 */
export interface AutoSyncState {
  pending: number;
  attention: number;
  sending: boolean;
  justSent: boolean;
  online: boolean;
}

const QUEUE_DELAY_MS = 3000;
const BACKOFF_MS = [30_000, 120_000, 300_000];
const SENT_FLASH_MS = 4000;
const WAITING = new Set(["pending", "sending", "retryable_failed"]);
const ATTENTION = new Set(["conflict", "rejected", "dead_letter"]);

export function useAutoSync(tenantId: string | null, membershipId: string | null): AutoSyncState {
  const [state, setState] = useState<AutoSyncState>({ pending: 0, attention: 0, sending: false, justSent: false, online: typeof navigator === "undefined" ? true : navigator.onLine });
  const running = useRef(false);
  const failures = useRef(0);
  const timer = useRef<number | undefined>(undefined);
  const flash = useRef<number | undefined>(undefined);

  const count = useCallback(async () => {
    if (!tenantId || !membershipId) return { pending: 0, attention: 0 };
    try {
      const rows = await listOutbox(tenantId, membershipId);
      const counts = { pending: rows.filter((row) => WAITING.has(row.state)).length, attention: rows.filter((row) => ATTENTION.has(row.state)).length };
      setState((current) => ({ ...current, ...counts }));
      return counts;
    } catch {
      return { pending: 0, attention: 0 }; // no device storage: nothing can be waiting here
    }
  }, [tenantId, membershipId]);

  const schedule = useCallback((delay: number, run: () => void) => {
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(run, delay);
  }, []);

  const send = useCallback(async () => {
    if (!tenantId || !membershipId || running.current) return;
    if (typeof navigator !== "undefined" && !navigator.onLine) return;
    running.current = true; // claimed before any await, so two triggers can never both send
    const { pending } = await count();
    if (!pending) { running.current = false; return; }
    setState((current) => ({ ...current, sending: true }));
    let retry = false;
    try {
      const outcome = await syncNow(tenantId, membershipId);
      if (outcome.kind === "ok") {
        failures.current = 0;
        setState((current) => ({ ...current, justSent: true }));
        window.clearTimeout(flash.current);
        flash.current = window.setTimeout(() => setState((current) => ({ ...current, justSent: false })), SENT_FLASH_MS);
      } else if (outcome.kind === "offline") {
        retry = true;
      }
      window.dispatchEvent(new Event(SYNC_COMPLETED_EVENT));
    } catch {
      retry = true;
    } finally {
      running.current = false;
      setState((current) => ({ ...current, sending: false }));
      await count();
    }
    if (retry) {
      const delay = BACKOFF_MS[Math.min(failures.current, BACKOFF_MS.length - 1)]!;
      failures.current += 1;
      schedule(delay, () => { void send(); });
    }
  }, [tenantId, membershipId, count, schedule]);

  useEffect(() => {
    if (!tenantId || !membershipId) return undefined;
    failures.current = 0;
    void send(); // the app opened: send anything left from before
    const online = () => { setState((current) => ({ ...current, online: true })); failures.current = 0; void send(); };
    const offline = () => setState((current) => ({ ...current, online: false }));
    const queued = () => { void count(); schedule(QUEUE_DELAY_MS, () => { void send(); }); };
    window.addEventListener("online", online);
    window.addEventListener("offline", offline);
    window.addEventListener(OUTBOX_CHANGED_EVENT, queued);
    return () => {
      window.removeEventListener("online", online);
      window.removeEventListener("offline", offline);
      window.removeEventListener(OUTBOX_CHANGED_EVENT, queued);
      window.clearTimeout(timer.current);
      window.clearTimeout(flash.current);
    };
  }, [tenantId, membershipId, send, count, schedule]);

  return state;
}
