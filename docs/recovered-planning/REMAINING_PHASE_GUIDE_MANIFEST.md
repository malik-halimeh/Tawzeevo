# Tawzeevo Remaining Phase Guide Manifest

These files are newly generated implementation-grade phase guides derived from the current authoritative project materials:

- current `00_PROJECT_CONTRACT.md`;
- current `04_DECISIONS.md`;
- current `02_PHASE_INDEX.md`;
- frozen `cash-van-production-roadmap-v2.1.1.md`.

They are not presented as verbatim recovered originals. They are the consolidated future implementation specifications to restore the missing phase-file system while preserving the frozen contracts and later approved decisions.

## Files and declared milestone counts

- `PHASE_03.md` — 6 milestones
- `PHASE_04.md` — 6 milestones
- `PHASE_05.md` — 5 milestones
- `PHASE_06.md` — 5 milestones
- `PHASE_07.md` — 4 milestones
- `PHASE_08.md` — 4 milestones
- `PHASE_09.md` — 6 milestones
- `PHASE_10.md` — 3 milestones

## Intentionally unresolved/late-bound decisions

These are preserved as gates rather than silently invented:

1. Phase 4: exact Google OAuth scope must be explicitly approved before the Google backup milestone if it is not already recorded.
2. Phase 7: the current online routing/geocoding provider must be explicitly approved immediately before Phase 7.
3. Phase 9: concrete deployment/hosting provider choices must be recorded before staging deployment rehearsal if not already approved.
4. Phase 10: machine learning is conditional. The statistical baseline comes first; ML is adopted only with measured improvement.

## Later approved changes incorporated

- owner may personally operate the Cash Van without a second driver account/membership;
- neutral owner/driver delivery assignment;
- single-owner/no-driver workflow;
- platform-admin tenant lifecycle boundary;
- temporary non-payment suspends rather than deletes tenant data;
- tenant storefront contains only tenant-adopted or tenant-created published products;
- tenant owner controls tenant product selling prices;
- master catalog never automatically publishes a product;
- tenant may create products missing from the master catalog;
- `is_published` is visibility only, never availability;
- no stock/inventory/warehouse system;
- no customer-facing driver tracking;
- supplier payments remain aggregate supplier-ledger payments, not per-purchase allocations;
- no automatic customer merge;
- financial history remains immutable;
- public Git repository must never contain credentials/private production data.
