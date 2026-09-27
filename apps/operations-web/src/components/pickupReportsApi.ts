import { apiRequest } from "../api/client";

/** A pickup report as the owner sees it (D-106). */
export interface PickupReport {
  id: string; status: "PENDING" | "CONFIRMED" | "REJECTED"; list_id: string; list_title: string; supplier_id: string; supplier_name: string;
  reporter_name: string; currency: string; total: string; notes: string | null; reason: string | null; created_at: string;
  lines: { procurement_item_id: string; product_id: string; product_name: string; quantity: string; unit_cost: string }[];
}

export const PICKUP_REPORTS_KEY = "pickup-reports";

export function fetchPendingPickups(tenantId: string): Promise<PickupReport[]> {
  return apiRequest<{ reports: PickupReport[] }>(`/api/v1/procurement/pickup-reports?tenant_id=${tenantId}&status=PENDING`).then((body) => body.reports);
}
