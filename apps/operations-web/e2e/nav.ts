import type { Page } from "@playwright/test";

/**
 * The owner navigation groups sections by job: the rail ("Workspace navigation") shows groups, and a
 * group with several sections shows them as "Section tabs" above the page. Specs name the section
 * they want; this opens its group, then its tab when the group has more than one section.
 */
const SECTIONS: Record<string, { group: string | RegExp; tab?: string | RegExp }> = {
  Work: { group: "Today" },
  Customers: { group: "Customers" },
  Deliveries: { group: "Deliveries" },
  Orders: { group: /^Sales/, tab: /^Orders/ },
  Invoices: { group: /^Sales/, tab: "Invoices" },
  Products: { group: "Catalog", tab: "Products" },
  Categories: { group: "Catalog", tab: "Categories" },
  Pricing: { group: "Catalog", tab: "Pricing" },
  Storefront: { group: "Settings", tab: "Storefront" },
  Procurement: { group: "Buying", tab: "Procurement" },
  "Suppliers & costs": { group: "Buying", tab: "Suppliers & costs" },
  Analytics: { group: "Insights", tab: "Analytics" },
  Assistant: { group: "Insights", tab: "Assistant" },
  Branding: { group: "Settings", tab: "Branding" },
  Offline: { group: "Settings", tab: "Offline" },
  Backup: { group: "Settings", tab: "Backup" },
};

export async function openSection(page: Page, section: keyof typeof SECTIONS): Promise<void> {
  const target = SECTIONS[section];
  const rail = page.getByRole("navigation", { name: "Workspace navigation" });
  await rail.getByRole("link", typeof target.group === "string" ? { name: target.group, exact: true } : { name: target.group }).click();
  if (target.tab === undefined) return;
  const tabs = page.getByRole("navigation", { name: "Section tabs" });
  await tabs.getByRole("link", typeof target.tab === "string" ? { name: target.tab, exact: true } : { name: target.tab }).click();
}
