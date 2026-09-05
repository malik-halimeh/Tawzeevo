import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import i18n from "../i18n";
import { InvoiceEditor } from "./InvoiceEditor";

const tenantId = "11111111-1111-1111-1111-111111111111";
const customerId = "22222222-2222-2222-2222-222222222222";
const productId = "33333333-3333-3333-3333-333333333333";

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function requestUrl(input: RequestInfo | URL): string {
  if (typeof input === "string") return input;
  if (input instanceof URL) return input.href;
  return input.url;
}

beforeEach(async () => {
  await i18n.changeLanguage("en");
  vi.stubGlobal("crypto", { randomUUID: vi.fn(() => "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa") });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

test("owner confirms an ambiguous suggestion, saves a draft, and confirms its official number", async () => {
  const requests: Array<{ url: string; method: string; body?: string | undefined }> = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = requestUrl(input);
      const method = init?.method ?? "GET";
      requests.push({ url, method, body: typeof init?.body === "string" ? init.body : undefined });
      if (url.includes("/customer-ledger/settings")) {
        return json({ tenant_id: tenantId, customer_overdue_threshold_days: null });
      }
      if (url.includes("/customer-ledger/debts")) {
        return json({ debts: [] });
      }
      if (url.includes(`/customer-ledger/customers/${customerId}/balances`)) {
        return json({ customer_id: customerId, customer_name: "Maya Market", balances: [] });
      }
      if (url.includes(`/payments/customers/${customerId}/obligations`)) {
        return json({ customer_id: customerId, currency: "USD", obligations: [] });
      }
      if (url.includes("/history")) {
        return json({ revisions: [] });
      }
      if (url.includes("/customers/search")) {
        return json({
          customers: [
            {
              id: customerId,
              tenant_id: tenantId,
              name: "Maya Market",
              phone: "+96170123456",
              address: "Hamra",
              latitude: null,
              longitude: null,
              grade: "A",
              created_at: "2026-08-27T08:00:00Z",
              updated_at: "2026-08-27T08:00:00Z",
            },
          ],
        });
      }
      if (url.includes("/item-parser")) {
        return json({
          threshold: "0.7000",
          items: [
            {
              source_text: "2 Cedar watr",
              normalized_query: "cedar watr",
              quantity: "2.0000",
              resolution: "AMBIGUOUS",
              selected: null,
              suggestions: [
                {
                  product_id: productId,
                  name: "Cedar Water",
                  barcode: "5280000000012",
                  package_level: "PIECE",
                  currency: "USD",
                  price_basis: "PIECE",
                  unit_price: "12.5000",
                  image_url: null,
                  match_type: "FUZZY",
                  score: "0.9200",
                },
              ],
            },
          ],
        });
      }
      if (url.includes(`/products/${productId}/cost-options`)) {
        return json({ options: [] });
      }
      if (url.includes("/confirm") && method === "POST") {
        return json({
          id: "44444444-4444-4444-4444-444444444444",
          tenant_id: tenantId,
          status: "CONFIRMED",
          official_invoice_number: "2026-000001",
          confirmed_at: "2026-08-27T08:10:00Z",
          customer_id: customerId,
          customer_snapshot: { id: customerId, name: "Maya Market", grade: "A" },
          current_revision_id: "55555555-5555-4555-8555-555555555555",
          server_revision_number: 1,
          pricing_version: "pricing-v1",
          currency: "USD",
          prior_balance: "5.0000",
          subtotal: "22.5000",
          discount_total: "0.0000",
          markup_total: "0.0000",
          net_sales: "22.5000",
          total_due: "27.5000",
          items: [],
          created_at: "2026-08-27T08:00:00Z",
          updated_at: "2026-08-27T08:10:00Z",
        });
      }
      if (url.endsWith(`/api/v1/invoices?tenant_id=${tenantId}`) && method === "POST") {
        return json(
          {
            id: "44444444-4444-4444-4444-444444444444",
            tenant_id: tenantId,
            status: "DRAFT",
            official_invoice_number: null,
            confirmed_at: null,
            customer_id: customerId,
            customer_snapshot: { id: customerId, name: "Maya Market", grade: "A" },
            current_revision_id: "55555555-5555-4555-8555-555555555555",
            server_revision_number: 1,
            pricing_version: "pricing-v1",
            currency: "USD",
            prior_balance: "5.0000",
            subtotal: "22.5000",
            discount_total: "0.0000",
            markup_total: "0.0000",
            net_sales: "22.5000",
            total_due: "27.5000",
            items: [
              {
                id: "66666666-6666-4666-8666-666666666666",
                line_number: 1,
                product_id: productId,
                product_name: "Cedar Water",
                barcode: "5280000000012",
                media_snapshot: { images: [] },
                quantity: "2.0000",
                price_basis: "PIECE",
                pieces_per_box: 12,
                normal_unit_price: "12.5000",
                effective_unit_price: "11.2500",
                customer_grade: "A",
                price_source: "GRADE_DISCOUNT",
                grade_discount_percent: "10.0000",
                line_discount: "0.0000",
                line_markup: "0.0000",
                line_total: "22.5000",
                supplier_id: null,
                product_cost_entry_id: null,
                unit_cost: null,
                cost_currency: null,
                cost_basis: null,
                cost_pieces_per_box: null,
                cost_source_type: null,
                is_cost_override: false,
                cost_override_reason: null,
              },
            ],
            created_at: "2026-08-27T08:00:00Z",
            updated_at: "2026-08-27T08:00:00Z",
          },
          201,
        );
      }
      throw new Error(`Unexpected request: ${method} ${url}`);
    }),
  );

  render(<InvoiceEditor tenantId={tenantId} />);
  fireEvent.change(screen.getByLabelText("Phone"), { target: { value: "+96170" } });
  fireEvent.click(screen.getAllByRole("button", { name: "Search" })[0]!);
  await screen.findByRole("button", { name: /Maya Market/ });
  fireEvent.click(screen.getByRole("button", { name: /Maya Market/ }));

  fireEvent.change(screen.getByRole("textbox", { name: "Text list" }), {
    target: { value: "2 Cedar watr" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Parse list" }));
  const confirmation = await screen.findByRole("region", { name: "Confirm suggested matches" });
  expect(screen.getByText("No invoice lines yet")).toBeInTheDocument();
  fireEvent.click(within(confirmation).getByRole("button", { name: /Cedar Water/ }));
  expect(await screen.findByText("Cedar Water")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Calculate and save draft" }));
  expect(await screen.findByText("27.5000 USD")).toBeInTheDocument();
  const save = requests.find(
    (request) => request.url.endsWith(`/api/v1/invoices?tenant_id=${tenantId}`),
  );
  expect(save).toBeDefined();
  const payload = JSON.parse(save?.body ?? "{}") as {
    customer_id: string;
    items: Array<{ accepted_fuzzy_match: { selected_product_id: string } }>;
  };
  expect(payload.customer_id).toBe(customerId);
  expect(payload.items[0]?.accepted_fuzzy_match.selected_product_id).toBe(productId);
  fireEvent.click(await screen.findByRole("button", { name: "Confirm and assign invoice number" }));
  expect(await screen.findByText("2026-000001")).toBeInTheDocument();
  expect(requests.some((request) => request.url.includes("/confirm"))).toBe(true);
  expect(screen.getByRole("button", { name: "Cancel invoice" })).toBeInTheDocument();
}, 10_000);

test("owner records a selected receipt allocation and can reverse the immutable receipt", async () => {
  const requests: Array<{ url: string; method: string; body?: string | undefined }> = [];
  const obligationId = "77777777-7777-4777-8777-777777777777";
  const paymentId = "88888888-8888-4888-8888-888888888888";
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = requestUrl(input);
      const method = init?.method ?? "GET";
      requests.push({ url, method, body: typeof init?.body === "string" ? init.body : undefined });
      if (url.includes("/customer-ledger/settings")) {
        return json({ tenant_id: tenantId, customer_overdue_threshold_days: null });
      }
      if (url.includes("/customer-ledger/debts")) return json({ debts: [] });
      if (url.includes("/customers/search")) {
        return json({
          customers: [{
            id: customerId,
            tenant_id: tenantId,
            name: "Maya Market",
            phone: "+96170123456",
            address: "Hamra",
            latitude: null,
            longitude: null,
            grade: "A",
            created_at: "2026-08-27T08:00:00Z",
            updated_at: "2026-08-27T08:00:00Z",
          }],
        });
      }
      if (url.includes(`/customer-ledger/customers/${customerId}/balances`)) {
        return json({ customer_id: customerId, customer_name: "Maya Market", balances: [] });
      }
      if (url.includes(`/payments/customers/${customerId}/obligations`)) {
        return json({
          customer_id: customerId,
          currency: "USD",
          obligations: [{
            target_ledger_entry_id: obligationId,
            source_type: "INVOICE",
            source_id: "44444444-4444-4444-4444-444444444444",
            label: "Invoice 2026-000001",
            effective_at: "2026-08-01T08:00:00Z",
            original_amount: "25.0000",
            allocated_amount: "0.0000",
            outstanding_amount: "25.0000",
          }],
        });
      }
      if (url.includes("/customer-receipts") && method === "POST") {
        return json({
          id: paymentId,
          tenant_id: tenantId,
          customer_id: customerId,
          direction: "CUSTOMER_RECEIPT",
          amount: "10.0000",
          currency: "USD",
          method: "CASH",
          reference: null,
          paid_at: "2026-08-27T08:00:00Z",
          recorded_at: "2026-08-27T08:00:00Z",
          reverses_payment_id: null,
          notes: null,
          allocated_amount: "7.0000",
          unallocated_amount: "3.0000",
          customer_balance: "15.0000",
          available_credit: "0.0000",
          allocations: [],
        }, 201);
      }
      if (url.includes(`/payments/${paymentId}/reverse`) && method === "POST") {
        return json({
          id: "99999999-9999-4999-8999-999999999999",
          tenant_id: tenantId,
          customer_id: customerId,
          direction: "CUSTOMER_RECEIPT_REVERSAL",
          amount: "10.0000",
          currency: "USD",
          method: "CASH",
          reference: null,
          paid_at: "2026-08-27T08:05:00Z",
          recorded_at: "2026-08-27T08:05:00Z",
          reverses_payment_id: paymentId,
          notes: "Duplicate receipt",
          allocated_amount: "0.0000",
          unallocated_amount: "0.0000",
          customer_balance: "25.0000",
          available_credit: "0.0000",
          allocations: [],
        }, 201);
      }
      throw new Error(`Unexpected request: ${method} ${url}`);
    }),
  );

  render(<InvoiceEditor tenantId={tenantId} />);
  fireEvent.change(screen.getByLabelText("Phone"), { target: { value: "+96170" } });
  fireEvent.click(screen.getAllByRole("button", { name: "Search" })[0]!);
  fireEvent.click(await screen.findByRole("button", { name: /Maya Market/ }));
  fireEvent.click(await screen.findByRole("button", { name: "Choose amounts" }));
  fireEvent.change(screen.getByLabelText("Allocate to Invoice 2026-000001"), {
    target: { value: "7.0000" },
  });
  fireEvent.change(screen.getByLabelText("Amount received"), {
    target: { value: "10.0000" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Record receipt" }));
  expect(await screen.findByText("Customer receipt")).toBeInTheDocument();
  expect(screen.getByText("3.0000 USD")).toBeInTheDocument();
  const receipt = requests.find((request) => request.url.includes("/customer-receipts"));
  const payload = JSON.parse(receipt?.body ?? "{}") as {
    allocations: Array<{ target_ledger_entry_id: string; amount: string }>;
  };
  expect(payload.allocations).toEqual([
    { target_ledger_entry_id: obligationId, amount: "7.0000" },
  ]);
  fireEvent.change(screen.getByLabelText("Required reversal reason"), {
    target: { value: "Duplicate receipt" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Reverse this receipt" }));
  expect(await screen.findByText("Receipt reversal")).toBeInTheDocument();
  expect(requests.some((request) => request.url.includes(`/payments/${paymentId}/reverse`))).toBe(true);
}, 10_000);

test("debt desk marks an overdue customer with text and a non-color alert mark", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      const url = requestUrl(input);
      if (url.includes("/customer-ledger/settings")) {
        return json({ tenant_id: tenantId, customer_overdue_threshold_days: 30 });
      }
      if (url.includes("/customer-ledger/debts")) {
        return json({
          debts: [
            {
              customer_id: customerId,
              customer_name: "Maya Market",
              customer_phone: "+96170123456",
              currency: "USD",
              balance: "75.0000",
              oldest_unpaid_at: "2026-07-18T08:00:00Z",
              overdue_age_days: 40,
              overdue_threshold_days: 30,
              is_overdue: true,
              alert_key: `customer-overdue:${customerId}:USD`,
            },
          ],
        });
      }
      throw new Error(`Unexpected request: ${url}`);
    }),
  );
  const { container } = render(<InvoiceEditor tenantId={tenantId} />);
  expect(await screen.findByText("Overdue · 40 days old")).toBeInTheDocument();
  expect(screen.getByText("75.0000 USD")).toBeInTheDocument();
  expect(container.querySelector(".debt-row.is-overdue .debt-alert-mark")).toHaveTextContent("!");
});
