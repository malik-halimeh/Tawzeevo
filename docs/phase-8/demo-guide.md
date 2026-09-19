# Phase 8 demo and presentation guide

This guide demonstrates only completed Phase 8 behavior: trusted business figures by currency and
period, historical gross profit with coverage, the event flow, one customer over time, business
branding on the desk, the storefront and the customer invoice page, and the safe public platform
statistics. Use synthetic data only.

## Prepare the environment

1. Follow the root `README.md` local setup. Never demonstrate against production data.
2. Apply migrations and confirm revision `20260919_0027` is the current Alembic head.
3. Sign in as the active owner of an approved synthetic business with a published product that
   has a supplier cost, one or two customers, a few confirmed invoices in one currency (and one
   in a second currency if you want to show separation), one receipt, one accepted edit and one
   cancelled invoice.
4. Have a small PNG logo at hand.

## Recommended presentation route

### 1. The figures (Analytics)

Open **Analytics**. Read the *Current state* block: invoiced sales, receipts, refunds, owed by
customers, owed to suppliers — one line per currency, never added together. Change the period
(30 days, 90 days, last year, all time) and say: periods follow the business calendar
(Asia/Beirut), not UTC midnight (D-068).

Point at *Historical gross profit*: selling price minus the supplier cost recorded at the moment
of sale, line by line; a later purchase never rewrites it; a line without a recorded cost is
counted as *uncovered* and the coverage stands next to the profit. Nothing is estimated (D-067).

### 2. What happened and when (event flow)

Show the *Event flow* table: confirmations on their confirmation date, accepted edits as the
difference on their acceptance date, cancellations as a reversal on their approval date; the
monthly table underneath. Say: the current-state figures and the event flow are two views of the
same confirmed truth.

### 3. One customer over time

Type the customer's phone under *One customer over time*. Read: current grade, confirmed invoices
(with cancelled counted separately), first → latest purchase, rhythm, late payments against the
overdue threshold, cancellation requests; the money table by currency (purchased, largest,
average, receipts, outstanding, discounts, markups); top products, top categories, the grade at
each sale, monthly spend. Say: two customer records are never combined, even with the same phone
(D-069); a customer with no confirmed purchase shows "nothing to compute" instead of a guess.

### 4. Branding

Open **Branding**. Fill a description, phone, colours, storefront title, banner, About text,
invoice header/terms/thank-you line, switch on the QR, set the default language, save; upload
the logo. Say: this is presentation only — no price, role, ledger or storefront permission
changes here, and the API enforces that, not the screen.

### 5. The storefront and the invoice page

Open the storefront in a fresh private window: it opens in the business's default language, with
the title, logo, banner, the colours (only when readable), the contact and social footer, and
the About/Contact/Privacy/Terms pages; switch the language with the header link. Then open a
customer's private invoice link: header, terms, thank-you line, logo, and the QR that points
only at that same private page.

### 6. Public statistics

`GET /stats/count`, `/stats/average-age`, `/stats/top-cities` are unchanged from Phase 1.
`GET /stats/platform` returns aggregate counts only and says *insufficient data* until at least 5
businesses and 20 customers exist (D-070).

## Security expectations (say them out loud)

- Analytics are owner-only; a driver and the platform administrator get nothing tenant-private.
- Currencies are never converted or summed together; there is no exchange rate anywhere.
- Profit is never guessed: uncovered lines are reported, not filled from a later cost.
- Branding cannot alter prices, roles, scoping, ledgers, cancellation or API authority.
- The QR carries only the invoice page link the holder already has; the secret never enters a
  server-side URL.
- Public statistics never expose revenue, debt, supplier prices or identifiable history.

## Limitations to state plainly

- Favicon, featured products, promotional banners and a configurable homepage layout await the
  owner's decision (see the requirements audit).
- No forecasting (Phase 10, not authorized); no analytics warehouse; no FX.
- The chosen colours are applied only when they stay readable; the storefront layout is fixed.
