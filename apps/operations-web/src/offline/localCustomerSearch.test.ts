import "fake-indexeddb/auto";

import { afterEach, beforeEach, expect, test } from "vitest";

import { deleteLocalDatabase, openLocalDatabase } from "./db";
import { searchLocalCustomers } from "./sync";

const tenant = "11111111-1111-4111-8111-111111111111";
const membership = "22222222-2222-4222-8222-222222222222";

function customer(id: string, name: string, phone: string) {
  return { id: id.padEnd(36, "0"), tenant_id: tenant, name, phone, phone_raw: null, address: null, latitude: null, longitude: null, grade: "A", version: 1, created_at: "2026-09-18T00:00:00Z", updated_at: "2026-09-18T00:00:00Z" };
}

beforeEach(async () => {
  await openLocalDatabase(tenant, membership).customers.bulkPut([
    customer("c1", "أحمد للتجارة", "+96170123451"),
    customer("c2", "مكتبة فاطمة", "+96170123452"),
    customer("c3", "Maya Market", "+96171999993"),
    customer("c4", "مـصطفى", "+96103123454"),
  ]);
});

afterEach(async () => {
  await deleteLocalDatabase(tenant, membership);
});

test("a typed name matches with the server's Arabic folding", async () => {
  const names = async (query: string) => (await searchLocalCustomers(tenant, membership, query)).map((row) => row.name);
  expect(await names("احمد")).toEqual(["أحمد للتجارة"]);
  expect(await names("فاطمه")).toEqual(["مكتبة فاطمة"]);
  expect(await names("مصطفي")).toEqual(["مـصطفى"]);
  expect(await names("أَحْمَد")).toEqual(["أحمد للتجارة"]);
  expect(await names("maya")).toEqual(["Maya Market"]);
  expect(await names("nobody")).toEqual([]);
});

test("a phone keeps the exact-then-contains phone search, also with Arabic-Indic digits", async () => {
  expect((await searchLocalCustomers(tenant, membership, "70 123 452")).map((row) => row.name)).toEqual(["مكتبة فاطمة"]);
  expect((await searchLocalCustomers(tenant, membership, "٧٠ ١٢٣ ٤٥٢")).map((row) => row.name)).toEqual(["مكتبة فاطمة"]);
  expect(await searchLocalCustomers(tenant, membership, "0000")).toEqual([]);
});
