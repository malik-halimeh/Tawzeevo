import { useEffect, useState } from "react";

import { apiRequest } from "../api/client";

/** One supplier with its balance per currency, as the server sums the supplier ledger (D-100). */
export interface SupplierBalanceRow { supplier_id: string; supplier_name: string; balances: { currency: string; balance: string }[] }

/** Balances of every supplier, reloaded whenever `version` changes (a payment or reversal happened). */
export function useSupplierBalances(tenantId: string, version: number) {
  const [balances, setBalances] = useState<Record<string, SupplierBalanceRow["balances"]>>({});
  useEffect(() => {
    let live = true;
    apiRequest<{ suppliers: SupplierBalanceRow[] }>(`/api/v1/supplier-ledger/balances?tenant_id=${tenantId}`)
      .then((body) => { if (live) setBalances(Object.fromEntries(body.suppliers.map((row) => [row.supplier_id, row.balances]))); })
      // The balance chips are a convenience beside the list; the ledger desk below still shows them.
      .catch(() => undefined);
    return () => { live = false; };
  }, [tenantId, version]);
  return balances;
}
