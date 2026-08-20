# Isolated role gallery

The public `/demo` route is a synthetic, frontend-only presentation of Tawzeevo from four
perspectives. It is separate from Phase 1 evidence and does not implement Phase 2.

Public URL: `https://tawzeevo-malik-halimeh.onrender.com/demo`

## Presentation walkthrough

1. Start on **Guest**. Filter the published catalog, add a product, and open the guest checkout.
2. Enter synthetic name, phone, and address values to move into the **Customer** order view.
3. Request cancellation and point out that the request waits for business review; the customer
   cannot directly cancel and receives no delivery-tracking surface.
4. Open **Owner**. Show the active tenant, `Client` system type, `Owner` tenant membership,
   customer lookup, barcode resolution, piece/box prices, draft invoice, and assignment to the
   same owner membership without driver setup.
5. Open **Driver**. Expand an assigned stop and show the minimum contact, invoice reference, and
   note. The view has no reassignment, platform, supplier-cost, or broad analytics controls.
6. Switch to Arabic and repeat one interaction to demonstrate RTL layout and LTR phone/barcode
   presentation. Use **Reset preview** to clear the memory-only journey.

Every perspective displays the synthetic-preview banner. Nothing on `/demo` is evidence of live
business behavior.

## Isolation contract

- `VITE_DEMO_PREVIEW=true` enables the route at build time; `false` returns the preview-unavailable
  screen.
- The `/demo` branch is selected before authentication and server-state providers mount.
- Fixtures and interaction state live only under `apps/operations-web/src/demo` and React memory.
- The gallery makes no API/database request and writes no cookie, local storage, session storage,
  or IndexedDB data.
- It introduces no credential, role enum, backend route, database row, migration, or dependency.
- Guest/customer remain unauthenticated perspectives. Owner/driver remain tenant memberships.

## Local presentation

Set `VITE_DEMO_PREVIEW=true`, run `npm run dev:operations`, and open
`http://localhost:5173/demo`. Restore the flag to `false` when the gallery should not be exposed.

## Teardown checklist

Removing the gallery requires only these reversible source/configuration changes:

- [ ] Delete `apps/operations-web/src/demo/`.
- [ ] Remove the demo imports and `/demo` boot branch from
      `apps/operations-web/src/ApplicationRoot.tsx`.
- [ ] Remove the isolated-gallery cases from
      `apps/operations-web/src/ApplicationRoot.test.tsx`.
- [ ] Remove `VITE_DEMO_PREVIEW` from `.env.example` and `render.yaml`.
- [ ] Remove this document, its README link, and `docs/demo-role-gallery-plan.md` if the approved
      plan is no longer needed.
- [ ] Remove the completed `DRG` workstream lines from `03_IMPLEMENTATION_STATUS.md` when normal
      phase execution resumes.
- [ ] Run `npm run check` and verify `/login`, `/register`, and `/stats` remain healthy.

No database cleanup, migration rollback, backend change, secret rotation, account deletion, or
hosted PostgreSQL action is required.
