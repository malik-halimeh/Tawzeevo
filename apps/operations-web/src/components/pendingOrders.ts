import { apiRequest } from "../api/client";

/**
 * Orders awaiting the owner (status RECEIVED), polled for the Orders badge, the tab title and the
 * new-order notice. Read-only: it reuses the owner's order list filtered by status, keeps no
 * read/unread state, and a count drops as soon as the owner confirms or declines.
 */
export interface PendingOrder { id: string; contact_name: string; created_at: string }

/** How often the workspace asks while it is open (browsers may slow this down in a hidden tab). */
export const PENDING_POLL_MS = 20_000;

export const PENDING_ORDERS_KEY = "pending-orders";

export function fetchPendingOrders(tenantId: string): Promise<PendingOrder[]> {
  return apiRequest<{ orders: PendingOrder[] }>(`/api/v1/tenants/${tenantId}/orders?tenant_id=${tenantId}&status=RECEIVED`)
    .then((body) => body.orders);
}

/** Orders that were not awaiting review at the previous answer. The first answer is only a baseline. */
export function newArrivals(baseline: ReadonlySet<string> | null, current: readonly PendingOrder[]): PendingOrder[] {
  if (baseline === null) return [];
  return current.filter((order) => !baseline.has(order.id));
}

/** "(3) Tawzeevo Operations" while orders await review; the plain title otherwise. */
export function titleWithCount(base: string, count: number): string {
  return count > 0 ? `(${count}) ${base}` : base;
}
