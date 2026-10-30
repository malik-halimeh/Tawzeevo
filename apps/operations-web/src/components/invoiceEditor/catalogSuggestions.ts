import { useCallback, useEffect, useRef } from "react";
import { apiRequest } from "../../api/client";
import type { InvoiceCatalogMatch, InvoiceCatalogSearchResponse } from "../../api/types";

/** Cancel both transport and publication: even a response that ignores abort cannot replace newer results. */
export function useCatalogSuggestions({ tenantId, query, active, onMatches }: {
  tenantId: string;
  query: string;
  active: boolean;
  onMatches: (matches: InvoiceCatalogMatch[]) => void;
}) {
  const sequence = useRef(0);
  const timer = useRef<number | undefined>(undefined);
  const controller = useRef<AbortController | undefined>(undefined);
  const handler = useRef(onMatches);
  useEffect(() => { handler.current = onMatches; });
  const cancel = useCallback(() => {
    window.clearTimeout(timer.current);
    sequence.current += 1;
    controller.current?.abort();
  }, []);
  const search = useCallback(async (typed: string) => {
    cancel();
    const ticket = sequence.current;
    const request = new AbortController();
    controller.current = request;
    try {
      const result = await apiRequest<InvoiceCatalogSearchResponse>(`/api/v1/invoices/catalog-search?tenant_id=${tenantId}&query=${encodeURIComponent(typed)}`, { signal: request.signal });
      if (ticket === sequence.current) handler.current(result.matches);
    } catch (error) {
      if (ticket === sequence.current && !request.signal.aborted) throw error;
    }
  }, [tenantId, cancel]);
  useEffect(() => {
    cancel();
    handler.current([]);
    if (active && query.trim().length >= 2) {
      timer.current = window.setTimeout(() => { void search(query.trim()).catch(() => undefined); }, 250);
    }
    return cancel;
  }, [query, active, cancel, search]);
  return { cancel, search };
}
