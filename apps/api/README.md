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

The API exposes `/health`, `/health/database`, `/docs`, and `/openapi.json` in this milestone.
