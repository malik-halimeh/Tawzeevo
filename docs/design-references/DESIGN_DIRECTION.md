# Daylight: draft design direction

Status: interactive concept implemented; awaiting visual approval. This is not a production UI freeze.

The public landing/sign-in extension requested on 2026-09-22 is documented in
[PUBLIC_ENTRY.md](PUBLIC_ENTRY.md), with its own rendered screenshots and browser checks.

The owner approved this prototype's scope on 2026-09-21. It follows D-081 and the Design-Agent
Contract. Product contracts and recorded decisions remain authoritative. The earlier UI chat and
generated screenshots were treated as non-binding research; none of their inventory, credit-limit,
tax, permission, or invoice-locking assumptions were adopted.

## Intent and visual system

Lead with an owner personally running deliveries on a phone. Desktop expands the same job into a
list and detail workspace. The storefront shares the design vocabulary while presenting the
tenant's business identity. Tone: clear, capable, welcoming. Distinctiveness comes from coordinated
type, the date tab, the ordered stop list, and the attached action area, rather than ornamental charts.

| Token | Value | Use |
|---|---|---|
| Paper | `#F5F7FA` | Page canvas |
| Surface | `#FFFFFF` | Documents, records, forms |
| Ink | `#172A3A` | Primary content |
| Muted | `#586A7C` | Supporting copy |
| Blue | `#2455D6` | Primary actions and active selection |
| Blue deep | `#173B98` | Primary hover |
| Mist | `#E7EEF8` | Selection and attached action context |
| Citron | `#E5EF92` | Small brand accent with ink text |
| Line | `#DBE2EB` | Quiet structural separators |
| Success | `#216447` on `#E9F5EE` | Accepted/completed states |
| Warning | `#815108` on `#FFF3D6` | Connection and queued-work warnings |
| Error | `#A32D3B` on `#FDEEF0` | Failed requests and overdue balance |

IBM Plex Sans and IBM Plex Sans Arabic are locally hosted; their OFL notices accompany them.
Body text is 16px. Supporting labels use 12–14px. Phone headings are 28–34px, desktop primary
headings up to 44px. Arabic receives additional line height and no letter spacing. Amounts use
tabular numerals, explicit currency codes, and isolated LTR spans. Color is always supplemented by
a state label. Do not infer a financial state from an accent color.

Primary touch targets are at least 48px tall. Regular controls use 8–9px corners, records 13–16px,
and dialogs 15–18px. Lists use separators rather than stacked decorative cards. Motion is limited
to 150ms control feedback; the reduced-motion rule removes it. Amounts never count up theatrically.

## Composition and interaction

- Owner navigation: Work, Customers, Invoices, More. Driver navigation: My work, Sync. These are
  presentation groupings for this bounded prototype, not new authorization roles or backend routes.
- Work pairs the ordered stop list with a selected delivery. Only completed deliveries fill the
  progress marks. Queued updates are not represented as accepted completions.
- Customer detail puts identity and the single selected currency's balance above account activity.
  Receipts and confirmed invoices are distinct entries. A payment does not silently complete a stop.
- An invoice draft is a working form; a confirmed invoice is a readable document. Confirmed records
  retain Create revision. Previous revision lines and totals remain independently viewable.
- The action area attaches customer context and the relevant amount to one primary action. The
  delivery version says Amount to collect; it never says payment received. On phones it sits above
  bottom navigation. On desktop it is the record footer.
- Storefront: catalog, product, basket, contact/address checkout, and acknowledgement with a
  provisional invoice. No login is required, and no delivery date is promised before owner review.
- Search edits only the results region, preserving focus. Returning to a list preserves search and
  scroll position. Dialogs use the native modal element, Escape, focus trapping, and focus return.
- Successful payments append one receipt. Failure retains the same pending payment identity and
  leaves balances unchanged. Retry is idempotent within the running preview.

## Responsive and bilingual rules

- At 1100px and above, use the operations rail and list/detail layout. Below 1100px, show one pane
  and persistent bottom navigation. Do not compress simultaneous panes onto a phone.
