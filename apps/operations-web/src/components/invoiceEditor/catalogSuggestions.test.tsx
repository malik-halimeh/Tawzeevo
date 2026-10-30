import { act, renderHook } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { apiRequest } from "../../api/client";
import type { InvoiceCatalogSearchResponse } from "../../api/types";
import { useCatalogSuggestions } from "./catalogSuggestions";

vi.mock("../../api/client", () => ({ apiRequest: vi.fn() }));
afterEach(() => { vi.useRealTimers(); vi.resetAllMocks(); });

test("catalog lookup waits 250 ms from two characters and cancels pending, in-flight and late results", async () => {
  vi.useFakeTimers();
  const pending: { resolve: (value: InvoiceCatalogSearchResponse) => void; signal: AbortSignal }[] = [];
  vi.mocked(apiRequest).mockImplementation((_url, options) => new Promise((resolve) => {
    pending.push({ resolve, signal: options!.signal as AbortSignal });
  }));
  const onMatches = vi.fn();
  const { rerender, unmount } = renderHook(({ query, active }) => useCatalogSuggestions({ tenantId: "tenant", query, active, onMatches }), { initialProps: { query: "s", active: true } });
  await act(() => vi.advanceTimersByTimeAsync(300));
  expect(apiRequest).not.toHaveBeenCalled();
  rerender({ query: "su", active: true });
  await act(() => vi.advanceTimersByTimeAsync(200));
  rerender({ query: "sun", active: true });
  await act(() => vi.advanceTimersByTimeAsync(249));
  expect(apiRequest).not.toHaveBeenCalled();
  await act(() => vi.advanceTimersByTimeAsync(1));
  expect(apiRequest).toHaveBeenCalledTimes(1);
  expect(vi.mocked(apiRequest).mock.calls[0]?.[0]).toContain("query=sun");
  rerender({ query: "oil", active: true });
  expect(pending[0]!.signal.aborted).toBe(true);
  await act(() => vi.advanceTimersByTimeAsync(250));
  const fresh = [{ product_id: "fresh" }] as InvoiceCatalogSearchResponse["matches"];
  const stale = [{ product_id: "stale" }] as InvoiceCatalogSearchResponse["matches"];
  await act(() => { pending[1]!.resolve({ matches: fresh }); return Promise.resolve(); });
  expect(onMatches).toHaveBeenLastCalledWith(fresh);
  await act(() => { pending[0]!.resolve({ matches: stale }); return Promise.resolve(); });
  expect(onMatches).toHaveBeenLastCalledWith(fresh);
  rerender({ query: "oil", active: false });
  expect(pending[1]!.signal.aborted).toBe(true);
  expect(onMatches).toHaveBeenLastCalledWith([]);
  unmount();
});

test("explicit Search runs immediately and cancel prevents publication after adding or leaving", async () => {
  vi.useFakeTimers();
  let resolve!: (value: InvoiceCatalogSearchResponse) => void;
  vi.mocked(apiRequest).mockImplementation(() => new Promise((done) => { resolve = done; }));
  const onMatches = vi.fn();
  const { result, unmount } = renderHook(() => useCatalogSuggestions({ tenantId: "tenant", query: "water", active: true, onMatches }));
  let search!: Promise<void>;
  act(() => { search = result.current.search("water"); });
  expect(apiRequest).toHaveBeenCalledTimes(1);
  act(() => result.current.cancel());
  await act(async () => { resolve({ matches: [] }); await search; });
  await act(() => vi.advanceTimersByTimeAsync(300));
  expect(apiRequest).toHaveBeenCalledTimes(1);
  expect(onMatches).toHaveBeenCalledTimes(1); // initial clearing only
  unmount();
});
