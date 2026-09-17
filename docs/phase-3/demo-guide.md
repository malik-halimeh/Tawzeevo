# Phase 3 demo and presentation guide

This guide demonstrates only completed Phase 3 financial behavior: invoice editor, confirmation and
official numbering, immutable revisions, customer ledger and opening balances, receipts and
allocations, refunds, cancellation, overdue indication, supplier setup and supplier payments, and
private invoice sharing. Use synthetic data only.

## Prepare the environment

1. Follow the root `README.md` local setup. Never demonstrate against production data.
2. Apply migrations and confirm revision `20260909_0012` is the current Alembic head.
3. Start the API and the operations client. Confirm `/health`, `/docs` and the client load.
4. Sign in as the active owner of an approved synthetic tenant. Create at least one category, one
   product with a barcode and a piece/box price, and two customers (one with grade A).
5. Open the **Suppliers & costs** tab, create one supplier, and save a cost entry for the product.
   Explain that without this step confirmation is blocked on purpose (every confirmed line must
   snapshot its cost).

## Recommended presentation route

### 1. Build and confirm an invoice

1. Open **Invoices**, look up a customer by phone, add the product by barcode and a manual line.
2. Show the calculator field (`2 + 1`), a line discount, and the server-calculated totals.
3. Point out that the tally is returned by the backend; the client only previews.
4. Save the draft, then confirm. Show the official number `YYYY-000001` and the revision history.

### 2. Edit after confirmation

1. Change a quantity and save an auditable revision. Show the new revision and the exact ledger
   delta in the history panel.
2. Try to discount the invoice to zero: the server refuses (`ZERO_VALUE_INVOICE_NOT_CONFIRMABLE`).
   State that a zero economic effect uses cancellation, never a zero-value confirmed invoice.

### 3. Opening balance, debt and overdue

1. In the debt desk, set the overdue threshold (for example 30 days).
2. Record an opening balance dated 40 days ago for the second customer and show the red overdue
   indicator with its age in days. Mention that the day boundary follows the Lebanon calendar.
3. Show that the opening balance is a ledger event and not counted as sales.

### 4. Receipts, allocation, refund, cancellation

1. Record a receipt smaller than the invoice; show FIFO allocation and the remaining outstanding.
2. Record a second receipt larger than the remaining obligation; show unallocated credit.
3. Issue a refund from the available credit; then try to refund more than the credit (refused).
4. Cancel a confirmed invoice; show that payments stay and their allocations become credit.
5. Point at the tally label **Due at this revision (snapshot)** versus the live customer balance.

### 5. Suppliers and supplier payments

1. In **Suppliers & costs**, append a second cost entry and show that the first one is preserved.
2. In the **Supplier payable and payments** desk on the same tab: record an opening payable of 20,
   then try an ordinary payment of 25 (refused: it cannot exceed the payable), then record the
   same 25 as a prepayment (accepted and shown as −5 supplier credit). Reverse it with a reason
   and show the balance return to 20.

### 6. Private invoice sharing

1. On a **confirmed** invoice, create a private link and open the customer view: only the current
   invoice is shown, no balances, costs or history.
2. Create a second link: the first stops working (one active link per invoice).
3. Cancel the invoice: the link stops working immediately.
4. Show the WhatsApp share button uses the customer's normalized phone. Show a draft invoice has
   no sharing controls.

## Phase boundary to state aloud

- No offline mode, storefront, procurement lists, delivery routing, analytics or forecasting yet.
- Supplier payments are aggregate per currency; there is no per-purchase allocation.
- Overdue detection is a read-time indicator; scheduled notifications are a later policy.
- The public link is for confirmed invoices only; the Phase 5 provisional checkout view is separate.

## Pre-presentation checklist

- [ ] Alembic head is `20260909_0012` and `alembic check` reports no drift.
- [ ] `pytest apps/api/tests -q` passes on a disposable database (161 tests at freeze).
- [ ] `npm run check` passes (49 Vitest tests at freeze).
- [ ] A supplier and a cost entry exist for every product you will invoice.
- [ ] One customer has an old opening balance so the overdue indicator is visible.
- [ ] Browser language switch to Arabic works on the invoice editor and the public invoice page.
