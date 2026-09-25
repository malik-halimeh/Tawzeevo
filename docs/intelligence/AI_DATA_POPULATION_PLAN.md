# Owner intelligence — data needed to see every layer working

The intelligence features read only a business's own records. With too little history they
say so ("Too little history", "Not enough history yet to check …") instead of guessing. This
plan says, for each layer, what records it reads, the smallest dataset that switches it on, a
convincing demo dataset, and how to check it.

- **Fastest route:** the seed command in [§ 8](#8-the-demo-seed-command) builds the whole
  recommended demo dataset (about six months of trading) in one dedicated, empty business.
- **By hand:** follow §§ 2–7 in the workspace.

All thresholds below come from the code (`apps/api/tawzeevo_api/services/intelligence/`). The
calendar is **Asia/Beirut**, every currency is handled separately, and nothing is summed across
currencies.

## 1. Shared foundations (all layers)

| Need | Why | Where in the workspace |
|---|---|---|
| **Customer overdue threshold** (days) | Without it nothing is ever "overdue": no overdue reasons, no overdue anomaly, cash-flow shows "no overdue threshold set" | Invoices › Balances › overdue setting (`customer_overdue_threshold_days`, e.g. **30**) |
| Customers | Everything is per customer and currency | Customers › Add customer |
| Products with prices (and supplier costs for the below-cost check) | Invoices and the product tools | Products; Suppliers & costs |
| **Confirmed** invoices | Sales, cadence, spikes. Drafts are ignored; cancelled invoices count only as cancellations; an edited invoice counts at its current revision | Invoices |
| Receipts, refunds, reversals | Balances, collections, spikes | Invoices › Record payment |
| Supplier purchases and payments | Supplier payables, payable jump, supplier payments | Procurement / Suppliers & costs |
| Delivery tasks (assigned, with a date) | Planned collections | Deliveries |

**Dates matter.** Confirmation, payment and purchase times are stamped by the server when the
record is created, so real history accumulates day by day. Only payments (`paid_at`), opening
balances (`effective_at`) and delivery dates can be dated in the past or future by hand. That is
why a realistic history for a demo needs either weeks of real use or the seed command.

**Minimum vs demo vs production:** each section gives the *minimum* that switches the layer on,
the *recommended demo* shape, and what improves it in *production*.

## 2. Today's priorities (Work) and the attention list (Customers)

Deterministic. One score per customer and currency, 0–100, from four parts; parts with no data
are left out of the denominator (a new customer is not "bad", just unknown).

| Part (max points) | Reads | Earns points when |
|---|---|---|
| Collection urgency (40) | Customer ledger balance; oldest unpaid charge; overdue threshold | 10 = any balance owed; 30 = overdue; 40 = overdue ≥ 2 × threshold |
| Buying rhythm (30) | Confirmed invoice dates (≥ 3 invoices) | 10 WATCH, 20 AT_RISK, 30 LAPSED (see § 3) |
| Activity decline (20) | Sales in the last 30 days vs the 90-day average | 10 when below 75 %, 20 when below 50 % |
| Friction (10) | Last 30 days: cancelled invoices, cancellation requests, receipt reversals, negative adjustments | 5 per event, max 10 |

Bands: **High ≥ 50**, **Medium ≥ 25**, Low below. Suggested action: collect overdue → check in
(stopped buying) → follow up balance → ask why orders dropped → review cancellations → routine.

- **Minimum:** overdue threshold set (e.g. 7 days) + one customer with an **opening balance**
  dated 40 days ago → High priority, "Collect the overdue balance". (This is exactly what the
  E2E test `e2e/intelligence-presentation.spec.ts` does.)
- **Recommended demo:** 8–10 customers, 3+ months of weekly/10-day buying, including: one with a
  balance overdue for 2× the threshold, one who stopped buying, one whose last-30-day buying
  fell below half its 90-day pace, one with two cancellations and a reversed receipt this month,
  one with only 2 invoices, several paying on time. Two currencies (e.g. USD and LBP).
- **Production:** meaningful after about 3 months of normal invoicing and receipts; the
  threshold should reflect the business's real payment terms.
- **Visible outcome:** Work › "Today's priorities" (top 3 High/Medium) and Customers › "Needs
  attention" (per currency, "Show all" for Low). Opening a row opens the customer's record with a
  **Signals** block explaining the reasons.
- **Verify:** `GET /api/v1/intelligence/priorities?tenant_id=…` lists the same order; the
  overdue amount in the reason equals the customer's balance in Invoices › Balances.

## 3. Buying rhythm / inactivity (Customers › Buying rhythm)

Deterministic. Per customer and currency: median gap between purchase days (Beirut calendar)
over all confirmed invoices, and days since the last purchase.

| Band | Days since last purchase ÷ usual gap |
|---|---|
| Buying as usual (NORMAL) | < 1.25 |
| Later than usual (WATCH) | ≥ 1.25 |
| Well past their rhythm (AT_RISK) | ≥ 1.75 |
| Stopped buying (LAPSED) | ≥ 2.50 |
| Too little history | fewer than 3 confirmed invoices, or all on one day |

- **Minimum:** one customer with **3 confirmed invoices** on different days. (Within a single
  day this is not possible by hand — invoices are dated when confirmed.)
- **Recommended demo:** a customer buying every ~10 days for 3–4 months who then stopped ~50 days
  ago (LAPSED); a regular weekly buyer (NORMAL); one slightly late (WATCH); one with 2 invoices.
- **Production:** trustworthy after 5–10 purchases per customer; seasonal businesses should read
  the band next to the dates.
- **Verify:** "Last purchase N days ago; usually buys every M days" matches the customer's
  invoice list.

## 4. Unusual changes (Analytics)

Deterministic. The last 7 days (a "block") are compared with up to 8 earlier weekly blocks of
the same currency using a robust median/MAD score: **Worth a look** at 3, **Very unusual** at 5.

| Check | Needs before it can run | Fires when |
|---|---|---|
| Sales this week high / low | ≥ **6 whole weeks** of history after the first sale in that currency | Confirmed sales of the week far from the usual week |
| More cancellations / reversed receipts than usual | 6 weeks of history | ≥ **3** such events this week and far above usual |
| More refunds than usual | 6 weeks of history | ≥ **2** refunds this week, amount far above usual |
| Invoice far above this customer's usual | ≥ **5** earlier invoices of that customer | An invoice this week ≥ 2 × their median and far above it |
| Large receipt recorded late | ≥ **5** receipts in the prior 90 days | A receipt recorded ≥ **7 days** after its payment date and ≥ 2 × the median receipt |
| A balance has just become overdue | Overdue threshold set | Oldest unpaid charge crossed the threshold 1–7 days ago |
| What you owe suppliers jumped | 6 weeks of supplier-ledger history | Net supplier-ledger change this week far above usual |
| Sold below the recorded cost | Supplier cost captured on the line, same currency and unit | A line this week sold below its cost snapshot |

When a check lacks history, Analytics says "Not enough history yet in USD to check: …".

- **Minimum (by hand, no history):** set the threshold, give a customer an opening balance dated
  *threshold + 3* days ago → "A balance has just become overdue"; sell one product below its
  supplier cost today → "Sold below the recorded cost"; record a receipt today with a payment
  date 10 days ago (needs 5 earlier receipts) → "Large receipt recorded late".
- **Recommended demo:** 8+ weeks of steady weekly sales with one strong week now, two refunds
  this week, one customer's invoice 10× their usual, one late-recorded large receipt, one balance
  crossing the threshold, one below-cost line, a large supplier purchase this week.
- **Production:** starts after ~7 weeks per currency; a quiet week correctly shows "Nothing
  unusual in the last 7 days". Unusual never means wrong.
- **Verify:** each row links to the invoice or customer it is about; the amounts match that
  record.

## 5. Cash position and ageing (Analytics)

Deterministic; history and position only — no forecast.

| Figure | Reads |
|---|---|
| Overdue of owed (customers) | Customer ledger + overdue threshold |
| Unpaid balances by age (0–30, 31–60, 61–90, over 90 days) | Age of each customer's oldest unpaid charge |
| Collected in the period (net), refunds, average per week | Receipts, reversals and refunds in the chosen period (30 days … all) |
| Paid to suppliers | Supplier payments net of reversals |
| Planned deliveries (projection) | Assigned delivery tasks dated today … today + 6, their *amount to collect* (does not include later invoice adjustments) |

- **Minimum:** one customer balance (opening balance) + threshold → overdue and one age bucket.
- **Recommended demo:** balances in at least three age buckets, receipts every week of the
  period, a refund, supplier purchases and payments, 3–4 deliveries planned for the coming days,
  and a second currency.
- **Production:** meaningful from the first month; ageing is most useful once the threshold
  matches the real payment terms.
- **Verify:** "Owed" equals "Owed by customers" in Analytics › Current state for the same
  currency; the ageing rows add up to it.

## 6. Business assistant (Assistant)

LLM-assisted, over the deterministic figures above. It needs the provider key
([AI_SETUP_REQUIRED.md](AI_SETUP_REQUIRED.md)) and the same data as §§ 2–5, plus:

| Tool the model may call | Reads |
|---|---|
| Period figures | Analytics overview (sales, receipts, refunds per currency) |
| Customer history / balances | Lifetime analytics, customer debts |
| Today's priorities, buying rhythm, unusual changes, cash position | §§ 2–5 |
| Top products | Confirmed invoice lines (line sales before invoice-level discounts) |
| Catalog | Product names and list prices |

- **Minimum:** any business with a few confirmed invoices; questions about missing history get
  "not enough history" answers.
- **Recommended demo:** the § 8 dataset, then ask: "Who should I call today?", "Which customers are
  overdue, and by how much?", "Was anything unusual this week?", "How much did we collect in the
  last 30 days?", "What are our top products this month?", and one in Arabic
  ("بمن يجب أن أتصل اليوم؟").
- **Visible outcome:** a short answer, clickable customer names, a "Based on:" line naming the
  figures used, and a yellow note if any number did not come from Tawzeevo.
- **Verify:** the customers and amounts match Customers › Needs attention and Analytics.

## 7. Arabic and mixed-language data

Customer and product names may be Arabic or English; both display correctly (amounts stay
left-to-right). Include at least one Arabic customer name (e.g. `دكان الأرز`) and Arabic product
names to show this. The assistant answers in the language of the question.

## 8. The demo seed command

`apps/api/tawzeevo_api/cli/seed_intelligence_demo.py` writes about six months of synthetic,
ledger-consistent trading into **one dedicated, empty business**, through the same service
functions the API uses, each record created at its historical moment. Every name and phone is
invented.

**What it creates** (default seed 89): 10 customers (one Arabic name), 10 products (8 USD, 2 LBP)
with supplier costs, 2 suppliers, ~193 confirmed invoices (2 later cancelled), ~169 receipts,
2 reversals, 3 refunds, 25 supplier purchases, 24 supplier payments, 5 delivery tasks for the
next few days, overdue threshold 30 days.

**Expected on the day it is seeded:**

| Layer | Outcome |
|---|---|
| Priorities (USD) | Tyre Fresh Foods High — collect overdue (~76 days); Byblos Grocery High — stopped buying; Zahle Wholesale and Batroun Bakery Medium; the rest Low |
| Priorities (LBP) | Hamra Café — follow up LBP balance |
| Buying rhythm | Byblos LAPSED; Tyre and Batroun WATCH; Saida Corner Shop too little history; others as usual |
| Unusual changes (USD) | sales high, refunds high, Tripoli Traders' large invoice, what you owe suppliers jumped, Batroun's late-recorded receipt, Zahle just overdue, olive oil sold below cost |
| Cash position | USD overdue across 0–30 / 31–60 / 61–90; 4 planned USD deliveries and 1 LBP |

Not produced on purpose: "more cancellations/reversed receipts than usual" (needs ≥ 3 in the
current week), "sales unusually low", and storefront cancellation requests.

**Run it** (from `apps/api`, in its own process — never inside the running API):

1. Create the demo business normally: register an owner, apply, approve it as platform admin.
   Use a name that marks it as a demo (e.g. "Cedar Demo Distribution"). It must have **no
   customers, invoices or payments**.
2. Point `DATABASE_URL` at the target database for this one command only.
3. Run:

   ```text
   python -m tawzeevo_api.cli.seed_intelligence_demo \
     --owner-email <owner e-mail> --tenant-id <business id> \
     --confirm-tenant-name "Cedar Demo Distribution"
   ```

   Options: `--as-of YYYY-MM-DD` (history ends before this Beirut date; default today),
   `--seed N` (default 89), `--allow-production` (see below).

**Guards:** refuses a business that already has customers, invoices or payments; refuses a
confirmation name that does not match exactly; refuses the owner/tenant pairing the API itself
would refuse; refuses when `APP_ENV=production` unless `--allow-production` is given. It is all or
nothing (one transaction) and records one audit event marked synthetic. It prints counts and the
expected outcomes, never the database address.

**Where to run it:**

- **Local / disposable database:** safest; use it for rehearsals and screenshots.
- **Staging** (own database): run it from a machine that can reach the staging database, with
  the staging `DATABASE_URL` set only for that command, into a new demo business.
- **Live:** only into a brand-new demo business, only with `--allow-production`, and only if you
  are comfortable with a synthetic business living beside real ones. The command never touches
  other businesses, but the demo data cannot be removed afterwards (financial records are
  immutable by design) — the business can only be suspended.

**Timing:** results are computed for *today*. Seed on (or the day before) the demo day. A week
later the week-based items (sales high, the large invoice, the late receipt, just overdue) will
have left the 7-day window and the deliveries will be in the past; seed a fresh demo business
instead of re-running into the same one.

## 9. Production reality

| Layer | Starts to be useful | Gets better with |
|---|---|---|
| Priorities | Day 1 for balances (with the threshold set); ~1 month for rhythm | Consistent receipts recording; a realistic threshold |
| Buying rhythm | 3 invoices per customer | 5–10+ purchases per customer |
| Unusual changes | ~7 weeks per currency | Steady weekly use; supplier purchases entered in Tawzeevo |
| Cash position | Day 1 | Delivery tasks planned ahead; payments recorded on the day |
| Assistant | Key set + some confirmed invoices | Everything above |

Synthetic data (including the seed) is for demonstrations and tests only. It must not be used to
judge thresholds or to claim that any figure predicts the future (D-086).
