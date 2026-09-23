import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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

/** The Invoices section shows one view at a time (Invoice first); a member opens a view before using it. */
function openView(name: "Invoice" | "Payments" | "Balances") {
  fireEvent.click(within(screen.getByRole("group", { name: "Invoice views" })).getByRole("button", { name }));
}

/** Item entry shows one method at a time (Barcode first); the others stay mounted with what was typed. */
function openEntryMethod(name: "Barcode" | "Catalog search" | "Text list" | "Manual item") {
  fireEvent.click(within(screen.getByRole("group", { name: "Item entry method" })).getByRole("button", { name }));
}

beforeEach(async () => {
  sessionStorage.clear();
  await i18n.changeLanguage("en");
  vi.stubGlobal("crypto", { randomUUID: vi.fn(() => "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa") });
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
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

  render(<InvoiceEditor tenantId={tenantId} membershipId="66666666-6666-4666-8666-666666666666" />);
  fireEvent.change(screen.getByLabelText("Phone"), { target: { value: "+96170" } });
  fireEvent.click(screen.getAllByRole("button", { name: "Search" })[0]!);
  await screen.findByRole("button", { name: /Maya Market/ });
  fireEvent.click(screen.getByRole("button", { name: /Maya Market/ }));

  openEntryMethod("Text list");
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

  render(<InvoiceEditor tenantId={tenantId} membershipId="66666666-6666-4666-8666-666666666666" />);
  fireEvent.change(screen.getByLabelText("Phone"), { target: { value: "+96170" } });
  fireEvent.click(screen.getAllByRole("button", { name: "Search" })[0]!);
  fireEvent.click(await screen.findByRole("button", { name: /Maya Market/ }));
  openView("Payments");
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

test.each([false, true])("lost financial responses retain one command while the next completed intent gets a new command (remount: %s)", async (remount) => {
  const commandIds = [
    "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
  ];
  vi.stubGlobal("crypto", {
    randomUUID: vi.fn(() => commandIds.shift() ?? "dddddddd-dddd-4ddd-8ddd-dddddddddddd"),
  });
  const receiptRequests: Array<Record<string, unknown>> = [];
  const refundRequests: Array<Record<string, unknown>> = [];
  const persisted = new Map<string, Record<string, unknown>>();
  const persistedRefunds = new Map<string, Record<string, unknown>>();
  let refreshCount = 0;
  let paymentEffects = 0;
  let ledgerEffects = 0;
  let allocationEffects = 0;
  let auditEffects = 0;

  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = requestUrl(input);
      const method = init?.method ?? "GET";
      if (url.endsWith("/api/v1/auth/refresh")) {
        refreshCount += 1;
        return Promise.resolve(
          json({ access_token: "refreshed-access-token", token_type: "bearer" }),
        );
      }
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
            target_ledger_entry_id: "77777777-7777-4777-8777-777777777777",
            source_type: "INVOICE",
            source_id: "44444444-4444-4444-8444-444444444444",
            label: "Invoice 2026-000001",
            effective_at: "2026-08-27T08:00:00Z",
            original_amount: "50.0000",
            allocated_amount: "0.0000",
            outstanding_amount: "50.0000",
          }],
        });
      }
      if (url.includes("/customer-receipts") && method === "POST") {
        const body = JSON.parse(typeof init?.body === "string" ? init.body : "{}") as Record<
          string,
          unknown
        >;
        receiptRequests.push(body);
        if (receiptRequests.length === 1) return json({}, 401);
        const commandId = String(body.idempotency_key);
        let payment = persisted.get(commandId);
        if (!payment) {
          paymentEffects += 1;
          ledgerEffects += 1;
          allocationEffects += 1;
          auditEffects += 1;
          payment = {
            id: `${paymentEffects}8888888-8888-4888-8888-888888888888`.slice(-36),
            tenant_id: tenantId,
            customer_id: customerId,
            direction: "CUSTOMER_RECEIPT",
            amount: "10.0000",
            currency: "USD",
            method: "CASH",
            reference: null,
            paid_at: "2026-08-27T08:00:00Z",
            recorded_at: "2026-08-27T08:00:01Z",
            reverses_payment_id: null,
            notes: null,
            allocated_amount: "10.0000",
            unallocated_amount: "0.0000",
            customer_balance: paymentEffects === 1 ? "40.0000" : "30.0000",
            available_credit: "0.0000",
            allocations: [],
          };
          persisted.set(commandId, payment);
        }
        if (receiptRequests.length === 2 || receiptRequests.length === 3) {
          throw new TypeError("simulated response loss after commit");
        }
        return json(payment, 201);
      }
      if (url.includes("/customer-refunds") && method === "POST") {
        const body = JSON.parse(typeof init?.body === "string" ? init.body : "{}") as Record<
          string,
          unknown
        >;
        refundRequests.push(body);
        const commandId = String(body.idempotency_key);
        let refund = persistedRefunds.get(commandId);
        if (!refund) {
          refund = {
            id: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
            tenant_id: tenantId,
            customer_id: customerId,
            direction: "CUSTOMER_REFUND",
            amount: "5.0000",
            currency: "USD",
            method: "CASH",
            reference: null,
            paid_at: "2026-08-27T08:10:00Z",
            recorded_at: "2026-08-27T08:10:01Z",
            reverses_payment_id: null,
            notes: null,
            allocated_amount: "0.0000",
            unallocated_amount: "0.0000",
            customer_balance: "-5.0000",
            available_credit: "5.0000",
            allocations: [],
          };
          persistedRefunds.set(commandId, refund);
        }
        if (refundRequests.length === 1) {
          throw new TypeError("simulated refund response loss after commit");
        }
        return json(refund, 201);
      }
      throw new Error(`Unexpected request: ${method} ${url}`);
    }),
  );

  const mountCustomer = async () => {
    render(<InvoiceEditor tenantId={tenantId} membershipId="66666666-6666-4666-8666-666666666666" />);
    fireEvent.change(screen.getByLabelText("Phone"), { target: { value: "+96170" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Search" })[0]!);
    fireEvent.click(await screen.findByRole("button", { name: /Maya Market/ }));
    openView("Payments");
  };
  const remountCustomer = async () => {
    if (!remount) return;
    cleanup();
    await mountCustomer();
  };
  await mountCustomer();
  let amount = screen.getByLabelText("Amount received");
  fireEvent.change(amount, { target: { value: "10.0000" } });

  fireEvent.click(screen.getByRole("button", { name: "Record receipt" }));
  await screen.findByText("simulated response loss after commit");
  expect(amount).toHaveValue(10);
  await remountCustomer();
  amount = screen.getByLabelText("Amount received");
  fireEvent.change(amount, { target: { value: "10.0000" } });
  fireEvent.click(screen.getByRole("button", { name: "Record receipt" }));
  await waitFor(() => expect(receiptRequests).toHaveLength(3));
  await remountCustomer();
  amount = screen.getByLabelText("Amount received");
  fireEvent.change(amount, { target: { value: "10.0000" } });
  fireEvent.click(screen.getByRole("button", { name: "Record receipt" }));
  await screen.findByText("Customer receipt");

  expect(refreshCount).toBe(1);
  expect(receiptRequests.slice(0, 4).map((request) => request.idempotency_key)).toEqual([
    "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  ]);
  expect(receiptRequests.slice(1, 4)).toEqual([
    receiptRequests[0],
    receiptRequests[0],
    receiptRequests[0],
  ]);
  expect(paymentEffects).toBe(1);
  expect(ledgerEffects).toBe(1);
  expect(allocationEffects).toBe(1);
  expect(auditEffects).toBe(1);

  await remountCustomer();
  amount = screen.getByLabelText("Amount received");
  fireEvent.change(amount, { target: { value: "10.0000" } });
  fireEvent.click(screen.getByRole("button", { name: "Record receipt" }));
  await waitFor(() => expect(receiptRequests).toHaveLength(5));
  expect(receiptRequests[4]?.idempotency_key).toBe("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb");
  expect(paymentEffects).toBe(2);
  expect(ledgerEffects).toBe(2);
  expect(allocationEffects).toBe(2);
  expect(auditEffects).toBe(2);

  const refundAmount = screen.getByLabelText("Refund amount");
  fireEvent.change(refundAmount, { target: { value: "5.0000" } });
  fireEvent.click(screen.getByRole("button", { name: "Issue credit refund" }));
  await screen.findByText("simulated refund response loss after commit");
  expect(refundAmount).toHaveValue(5);
  await remountCustomer();
  fireEvent.change(screen.getByLabelText("Refund amount"), { target: { value: "5.0000" } });
  fireEvent.click(screen.getByRole("button", { name: "Issue credit refund" }));
  await waitFor(() => expect(refundRequests).toHaveLength(2));
  expect(refundRequests.map((request) => request.idempotency_key)).toEqual([
    "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
    "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
  ]);
  expect(persistedRefunds).toHaveLength(1);
}, 20_000);

test.each([
  ["Amount received", "Record receipt", "customer-receipts", "CUSTOMER_RECEIPT"],
  ["Refund amount", "Issue credit refund", "customer-refunds", "CUSTOMER_REFUND"],
])("%s retains identity when a successful response arrives after unmount", async (label, button, path, direction) => {
  let sequence = 0;
  vi.stubGlobal("crypto", { randomUUID: () => `${++sequence}aaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa` });
  const requests: Record<string, unknown>[] = [];
  let finishFirst!: (response: Response) => void;
  const payment = { id: "88888888-8888-4888-8888-888888888888", direction, amount: "10.0000", currency: "USD", allocations: [], customer_balance: "0", available_credit: "0" };
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = requestUrl(input);
    if (url.includes(`/${path}`) && init?.method === "POST") {
      requests.push(JSON.parse(typeof init.body === "string" ? init.body : "{}") as Record<string, unknown>);
      if (requests.length === 1) return new Promise<Response>((resolve) => { finishFirst = resolve; });
      return json(payment, 201);
    }
    if (url.includes("/customer-ledger/settings")) return json({ customer_overdue_threshold_days: null });
    if (url.includes("/customer-ledger/debts")) return json({ debts: [] });
    if (url.includes("/customers/search")) return json({ customers: [{ id: customerId, name: "Maya Market", phone: "+96170123456" }] });
    if (url.includes("/balances")) return json({ balances: [] });
    if (url.includes("/obligations")) return json({ obligations: [] });
    throw new Error(`Unexpected request: ${url}`);
  }));
  const submit = async () => {
    render(<InvoiceEditor tenantId={tenantId} membershipId="66666666-6666-4666-8666-666666666666" />);
    fireEvent.change(screen.getByLabelText("Phone"), { target: { value: "+96170" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Search" })[0]!);
    fireEvent.click(await screen.findByRole("button", { name: /Maya Market/ }));
    openView("Payments");
    fireEvent.change(screen.getByLabelText(label), { target: { value: "10" } });
    fireEvent.click(screen.getByRole("button", { name: button }));
  };
  await submit();
  await waitFor(() => expect(requests).toHaveLength(1));
  cleanup();
  await act(async () => {
    finishFirst(json(payment, 201));
    await Promise.resolve();
  });
  await submit();
  await waitFor(() => expect(requests).toHaveLength(2));
  expect(requests[1]).toEqual(requests[0]);
});

test.each(["getItem", "setItem"] as const)("receipt and refund send nothing when session storage %s fails", async (method) => {
  const posts: string[] = [];
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = requestUrl(input);
    if (init?.method === "POST") { posts.push(url); return json({}); }
    if (url.includes("/customer-ledger/settings")) return json({ customer_overdue_threshold_days: null });
    if (url.includes("/customer-ledger/debts")) return json({ debts: [] });
    if (url.includes("/customers/search")) return json({ customers: [{ id: customerId, name: "Maya Market", phone: "+96170123456" }] });
    if (url.includes("/balances")) return json({ balances: [] });
    if (url.includes("/obligations")) return json({ obligations: [] });
    throw new Error(`Unexpected request: ${url}`);
  }));
  render(<InvoiceEditor tenantId={tenantId} membershipId="66666666-6666-4666-8666-666666666666" />);
  fireEvent.change(screen.getByLabelText("Phone"), { target: { value: "+96170" } });
  fireEvent.click(screen.getAllByRole("button", { name: "Search" })[0]!);
  fireEvent.click(await screen.findByRole("button", { name: /Maya Market/ }));
  openView("Payments");
  vi.spyOn(Storage.prototype, method).mockImplementation(() => { throw new Error("storage unavailable"); });
  for (const [label, button] of [["Amount received", "Record receipt"], ["Refund amount", "Issue credit refund"]]) {
    fireEvent.change(screen.getByLabelText(label!), { target: { value: "10" } });
    fireEvent.click(screen.getByRole("button", { name: button! }));
    await screen.findByText(/pending payment could not be safely recovered or saved/);
    expect(posts).toEqual([]);
  }
});

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
  const { container } = render(<InvoiceEditor tenantId={tenantId} membershipId="66666666-6666-4666-8666-666666666666" />);
  expect(await screen.findByText("Overdue · 40 days old")).toBeInTheDocument();
  openView("Balances");
  expect(screen.getByText("Overdue · 40 days old")).toBeVisible();
  expect(screen.getByText("75.0000 USD")).toBeInTheDocument();
  expect(container.querySelector(".debt-row.is-overdue .debt-alert-mark")).toHaveTextContent("!");
});


