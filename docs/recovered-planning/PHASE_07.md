# PHASE_07.md — Owner/Driver Delivery Operations, Locations, Route Assistance

## Phase objective
Support Cash Van field operations for:
1. one-person businesses where the owner personally operates the Cash Van; and
2. larger tenants with separate least-privileged drivers.

Owner-as-operator never requires a second account or duplicate membership.

Customer-facing delivery tracking remains prohibited.

## Start gate — Gate F
Do not begin Phase 7 until:
- delivery task model locked;
- owner-as-operator rules locked;
- owner/driver assignee authorization locked;
- single-owner/no-driver default locked;
- driver least-privilege projection locked;
- location rules locked;
- route input contract locked;
- **current online routing/geocoding provider explicitly approved by user**.

ADR-027 must be finalized immediately before Phase 7 using then-current Lebanon coverage, pricing, quota, privacy, reliability.

Do not choose provider silently.

---

# A. Eligible delivery operator

Use neutral assignee membership semantics such as:
```text
assigned_membership_id
```

Eligible active role:
- `owner`;
- `driver`.

Rules:
1. owner may assign self;
2. owner may assign active driver;
3. exactly one active usable owner + zero active drivers → delivery defaults to owner and UI does not require driver setup;
4. multiple eligible memberships → owner chooses;
5. owner may reassign;
6. reassignment audited;
7. driver cannot assign/reassign unless later explicitly approved;
8. actual assignee/performer recorded.

One membership keeps one role. No duplicate owner+driver membership for same person.

---

# B. Delivery task lifecycle

Confirmed order becomes eligible.

Do not create task merely because an unconfirmed order exists.

Task:
- id;
- tenant_id;
- order_id;
- invoice_id;
- customer_id;
- assigned_membership_id;
- current owner-set delivery date;
- route_sequence nullable;
- internal state;
- amount-to-collect projection if needed;
- timestamps/version.

States:
```text
ASSIGNED
COMPLETED
CANCELLED
```

Transitions:
- ASSIGNED→COMPLETED by authorized assigned owner/driver;
- ASSIGNED→CANCELLED by owner/system cancellation;
- terminal afterward unless future explicit reopen.

Never expose these states as customer tracking.

---

# C. Owner-as-operator

Owner:
- keeps full owner permissions;
- may be delivery assignee;
- uses task/location/route features directly;
- may complete task;
- may assign/reassign self/driver;
- may view tenant delivery operations per owner authority.

No identity switching or second driver account.

---

# D. Driver least privilege

Driver receives assigned/necessary only:
- assigned tasks;
- required customer name/phone/address/location;
- relevant invoice items;
- amount to collect;
- route/operational data;
- authorized Phase 6 pickup need.

Driver never receives:
- supplier prices/cost;
- profit/margin;
- broad owner analytics;
- unrelated customers/orders/tasks;
- sensitive tenant settings;
- platform admin data.

Server API, bootstrap, IndexedDB, and local cache enforce this. UI hiding alone is insufficient.

---

# E. Location

Store:
- latitude;
- longitude;
- captured_at;
- accuracy_meters nullable;
- source `gps | manual | geocoded`;
- confirmation/actor where relevant.

Rules:
- exact customer location only owner + assigned/authorized operator;
- driver updates only within assigned work/permission;
- confirmed location never overwritten automatically;
- operator confirmation required;
- worse reading does not replace better confirmed location silently;
- no continuous driver GPS tracking/history;
- route history retains only needed stop/order data.

---

# F. Offline route suggestion

Deterministic heuristic:
1. current/selected origin;
2. nearest-neighbor stop selection;
3. simple 2-opt improvement;
4. manual reorder.

Label:
```text
offline stop-order suggestion
```

Never claim guaranteed optimal road route.

---

# G. Online route assistance

Use only user-approved provider via abstraction.

Requirements:
- Lebanon coverage verified;
- quota/error handling;
- privacy-conscious payload;
- timeout/retry;
- provider outage fallback to offline heuristic/manual order;
- core delivery completion cannot depend on provider availability.

Manual reorder remains.

---

# H. Nearby supplier reminder

If authorized owner/driver is near supplier and procurement need exists:

Owner may see:
- supplier identity/location;
- operational need;
- price/history/recommendation.

Driver may see:
- supplier identity/location;
- assigned pickup need.

Driver never sees price/cost history.

No background continuous location tracking beyond approved checks.

---

# I. Offline behavior

Use Phase 4 sync:
- assigned task projection;
- expected version;
- completion command;
- authorized location update;
- route sequence/manual reorder;
- conflict handling;
- reconnect exactly once.

