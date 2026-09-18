# Phase 5 demo and presentation guide

This guide demonstrates only completed Phase 5 behavior: one public storefront per business,
personalized customer links, guest checkout with a safe provisional page, the owner's order
review, delivery date and cancellation decisions. Use synthetic data only.

## Prepare the environment

1. Follow the root `README.md` local setup. Never demonstrate against production data.
2. Apply migrations and confirm revision `20260919_0021` is the current Alembic head.
3. Start the API, the operations client and the storefront (see `docs/phase-5/test-report.md`
   § Reproduction for the three commands and the `API_BASE_URL` the storefront needs).
4. Sign in as the active owner of an approved synthetic business with one category, two
   published products, one supplier cost per product (needed to confirm), and one customer with
   a grade whose price differs from the public price.
5. Have two browser windows ready: one signed in as the owner, one private window for the
   customer.

## Recommended presentation route

### 1. The public shop

1. In the owner window open **Storefront settings** and show the slug; explain that renaming
   keeps the old address working through an audited redirect (D-047).
2. In the private window open `/<slug>`: the published products with public prices, search,
   categories, the featured strip. Open a product page; explain that views feed the
   recommendations pseudonymously (30-minute window, D-062) and that nothing is tracked across
   shops.

### 2. A personalized link

1. Owner window, **Customers** → the graded customer → **Create personalized link**. Copy the
   link; say it is shown once and stored only as a hash.
2. Private window: open the link. The banner names the customer; the same product now shows the
   customer's price. Say: the link proves possession, not identity — it changes prices, never
   money (D-072).
3. Owner window: **Replace link**. Reload the private window: the old context is gone and the
   public price is back. Revocation without replacement behaves the same.

### 3. Guest checkout

1. Private window: add a product, open the cart, fill name, phone and address, place the order.
   Show the provisional page: a summary, "Received", no invoice number, no grade, no history.
2. Say: the browser keeps one idempotency key per cart, so a retried submission after a network
   failure cannot create a second order (covered by `test_checkout.py`).
3. Show the address bar: the reference is not in it.

### 4. The owner decides

1. Owner window, **Orders** tab: the `1 new` badge and the order. Open it: contact snapshot,
   lines, and — if the guest used the personalized link — the *suggested* customer chip. Say:
   nothing is linked automatically; the owner links.
2. Link the suggested customer (or create one from the snapshot with a grade): the lines are
   re-priced as a new revision. Confirm: the official invoice number comes from the Phase 3
   engine.
3. Set tomorrow's delivery date; say the reminder is a job record due at 09:00 Beirut time.
4. Private window: reload the order page — "Confirmed by the shop" and the planned delivery date.

### 5. Cancellation is a request

1. Private window: type a reason and ask the shop to cancel. The page says the shop will decide.
2. Owner window: open the order, read the reason, approve. Explain the reversal is booked by the
   Phase 3 cancellation, and the reminder is cancelled with it. Reject instead to show the
   order stays as it is.
3. Private window: reload — "Cancelled."

### 6. Arabic on a phone

Add `?lang=ar` and narrow the window (or use the device toolbar): right-to-left layout, Arabic
copy, no horizontal scrolling, the same checkout.

## Security expectations (say them out loud)

- Public catalog is cacheable; every page that knows who you are is `no-store`, `noindex`,
  `no-referrer`.
- Capabilities and order references travel in a private header or a URL fragment, are stored as
  SHA-256 only, and are redacted from logs.
- A wrong or dead capability gets the same 404 as a missing one; the limit of 60 requests per
  minute per address on private paths is operational policy, not the security boundary (D-076).
- A personalized link is not an account. Accounts and OTP verification are later Phase 9 work
  (D-073/D-074) and will attach to the same customer record.

## Limitations to state plainly

- Reminders are recorded, not yet sent; the channel is a Phase 9 provider decision.
- The provisional page is available for 72 hours through its reference; the owner's invoice link
  (D-042) is the durable customer view after confirmation.
- Rate limiting is per API process.
