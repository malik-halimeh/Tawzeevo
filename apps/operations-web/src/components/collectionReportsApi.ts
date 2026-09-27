import { apiRequest } from "../api/client";

/** A driver's collection report as the owner sees it (D-114): not a payment until confirmed. */
export interface CollectionReport {
  id: string; status: "PENDING" | "CONFIRMED" | "REJECTED"; kind: "FULL" | "PARTIAL" | "NONE"; amount: string | null; currency: string;
  task_id: string; invoice_id: string; official_invoice_number: string | null; customer_id: string; customer_name: string;
  reporter_name: string; created_at: string;
}

export const COLLECTION_REPORTS_KEY = "collection-reports";

export function fetchPendingCollections(tenantId: string): Promise<CollectionReport[]> {
  return apiRequest<{ reports: CollectionReport[] }>(`/api/v1/collection-reports?tenant_id=${tenantId}&status=PENDING`).then((body) => body.reports);
}
