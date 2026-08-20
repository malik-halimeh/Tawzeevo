# Future phase sequence

Phase 1 is complete. The items below are approved sequence summaries, not claims that later functionality exists.

| Phase | Contracted objective | Required start condition |
|---|---|---|
| 2 | Tenant, customer, catalog, barcode, grade, and pricing core | Explicit `Start Phase 2`; Phase 1 Definition of Done complete |
| 3 | Invoice, ledger, payment, and debt financial core | Gate C financial contracts locked and tested |
| 4 | Offline-first sync and encrypted Google Drive backup/export | Gate D sync contracts; user-approved Google OAuth scope/folder model |
| 5 | Linked bilingual guest storefront | Gate E order, idempotency, capability-token, privacy, and notification contracts |
| 6 | Supplier price history, procurement, and supplier debt | Phase 5 Definition of Done |
| 7 | Owner/driver delivery operations, locations, and route assistance | Gate F delivery/location rules plus explicit routing-provider approval |
| 8 | Analytics, lifetime statistics, and tenant branding | Gate G metric, revision, currency, and timezone definitions |
| 9 | Production hardening, deployment, and pilot | Phases 1–8 Definitions of Done |
| 10 | Optional season/month product forecasting | Reliable production-like historical data |

No later phase begins from a generic `continue`. The next authorized transition requires the exact user command `Start Phase 2`; its own phase file and gate are read only at that time.
