# Daylight interactive concept

An isolated, bilingual, phone-first Tawzeevo design prototype. Scope is implemented and browser
validated; visual approval and production integration are separate steps.

## Open it

The public-entry extension is at [landing](http://127.0.0.1:4180/welcome.html) and
[sign-in](http://127.0.0.1:4180/welcome.html#signin). It includes English/Arabic, local icon
illustrations, and simulated form states. See `../PUBLIC_ENTRY.md` for source mapping and
integration boundaries. The workspace preview title links back to the landing page.

Open `index.html` directly in a browser, or use the loopback-only server:

```powershell
node docs/design-references/prototype/serve.cjs
```

Then visit [the local preview](http://127.0.0.1:4180). The server exposes only the prototype folder.
No package installation or build is needed. Assets are local, and the browser makes no API calls.

The top toolbar selects Owner, Driver, or Storefront, switches English/Arabic, simulates the network,
and displays empty/loading/error states. Reset or reload returns all synthetic data to its initial
state. There is no real account, backend connection, service worker, or persistent storage.

## Try these journeys

1. **Owner delivery:** open Al Nour Market, inspect the goods and amount to collect, then complete
   delivery. Completion never records payment. Change the network to Offline before completing a
   different stop to see queued work. Set Fail requests and use Sync now to see failure, then set
   Online and retry.
2. **Customer payment:** Customers → Al Nour Market → Record payment → enter an amount → review →
   record. To see a failed payment, choose Fail requests before opening the payment form. Reconnect
   & retry changes only the preview network and reuses the same payment intent.
3. **Invoice revisions:** Invoices → INV-00482 → Create revision → adjust a quantity → confirm →
   View revision history. Open revision 1 to see its unchanged 79.00 USD total. New invoice and Add
   product demonstrate creation, product selection, piece/box units, and totals.
4. **Driver:** choose Driver in the toolbar. Only Safa Grocery is assigned to this fictional driver.
   Owner customers, invoices, balances, grades and financial actions are not rendered.
5. **Storefront:** browse or search products, open a product, choose a piece or box, add quantities,
   review the basket, and submit fictional guest contact information. A failed request retains
   the basket and contact details for retry. Acknowledgement includes a provisional invoice and
   leaves the delivery date unassigned.
6. **Arabic/mobile:** change the language at any step and resize the browser. The operations rail
   becomes bottom navigation below 1100px; phone records open as one focused pane.

Sample business names, people, phone numbers and records are fictional. Map links point to general
Saida coordinates to demonstrate the existing external-navigation pattern; no live position is
requested. Do not use sample telephone numbers to contact anyone.

## Reproduce verification

The tests use the existing repository's Playwright, ESLint, and axe-core. A worktree without its
own `node_modules` can point the test tools to the original dependency installation:

```powershell
$env:TAWZEEVO_TOOL_ROOT = 'C:\Users\malik\Desktop\DigitalHub\Tawzeevo'
node --check docs/design-references/prototype/app.js
node docs/design-references/prototype/tests/lint.cjs
node docs/design-references/prototype/tests/verify.cjs
node docs/design-references/prototype/tests/edge.cjs
```

Keep `serve.cjs` running in another terminal during browser tests. Omit the environment override
when running from a checkout that already has its own dependencies. The main browser test accepts
`DAYLIGHT_URL` to override its default loopback address.

See [TEST_REPORT.md](TEST_REPORT.md) for executed results and limitations. JSON evidence is in
`tests/results.json` and `tests/edge-results.json`. Screenshots are actual Chromium renders, not
image-generated UI mockups.

## Representative renders

- [Owner desktop, English](screenshots/owner-1440-en.png)
- [Owner phone, English](screenshots/owner-390-en.png)
- [Delivery phone, Arabic](screenshots/stop-390-ar.png)
- [Customer desktop, Arabic](screenshots/customer-1440-ar.png)
- [Invoice phone, English](screenshots/invoice-390-en.png)
- [Storefront desktop, English](screenshots/storefront-1440-en.png)
- [Storefront phone, Arabic](screenshots/storefront-390-ar.png)
- [Guest checkout, Arabic](screenshots/checkout-390-ar.png)

## Files and future integration

`index.html`, `daylight.css`, and `app.js` form the standalone prototype. `serve.cjs` is optional
local tooling. `assets/` contains the original fictional photography and licensed fonts;
[ASSETS.md](ASSETS.md) records their sources and generation prompt.

Read [the draft design specification](../DESIGN_DIRECTION.md) before porting this presentation into
production. This preview does not validate live authorization, offline persistence, API idempotency,
or backend calculations. All production code and audit evidence remain unchanged.
