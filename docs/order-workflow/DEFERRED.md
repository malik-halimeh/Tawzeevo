# Order workflow fix — deferred items

Found during the work. None of these blocks M1–M4, so none was fixed here.

| # | Item | Evidence | Why deferred |
|---|---|---|---|
| F-01 | Storefront `error.tsx` and `not-found` pages link back to the shop without the tab's `?c=` context. | `app/[slug]/error.tsx`, `app/not-found.tsx` | Rare pages. Following the link lands on the bare shop address, which is the most recently opened link as before, so no identity is merged into an order without the server resolving it. |
| F-02 | The owner's in-panel notification counter is never marked read (`POST /notifications/{id}/read` has no caller). | `components/OrdersPanel.tsx`, `routes/storefront.py` | Existing behaviour. Read/unread state is out of scope (no new notification state). |
| F-03 | **RESOLVED 2026-09-25** (branch `fix/public-order-decline`). Declining a public order the owner had not linked yet used to commit the invoice cancellation and then fail building a customer-bound editor response, leaving the invoice CANCELLED behind a RECEIVED order. Approving a cancellation request on such an order had the same flaw. Fixed by applying the cancellation without its own commit (`invoice_finance.apply_invoice_cancellation`), so each owner decision commits once with the order state. `cancel_invoice` keeps its behaviour for the invoice endpoint and sync. | `services/invoice_finance.py`, `services/orders.py`, `tests/test_order_decline.py` | — |
| F-04 | The owner order list returns at most 100 rows, so the badge would show 100 when more orders await review. | `services/orders.py` `list_orders(limit=100)` | Unlikely for a cash-van business; raising the limit or adding a count is an API change outside the scope. |
| F-05 | There is no invoice list page in the operations client. The list surface named in M4 does not exist. | `routes/invoices.py` has no list endpoint; the Invoices section only edits the current invoice | Building a list is new product surface, which the rules exclude. Invoices are reachable from orders, deliveries and payment lines. |
| F-06 | An invoice opened by link cannot be revised from that screen (read-only by design), because the editor's lines are not loaded from a saved invoice. | `InvoiceEditor.tsx` keeps lines only in session state | Loading saved lines into the editor touches the revision path. The session-based revise flow is unchanged. |
| F-07 | The public invoice page has no print button or print stylesheet. The browser's own print works on it. | `templates/public_invoice.html` | A print layout is a new design surface. |