test("the immutable due snapshot is labelled distinctly from the live balance (FA-011 / D-037)", async () => {
  await i18n.changeLanguage("en");
  expect(i18n.t("invoiceEditor.totalDue")).toBe("Due at this revision (snapshot)");
  expect(i18n.t("invoiceEditor.totalDueNote")).toContain("never this snapshot");
  expect(i18n.t("invoiceEditor.customerBalance")).toBe("Customer balance");
  await i18n.changeLanguage("ar");
  expect(i18n.t("invoiceEditor.totalDue")).toBe("المستحق عند هذه المراجعة (لقطة)");
  expect(i18n.t("invoiceEditor.totalDueNote")).toContain("لا هذه اللقطة");
  await i18n.changeLanguage("en");
});


test("a failed draft save retries with the same create command and a new invoice gets a new one (FA-009 / D-045)", async () => {
  await i18n.changeLanguage("en");
  const commands: string[] = [];
  let attempts = 0;
  let sequence = 0;
  vi.stubGlobal("crypto", { randomUUID: () => `${String(++sequence).padStart(8, "0")}-aaaa-4aaa-8aaa-aaaaaaaaaaaa` });
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = input instanceof Request ? input.url : input.toString();
    const method = init?.method ?? "GET";
    if (url.includes("/customers/search")) return Promise.resolve(Response.json({ customers: [{ id: customerId, tenant_id: tenantId, name: "Maya Market", phone: "+96170123456", phone_raw: "+96170123456", address: null, latitude: null, longitude: null, grade: "A", created_at: "", updated_at: "" }] }));
    if (url.includes("/suppliers")) return Promise.resolve(Response.json({ suppliers: [] }));
    if (url.includes("/customer-ledger/") || url.includes("/obligations") || url.includes("/history")) return Promise.resolve(Response.json({ debts: [], balances: [], obligations: [], revisions: [], settings: { customer_overdue_threshold_days: null }, customer_overdue_threshold_days: null }));
    if (url.endsWith(`/api/v1/invoices?tenant_id=${tenantId}`) && method === "POST") {
      const payload = JSON.parse(typeof init?.body === "string" ? init.body : "{}") as { client_command_id: string };
      commands.push(payload.client_command_id);
      attempts += 1;
      if (attempts === 1) return Promise.reject(new TypeError("Failed to fetch"));
      return Promise.resolve(Response.json({ id: "invoice-1", tenant_id: tenantId, status: "DRAFT", official_invoice_number: null, confirmed_at: null, customer_id: customerId, customer_snapshot: {}, current_revision_id: "rev-1", server_revision_number: 1, pricing_version: "pricing-v1", currency: "USD", prior_balance: "0.0000", subtotal: "3.0000", discount_total: "0.0000", markup_total: "0.0000", net_sales: "3.0000", total_due: "3.0000", items: [] }, { status: 201 }));
    }
    return Promise.resolve(Response.json({ detail: { code: "NOT_FOUND", message: url } }, { status: 404 }));
  }));
  render(<InvoiceEditor tenantId={tenantId} membershipId="membership" />);
  fireEvent.change(screen.getByRole("textbox", { name: "Phone" }), { target: { value: "+96170123456" } });
  fireEvent.click(screen.getAllByRole("button", { name: "Search" })[0]!);
  fireEvent.click(await screen.findByRole("button", { name: /Maya Market/ }));
  openEntryMethod("Manual item");
  fireEvent.change(screen.getByPlaceholderText("Item name"), { target: { value: "Ice" } });
  fireEvent.change(screen.getByRole("spinbutton", { name: "Unit price" }), { target: { value: "3" } });
  fireEvent.click(screen.getByRole("button", { name: "Add manual line" }));
  fireEvent.click(screen.getByRole("button", { name: "Calculate and save draft" }));
  await waitFor(() => expect(attempts).toBe(1));
  fireEvent.click(await screen.findByRole("button", { name: "Calculate and save draft" }));
  await waitFor(() => expect(attempts).toBe(2));
  expect(commands[0]).toBe(commands[1]);
  expect(await screen.findByText("Draft invoice created from the server calculation.")).toBeInTheDocument();
});

