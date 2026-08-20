# Phase 1 demo and presentation guide

This guide demonstrates only completed Phase 1 behavior.

## Prepare the environment

1. Copy `.env.example` to `.env` and replace local placeholders. Never use production credentials for a demonstration.
2. Start PostgreSQL with `docker compose up -d postgres postgres-test`.
3. Apply migrations with `.\.venv\Scripts\alembic -c .\apps\api\alembic.ini upgrade head`.
4. Start the API:

   ```powershell
   .\.venv\Scripts\uvicorn tawzeevo_api.main:app --app-dir .\apps\api --reload
   ```

5. Start the operations client in another terminal with `npm run dev:operations`.
6. Confirm `http://localhost:8000/health`, `http://localhost:8000/docs`, and `http://localhost:5173` load.

## Bootstrap the first platform administrator

The command uses a hidden, confirmed password prompt and accepts no password argument:

```powershell
.\.venv\Scripts\python -m tawzeevo_api.cli.create_admin --first-name Platform --last-name Owner --email owner@example.com --phone "+96170123456" --city Beirut --age 30
```

## Create synthetic Cash Van demo rows

First register a client, submit its business application, and approve it as the platform administrator. In Swagger, call `GET /api/v1/platform/tenants` with the administrator bearer token and copy the approved tenant ID.

The seeder requires that tenant and its existing active owner. It does not create credentials, bypass onboarding, or accept private customer data by default:

```powershell
.\.venv\Scripts\python -m tawzeevo_api.cli.seed_demo --owner-email client@example.com --tenant-id 00000000-0000-0000-0000-000000000000 --customer-phone "+96170555444" --currency USD
```

Use synthetic demonstration values only. The command atomically creates one customer, category, piece-priced barcode product, and draft invoice, then refuses replay for that tenant.

## Presentation route

1. Open public statistics and show live API-backed count, average age, and top cities.
2. Switch to Arabic and point out full RTL layout with phone fields remaining LTR.
3. Register a client and explain that public registration cannot choose `admin`.
4. Sign in as the client, edit the profile, and submit a tenant application.
5. Sign in as the platform administrator and review the pending application.
6. Approve it, then show the new active tenant without giving the administrator tenant membership.
7. Set or extend the access period, suspend with a reason, and reactivate the same tenant.
8. In Swagger, sign in as the approved owner and show customer phone search, category listing, barcode product resolution, and the seeded draft invoice.
9. Suspend the tenant and show that the same owner is denied business context; reactivate and show that the stored rows remain.
10. Close by stating the Phase 1 boundary: the draft invoice is not the later immutable confirmed-invoice/ledger engine, and there is no stock or availability system.

## Pre-presentation checklist

- [ ] `npm run check` passes.
- [ ] The PostgreSQL-backed backend suite passes.
- [ ] Alembic reports head `20260820_0003` and no drift.
- [ ] API and operations-client origins match the configured CORS allowlist.
- [ ] Administrator and client demo accounts are synthetic and can sign in.
- [ ] The client application is either ready to submit live or already approved for the seeded path.
- [ ] English and Arabic screens render without horizontal overflow.
- [ ] Browser storage contains no access or refresh token.
- [ ] No real customer, credential, payment, or production data is displayed.
- [ ] The presenter does not claim later-phase features as implemented.
