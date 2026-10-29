import { expect, test } from "vitest";

import { PHONE_PRIMARY_GROUPS, WORKSPACE_GROUPS, WORKSPACE_SECTIONS, groupOf, ownerSectionHref, sectionFromSearch, sectionHref, workspaceSearch } from "./workspaceSections";

test("every existing section belongs to one unchanged group; Sales opens Invoices", () => {
  expect(WORKSPACE_GROUPS.map((group) => group.id)).toEqual(["today", "sales", "customers", "deliveries", "catalog", "buying", "insights", "settings"]);
  expect(PHONE_PRIMARY_GROUPS).toEqual(["today", "sales", "customers", "catalog"]);
  expect(groupOf("invoices").sections).toEqual(["invoices", "orders"]);
  for (const { id } of WORKSPACE_SECTIONS) {
    expect(WORKSPACE_GROUPS.filter((group) => (group.sections as readonly string[]).includes(id))).toHaveLength(1);
    expect(sectionFromSearch(new URLSearchParams({ section: id }))).toBe(id);
  }
});

test("owner navigation reserves list while old invoice addresses and driver Work links keep their meaning", () => {
  expect(ownerSectionHref("invoices", "business")).toBe("/workspace?tenant=business&section=invoices&view=list");
  expect(ownerSectionHref("work", "business")).toBe("/workspace?tenant=business&section=work");
  expect(sectionHref("work", "business")).toBe("/workspace?tenant=business");
  expect(workspaceSearch("work", "business")).toBe("?tenant=business"); // chooseBusiness contract
  expect(sectionHref("invoices", "business")).toBe("/workspace?tenant=business&section=invoices");
  for (const view of ["payments", "balances", "invoice"]) {
    expect(sectionHref("invoices", "business", { invoice: "i1", customer: "c1", view, currency: "LBP" })).toBe(`/workspace?tenant=business&section=invoices&invoice=i1&view=${view}&customer=c1&currency=LBP`);
  }
});
