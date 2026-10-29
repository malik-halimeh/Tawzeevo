import { useCallback, useEffect, useRef } from "react";

import { apiRequest } from "../../api/client";
import type { Customer } from "../../api/types";
import { searchLocalCustomers, type LocalCustomer } from "../../offline/sync";

/** A customer row from the owner's customer list (OE-03b): the record plus what they owe per currency. */
export interface CustomerMatch extends Customer {
  balances?: { currency: string; balance: string }[];
}

interface CustomerListPage {
  customers: CustomerMatch[];
}

export const SUGGESTION_MIN_LENGTH = 2;
export const SUGGESTION_DELAY_MS = 300;
const SUGGESTION_LIMIT = 10;
const QUERY_MAX_LENGTH = 64;

/** Local projection rows in the shape the customer results show (as the phone search always did). */
export function localAsCustomers(rows: LocalCustomer[]): Customer[] {
  return rows.map((row) => ({ ...row, phone_raw: row.phone_raw ?? row.phone, latitude: row.latitude, longitude: row.longitude, grade: row.grade })) as unknown as Customer[];
}

/** Name or part of a phone, from the server; offline, from this device's projection with the same folding. */
async function findCustomers(tenantId: string, membershipId: string, typed: string): Promise<{ matches: CustomerMatch[]; offline: boolean }> {
  try {
    const page = await apiRequest<CustomerListPage>(`/api/v1/tenants/${tenantId}/customers?q=${encodeURIComponent(typed.slice(0, QUERY_MAX_LENGTH))}&limit=${SUGGESTION_LIMIT}`);
    return { matches: page.customers, offline: false };
  } catch (problem) {
    if (!(problem instanceof TypeError)) throw problem;
    const local = await searchLocalCustomers(tenantId, membershipId, typed);
    return { matches: localAsCustomers(local.slice(0, SUGGESTION_LIMIT)), offline: true };
  }
}

/**
 * Matches while the owner types (at least two characters, after a short pause). Only the answer
 * to the latest text is shown; `cancel` drops the pending and in-flight lookups (the exact-phone
 * search the owner just asked for wins). A failed lookup shows nothing: Search still works.
 */
export function useCustomerSuggestions({ tenantId, membershipId, query, active, onMatches, onCleared }: {
  tenantId: string;
  membershipId: string;
  query: string;
  active: boolean;
  onMatches: (matches: CustomerMatch[], offline: boolean) => void;
  onCleared: () => void;
}) {
  const sequence = useRef(0);
  const timer = useRef<number | undefined>(undefined);
  const handlers = useRef({ onMatches, onCleared });
  useEffect(() => {
    handlers.current = { onMatches, onCleared };
  });

  useEffect(() => {
    if (!active) return;
    const typed = query.trim();
    const ticket = ++sequence.current;
    if (typed.length < SUGGESTION_MIN_LENGTH) {
      handlers.current.onCleared();
      return;
    }
    timer.current = window.setTimeout(() => {
      findCustomers(tenantId, membershipId, typed)
        .then(({ matches, offline }) => { if (ticket === sequence.current) handlers.current.onMatches(matches, offline); })
        .catch(() => undefined);
    }, SUGGESTION_DELAY_MS);
    return () => window.clearTimeout(timer.current);
  }, [tenantId, membershipId, query, active]);

  return useCallback(() => {
    window.clearTimeout(timer.current);
    sequence.current += 1;
  }, []);
}
