import type { TenantContext } from "../api/types";
import type { IconName } from "./Icon";

/**
 * The owner workspace sections (docs/design-references/DESIGN_DIRECTION.md, "Owner navigation:
 * Work, Customers, Invoices, More"). These are presentation groupings of existing owner
 * surfaces inside the single /workspace route — not routes, roles or permissions. Which
 * sections render for a membership is still decided by TenantWorkspace from the server's
 * tenant context (owners only); a driver never receives these entries.
 */
export const WORKSPACE_SECTIONS = [
  { id: "work", label: "nav.work", icon: "work" },
  { id: "customers", label: "tenantWorkspace.customers", icon: "people" },
  { id: "invoices", label: "invoiceEditor.tab", icon: "invoice" },
  { id: "orders", label: "orders.tab", icon: "bag" },
  { id: "deliveries", label: "delivery.tab", icon: "van" },
  { id: "categories", label: "tenantWorkspace.categories", icon: "layers" },
  { id: "products", label: "tenantWorkspace.products", icon: "box" },
  { id: "suppliers", label: "supplierSetup.tab", icon: "shop" },
  { id: "procurement", label: "procurement.tab", icon: "cart" },
  { id: "analytics", label: "analytics.tab", icon: "chart" },
  { id: "assistant", label: "copilot.tab", icon: "chat" },
  { id: "branding", label: "branding.tab", icon: "palette" },
  { id: "sync", label: "sync.tab", icon: "sync" },
  { id: "backup", label: "backup.tab", icon: "cloud" },
] as const satisfies readonly { id: string; label: string; icon: IconName }[];

export type WorkspaceSection = (typeof WORKSPACE_SECTIONS)[number]["id"];

/** The three sections that sit directly in the phone bottom navigation; the rest live under More. */
export const PHONE_PRIMARY_SECTIONS: readonly WorkspaceSection[] = ["work", "customers", "invoices"];

/**
 * The owner navigation groups the sections by job (report 2026-09-27, Part D): the rail and the phone
 * bar show groups, and a group with several sections shows them as tabs above the page. Groups are a
 * presentation layer only: every section id and address above keeps working unchanged, and the first
 * section of a group is where the group opens.
 */
export const WORKSPACE_GROUPS = [
  { id: "today", label: "nav.groups.today", icon: "work", sections: ["work"] },
  { id: "sales", label: "nav.groups.sales", icon: "invoice", sections: ["orders", "invoices"] },
  { id: "customers", label: "nav.groups.customers", icon: "people", sections: ["customers"] },
  { id: "deliveries", label: "nav.groups.deliveries", icon: "van", sections: ["deliveries"] },
  { id: "catalog", label: "nav.groups.catalog", icon: "box", sections: ["products", "categories"] },
  { id: "buying", label: "nav.groups.buying", icon: "cart", sections: ["procurement", "suppliers"] },
  { id: "insights", label: "nav.groups.insights", icon: "chart", sections: ["analytics", "assistant"] },
  { id: "settings", label: "nav.groups.settings", icon: "key", sections: ["branding", "sync", "backup"] },
] as const satisfies readonly { id: string; label: string; icon: IconName; sections: readonly WorkspaceSection[] }[];

export type WorkspaceGroup = (typeof WORKSPACE_GROUPS)[number];
export type WorkspaceGroupId = WorkspaceGroup["id"];

/** The groups that sit directly in the owner's phone bar; the others live under More. */
export const PHONE_PRIMARY_GROUPS: readonly WorkspaceGroupId[] = ["today", "sales", "customers"];

/** The group a section belongs to (every section belongs to exactly one). */
export function groupOf(section: WorkspaceSection): WorkspaceGroup {
  return WORKSPACE_GROUPS.find((group) => (group.sections as readonly WorkspaceSection[]).includes(section))!;
}

/** In-page anchors of the member work screen (MyWorkPanel): the driver's "My work / Sync" grouping. */
export const WORK_ANCHOR = "my-work";
export const SYNC_ANCHOR = "my-work-sync";

/**
 * The /workspace address carries both the selected business (`tenant`) and the open section
 * (`section`), so the shell's navigation, the workspace body and the browser history always
 * describe the same membership. Nothing here decides what a member may do: the server's
 * tenant-context list remains the only source of roles, and each panel still asks the API.
 */
const TENANT_PARAM = "tenant";
const SECTION_PARAM = "section";

export function isWorkspaceSection(value: string | null | undefined): value is WorkspaceSection {
  return WORKSPACE_SECTIONS.some((section) => section.id === value);
}

export function sectionFromSearch(search: URLSearchParams): WorkspaceSection {
  const requested = search.get(SECTION_PARAM);
  return isWorkspaceSection(requested) ? requested : "work";
}

export function tenantFromSearch(search: URLSearchParams): string | null {
  return search.get(TENANT_PARAM) || null;
}

/**
 * The membership the workspace shows: the business named in the address when the member belongs
 * to it, otherwise the first business the server listed. The shell and the body share this rule.
 */
export function selectedContext<T extends Pick<TenantContext, "tenant_id">>(contexts: readonly T[], tenantId: string | null): T | undefined {
  return contexts.find((context) => context.tenant_id === tenantId) ?? contexts[0];
}

/**
 * What a section may open with, so the owner continues from where they were instead of choosing
 * again: an order (Orders), an invoice and its view (Invoices), an invoice to deliver (Deliveries),
 * a customer (Customers, e.g. from a priority or an assistant answer).
 * These only select context; each panel still loads it from the API and ignores what it cannot find.
 */
export interface SectionContext { order?: string | null; invoice?: string | null; view?: string | null; customer?: string | null; currency?: string | null }
const CONTEXT_PARAMS = ["order", "invoice", "view", "customer", "currency"] as const;

export function contextFromSearch(search: URLSearchParams): SectionContext {
  return { order: search.get("order"), invoice: search.get("invoice"), view: search.get("view"), customer: search.get("customer"), currency: search.get("currency") };
}

/** Query string for a business and section: Work is the bare section and the first business needs no parameter. */
export function workspaceSearch(section: WorkspaceSection, tenantId: string | null, context: SectionContext = {}): string {
  const params = new URLSearchParams();
  if (tenantId) params.set(TENANT_PARAM, tenantId);
  if (section !== "work") params.set(SECTION_PARAM, section);
  for (const key of CONTEXT_PARAMS) {
    const value = context[key];
    if (value) params.set(key, value);
  }
  const query = params.toString();
  return query ? `?${query}` : "";
}

/** Sections are carried by a query parameter on the existing route; Work is the bare route. */
export function sectionHref(section: WorkspaceSection, tenantId: string | null = null, context: SectionContext = {}): string {
  return `/workspace${workspaceSearch(section, tenantId, context)}`;
}
