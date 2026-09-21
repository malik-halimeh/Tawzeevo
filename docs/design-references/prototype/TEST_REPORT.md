# Daylight prototype validation

Result: **PASS for the bounded interactive concept**. Production integration is not covered.

Executed 2026-09-21 on Windows with Node.js 22.21.0 and headless Chromium 141.0.7390.37,
using the repository's installed Playwright, ESLint, and axe-core. Latest main browser result:
`2026-09-21T18:50:50.227Z`. Exact results and timestamps are retained in the JSON files below.

## Executed checks

| Check | Result | Evidence |
|---|---|---|
| JavaScript syntax (`node --check`) | PASS | `app.js` parsed successfully |
| Prototype JavaScript, server and test-tool ESLint | PASS | `tests/lint.cjs`; zero errors/warnings |
| Browser acceptance suite | PASS, 145 checks | `tests/results.json` |
| Large LBP amounts and short-height input checks | PASS, 8 checks | `tests/edge-results.json` |
| Owner, driver and storefront rendering | PASS | Actual screenshots in `screenshots/` |
| Browser console / runtime errors | 0 | Main browser suite |
| External network requests during tested journeys | 0 | Main browser suite |
| Service-worker registrations and local/session storage | 0 | Main browser suite |
| Opening `index.html` directly with `file://` in Chromium | PASS | App rendered; fonts loaded; no console/runtime errors |

The main suite tests 360, 390, 768, and 1440 CSS-pixel widths in both English and Arabic.
Each combination exercises owner overview, delivery detail, customer detail, invoice document,
invoice composition, restricted driver detail, storefront catalog, product detail, basket, and
checkout. It checks page and content bounds. Representative states are captured as actual viewport
screenshots rather than synthetic UI images.

Automated axe WCAG A/AA scans pass on owner phone, payment review, driver details, English and
Arabic delivery details, Arabic driver details, and English/Arabic storefront and checkout.
The reviewed screenshots cover phone, tablet and desktop layouts, Arabic shaping, direction,
currency isolation, product-image cropping, hierarchy, and the attached action area.

## Journey and invariant evidence

- Customer search demonstrates no-match results and preserves the entered search after returning
  from a record. Native dialog dismissal restores focus; quantity controls retain keyboard focus
  after updating. Reduced-motion mode disables the transition.
- The initial Al Nour account reconciles to 42.00 opening + 79.00 invoice = 121.00 USD.
  A 20.25 receipt reduces the account to 100.75. Failure changes no balance; retry appends exactly
  one receipt. Zero amounts are rejected, and entry/review/pending/failure/success are distinct.
- Increasing the oil-box quantity creates a 127.00 invoice revision. Revision 1 retains its
  independent 79.00 total and original lines. A new mixed piece/box draft totals 98.50 USD.
  An unavailable confirmation keeps the draft, then succeeds after restoring the simulated network.
- An offline delivery queues, visibly enters Syncing, retains a failed update, and accepts the same
  update on successful retry. Delivery completion does not add a receipt.
- LBP values remain separate from USD. A 2,700,000 LBP balance and delivery action fit at 360px in
  both languages. The fixed-price sample catalog is USD-only and explicitly explains the absence
  of LBP composition data; it performs no currency conversion.
- The driver preview renders a separate Safa Grocery projection and no owner customer, grade,
  broad balance, invoice creation, payment, supplier, cost or profit controls. Closed modal contents
  are cleared when dismissed so old owner data does not remain in the rendered driver document.
- Storefront filters and empty searches work. Two boxes of water total 12.00 USD. Guest checkout
  validates name, phone, and address; a failed request retains the basket and form for retry.
  Successful acknowledgement shows a provisional invoice, pending owner confirmation, and no
  assigned delivery date. Input containing angle brackets is rendered as text, not markup.
- Successful checkout clears the basket; reloading resets all prototype state. No real data or
  external account is used.

