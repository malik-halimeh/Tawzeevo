# Daylight public entry — design extension

Date: 2026-09-22. Status: implemented as an isolated design prototype, pending visual approval.

## Intent and scope

The public landing page should explain Tawzeevo through the distributor's working day. The sign-in page should make returning to work feel familiar and clearly distinguish business sign-in from customer guest ordering. This extension follows the existing Daylight tokens, local IBM Plex fonts, and three-node Tawzeevo mark.

Open `prototype/welcome.html` for the landing page and `prototype/welcome.html#signin` for sign-in. The public-entry pages link to the existing sample workspace; the workspace preview title links back to the landing page.

This change is entirely under `docs/design-references/`. No production routes, application code, authentication, APIs, dependencies or schemas were modified. No implementation was delegated.

## Architecture assessment

Direct source inspection at baseline `aa5185edb493d0f3f3c779c64da337b28b21a7fe` establishes:

| Existing source | Finding | Future integration boundary |
|---|---|---|
| `apps/operations-web/src/App.tsx` | `/` redirects to `/stats`; `/login`, `/register`, and recovery routes already exist. | Render a presentation-only home component at `/` using the existing React Router. Keep `/stats` accessible. No new routing framework or backend service is necessary. |
| `apps/operations-web/src/pages/PublicStatsPage.tsx` | Statistics use existing public queries. | Keep the existing page and queries. Link to them secondarily rather than featuring them as the product introduction. Do not add invented marketing counters. |
| `00_PROJECT_CONTRACT.md`, Public statistics; `PHASE_01.md`, Public statistics | Required public statistics remain part of the contract. | De-emphasizing statistics does not authorize removing them or their endpoints. |
| `apps/operations-web/src/pages/AuthPages.tsx`, `LoginPage` | Email/password, validation, loading, error presentation, authenticated redirects and requested destination handling already exist. | Apply the layout and translated copy around the existing form and handlers. Preserve admin/workspace/requested-path destinations and all auth semantics. |
| `AuthPages.tsx`, `ForgotPasswordPage` and `ResetPasswordPage` | Recovery already exists; the response is enumeration-safe. | Preserve actual provider requests, token handling, throttles and generic responses. The prototype's timer is not authentication code. |
| `AuthPages.tsx`, `RegisterPage` | Registration is already implemented. | Keep its route, fields, validations and account lifecycle. No new onboarding or automatic business approval. |
| `apps/operations-web/src/components/AppShell.tsx`, `BrandMark`, `PublicHeader` | Existing wordmark and public navigation. | Reuse the mark and language controls; preserve authenticated navigation behavior. |
| Existing storefront and owner order workflows | Guest orders, owner confirmation and owner-controlled dates are established. | Public copy describes these capabilities without tracking, stock, customer-selected dates or automatic payment claims. |

This is a bounded frontend presentation change, with a small root-route adjustment at production integration. It does not require architectural changes. Production integration still requires source review, frontend checks and critical-journey regressions; this design extension does not certify that future integration.

Maturity assessment: existing production route/auth/form patterns are established (M2 for this surface). New composition and visual choices are A1 design work retained by the Design & Planning Agent. Existing financial and authentication behavior stays authoritative and outside this task.

## Composition

- Landing: product statement, concise explanation, sign-in action, illustrative order-to-delivery panel, three concrete capabilities, sole-owner/team context, secondary statistics link.
- Signature: a restrained family of local line icons (shop, document, parcel, van, customer, sun), connected by a dashed illustrative path on the sign-in panel. It represents a working day, not a geographic route or tracking interface.
- The decorative panel has white icons on cobalt with a small citron label. The label is brand decoration, not payment/delivery success or a warning.
- The primary form has email/lock icons, a labelled password visibility button, recovery and registration affordances, and a short explanation directing customers to their supplier's storefront.
- English display headings use IBM Plex Sans semibold; Arabic uses IBM Plex Sans Arabic semibold with more line height. The established brand is retained, with no permanent logo redesign.
- Palette: porcelain `#F5F7FA`, white `#FFFFFF`, ink `#172A3A`, cobalt `#2455D6`, mist `#E7EEF8`, citron `#E5EF92`; muted text `#526477`, error `#A72E3E`, success `#216346`.

## Responsive and interaction rules

- At 700px and below, the landing stacks copy and illustration. The sign-in form precedes its illustration. Redundant header links disappear; the wordmark still returns home. Main actions are at least 48px tall, with 16px inputs/body copy.
- Above 700px, the sign-in illustration and form sit beside one another; the form remains approximately 410px wide. Large desktop layouts use 1200px content width.
- Arabic mirrors layout and action arrows. Email/password inputs retain LTR direction. The decorative diagram does not encode reading-order-dependent business states.
- No fixed footer or action overlay covers the sign-in inputs. The document scrolls naturally in a short viewport, with safe-area footer padding. Physical software-keyboard behavior still needs device testing.
- Navigation moves focus to the main region. Validation focuses the first invalid field and exposes its error through `aria-describedby` and `aria-invalid`. The visibility toggle has a changing accessible label and pressed state. Dialog Escape closes and restores focus.
- Only brief hover transitions; reduced-motion removes them. No ambient animation, count-up metrics or delayed reading of values.

## Synthetic preview boundaries

- Only `rami@example.invalid` / `daylight-demo` are accepted by the simulated form. The visible notice instructs reviewers not to enter real credentials. There is no authentication, request, storage or service worker; CSP blocks connections and form submissions.
- The preview toolbar selects normal, sign-in failure, offline or sustained loading. Submit demonstrates the selected state. Reset cancels timers and restores sample fields. Changing preview state or language also resets the sample form; this is a preview convenience, not specified production behavior.
- Successful preview leads to the existing fictional owner workspace with an explicit statement that no account was signed in. Production must retain role-aware destinations, not this sample redirect.
- Password recovery has validation and a generic simulated result. No email is sent. Registration and statistics links open explicit scope dialogs because those pages are not rebuilt here.
- The landing's sample-workday link, preview toolbar, demo values and boundary dialogs are reviewer tools. They must not silently become production features. Remove them at integration or use an independently approved existing demo mechanism.

## Verification

Run from the design worktree with the existing repository tooling available:

```powershell
$env:TAWZEEVO_TOOL_ROOT = 'C:\Users\malik\Desktop\DigitalHub\Tawzeevo'
node docs/design-references/prototype/serve.cjs
# In another terminal:
node docs/design-references/prototype/tests/entry.cjs
node docs/design-references/prototype/tests/lint.cjs
```

`prototype/tests/entry-results.json` records the actually executed 87 browser assertions. These cover both pages at 360, 390, 768 and 1440px in English/Arabic, correct view selection, page overflow, text bounds, axe WCAG A/AA scans, validation/failure/offline/loading/success/recovery, scope dialogs, focus restoration, keyboard navigation, short viewport, mixed direction, reduced motion and absence of network/storage/service workers. Actual full-page screenshots are in `prototype/screenshots/entry-*.png`.

These checks apply to the prototype only. They do not replace physical-phone, software-keyboard, screen-reader, Safari, production authentication, accessibility or PWA regression testing.

The remediation branch and audit evidence remain unchanged. No merge or deployment is authorized by this design preview, and Fable 5/remediation closure remains the integration gate.
