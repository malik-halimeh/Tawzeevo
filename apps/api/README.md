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

## Create the first platform administrator

There is no public administrator-registration route and no default administrator password. After applying migrations, run the local command below against the intended database. The password is entered twice through a hidden prompt and is never accepted as a command-line argument.

```powershell
$env:DATABASE_URL = "postgresql+psycopg://tawzeevo:change-me@localhost:5432/tawzeevo"
.\.venv\Scripts\python -m tawzeevo_api.cli.create_admin --first-name Platform --last-name Owner --email owner@example.com --phone "+96170123456" --city Beirut --age 30
```