// ---------- Views, confirmed document and revision detail (presentation over the same handlers) ----------

const customerRow = { id: customerId, tenant_id: tenantId, name: "Maya Market", phone: "+96170123456", address: "Hamra", latitude: null, longitude: null, grade: "A", created_at: "2026-08-27T08:00:00Z", updated_at: "2026-08-27T08:00:00Z" };
const invoiceId = "44444444-4444-4444-4444-444444444444";

function crateLine(id: string, quantity: string, lineTotal: string) {
  return { id, line_number: 1, product_id: null, product_name: "Water crate", barcode: null, media_snapshot: { images: [] }, quantity, price_basis: "PIECE", pieces_per_box: null, normal_unit_price: "5.0000", effective_unit_price: "5.0000", customer_grade: "A", price_source: "NORMAL", grade_discount_percent: null, line_discount: "0.0000", line_markup: "0.0000", line_total: lineTotal, supplier_id: null, product_cost_entry_id: null, unit_cost: null, cost_currency: null, cost_basis: null, cost_pieces_per_box: null, cost_source_type: null, is_cost_override: false, cost_override_reason: null };
}

/** Server answers for one invoice: R1 is 2 crates (10.0000 + 3.0000 carried = 13.0000), R2 is 4 crates. */
function invoiceAnswer(overrides: Record<string, unknown> = {}) {
  return { id: invoiceId, tenant_id: tenantId, status: "DRAFT", official_invoice_number: null, confirmed_at: null, customer_id: customerId, customer_snapshot: { id: customerId, name: "Maya Market", phone: "+96170123456", grade: "A" }, current_revision_id: "rev-1", server_revision_number: 1, pricing_version: "pricing-v1", currency: "USD", prior_balance: "3.0000", subtotal: "10.0000", discount_total: "0.0000", markup_total: "0.0000", net_sales: "10.0000", total_due: "13.0000", items: [crateLine("item-1", "2.0000", "10.0000")], created_at: "2026-09-23T08:00:00Z", updated_at: "2026-09-23T08:00:00Z", ...overrides };
}
const confirmedR1 = () => invoiceAnswer({ status: "CONFIRMED", official_invoice_number: "2026-000007", confirmed_at: "2026-09-23T08:10:00Z" });
const confirmedR2 = () => invoiceAnswer({ status: "CONFIRMED", official_invoice_number: "2026-000007", confirmed_at: "2026-09-23T08:10:00Z", current_revision_id: "rev-2", server_revision_number: 2, subtotal: "20.0000", net_sales: "20.0000", total_due: "23.0000", items: [crateLine("item-2", "4.0000", "20.0000")] });

