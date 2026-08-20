# 00_PROJECT_CONTRACT.md — Locked Product and Architecture Contract

## Product

**Tawzeevo** is a multi-tenant Cash Van operations SaaS with a linked bilingual customer e-commerce storefront.

The public platform/product name and repository name are `Tawzeevo`. “Cash Van” is a description of the operating model, not the product name.

The operational product is a **website/PWA**, not a native mobile app.

Languages:
- English
- Arabic
- LTR/RTL

## Absolute Phase 1 rule

Every training-program requirement listed in `PHASE_01.md` is mandatory in Phase 1.

The frontend that the source specification labels “bonus” is treated as mandatory for this project.

Future architecture may be contracted in Phase 1, but later-phase functionality must not be falsely presented as implemented.

## Identity and roles

System user types required in Phase 1:
- `admin`
- `client`

Public `/register`:
- never accepts authorization role/type;
- always creates `client`.

Tenant/business roles:
- `owner`
- `driver`

Role relationship:
- `owner` is the full tenant-management role and also includes the operational permissions needed to personally operate the Cash Van, perform delivery work, use routes, and complete owner-authorized operational tasks;
- `driver` is a restricted operational role for a separate worker and is limited to assigned/necessary data;
- an owner never needs a second driver account or a second tenant membership merely to operate the Cash Van personally;
- one membership keeps one role; do not create duplicate owner+driver memberships for the same responsibility.

For delivery/route authorization, an active tenant membership is an eligible operational assignee when its role is `owner` or `driver`.

If a tenant has exactly one active usable owner and no active drivers, delivery work defaults to that owner and the UI must not require driver setup.

If several eligible owner/driver memberships exist, an owner selects the assignee.

System role and tenant role are different concepts.

A platform `admin` does not automatically become a tenant owner.

Additional roles require user approval before introduction.

## Multi-tenancy

Multi-tenancy exists from the first business tables.

Every tenant-owned business table has explicit `tenant_id`.

Business access chain:

```text
authenticate
→ validate session
→ resolve active tenant
→ validate membership/role
→ tenant-scoped service/repository
→ PostgreSQL RLS defense in depth
```

Never trust a client-provided tenant ID as authorization.

An `ACTIVE` tenant must always have at least one active usable owner.

`DELETE /users/{id}` must return `409 OWNER_TRANSFER_REQUIRED` if deleting the user would orphan any active tenant.

## Tenant lifecycle

States:
- `ACTIVE`
- `SUSPENDED`
- `CLOSED`

Use `SUSPENDED` for temporary loss of business access, including non-payment. Do not use deletion for subscription/access enforcement.

Tenant access-control fields:
- `access_until` nullable;
- `grace_until` nullable;
- `suspension_reason` nullable;
- lifecycle timestamps required for activation/suspension/reactivation auditability.

Supported suspension reasons include:
- `SUBSCRIPTION_OVERDUE`;
- `ADMINISTRATIVE`;
- `SECURITY`;
- `OTHER`.

`SUSPENDED`/`CLOSED`:
- block tenant business access/mutations server-side;
- revoke registered sync devices;
- invalidate offline leases server-side;
- reject/quarantine revoked-device queued work on reconnect;
- do not silently apply that work.

`SUSPENDED` preserves the tenant and all tenant-owned business data. Reactivation resumes the same tenant with the same stored customers, products, invoices, supplier history, settings, and other retained data.

`CLOSED` is a separate deliberate lifecycle state and is not the normal response to temporary non-payment.

An already physically offline browser cannot receive remote revocation until reconnect/lease expiry; that limitation must remain explicit.

`access_until` and optional `grace_until` are manual access-management metadata. In Phase 1 they may identify an overdue tenant in the platform-admin dashboard, but they do not silently delete data and do not require automatic payment processing.


## Platform administration and tenant applications

The system `admin` role is the platform-administration role.

Platform admin can manage SaaS access without becoming a member/owner of the tenant and without automatically receiving access to tenant-private business data.

Tenant application flow:

```text
registered client
→ submit tenant application
→ platform admin reviews
→ approve or reject
```

Tenant-application states:
- `PENDING`
- `APPROVED`
- `REJECTED`

Application approval is transactional:
- mark application approved;
- create the tenant;
- create the applicant's `owner` membership;
- activate the tenant;
- optionally set `access_until` / `grace_until`;
- audit the approval.

Application rejection:
- does not delete the applicant user;
- retains the application/review history;
- creates no tenant/owner membership.

