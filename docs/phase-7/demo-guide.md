# Phase 7 demo and presentation guide

This guide demonstrates only completed Phase 7 behavior: deliveries for a sole owner, drivers
with least privilege, offline completion, locations with provenance, stop-order suggestions with
manual reorder, and the nearby supplier reminder. Use synthetic data only.

## Prepare the environment

1. Follow the root `README.md` local setup. Never demonstrate against production data.
2. Apply migrations and confirm revision `20260919_0026` is the current Alembic head.
3. Sign in as the active owner of an approved synthetic business with two customers that have
   coordinates and two confirmed invoices (supplier cost recorded).
4. Register a second Tawzeevo account to play the driver (registration only; the owner attaches
   it during the demo).
5. Optional: set `OPENROUTESERVICE_API_KEY` for the online route; without it the offline
   suggestion is shown and labelled.

## Recommended presentation route

### 1. One-person business

**Deliveries** → the screen says *My deliveries* and asks for no driver. Create a delivery from
a confirmed invoice, open *My route* below, press *Suggest stop order*, move a stop by hand,
save. Mark a stop delivered. Say: completed and cancelled are final (D-063); a mistake gets a new
delivery for the same invoice; nothing here touches the invoice.

### 2. A driver joins

Open *Team (drivers)*, add the driver by e-mail. The title becomes *Deliveries* and a *Deliver by*
choice appears. Create a delivery for the driver; reassign it once and say the reassignment is
audited.

### 3. What the driver sees

Sign in as the driver in another window: *My route* with the assigned stop only — contact,
address, map link, items, amount to collect. No supplier tab, no prices, no other customers.
Say: the API, the sync bootstrap and the sync feed enforce this, not only the screen.

### 4. Offline completion

Driver window: switch the browser to *Offline* (developer tools), mark the stop delivered — the
completion is saved on the device. Back online, *Sync now* — it applies once. Show the owner's
list: the stop is delivered, performed by the driver.

### 5. Locations and the nearby reminder

*Use my position for …* with the browser's location permission: say the rule (D-061) — a confirmed
location is never replaced without confirming again; a worse reading never replaces a better one;
one current reading per customer, no history, no tracking. *Suppliers near me*: suppliers within
1.5 km that have an open pickup need; the driver sees the need without prices.

### 6. Revocation

Owner: *Revoke* the driver. The driver's next request is refused and the device is revoked for
sync.

## Security expectations (say them out loud)

- A driver never receives supplier prices, costs, profit, analytics, settings or another
  member's tasks — server, bootstrap, feed and cache all enforce it.
- Customers see no delivery tracking; the provisional order page is unchanged.
- The position is read once when a button is pressed; nothing runs in the background.
- Routing sends coordinates only to the provider, and the provider's absence changes nothing
  about completing deliveries.

## Limitations to state plainly

- Stop-order suggestions are suggestions, never a guaranteed best road route.
- No typed-address geocoding yet; no Google adapter (key slot only).
- A physically offline device learns about revocation on its next contact.