/** A fetch double for the Invoices section; `routes` answers the invoice-specific calls first. */
function sectionFetch(routes: (url: string, method: string, body: string | undefined) => Response | undefined) {
  return vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = requestUrl(input);
    const method = init?.method ?? "GET";
    const answer = routes(url, method, typeof init?.body === "string" ? init.body : undefined);
    if (answer) return answer;
    if (url.includes("/customer-ledger/settings")) return json({ tenant_id: tenantId, customer_overdue_threshold_days: null });
    if (url.includes("/customer-ledger/debts")) return json({ debts: [] });
    if (url.includes("/customers/search")) return json({ customers: [customerRow] });
    if (url.includes("/balances")) return json({ customer_id: customerId, customer_name: "Maya Market", balances: [] });
    if (url.includes("/obligations")) return json({ customer_id: customerId, currency: "USD", obligations: [] });
    if (url.includes("/suppliers")) return json({ suppliers: [] });
    throw new Error(`Unexpected request: ${method} ${url}`);
  });
}

async function chooseCustomer() {
  fireEvent.change(screen.getByLabelText("Phone"), { target: { value: "+96170" } });
  fireEvent.click(screen.getAllByRole("button", { name: "Search" })[0]!);
  fireEvent.click(await screen.findByRole("button", { name: /Maya Market/ }));
}

