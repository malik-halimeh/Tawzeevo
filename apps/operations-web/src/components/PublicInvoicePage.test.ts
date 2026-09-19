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
  expect(document.querySelector('img[src="x"]')).toBeNull();
  expect(document.getElementById("logo")).not.toBeVisible(); // no branding: logo and QR stay hidden
  expect(document.getElementById("qr")).not.toBeVisible();
  expect(fetch).toHaveBeenCalledOnce();
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

test("public invoice renders branding, defaults to the business language and asks for the QR only when enabled", async () => {
  document.body.innerHTML = html.split("<body>")[1]!.split("<script>")[0]!;
  const history = {replaceState:vi.fn()};
  const fetch = vi.fn((url: string) => url === "invoice/qr"
    ? Promise.resolve(new Response(new Blob([new Uint8Array([137,80,78,71])], {type:"image/png"})))
    : Promise.resolve(Response.json({
      business_name:"Cedar Business", customer_name:null, number:"2026-000002", revision:1, status:"CONFIRMED", currency:"USD",
      subtotal:"10.0000", discount:"0.0000", markup:"0.0000", net_sales:"10.0000", items:[],
      branding:{business_name:"Cedar Business", logo_path:"/api/v1/public/cedar/branding/logo?v=3", business_tel:"+9613111222", business_whatsapp:null, business_location:"Beirut",
        invoice_header:"Cedar Van · Beirut", invoice_footer:"Thank you for your trust", invoice_terms:"Payment within 7 days", thank_you_text:"See you next week",
        invoice_qr_enabled:true, default_language:"ar", date_format:"YYYY-MM-DD"},
    })));
  URL.createObjectURL = vi.fn(() => "blob:qr");
  runPage(
    {hash:`#${token}`,pathname:"/api/v1/public/invoice"}, history, fetch,
  );
  expect(await screen.findByText("Cedar Van · Beirut")).toBeVisible();
  expect(document.documentElement.dir).toBe("rtl"); // business default language applied on first render
  expect(document.getElementById("logo")).toHaveAttribute("src", "/api/v1/public/cedar/branding/logo?v=3");
  expect(screen.getByText("Payment within 7 days")).toBeVisible();
  expect(screen.getByText("See you next week")).toBeVisible();
  expect(screen.getByText("+9613111222 · Beirut")).toBeVisible();
  await waitFor(() => expect(document.getElementById("qr")).toHaveAttribute("src", "blob:qr"));
  expect(fetch).toHaveBeenCalledWith("invoice/qr", expect.objectContaining({headers:{"X-Invoice-Capability":token}}));
  fireEvent.click(screen.getByRole("button",{name:"English"}));
  expect(fetch).toHaveBeenCalledTimes(2); // language switches never re-request the QR
});
