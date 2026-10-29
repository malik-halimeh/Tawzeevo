# Owner workspace made phone-easy (D-119, D-120)

The owner uses Tawzeevo on a phone almost all the time, mostly in Arabic. This stream changes how the
owner side is **presented and reached**. Every existing screen, rule and address still works; nothing
was hidden or removed. The only new capabilities are the two the owner approved (D-119): a list of
every invoice of the business, and a customer search by part of a name or phone.

## 1. What the owner sees now

| Where | Before | Now |
|---|---|---|
| Opening the app | Today (work) page | **Sales › Invoices**: the invoices front page (`?section=invoices&view=list`) |
| Phone bar | Today · Sales · Customers · More (Sales opened Orders) | **Today · Sales · Customers · Catalog · More** (Sales opens the invoices front page) |
| Invoices front page | — (Invoices opened the editor) | "Needs you" strip; money owed and overdue per currency; chips All · Unpaid · Overdue · Paid · Draft · Cancelled; filters (currency, dates); every invoice grouped by month; **New invoice** button and round **+** |
| Invoice editor | One long page | Stacked cards; total, Save and Confirm in a bar fixed at the bottom; the customer picker shows matches by name or phone as you type |
| Customers | Exact-phone lookup first | List with search as you type (name, or 3+ digits of the phone), sort Name · Newest · Who owes most, what each customer owes per currency, row ⋮ menu (New invoice, Record payment, Edit, Shop link, Invoices), round **+** to add. The exact-phone lookup is still on the page |
| Customer form | Every field at once | Name and phone first; the rest under "Show more fields" (opens by itself when one of them is filled or has an error) |
| Products | Cards with buttons | List with search, category chips, Published / Hidden filter, row ⋮ menu (Edit, Hide/Publish, Add barcode, Pricing & photos), round **+** to add (scan desk first) |
| Orders | Plain list | Count, state chips with numbers, compact rows; tapping a row opens the same order review; row ⋮ = Order review and, when confirmed or cancelled, the invoice. Confirming and declining stay in the review |
| Settings | Four separate tabs | A hub with three pages — **Business** (branding, storefront), **Invoices & pricing** (grade discounts, overdue days and opening balances, invoice sharing note), **General** (language, offline sync, backup, profile, public statistics, sign out). The old tabs still open directly |
| Deliveries, Buying, Insights | Own heading styles | The same header as the list pages (title, and a count where the page already has the list) |

Daily pages are at most **2 taps** from anywhere on a phone; settings pages are **3** (More → hub page
→ row), as the owner chose.

## 2. Addresses (deep links)

All addresses that existed before still open the same screen. New ones:

- `?section=invoices&view=list` — invoices front page (the owner's landing page).
- `?section=settings&view=business|invoices|general` — settings hub pages.
- `?section=work` — Today (the owner's Today page now has its own address).

Any other invoices address (`invoice=`, `customer=`, `fresh=`, `view=payments|balances|invoice`, or no
`view`) opens the editor as before; `view=balances` opens the Balances view.

## 3. New read-only API (D-119)

- `GET /api/v1/invoices/all?tenant_id=…` — every invoice of the business, newest first, 1–100 per page;
  filters `status`, `paid_state` (UNPAID, PARTLY_PAID, PAID, OPEN), `overdue`, `customer_id`, `currency`,
  `date_from`/`date_to` (Beirut calendar), `q` (official number or customer name).
- `GET /api/v1/invoices/summary?tenant_id=…` — per currency: outstanding and overdue totals and counts.
  Amounts are never added across currencies.
- `GET /api/v1/tenants/{tenant_id}/customers?q=&sort=name|newest|owes_most` — search folds Arabic letter
  variants, diacritics, tatweel and Arabic-Indic digits; each row carries its balances per currency.

Owner only, tenant-scoped, no writes, no migration.

## 4. Demo notes (Arabic, phone)

1. Sign in as the demo owner → the invoices front page opens. Point at "Needs you", the owed/overdue
   cards (one per currency) and the chips; tap **Overdue**.
2. Tap an invoice → the editor opens on it; the bottom bar holds the total and the actions.
3. Back, tap **New invoice** (or +) → pick a customer by typing part of the name in Arabic → add items →
   Save → Confirm.
4. Customers → type two letters → sort by "Who owes most" → row ⋮ → Record payment.
5. Catalog → Products → chip a category → row ⋮ → Pricing & photos.
6. More → General → switch the language; More → Business → Branding.

## 5. Known limits

- Order rows show no amount: the order list carries no totals and no new request was added.
- "Who owes most" ranks by the largest single-currency number, so a large LBP balance ranks above a
  smaller USD one; every balance is shown with its currency.
- Money keeps the app-wide "value CUR" format with four decimals.
- Two storefront-only browser tests (`order-workflow-isolation`, `phase9-verification`) were unstable on
  the local test stack during verification; the storefront and its API are unchanged by this stream, and
  the isolation test fails the same way with `main`'s API code.
- The visual look (more "metallic") is a separate, later stream; this stream used existing design tokens only.

## 6. Changes (branch `feature/owner-ease`)

- api: owner list of all invoices with paid state, overdue and per-currency totals (read-only).
- api: customer list searches by name or part of the phone and sorts by name, newest or who owes most.
- Owner phone bar Today · Sales · Customers · Catalog · More; owners open on Sales › Invoices.
- Shared list-page kit (header with search, sort menu, chips, filter sheet, row with action menu, + button,
  month groups, empty hint).
- Invoice editor as stacked cards with a bottom bar; customer picker searches as you type.
- Invoices front page.
- Customers page as a list; customer form shows required fields first.
- Products page as a list with chips, visibility filter and row menus.
- Settings hub (Business, Invoices & pricing, General).
- Orders inbox in the list kit.
- Deliveries, Buying and Insights use the shared header.
- Decisions D-119 and D-120; browser tests follow the new navigation.
