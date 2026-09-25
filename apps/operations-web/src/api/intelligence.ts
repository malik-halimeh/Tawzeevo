import { useQuery } from "@tanstack/react-query";

import { apiRequest } from "./client";

/**
 * Owner intelligence (D-089). Every figure below is computed by the API from the canonical
 * invoices, ledgers and receipts; the client only displays it. Amounts are decimal strings that
 * always travel with their currency, lists are grouped per currency and never summed together.
 * Scores and bands are workflow rankings, never probabilities; cash-flow has no forecast field.
 */
export type Scalar = string | number | boolean | null;
export interface Reason { code: string; value: Scalar; context: Record<string, Scalar> }
export type PriorityBand = "HIGH" | "MEDIUM" | "LOW";
export type InactivityStatus = "NORMAL" | "WATCH" | "AT_RISK" | "LAPSED" | "INSUFFICIENT_HISTORY";

export interface PriorityItem {
  customer_id: string;
  customer_name: string;
  customer_grade: string | null;
  currency: string;
  score: number;
  band: PriorityBand;
  components: Record<"collection_urgency" | "relationship_inactivity" | "activity_decline" | "friction_signals", number | null>;
  reasons: Reason[];
  suggested_action_code: string;
  inactivity_status: InactivityStatus;
  outstanding_balance: string;
  days_since_last_purchase: number | null;
}
export interface PrioritiesResponse { as_of: string; groups: { currency: string; items: PriorityItem[] }[] }

export interface InactivityItem {
  customer_id: string;
  customer_name: string;
  customer_grade: string | null;
  currency: string;
  status: InactivityStatus;
  recency_ratio: string | null;
  days_since_last_purchase: number | null;
  median_purchase_interval_days: string | null;
  purchase_interval_mad_days: string | null;
  invoice_count_lifetime: number;
  invoice_count_90d: number;
  sales_30d: string;
  sales_90d: string;
  outstanding_balance: string;
  last_purchase_at: string | null;
  reason_codes: string[];
}
export interface InactivityResponse { as_of: string; groups: { currency: string; items: InactivityItem[] }[] }

export interface AnomalyItem {
  type: string;
  severity: "HIGH" | "WATCH";
  detected_at: string;
  subject_type: "TENANT" | "CUSTOMER" | "INVOICE";
  subject_id: string | null;
  metric: string;
  observed_value: string;
  baseline: { method: string; median: string | null; mad: string | null; sample_size: number | null };
  reason_code: string;
  details: Record<string, Scalar>;
}
export interface AnomaliesResponse {
  as_of: string;
  window: { start: string; end: string; timezone: string; block_days: number; baseline_blocks: number };
  groups: { currency: string; items: AnomalyItem[]; insufficient_history: string[] }[];
}

export interface CurrencyCashFlow {
  currency: string;
  position: { customer_receivables: string; customer_credit: string; overdue_receivables: string; overdue_customer_count: number; supplier_payables: string; supplier_credit: string };
  ageing: { bucket: string; amount: string; customer_count: number }[];
  historical_flow: { customer_receipts: string; customer_refunds: string; supplier_payments: string; net_customer_collections: string; average_weekly_collections: string | null };
  planned_collections: { amount: string; task_count: number; from_date: string; through_date: string; source: string; projection_warning_code: string };
}
export type CashFlowPeriod = "30d" | "90d" | "1y" | "all";
export interface CashFlowResponse {
  as_of: string;
  period: { key: string; start: string | null; end: string; timezone: string };
  overdue_threshold_days: number | null;
  currencies: CurrencyCashFlow[];
}

export interface CopilotStatus { configured: boolean; provider: string | null; model: string | null }
/** What every written answer carries, from the assistant or a contextual explanation. */
export interface GroundedAnswer {
  answer: string;
  references: { ref: string; customer_id: string; customer_name: string }[];
  grounding: { tool: string; period: string | null; currency: string | null; ok: boolean }[];
  warnings: string[];
  unverified_numbers: string[];
}
export interface CopilotTurn { role: "user" | "assistant"; content: string }
export interface CopilotResponse extends GroundedAnswer {
  conversation_id: string;
  /** The answer as the provider wrote it (customer references, not names): the history to send back. */
  conversation_text: string;
}