Platform-admin dashboard must support:
- pending application review;
- approve/reject;
- tenant list/search/filter;
- active/suspended/closed filtering;
- overdue-access indication from `access_until` / `grace_until`;
- manual access-period set/extension;
- suspend tenant;
- reactivate tenant;
- record suspension reason;
- audit activation/suspension/reactivation.

Non-payment handling:

```text
tenant remains stored
→ platform admin suspends with SUBSCRIPTION_OVERDUE
→ tenant business access stops
→ all retained business data remains stored
→ payment/renewal occurs outside automatic billing
→ platform admin extends access period/reactivates
→ same tenant and data become usable again
```

Platform administration is lifecycle/access control, not permission to browse tenant-private invoices, customers, supplier prices, debt, or other commercial data by default.

Automated payment collection/provider billing is not required by this contract unless later explicitly approved.

## Customers are not application users

Storefront customers can order without:
- login;
- verified account;
- password;
- email;
- age.

`users` and `customers` remain separate.

Customer phone:
- is mandatory for checkout/search;
- is not authentication;
- must never reveal prior history, debt, grade, address history, or invoices by itself.

Duplicate phone records may exist within one tenant and must be disambiguated instead of silently merged.

Do not implement automatic customer merge unless explicitly approved.

## No stock / no availability

Never implement:
- stock quantity;
- quantity-on-hand;
- reserved stock;
- warehouse stock;
- automatic stock deduction;
- inventory movements;
- “in stock/out of stock”;
- “needs supplier” availability states.

`is_published` means catalog visibility only, not supply availability.

Procurement quantities describe customer demand/purchases, not inventory.

## Catalog and barcodes

Two commercial scopes:
- global master product identity/catalog;
- tenant-specific commercial product/pricing.

The platform should support a curated Lebanese-market barcode catalog.

If a product is missing, an owner can manually create a tenant product.

Barcode scan should resolve and show:
- product identity/name;
- image;
- tenant-specific price.

Piece/box support is required:
- pieces per box;
- owner may set price basis by piece or box;
- counterpart unit price is derived consistently.

## Customer grades and pricing

Initial grades:
- A+
- A
- B+
- B

Support:
1. grade percentage discount;
2. explicit product price for a grade.

Price precedence:
```text
explicit product-grade price
→ otherwise grade percentage discount
→ otherwise normal product price
```

Financial calculations are backend-authoritative.

No binary floating point for money.

Currencies are never silently mixed in one aggregate.

## Invoice behavior

Invoice maker must ultimately support:
- customer phone lookup;
- barcode item entry;
- manual item entry;
- text list → item/quantity parsing with safe fuzzy suggestions;
- product images;
- piece/box;
- calculator-style numbers/operators;
- discounts;
- markup;
- customer grade pricing;
- previous/old balance;
- WhatsApp share to the customer number.

Before confirmation:
- owner may edit customer order/purchase freely within allowed fields.

After confirmation:
- invoice may still be edited;
- history must remain immutable/auditable;
- edits create new immutable revision and ledger delta;
- never overwrite financial history.

Official invoice/revision business sequences are server-authoritative.
Offline devices use UUIDs/temp references until server acceptance.

## Financial truth

Financial history is append-only.

Canonical concepts:
- immutable invoice revisions;
- immutable customer/supplier ledger entries;
- immutable payments;
- immutable customer payment allocations;
- compensating reversals.

Customer balance by currency:
```text
SUM(customer_ledger_entries.signed_amount)
```

Positive = customer owes tenant.
Negative = customer credit.

Customer refund ceiling:
```text
available_credit(currency) = MAX(0, -current_balance(currency))
refund_amount <= available_credit(currency)
```

Refund must be serialized transactionally so concurrent refunds cannot spend the same credit twice.

No refund may create new customer debt.

Supplier payments in Phases 1–10 reduce the aggregate supplier payable. Do not invent per-purchase supplier-payment allocation unless explicitly approved.

## Debt/loans

Required:
- old/opening customer balance;
- customer outstanding/loan;
- supplier outstanding/loan;
- total customer/supplier debt by currency;
- owner-configurable overdue threshold X days;
- overdue customer visual red indicator;
- loan delay alerts.

## Order/storefront behavior

Linked bilingual storefront:
- categories;
- product images/prices;
- guest checkout;
- mandatory name/phone/address;
- no verified customer account required.

Checkout:
- creates order;
- creates provisional customer-facing invoice representation;
- owner receives notification;
- retry must be idempotent.