function addManualLine(name: string, price: string) {
  openEntryMethod("Manual item");
  fireEvent.change(screen.getByRole("textbox", { name: "Item name" }), { target: { value: name } });
  fireEvent.change(screen.getByRole("spinbutton", { name: "Unit price" }), { target: { value: price } });
  fireEvent.click(screen.getByRole("button", { name: "Add manual line" }));
}

async function confirmOneInvoice(confirmAnswer: Record<string, unknown>) {
  await chooseCustomer();
  addManualLine("Water crate", "5");
  fireEvent.click(screen.getByRole("button", { name: "Calculate and save draft" }));
  fireEvent.click(await screen.findByRole("button", { name: "Confirm and assign invoice number" }));
  return screen.findByRole("article", { name: String(confirmAnswer.official_invoice_number) });
}

const renderEditor = () => render(<InvoiceEditor tenantId={tenantId} membershipId="66666666-6666-4666-8666-666666666666" />);

test("switching views keeps what was typed: a receipt amount and reference, manual line fields, lines and the entry method", async () => {
  vi.stubGlobal("fetch", sectionFetch(() => undefined));
  renderEditor();
  await chooseCustomer();
  addManualLine("Ice", "3");
  expect(await screen.findByText("Ice")).toBeInTheDocument();
  fireEvent.change(screen.getByRole("textbox", { name: "Item name" }), { target: { value: "Coal" } }); // typed, not yet added

  openView("Payments");
  fireEvent.change(screen.getByLabelText("Amount received"), { target: { value: "12.5" } });
  fireEvent.change(screen.getByLabelText("Reference"), { target: { value: "R-17" } });
  openView("Balances");
  expect(screen.getByLabelText("Amount received")).not.toBeVisible();

  openView("Invoice");
  expect(screen.getByRole("textbox", { name: "Item name" })).toHaveValue("Coal");
  expect(screen.getByText("Ice")).toBeVisible();
  openView("Payments");
  expect(screen.getByLabelText("Amount received")).toHaveValue(12.5);
  expect(screen.getByLabelText("Reference")).toHaveValue("R-17");
  expect(within(screen.getByRole("group", { name: "Invoice views" })).getByRole("button", { name: "Payments" })).toHaveAttribute("aria-pressed", "true");
  expect(within(screen.getByRole("group", { name: "Invoice views" })).getByRole("button", { name: "Invoice" })).toHaveAttribute("aria-pressed", "false");
});

