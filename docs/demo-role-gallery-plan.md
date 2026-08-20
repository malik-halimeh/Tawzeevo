# Reversible role demo gallery plan

## Purpose

Provide one polished, public, interactive demonstration of Tawzeevo's guest, customer,
owner, and driver perspectives without implementing Phase 2 or any later-phase backend
behavior.

This is an ancillary demonstration workstream. Phase 1 remains complete and Phase 2 remains
locked until the user explicitly says `Start Phase 2`.

## Locked role semantics

| Perspective | Demonstration meaning | Not permitted |
|---|---|---|
| Guest | An unauthenticated storefront visitor browsing synthetic catalog data. | A stored role, account, or authenticated session. |
| Customer | A guest who supplied checkout details and is viewing a synthetic order-facing state. | A `users` row, password, customer-login system, direct cancellation, or delivery tracking. |
| Owner | An authenticated `client` user with an `owner` tenant membership. The owner may also operate the Cash Van. | A new system role, duplicate driver membership, or platform-admin access by implication. |
| Driver | An authenticated user with a least-privileged `driver` tenant membership and assigned operational work. | Owner controls, reassignment rights, platform administration, or unrelated tenant-private data. |

No new role enum, credential, authorization rule, or public product contract may be introduced
for the gallery.

## Isolation architecture

- Gallery entry point: `/demo` in `apps/operations-web`.
- Build-time gate: `VITE_DEMO_PREVIEW=true`.
- The demo entry is selected before `AuthProvider` mounts, so opening `/demo` performs no
  refresh, login, API, or database request.
- All records are clearly labeled synthetic fixtures kept under an isolated demo directory.
- Demo state is memory-only and resets on reload. It must not use cookies, localStorage,
  sessionStorage, IndexedDB, Supabase, or the FastAPI service.
- Demo code must not import `apiRequest`, `fetch`, authentication helpers, or server-state
  hooks.
- Every screen carries a visible statement that it is a synthetic preview and saves nothing.
- Existing EN/AR and LTR/RTL foundations are reused without adding a new dependency.
- Existing production routes and authentication behavior remain unchanged.
- No backend file, migration, database row, secret, or deployment credential is changed.

## Design direction

Reading: an interactive product showcase for evaluators, preserving Tawzeevo's existing
route-map visual language.

- `DESIGN_VARIANCE: 5`
- `MOTION_INTENSITY: 3`
- `VISUAL_DENSITY: 6`
- Preserve the existing native-CSS token system, typography, orange route accent, radii, and
  accessible focus treatment.
- Use semantic controls, visible focus, adequate contrast, keyboard navigation, reduced-motion
  support, responsive layouts, and EN/AR parity.
- Use real interactive components, not screenshots or claims that future behavior is complete.
- Do not add a UI framework, icon package, animation library, image provider, or design-system
  dependency.

## Milestones

One user `continue` executes exactly one milestone. Every milestone stops after its validation
report. A failing required check blocks completion.

### DRG-M1 - Isolation boundary and gallery shell

Implement the gated `/demo` boot path, synthetic-preview banner, role selector, reset behavior,
and isolated file/style structure. The four role choices may show boundary copy only; detailed
role views belong to later milestones.

Required validation:

- Tests prove `/demo` makes zero network calls and mounts without `AuthProvider`.
- Tests prove normal `/login`, `/register`, and `/stats` behavior is unchanged.
- Tests prove the disabled flag makes the demo unavailable.
- Keyboard and accessible-name checks cover the role selector and reset control.
- `npm run lint:operations` passes.
- `npm run typecheck:operations` passes.
- `npm run test:operations` passes.
- `npm run build:operations` passes.
- `git diff --check` passes.
- No backend, migration, lockfile, or dependency change exists.

### DRG-M2 - Guest and customer perspectives

Add a synthetic guest catalog and a customer-facing order preview. The guest can demonstrate
category/product browsing and a memory-only basket/checkout transition. Checkout uses the
locked name, phone, and address fields. The resulting customer view permits a cancellation
request but never direct cancellation or delivery tracking.

