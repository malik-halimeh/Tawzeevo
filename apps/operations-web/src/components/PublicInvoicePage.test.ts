import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import html from "../../../api/tawzeevo_api/templates/public_invoice.html?raw";
const script = html.split("<script>")[1]!.split("</script>")[0]!;
const token = `${"a".repeat(32)}.${"B".repeat(43)}`;
// Execute the committed HTML script verbatim; only test-owned browser doubles are injected.
// eslint-disable-next-line @typescript-eslint/no-implied-eval
const runPage = new Function("location", "history", "fetch", script) as (
  location: { hash: string; pathname: string },
  history: { replaceState: ReturnType<typeof vi.fn> },
  fetch: ReturnType<typeof vi.fn>,
) => void;

afterEach(() => {
  document.body.replaceChildren();
  document.documentElement.dir = "ltr";
  document.documentElement.lang = "en";
});

test("public invoice uses a secret header, safe text rendering, and Arabic RTL", async () => {
  document.body.innerHTML = html.split("<body>")[1]!.split("<script>")[0]!;
  const history = {replaceState:vi.fn()};
  const fetch = vi.fn(() => Promise.resolve(Response.json({
    business_name:"Cedar Business", customer_name:"<img src=x onerror=alert(1)>",
    number:"2026-000001", revision:2, status:"CONFIRMED", currency:"USD",
    subtotal:"10.0000", discount:"1.0000", markup:"0.0000", net_sales:"9.0000",
    items:[{name:"Water",quantity:"2.0000",unit:"PIECE",unit_price:"5.0000",total:"10.0000"}],
  })));
  runPage(
    {hash:`#${token}`,pathname:"/api/v1/public/invoice"}, history, fetch,
  );
  expect(await screen.findByText("Cedar Business")).toBeVisible();
  expect(history.replaceState).toHaveBeenCalledWith(null,"","/api/v1/public/invoice");
  expect(fetch).toHaveBeenCalledWith("invoice/data", {
    headers:{"X-Invoice-Capability":token}, credentials:"omit", cache:"no-store", referrerPolicy:"no-referrer",
  });
  expect(document.querySelector("img")).toBeNull();
  expect(screen.getByText(/<img src=x/)).toBeVisible();
  fireEvent.click(screen.getByRole("button",{name:"العربية"}));
  expect(document.documentElement.dir).toBe("rtl");
  expect(screen.getByRole("columnheader",{name:"الصنف"})).toBeVisible();
  expect(screen.getByText("قيمة الفاتورة")).toBeVisible();
});

test("public invoice invalid and unavailable links show no financial content", async () => {
  document.body.innerHTML = html.split("<body>")[1]!.split("<script>")[0]!;
  const history = {replaceState:vi.fn()};
  const fetch = vi.fn(() => Promise.resolve(Response.json({}, {status:404})));
  runPage(
    {hash:"#internal-invoice-id",pathname:"/api/v1/public/invoice"}, history, fetch,
  );
  expect(fetch).not.toHaveBeenCalled();
  expect(screen.getByRole("status")).toHaveTextContent("invalid");
  runPage(
    {hash:`#${token}`,pathname:"/api/v1/public/invoice"}, history, fetch,
  );
  await waitFor(() => expect(fetch).toHaveBeenCalledOnce());
  expect(document.getElementById("invoice")).not.toBeVisible();
});