## Corrections made during validation

The initial Python preview server reset some font connections; the included loopback Node server
serves all assets successfully. A tablet product grid initially exceeded its available width;
explicit shrinkable columns fixed it. Phone detail screens now remove redundant overview headings.
Focus is preserved across quantity edits and restored on dialog exit. Financial signs are enclosed
with their amounts inside an LTR isolation span for Arabic. Earlier failing screenshots were
removed; the retained matrix captures reflect the final tested presentation.

## Reproduction

From the design worktree, run the local server in one terminal:

```powershell
node docs/design-references/prototype/serve.cjs
```

In another terminal, using the existing dependency installation:

```powershell
$env:TAWZEEVO_TOOL_ROOT = 'C:\Users\malik\Desktop\DigitalHub\Tawzeevo'
node --check docs/design-references/prototype/app.js
node docs/design-references/prototype/tests/lint.cjs
node docs/design-references/prototype/tests/verify.cjs
node docs/design-references/prototype/tests/edge.cjs
```

No dependency, lockfile, production app or API changes are needed. The implementation therefore
does not run or claim a new production TypeScript/build/backend test pass. Its executable files are
JavaScript checked by ESLint, syntax validation and browser tests.

## Boundaries and remaining verification

- This is a synthetic UI proof, not a complete production application. Backend authority, real
  authorization/RLS, live payment idempotency, sync leases, offline persistence, and customer
  capability security are not implemented or validated by this prototype.
- The persona toolbar is not authentication; fixture source is inspectable. There is no real
  personal or commercial data in the fixture. The restricted rendering check is not a claim that
  client-side filtering is adequate production security.
- Short viewport tests check payment input visibility and dismissal at 360×440. Physical device
  keyboards, iOS Safari, Android Chrome, native screen readers, and outdoor readability still need
  real-device evaluation. Desktop Chromium checks do not prove those behaviors.
- Arbitrary tenant color input is not exposed in this static concept. One accessible sample brand
  is shown. Production must preserve `theme.ts` validation/fallback and retest multiple tenant themes.
- Only the planned representative workflows are included. Full pricing, refunds, cancellations,
  suppliers/procurement, administration, analytics, and settings remain separate work.
- Fable 5 and remediation closure must precede merging. After integration, repeat real production
  lint, TypeScript, builds, relevant tests, role-access/E2E journeys, mobile/RTL/accessibility, PWA,
  and material performance/bundle checks.

## Repository isolation

Design branch: `codex/astra-ui-concept`. Baseline:
`aa5185edb493d0f3f3c779c64da337b28b21a7fe`.
Changes are confined to `docs/design-references/` in the separate managed worktree. No tracked
production or audit files were changed; the original remediation HEAD and its pre-existing
untracked `docs/UI/` and `docs/mentor-defense/` remain unchanged.

`graphify update .` was run in the design worktree using AST-only extraction. Its ignored local
output is supplementary navigation, not a SHA-verified audit artifact for this uncommitted concept.
No graph results were used to establish security or financial correctness. No commit, push, merge,
phase completion, deployment, or revision of frozen remediation evidence occurred.

## Public-entry extension — 2026-09-22

The landing and sign-in design extension is documented in `../PUBLIC_ENTRY.md`.
`tests/entry.cjs` passed 87 browser assertions across 360/390/768/1440px in EN/AR, including
axe WCAG A/AA scans and synthetic form states. `tests/verify.cjs` passed all 145 existing
checks again; `tests/edge.cjs` passed its 8 existing checks again. Total: 240 passing assertions.
ESLint and JavaScript syntax checks passed. These are prototype checks, not production regression.
Actual renders: `screenshots/entry-*.png`. Machine-readable evidence: `tests/entry-results.json`.
The review caught and corrected hash-navigation screen selection, a narrow Arabic header, and
a decorative parcel overlapping an action label; the parcel was removed.