test("a confirmed invoice reads as a document from the server's answer, and Create revision opens the existing revision editor", async () => {
  const requests: Array<{ url: string; method: string; body?: string | undefined }> = [];
  vi.stubGlobal("fetch", sectionFetch((url, method, body) => {
    requests.push({ url, method, body });
    if (url.endsWith(`/api/v1/invoices?tenant_id=${tenantId}`) && method === "POST") return json(invoiceAnswer(), 201);
    if (url.includes("/confirm") && method === "POST") return json(confirmedR1());
    if (url.includes(`/invoices/${invoiceId}?`) && method === "PUT") return json(confirmedR2());
    if (url.includes("/history")) return json({ revisions: [] });
    return undefined;
  }));
  renderEditor();
  const document = await confirmOneInvoice(confirmedR1());

  expect(within(document).getByText("Confirmed · every change is recorded as a revision")).toBeVisible();
  expect(within(document).getByText("Maya Market")).toBeVisible();
  expect(within(document).getByText("USD")).toBeVisible();
  expect(within(document).getByText("R1")).toBeVisible();
  const lines = within(document).getByRole("table", { name: "Invoice lines" });
  expect(within(lines).getByText("Water crate")).toBeVisible();
  expect(within(lines).getByText("2.0000")).toBeVisible();
  expect(within(document).getByText("3.0000 USD")).toBeVisible(); // previous balance, as the server returned it
  expect(within(document).getByText("13.0000 USD")).toBeVisible(); // due at this revision
  expect(within(document).getByText(/never this snapshot/)).toBeVisible();
  expect(document.textContent).not.toMatch(/final|locked|closed/i);
  expect(screen.queryByRole("button", { name: "Save an auditable revision" })).not.toBeInTheDocument();

  fireEvent.click(within(document).getByRole("button", { name: "Create revision" }));
  expect(screen.getByText("New revision of", { exact: false })).toBeVisible();
  expect(screen.getByRole("region", { name: "Invoice lines" })).toBeVisible();
  fireEvent.change(screen.getByLabelText("Quantity / calculator"), { target: { value: "4" } });
  fireEvent.click(screen.getByRole("button", { name: "Save an auditable revision" }));

  const revised = await screen.findByRole("article", { name: "2026-000007" });
  expect(within(revised).getByText("23.0000 USD")).toBeVisible();
  expect(within(revised).getByText("R2")).toBeVisible();
  const put = requests.find((request) => request.method === "PUT");
  expect(JSON.parse(put?.body ?? "{}")).toMatchObject({ expected_predecessor_revision_id: "rev-1", items: [{ quantity_expression: "4" }] });
  await waitFor(() => expect(screen.getByRole("heading", { name: "2026-000007" })).toHaveFocus());
});