Owner cache may contain owner-authorized data.
Driver cache strictly limited.

Revoked membership/tenant suspension purges/locks access.

---

# J. API/frontend scope

Canonical groups:
```text
/api/v1/delivery-tasks
/api/v1/routes/suggest-order
```

Authorization validates tenant, membership, role, assignment, lifecycle, version.

Owner UI:
- tasks;
- self/default assignment;
- driver assignment/reassignment;
- date/order/customer context;
- route planning/manual reorder;
- location review/correction;
- completion;
- nearby supplier reminders;
- offline state.

Driver UI:
- My Work only;
- required contact/location/invoice collection;
- route;
- completion;
- location correction if allowed;
- assigned procurement pickup;
- no owner financial/supplier-price UI.

Single-owner UX should be "My route / My deliveries", not forced driver setup.

EN/AR/RTL/accessibility mandatory.

---

# K. Migration requirements

Add migrations for:
- delivery tasks;
- neutral assigned membership FK;
- state/version;
- route sequence/order persistence as needed;
- missing location metadata;
- constraints/indexes/RLS.

If an old driver-only FK exists, migrate safely to neutral membership semantics.

Never edit applied migrations.
Zero + Phase 6 upgrade pass.

---

# L. Tests

## Owner-as-operator
- one owner/zero drivers works;
- task defaults to sole owner where applicable;
- owner self-assigns/completes;
- no second account/membership.

## Assignment
- owner assigns active driver;
- owner reassigns/audit;
- inactive/revoked/cross-tenant assignee rejected;
- driver cannot assign/reassign.

## Driver security
- assigned task visible;
- other driver task denied;
- unrelated customer/order denied;
- supplier price/profit/analytics/settings denied;
- cache only allowed projection.

## Lifecycle/location
- task only from confirmed eligible order;
- valid transitions;
- terminal behavior;
- cancellation integration;
- accuracy/confirmation;
- confirmed location not silently overwritten;
- unassigned driver denied.

## Route/supplier
- deterministic offline heuristic;
- manual reorder;
- online provider success;
- timeout/error fallback;
- privacy rules;
- owner price visible;
- driver price hidden.

## Offline/public
- offline task completion/reconnect;
- idempotent;
- version conflict;
- revoke offline→reject/purge;
- tenant suspension;
- no delivery/driver tracking in customer projection.

---

# M. Milestones

## P7-M1 — Delivery tasks + owner/driver assignment authorization
PRECONDITION: Gate F + provider approval recorded.

Implement neutral task assignee, state model, owner self/default assignment, driver assignment/reassignment, audit, owner core UI/API, migration/RLS.

Acceptance:
- sole owner/zero drivers works;
- owner self-operates;
- driver assignment protected;
- no driver-only schema assumption.

STOP.

## P7-M2 — Owner/driver operational API, least-privilege projection + offline updates
Implement owner actions, assigned-only driver API, driver bootstrap/cache, offline completion/version conflicts, procurement pickup projection, authorization matrix.

Acceptance:
- unrelated data denied;
- owner secrets absent driver API/cache;
- offline completion exactly once.

STOP.

## P7-M3 — Locations, route assistance, nearby supplier reminders
Implement location capture/correction, deterministic heuristic/manual reorder, approved provider, fallback, nearby supplier role projection.

Acceptance:
- confirmed location safe;
- route deterministic offline;
- provider outage safe;
- driver price never exposed.

STOP.

## P7-M4 — Field E2E/security/accessibility freeze
No new scope.

Complete assignment matrix, synthetic owner/driver scenarios, offline/revocation, provider failure, no-tracking, EN/AR/RTL/accessibility, migrations/OpenAPI/docs/ADR.

Acceptance:
- DoD passes;
- no critical/high field authorization/privacy defect.

Mark Phase 7 COMPLETE and STOP. Do not start Phase 8.

---

# N. Definition of Done

- single-owner business works with zero drivers;
- owner can be recorded assignee;
- owner can assign/reassign driver;
- driver cannot assign/reassign;
- assigned-only access enforced server/local;
- owner secrets absent driver payload/cache;
- task lifecycle correct;
- location update safe;
- offline completion syncs;
- offline route/manual reorder works;
- approved provider works with fallback;
- nearby supplier respects price privacy;
- customer sees no tracking;
- RLS/cross-tenant passes.

## Explicit exclusions
No continuous GPS tracking, customer driver map/tracking, driver product catalogs, driver referral analytics unless approved, driver supplier prices/profit, unapproved routing provider, or claim of optimal offline road routing.

First milestone to implement: **P7-M1 — Delivery tasks + owner/driver assignment authorization**
