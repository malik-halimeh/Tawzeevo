import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { useAutoSync } from "./autoSync";
import { OUTBOX_CHANGED_EVENT, SYNC_COMPLETED_EVENT } from "./events";
import { listOutbox } from "./outbox";
import { syncNow } from "./pull";

vi.mock("./outbox", () => ({ listOutbox: vi.fn() }));
vi.mock("./pull", () => ({ syncNow: vi.fn() }));

type Row = { state: string };
let rows: Row[] = [];
const ok = { kind: "ok", push: {}, pull: {}, status: {} } as unknown as Awaited<ReturnType<typeof syncNow>>;

beforeEach(() => {
  rows = [];
  vi.mocked(listOutbox).mockImplementation(() => Promise.resolve(rows as unknown as Awaited<ReturnType<typeof listOutbox>>));
  vi.mocked(syncNow).mockReset();
  vi.spyOn(navigator, "onLine", "get").mockReturnValue(true);
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.useRealTimers(); });

test("opening the app sends what was left waiting, once, and reports it sent", async () => {
  rows = [{ state: "pending" }, { state: "retryable_failed" }];
  vi.mocked(syncNow).mockImplementation(() => { rows = []; return Promise.resolve(ok); });
  const completed = vi.fn();
  window.addEventListener(SYNC_COMPLETED_EVENT, completed);
  const { result } = renderHook(() => useAutoSync("t1", "m1"));
  await waitFor(() => expect(syncNow).toHaveBeenCalledTimes(1));
  await waitFor(() => expect(result.current.justSent).toBe(true));
  expect(result.current.pending).toBe(0);
  expect(completed).toHaveBeenCalledTimes(1);
  window.removeEventListener(SYNC_COMPLETED_EVENT, completed);
});

test("nothing waiting sends nothing; a queued change is sent a few seconds later; offline waits for the connection", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const { result } = renderHook(() => useAutoSync("t1", "m1"));
  await waitFor(() => expect(listOutbox).toHaveBeenCalled());
  expect(syncNow).not.toHaveBeenCalled();

  rows = [{ state: "pending" }];
  vi.mocked(syncNow).mockImplementation(() => { rows = []; return Promise.resolve(ok); });
  act(() => { window.dispatchEvent(new Event(OUTBOX_CHANGED_EVENT)); });
  await waitFor(() => expect(result.current.pending).toBe(1));
  expect(syncNow).not.toHaveBeenCalled(); // not at once
  await act(async () => { await vi.advanceTimersByTimeAsync(3100); });
  await waitFor(() => expect(syncNow).toHaveBeenCalledTimes(1));

  rows = [{ state: "pending" }];
  vi.spyOn(navigator, "onLine", "get").mockReturnValue(false);
  act(() => { window.dispatchEvent(new Event(OUTBOX_CHANGED_EVENT)); });
  await act(async () => { await vi.advanceTimersByTimeAsync(3100); });
  expect(syncNow).toHaveBeenCalledTimes(1); // offline: nothing sent
  vi.spyOn(navigator, "onLine", "get").mockReturnValue(true);
  act(() => { window.dispatchEvent(new Event("online")); });
  await waitFor(() => expect(syncNow).toHaveBeenCalledTimes(2));
});

test("changes that need a look are counted, and a failed send is retried later rather than at once", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  rows = [{ state: "conflict" }, { state: "pending" }];
  vi.mocked(syncNow).mockResolvedValue({ kind: "offline" });
  const { result } = renderHook(() => useAutoSync("t1", "m1"));
  await waitFor(() => expect(syncNow).toHaveBeenCalledTimes(1));
  expect(result.current.attention).toBe(1);
  await act(async () => { await vi.advanceTimersByTimeAsync(5_000); });
  expect(syncNow).toHaveBeenCalledTimes(1); // no tight loop
  await act(async () => { await vi.advanceTimersByTimeAsync(30_000); });
  await waitFor(() => expect(syncNow).toHaveBeenCalledTimes(2));
});