test("an expanded past revision shows that revision's own items and totals, never the current ones", async () => {
  const past = { ...confirmedR1(), predecessor_revision_id: null, reason: null, revision_created_at: "2026-09-23T08:10:00Z", is_current: false, ledger_delta: "13.0000" };
  const current = { ...confirmedR2(), predecessor_revision_id: "rev-1", reason: "Customer asked for two more crates", revision_created_at: "2026-09-23T09:00:00Z", is_current: true, ledger_delta: "10.0000" };
  vi.stubGlobal("fetch", sectionFetch((url, method) => {
    if (url.endsWith(`/api/v1/invoices?tenant_id=${tenantId}`) && method === "POST") return json(invoiceAnswer(), 201);
    if (url.includes("/confirm") && method === "POST") return json(confirmedR2());
    if (url.includes("/history")) return json({ revisions: [past, current] });
    return undefined;
  }));
  renderEditor();
  await confirmOneInvoice(confirmedR2());
  const history = await screen.findByRole("region", { name: "Immutable revision history" });
  const pastEntry = within(history).getByText("R1").closest("details")!;
  const currentEntry = within(history).getByText("R2").closest("details")!;

  expect(within(pastEntry).getByText("13.0000 USD")).not.toBeVisible(); // closed until the owner opens it
  fireEvent.click(pastEntry.querySelector("summary")!);
  expect(pastEntry).toHaveAttribute("open");
  expect(within(pastEntry).getByText("13.0000 USD")).toBeVisible(); // R1's own due, not the current 23.0000
  expect(within(pastEntry).getByText("2.0000")).toBeVisible(); // R1's own quantity
  expect(within(pastEntry).queryByText("23.0000 USD")).not.toBeInTheDocument();
  expect(within(pastEntry).queryByText("4.0000")).not.toBeInTheDocument();
  expect(within(currentEntry).getByText("23.0000 USD")).toBeInTheDocument();
  expect(within(currentEntry).getByText("Customer asked for two more crates")).toBeInTheDocument();
});