Required validation:

- Tests cover guest-to-customer local state, required checkout fields, and reset-on-reload
  behavior.
- Tests prove neither perspective renders login/account behavior.
- Tests prove the customer action is `request cancellation`, not `cancel`.
- Tests prove no customer-facing delivery tracking is rendered.
- Tests and text scans prove there is no stock, availability, or quantity-on-hand language.
- EN/AR and LTR/RTL component tests pass, including LTR phone presentation in Arabic.
- The complete frontend lint, type, test, and production-build checks pass.
- Static isolation scans find no API/auth/storage imports in demo code.

### DRG-M3 - Owner perspective

Add a synthetic owner workspace showing the approved tenant context, customer lookup, catalog
pricing, draft invoice presentation, and owner-as-operator assignment. It is a visual preview,
not an authoritative invoice engine or live tenant operation.

Required validation:

- Tests prove the owner is presented as a tenant membership, not a new system role.
- Tests prove one owner may be the operational assignee without a duplicate driver account.
- Tests cover product piece/box presentation, barcode, customer context, and draft status.
- Tests prove no stock/availability behavior and no confirmed-ledger claim is shown.
- EN/AR, keyboard, responsive component, and accessible-label checks pass.
- The complete frontend lint, type, test, and production-build checks pass.
- Static isolation scans find no API/auth/storage imports in demo code.

### DRG-M4 - Driver perspective and least privilege

Add a synthetic driver workspace limited to assigned delivery work and the minimum operational
details needed for the preview. Do not choose or simulate a routing provider.

Required validation:

- Tests prove driver content contains assigned work but no reassignment control.
- Tests prove owner, platform-admin, supplier, broad financial, and unrelated customer controls
  are absent.
- Tests prove the gallery does not display customer-facing delivery tracking.
- Tests prove no map/provider dependency or provider-specific claim is introduced.
- EN/AR, keyboard, responsive component, and accessible-label checks pass.
- The complete frontend lint, type, test, and production-build checks pass.
- Static isolation scans find no API/auth/storage imports in demo code.

### DRG-M5 - Cross-role hardening, deployment, and teardown proof

Polish the complete gallery, add presentation documentation, enable it in the Render frontend
build, deploy, and verify the public route while keeping all existing live routes healthy.

Required validation:

- `npm run check` passes in full.
- Both flag states build successfully; the disabled state exposes no demo route.
- Browser checks cover desktop and mobile widths, EN and AR, keyboard-only navigation, visible
  focus, reduced motion, overflow, and readable contrast.
- Network instrumentation proves the complete `/demo` journey makes zero API/database requests.
- Storage checks prove the gallery writes no cookie, localStorage, sessionStorage, or IndexedDB
  data.
- Existing live `/stats`, `/login`, and `/register` routes remain healthy after deployment.
- The live `/demo` route renders all four perspectives and visibly identifies synthetic data.
- Repository scans confirm no secret, credential, assistant-branding, backend, migration, or
  dependency change.
- A teardown checklist confirms removal requires only the demo directory, boot selection,
  translations/styles, environment flag, tests, and demo documentation. No data cleanup or
  migration rollback is required.

## Phase 2 boundary

The gallery must never become the source of truth for Phase 2. When Phase 2 starts:

1. treat the phase contract and backend behavior as authoritative;
2. do not copy synthetic demo state transitions into production services;
3. either keep the gallery isolated or remove it using the teardown checklist;
4. never migrate demo fixtures into PostgreSQL;
5. never count gallery behavior as phase completion evidence.

## Milestone report format

```text
Milestone: <DRG-M#> <name>
Status: COMPLETE | BLOCKED

Implemented:
- ...

Validation:
- test/check -> PASS/FAIL

Isolation:
- API/database/storage writes -> NONE | details
- backend/migrations/dependencies -> UNCHANGED | details

Next:
- <next demo milestone>

User command:
continue
```