Owner review:
- can add/remove/change items/quantities before confirmation.

After confirmation:
- owner sets estimated delivery date;
- customer does not set delivery date;
- owner reminder is created.

Customer:
- can request cancellation;
- cannot directly cancel.

Owner:
- approves/rejects cancellation.

No customer-facing delivery tracking.

Public invoice access:
- random capability token;
- internal IDs alone never authorize;
- no-store/noindex/no-referrer;
- token is not logged.

## Homepage advertisements

Owner can explicitly feature products on storefront homepage.

Default duration:
- 7 days

This is advertising, not availability or stock.

## Recommendations

Deterministic first.

Signals:
- view
- purchase

Purchase must carry higher weight than view.

Cancelled/non-valid sales must not count as current purchase recommendations.

Do not add generative AI to recommendations unless explicitly approved later.

## Suppliers / procurement

Required:
- suppliers with contacts/address/location;
- append-only supplier price history;
- quote/actual price context;
- last/lowest/highest price;
- last purchase date;
- trend/stability;
- best known comparable supplier;
- daily procurement list from demand;
- manual item/quantity adjustments;
- partial purchase;
- supplier grouping;
- estimated purchase cost;
- carry-forward;
- print/export;
- actual supplier purchase;
- supplier payable/payment.

Demand chain:
```text
customer demand
→ procurement
→ supplier purchase
→ supplier payable/payment
```

Never convert this into inventory.

## Location / driver

Customer:
- address;
- saved coordinates/location.

Owner as Cash Van operator:
- an owner may personally perform all delivery/route operational actions without creating a separate driver account;
- when the owner physically performs a delivery task, the task is assigned to the owner's tenant membership;
- owner may view/manage all tenant delivery tasks and may assign/reassign them;
- assignment/reassignment must remain auditable.

Driver:
- strict least-privilege;
- sees only assigned work and required customer/invoice projection;
- never receives owner profit, supplier price history/costs, broad analytics, or unrelated customer data;
- cannot assign/reassign delivery work unless a later explicit user decision approves it.

Driver/delivery task state is internal; it is never customer tracking.

Route:
- offline deterministic stop-order suggestion;
- online provider-assisted routing once provider is explicitly approved.

Nearby supplier reminder:
- may show identity/location/operational need to driver if authorized;
- supplier price/cost remains owner-only.

## Offline-first operations

Operations web app uses IndexedDB.

Required principles:
- local mutation + outbox atomic;
- server idempotency;
- entity versions;
- bootstrap/pull cursor;
- tombstones;
- registered sync devices;
- permission revocation;
- protocol versioning;
- offline media queue.

`device_id` is deduplication/device identity only, never authorization.

PostgreSQL remains live authoritative source.

## Google-linked backup

Operational sync is not Google backup.

Google Drive:
- encrypted backup/export destination;
- never the live database.

Exact OAuth scope must be approved at the Phase 4 gate before implementation.

## Analytics

Required business views include:
- per-invoice sales/revenue facts;
- 30-day;
- 90-day;
- 1-year;
- customer outstanding;
- supplier payable;
- customer lifetime statistics.

Customer lifetime statistics include:
- total purchases;
- total payments;
- outstanding balance;
- number of orders/invoices;
- first/latest purchase;
- average invoice/order;
- purchase frequency;
- most purchased products/categories;
- grade;
- late-payment indicators;
- cancellation-request history where appropriate.

Public Phase 1 statistics remain required. Additional public stats must be aggregate and non-sensitive.

## Branding

Per-tenant branding later supports:
- business name;
- logo;
- contact;
- address;
- WhatsApp;
- default language;
- currency;
- timezone;
- storefront theme tokens;
- invoice header/footer;
- banner;
- favicon.

## AI

AI/forecasting is last.

Agreed future intelligence:
- predict best product by season/month from previous sales.

Start with explainable statistical baseline before ML/LLM.

## Explicitly out of scope unless user approves

- native mobile app;
- stock/inventory/warehouses;
- product availability states;
- customer account/login requirement;
- customer delivery tracking;
- customer self-cancellation;
- customer-selected delivery date;
- Gmail as database;
- generic CRM;
- full accounting/ERP;
- automated payment-provider subscription billing / automatic charging (manual platform-admin access-period and suspension/reactivation control is in scope);
- tax/VAT engine;
- early AI/LLM;
- automatic customer merging;
- per-purchase supplier payment allocation.