- On small detail views, remove the generic overview heading so the selected task gets the space.
- Product detail uses shrinkable grid columns on tablets and one column on small phones.
- Keep screen-edge padding at 18px on phones and expand to 42px for wide workspaces.
- Reserve bottom padding for fixed action/navigation regions and device safe areas. VisualViewport
  handling moves attached actions above a software keyboard and hides phone navigation while typing.
- Use logical spacing and layout properties. Mirror directional arrows, not product photos, phone
  numbers, currency codes, or invoice references. English and Arabic receive the same capabilities.
- The separate preview toolbar changes persona, language, synthetic network conditions, and
  empty/loading/error scenarios; it is not part of the production navigation proposal.

## Capability mapping and protected boundaries

Paths below are existing production references at baseline
`aa5185edb493d0f3f3c779c64da337b28b21a7fe`; the prototype does not import or modify them.

| Prototype behavior | Existing source / authority |
|---|---|
| Owner and driver delivery projections, contact and map links, queued completion | `apps/operations-web/src/components/MyWorkPanel.tsx`; Phase 7; product contract Location / driver |
| Ordered stops without customer tracking | `apps/operations-web/src/components/RoutePlanner.tsx`; Phase 7 |
| Customer identity, grades and piece/box products | `apps/operations-web/src/components/TenantWorkspace.tsx`; product contract |
| Invoice confirmation and immutable revisions | `apps/operations-web/src/components/InvoiceEditor.tsx`; product contract Invoice behavior |
| Stable payment retry intent | `apps/operations-web/src/api/financialIntent.ts`; product contract Financial truth |
| Catalog, guest cart/checkout and order acknowledgement | `apps/storefront-web/components/ProductGrid.tsx`, `CartControls.tsx`, `CartCheckout.tsx`, `OrderView.tsx`; Phase 5 |
| Tenant brand identity and contrast boundary | `apps/storefront-web/components/ShopFrame.tsx`, `apps/storefront-web/lib/theme.ts`; Phase 8 |
| Final design authority and production invariants | `04_DECISIONS.md` D-081; `05_DESIGN_REFERENCES.md`; `00_PROJECT_CONTRACT.md` |

No API, database, role, state-machine, permission, financial formula, security, or sync contract
changes are proposed by this implementation. Production server-authoritative amounts must replace
the synthetic fixture arithmetic. The static storefront demonstrates one valid tenant palette;
production integration must continue using the existing theme validation and contrast fallback.

The USD composition fixtures contain whole-quantity, fixed-price products without discount/markup
examples. A separate LBP customer and stop demonstrate currency separation; this sample catalog
has no LBP product prices. That is a fixture limitation, not a new customer or catalog policy.
Full pricing, refund, cancellation, supplier, and admin workflows remain outside this concept.

## Isolation, delivery, and handoff

The build lives on `codex/astra-ui-concept`, based on the verified remediation SHA above. The
remediation checkout, Fable 5 audit target, audit evidence, and owner-supplied untracked documents
were not changed. This branch must remain unmerged until the independent review and remediation
closure. No commits, pushes, releases, or deployment changes are part of this delivery.

Open [the prototype](prototype/index.html), [reproduction guide](prototype/README.md), or
[executed validation report](prototype/TEST_REPORT.md). The application is standalone HTML, CSS,
and JavaScript, and has no added runtime dependency. Data lives in memory and resets on reload.
The persona picker is a demonstration tool, not authentication; synthetic fixture source is public.

The implementation agent should carry the approved tokens and interactions into existing
components only after visual approval. Do not replace the frameworks or import a competing UI kit.
Broader administration, procurement, analytics, settings, and production PWA work follow separately.
After Fable 5 and remediation closure, reconcile against the corrected codebase and run fresh
production lint, TypeScript, component, E2E, role-access, accessibility, RTL, mobile, PWA, and
material bundle/performance checks. Prototype validation does not replace those gates.