test("after confirmation, cancellation and sharing stay reachable, and a just-issued link survives view switches", async () => {
  const cancelBodies: string[] = [];
  const issued = { id: "link-1", expires_at: "2026-12-22T08:00:00Z", revoked_at: null, created_at: "2026-09-23T08:20:00Z", public_path: "/api/v1/public/invoice#secret-abc", customer_phone: "+96170123456", summary: "Invoice 2026-000007" };
  let links: unknown[] = [];
  vi.stubGlobal("fetch", sectionFetch((url, method, body) => {
    if (url.endsWith(`/api/v1/invoices?tenant_id=${tenantId}`) && method === "POST") return json(invoiceAnswer(), 201);
    if (url.includes("/confirm") && method === "POST") return json(confirmedR1());
    if (url.includes("/capabilities") && method === "POST") { links = [issued]; return json(issued, 201); }
    if (url.includes("/capabilities")) return json(links);
    if (url.includes("/cancel") && method === "POST") { cancelBodies.push(body ?? ""); return json({ ...confirmedR1(), status: "CANCELLED" }); }
    if (url.includes("/history")) return json({ revisions: [] });
    return undefined;
  }));
  renderEditor();
  await confirmOneInvoice(confirmedR1());
  expect(screen.getByRole("button", { name: "Cancel invoice" })).toBeVisible();
  expect(screen.getByLabelText("Cancellation reason")).toBeVisible();

  const sharing = screen.getByRole("region", { name: "Share invoice" });
  fireEvent.click(within(sharing).getByRole("button", { name: "Manage invoice links" }));
  fireEvent.click(await within(sharing).findByRole("button", { name: "Create private link" }));
  const url = (await within(sharing).findByLabelText<HTMLInputElement>("Private invoice URL")).value;
  expect(url).toContain("#secret-abc");

  openView("Payments");
  openView("Balances");
  openView("Invoice");
  expect(screen.getByLabelText("Private invoice URL")).toHaveValue(url); // the shown-once link is still here
  fireEvent.click(screen.getByRole("button", { name: "Create revision" }));
  fireEvent.click(screen.getByRole("button", { name: "Back to the invoice" }));
  expect(screen.getByLabelText("Private invoice URL")).toHaveValue(url);

  fireEvent.change(screen.getByLabelText("Cancellation reason"), { target: { value: "Customer withdrew" } });
  fireEvent.click(screen.getByRole("button", { name: "Cancel invoice" }));
  expect(await screen.findByText("Cancelled · the invoice and its revisions stay on record")).toBeVisible();
  expect(JSON.parse(cancelBodies[0] ?? "{}")).toMatchObject({ reason: "Customer withdrew" });
  expect(screen.queryByRole("button", { name: "Create revision" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Cancel invoice" })).not.toBeInTheDocument();
});

test("Payments without a customer explains why and switches to the customer step", async () => {
  vi.stubGlobal("fetch", sectionFetch(() => undefined));
  renderEditor();
  openView("Payments");
  const guide = screen.getByRole("note");
  expect(guide).toHaveTextContent("Choose a customer before saving.");
  expect(screen.getByRole("button", { name: "Record receipt" })).toBeDisabled();
  fireEvent.click(within(guide).getByRole("button", { name: "Choose the customer" }));
  expect(within(screen.getByRole("group", { name: "Invoice views" })).getByRole("button", { name: "Invoice" })).toHaveAttribute("aria-pressed", "true");
  await waitFor(() => expect(screen.getByLabelText("Phone")).toHaveFocus());
});