/**
 * Contextual explanations (D-091): wording of facts the server assembles for one customer, one
 * unusual change or the cash position. An anomaly is named as the screen shows it (currency,
 * position, type, subject); the server re-checks it and answers 409 ANOMALY_CHANGED otherwise.
 */
export type ExplainContext =
  | { kind: "customer"; customer_id: string }
  | { kind: "anomaly"; currency: string; index: number; type: string; subject_id: string | null }
  | { kind: "cash"; period: CashFlowPeriod; currency?: string | null };
export interface ExplanationResponse extends GroundedAnswer { kind: ExplainContext["kind"]; as_of: string }

/** Counted anomaly metrics; every other anomaly metric is an amount in the group's currency. */
export const COUNT_METRICS: ReadonlySet<string> = new Set(["cancelled_invoices_7d", "receipt_reversals_7d"]);

// Intelligence is computed on request over the whole business, so one answer is shared by the
// screens that show it (Work, Customers, a customer's record) for a minute instead of recomputed.
const SHARED = { staleTime: 60_000, retry: 1 } as const;

export const intelligenceKeys = {
  all: (tenantId: string) => ["intelligence", tenantId] as const,
};

export function usePriorities(tenantId: string, enabled = true) {
  return useQuery({
    queryKey: [...intelligenceKeys.all(tenantId), "priorities"],
    queryFn: () => apiRequest<PrioritiesResponse>(`/api/v1/intelligence/priorities?tenant_id=${tenantId}&limit=200`),
    enabled,
    ...SHARED,
  });
}

export function useInactivity(tenantId: string, enabled = true) {
  return useQuery({
    queryKey: [...intelligenceKeys.all(tenantId), "inactivity"],
    queryFn: () => apiRequest<InactivityResponse>(`/api/v1/intelligence/inactivity?tenant_id=${tenantId}&limit=500`),
    enabled,
    ...SHARED,
  });
}

export function useAnomalies(tenantId: string) {
  return useQuery({
    queryKey: [...intelligenceKeys.all(tenantId), "anomalies"],
    queryFn: () => apiRequest<AnomaliesResponse>(`/api/v1/intelligence/anomalies?tenant_id=${tenantId}`),
    ...SHARED,
  });
}

export function useCashFlow(tenantId: string, period: CashFlowPeriod) {
  return useQuery({
    queryKey: [...intelligenceKeys.all(tenantId), "cash-flow", period],
    queryFn: () => apiRequest<CashFlowResponse>(`/api/v1/intelligence/cash-flow?tenant_id=${tenantId}&period=${period}`),
    ...SHARED,
  });
}

export function useCopilotStatus(tenantId: string) {
  return useQuery({
    queryKey: [...intelligenceKeys.all(tenantId), "copilot-status"],
    queryFn: () => apiRequest<CopilotStatus>(`/api/v1/intelligence/copilot/status?tenant_id=${tenantId}`),
    ...SHARED,
  });
}

export function askCopilot(tenantId: string, message: string, conversation: CopilotTurn[], conversationId: string | null): Promise<CopilotResponse> {
  return apiRequest<CopilotResponse>(`/api/v1/intelligence/copilot/query?tenant_id=${tenantId}`, {
    method: "POST",
    body: JSON.stringify({ message, conversation, ...(conversationId ? { conversation_id: conversationId } : {}) }),
  });
}

/**
 * One explanation per exact context (business, kind, record or period, language). It is fetched
 * only when the owner asks (`asked`), never refetched in the background and kept for the session,
 * so reopening the same record shows the same wording until the owner asks again; a different
 * context is a different key and starts unasked, so no summary is ever shown for another context.
 */
export function useExplanation(tenantId: string, context: ExplainContext, language: "en" | "ar", asked: boolean) {
  return useQuery({
    queryKey: [...intelligenceKeys.all(tenantId), "explain", language, context],
    queryFn: () => apiRequest<ExplanationResponse>(`/api/v1/intelligence/explain?tenant_id=${tenantId}`, {
      method: "POST",
      body: JSON.stringify({ ...context, language }),
    }),
    enabled: asked,
    retry: false,
    staleTime: Infinity,
    gcTime: 30 * 60_000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });
}
