# Phase 6 demo and presentation guide

This guide demonstrates only completed Phase 6 behavior: supplier profiles, the append-only
price history with its derived insight, the deterministic supplier recommendation, demand-driven
procurement, actual purchases with their accounting, and the driver's price-free pickup view.
Use synthetic data only.

## Prepare the environment

1. Follow the root `README.md` local setup. Never demonstrate against production data.
2. Apply migrations and confirm revision `20260919_0024` is the current Alembic head.
3. Sign in as the active owner of an approved synthetic business with two products, two
   suppliers, and two or three confirmed invoices from today.
4. Optional for step 6: a second user with an active *driver* membership of the business.

## Recommended presentation route

### 1. Supplier profiles

**Suppliers & costs** → add a supplier with contact person, phone, address and coordinates.
Edit it; say that every edit carries the row version and that a stale edit from another device
is refused, never merged silently.

### 2. Price history and insight

Choose a product. Save a *Manual* cost for supplier A, then a *Quote* for supplier B "for
quantity 120". Point at the insight table: latest with source and age, lowest–highest, last
purchase (none yet), the recent trend, stability. Save a box-basis cost and show it sits in its
own comparable group — nothing is converted between units or currencies.

### 3. Recommendation you can explain

The *Recommended supplier* panel names the cheapest comparable supplier and says why each row is
where it is; stale prices are ranked last, never hidden; suppliers without a comparable price are
listed as *Not ranked* with the reason. Choose another supplier with a reason: the panel now
shows *Your choice … the ranking recommends …*.

### 4. Procurement from confirmed demand

**Procurement** → *Build from confirmed demand* for today. Explain the four numbers on each line:
required (what customers confirmed), target (yours), purchased (progress), remaining. Raise a
target; add a manual line; remove it with a reason and show it stays readable. Show the labelled
estimate and *Group by supplier*. Assign the list to yourself (a sole owner needs no driver).
Print or download the CSV.

### 5. The purchase that books everything

**Suppliers & costs** → *Record purchase*: pick the supplier and the list; the open lines are
preloaded. Record part of the quantity at the real price. Say what just happened in one
transaction: a new *Actual purchase* row in the price history, the supplier payable up, the list
*Partly purchased*. Reverse the purchase with a reason and show the compensating entry; then
record it again. Pay the supplier: a payment above the payable is refused; payments are never
allocated to a purchase.

### 6. Driver pickup view (optional)

Assign the list to the driver, sign in as the driver: supplier name, phone, address, map link
and quantities — no price, cost or estimate anywhere.

### 7. Offline (optional)

With the developer tools *Offline* switch on, save a quote or change a target: the screen says
the command is queued on this device. Back online, **Offline** → *Sync now*: it applies once.

## Security expectations (say them out loud)

- Suppliers, costs and procurement are tenant-private under row-level security; drivers see
  only their pickup projection.
- The price history is append-only; the invoice engine keeps the cost it was confirmed with.
- Nothing here is stock: no on-hand, reserved or availability value exists in the database.

## Limitations to state plainly

- Estimates are estimates from the latest comparable price; they are never booked.
- Offline screens for suppliers/procurement need a connection to read; only commands queue.
- Supplier payments are aggregate per currency by design (no allocation to purchases).
