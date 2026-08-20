# Tawzeevo API

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".\apps\api[dev]"
docker compose up -d postgres postgres-test
$env:DATABASE_URL = "postgresql+psycopg://tawzeevo:change-me@localhost:5432/tawzeevo"
.\.venv\Scripts\alembic -c .\apps\api\alembic.ini upgrade head
.\.venv\Scripts\uvicorn tawzeevo_api.main:app --app-dir .\apps\api --reload
```

The API exposes `/health`, `/health/database`, `/docs`, and `/openapi.json`.

Phase 1 authentication routes include:

- `POST /register`
- `POST /login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`

Access tokens use the Swagger bearer authorization control. Refresh tokens are opaque, hashed in PostgreSQL, rotated on every refresh, and sent only through the scoped HttpOnly cookie.

The Phase 1 tenant slice is exposed under `/api/v1/tenants/{tenant_id}`. An active owner membership is required for customer, category, tenant-product/barcode, and draft-invoice routes. The path tenant ID selects the requested context but never grants access: the API validates membership and tenant lifecycle state before every business operation.

The initial slice includes:

- `POST /customers`, `GET /customers/{customer_id}`, and `GET /customers/search?phone=...`
- `POST /categories`, `GET /categories`, and `GET /categories/{category_id}`
- `POST /products`, `GET /products/{product_id}`, and `GET /products/barcode/{barcode}`
- `POST /invoices` and `GET /invoices/{invoice_id}` for real database-backed drafts

Product and invoice money uses four-decimal values and an explicit ISO currency code. Draft invoices reject mixed-currency products.

## Seed synthetic demo data

The demo seeder never creates users, tenants, or memberships and never bypasses onboarding. Register a client, have a platform administrator approve its tenant application, then pass that existing active owner and tenant to the command. Currency and customer phone are explicit inputs; no credentials or production data are embedded.

```powershell
$env:DATABASE_URL = "postgresql+psycopg://tawzeevo:change-me@localhost:5432/tawzeevo"
.\.venv\Scripts\python -m tawzeevo_api.cli.seed_demo --owner-email owner@example.com --tenant-id 00000000-0000-0000-0000-000000000000 --customer-phone "+961 70 555 444" --currency USD
```

The command creates one synthetic customer, category, piece-priced barcode product, and database-backed draft invoice in one transaction. It refuses replay for the same tenant instead of silently duplicating the demo slice.

## Create the first platform administrator

There is no public administrator-registration route and no default administrator password. After applying migrations, run the local command below against the intended database. The password is entered twice through a hidden prompt and is never accepted as a command-line argument.

```powershell
$env:DATABASE_URL = "postgresql+psycopg://tawzeevo:change-me@localhost:5432/tawzeevo"
.\.venv\Scripts\python -m tawzeevo_api.cli.create_admin --first-name Platform --last-name Owner --email owner@example.com --phone "+96170123456" --city Beirut --age 30
```
