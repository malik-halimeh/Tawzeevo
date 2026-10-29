import { expect, type Page } from "@playwright/test";

/**
 * The owner navigation groups sections by job: the rail ("Workspace navigation") shows groups, and a
 * group with several sections shows them as "Section tabs" above the page. Specs name the section
 * they want; this opens its group, then its tab or Settings hub destination. "Invoices" opens
 * a new editor through the labelled button; "Invoices list" stays on the front page (D-120).
 */
const SECTIONS: Record<string, {
  group: string | RegExp;
  tab?: string | RegExp;
  settings?: { page: string; link: string | RegExp };
}> = {
  Work: { group: "Today" },
  Customers: { group: "Customers" },
  Deliveries: { group: "Deliveries" },
  Orders: { group: /^Sales/, tab: /^Orders/ },
  Invoices: { group: /^Sales/, tab: "Invoices" },
  "Invoices list": { group: /^Sales/, tab: "Invoices" },
  Products: { group: "Catalog", tab: "Products" },
  Categories: { group: "Catalog", tab: "Categories" },
  Pricing: { group: "Catalog", tab: "Pricing" },
  Storefront: { group: "Settings", settings: { page: "Business", link: /^Storefront & campaigns(?:,|$)/ } },
  Procurement: { group: "Buying", tab: "Procurement" },
  "Suppliers & costs": { group: "Buying", tab: "Suppliers & costs" },
  Analytics: { group: "Insights", tab: "Analytics" },
  Assistant: { group: "Insights", tab: "Assistant" },
  Branding: { group: "Settings", settings: { page: "Business", link: /^Branding(?:,|$)/ } },
  Offline: { group: "Settings", settings: { page: "General", link: /^Offline sync(?:,|$)/ } },
  Backup: { group: "Settings", settings: { page: "General", link: /^Backup(?:,|$)/ } },
};

export async function openSection(page: Page, section: keyof typeof SECTIONS): Promise<void> {
  const target = SECTIONS[section];
  const rail = page.getByRole("navigation", { name: "Workspace navigation" });
  await rail.getByRole("link", typeof target.group === "string" ? { name: target.group, exact: true } : { name: target.group }).click();
  if (target.settings) {
    const { page: settingsPage, link } = target.settings;
    await page.getByRole("navigation", { name: "Settings pages" }).getByRole("link", { name: settingsPage, exact: true }).click();
    await page.getByRole("list", { name: settingsPage, exact: true }).getByRole("link", typeof link === "string" ? { name: link, exact: true } : { name: link }).click();
    return;
  }
  if (target.tab === undefined) return;
  const tabs = page.getByRole("navigation", { name: "Section tabs" });
  await tabs.getByRole("link", typeof target.tab === "string" ? { name: target.tab, exact: true } : { name: target.tab }).click();
  if (section === "Invoices") {
    // The labelled header action precedes the empty-state action and floating + in the DOM.
    await page.getByRole("button", { name: "New invoice", exact: true }).filter({ visible: true }).first().click();
    await expect(page.getByRole("heading", { name: "Invoices", level: 3 })).toBeVisible();
  } else if (section === "Invoices list") {
    await expect(page.getByRole("heading", { name: "Invoices", level: 1, exact: true })).toBeVisible();
  }
}
