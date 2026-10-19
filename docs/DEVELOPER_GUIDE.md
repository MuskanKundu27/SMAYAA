# SMAYAA.ai – Developer Guide

For developers joining the project. This guide describes **only what exists in the code today**.

_Last updated: 2026-10-19_

## 1. What SMAYAA.ai is

A multi-tenant SaaS platform for cooling-tower water intelligence. Companies (tenants) own plants; plant staff enter water-chemistry, thermal and filter readings; the platform checks them against limits, raises alerts with treatments, computes KPIs and shows predicted problems. Parameters, formulas, limits, rules and module screens are configuration stored in the database, not code.

New to the project or to SaaS development? Read [LEARNING_JOURNAL.md](LEARNING_JOURNAL.md) first: it explains every step and decision in plain language.

## 2. Status

**Step 0 – Foundation: done.** The API and web app skeletons run, connect to each other and to PostgreSQL, and are covered by linting, type checks, tests and CI. There are no business features yet (no login, companies, readings, etc.).

## 3. Repository layout

Repository: https://github.com/MuskanKundu27/SMAYAA (default branch `main`)

```
README.md
.env.example              Template for the local .env (copy it; never commit .env)
.gitignore / .gitattributes
.pre-commit-config.yaml   Checks that run on every git commit
.github/workflows/ci.yml  GitHub Actions: API, web and Docker build jobs
docker-compose.yml        Optional full stack in Docker (not required for local dev)
docs/
  DEVELOPER_GUIDE.md      This file
  LEARNING_JOURNAL.md     Step-by-step "what and why" diary for junior developers
api/                      Backend (FastAPI, Python 3.12)
  pyproject.toml          Dependencies and tool settings (ruff, mypy, pytest)
  alembic.ini             Alembic config (no DB URL stored here)
  Dockerfile
  app/
    main.py               App factory: middleware, error handlers, routers under /api/v1
    core/config.py        Settings from environment variables / root .env
    core/logging.py       JSON log formatter; request ID context variable
    core/middleware.py    Request ID + one log line per request
    core/errors.py        Standard error shape and AppError classes
    db/base.py            SQLAlchemy declarative Base with constraint naming convention
    db/session.py         Engine, session factory, get_db dependency
    routers/health.py     GET /api/v1/health
  migrations/             Alembic environment and versions/ (0001 = empty baseline)
  scripts/
    create_dev_db.sql     Creates roles smayaa_owner / smayaa_app and DBs smayaa / smayaa_test
    grant_app_role.sql    Default privileges so smayaa_app can use tables smayaa_owner creates
    docker-init-db.sh     Same setup for the Docker Postgres container
  tests/                  pytest (conftest points the app at the test database)
web/                      Frontend (React 19 + TypeScript + Vite)
  vite.config.ts          Dev server on :5173, proxies /api to :8000
  src/App.tsx             Placeholder page that checks API health
  Dockerfile, nginx.conf  Production build served by nginx, /api proxied to the API
```

Some files exist only on the project owner's machine and are deliberately **not** in Git (internal brief, internal work log, reference designs). They are in `.gitignore`, and a pre-commit hook blocks them.

## 4. Prerequisites

Local development runs **natively, without Docker**:

- **Python 3.12** – Windows: `py install 3.12`, then use `py -3.12`.
- **PostgreSQL 16** – Windows: `winget install --id PostgreSQL.PostgreSQL.16 -e` (service `postgresql-x64-16`, port 5432; you choose the `postgres` superuser password during install).
- **Node.js 20+** and npm (CI uses Node 24).
- **Git**

## 5. Getting started (Windows, first time)

Commands are run from the repository root in Git Bash unless noted. On PowerShell, replace `/` with `\` in paths.

```bash
# 1. Databases and roles (choose two passwords; you will put them in .env)
"/c/Program Files/PostgreSQL/16/bin/psql.exe" -U postgres -h localhost \
    -v owner_pw=OWNER_PASSWORD -v app_pw=APP_PASSWORD -f api/scripts/create_dev_db.sql

# 2. Settings
cp .env.example .env        # then edit .env: passwords from step 1 and a random JWT_SECRET

# 3. API
py -3.12 -m venv api/.venv
api/.venv/Scripts/python.exe -m pip install -e "api[dev]"
cd api
.venv/Scripts/python.exe -m alembic upgrade head          # development database
MIGRATION_DATABASE_URL="<value of TEST_MIGRATION_DATABASE_URL>" .venv/Scripts/python.exe -m alembic upgrade head   # test database
cd ..

# 4. Web
cd web && npm ci && cd ..

# 5. Git hooks
api/.venv/Scripts/pre-commit.exe install
```

## 6. Everyday commands

| Task | Command (from repo root) |
|---|---|
| Run the API (http://localhost:8000) | `cd api && .venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000` |
| API docs (Swagger) | http://localhost:8000/api/v1/docs |
| Run the web app (http://localhost:5173) | `cd web && npm run dev` |
| API tests | `cd api && .venv/Scripts/python.exe -m pytest` |
| API lint + format | `cd api && .venv/Scripts/python.exe -m ruff check . && .venv/Scripts/python.exe -m ruff format .` |
| API type check | `cd api && .venv/Scripts/python.exe -m mypy app tests migrations` |
| Web lint / types / build | `cd web && npm run lint && npm run typecheck && npm run build` |
| New migration | `cd api && .venv/Scripts/python.exe -m alembic revision --autogenerate -m "describe change"` (review the file before committing) |
| Apply migrations | `cd api && .venv/Scripts/python.exe -m alembic upgrade head` |
| All commit checks | `api/.venv/Scripts/pre-commit.exe run --all-files` |

## 7. Configuration (environment variables)

Read by `api/app/core/config.py` from the process environment or the root `.env` file. See `.env.example`.

| Variable | Purpose |
|---|---|
| `ENVIRONMENT` | `development`, `test` or `production` |
| `DATABASE_URL` | Runtime connection, as **`smayaa_app`** (non-owner role, so row-level security applies) |
| `MIGRATION_DATABASE_URL` | Alembic connection, as **`smayaa_owner`** (owns the schema). Read by `migrations/env.py` |
| `TEST_DATABASE_URL` / `TEST_MIGRATION_DATABASE_URL` | Same pair for the `smayaa_test` database used by pytest |
| `JWT_SECRET` | Token signing secret, at least 32 characters |
| `CORS_ORIGINS` | Comma-separated allowed browser origins |
| `LOG_LEVEL` | e.g. `INFO`, `DEBUG` |

## 8. Architecture (current)

- **Request flow:** `RequestIdMiddleware` assigns an ID (or accepts a sane `X-Request-ID` header), logs one JSON line per request with method, path, status and duration, and returns the ID in the `X-Request-ID` response header. Then CORS, then the router.
- **Errors:** every error response has the shape `{"error": {"code", "message", "details"}}`. Services raise `AppError` subclasses (`NotFoundError`, `PermissionDeniedError`, `ConflictError`); validation errors and unexpected exceptions are converted to the same shape (`app/core/errors.py`). Unexpected errors are logged with a stack trace but never shown to the client.
- **Database:** SQLAlchemy 2.0 (synchronous). One session per request via the `get_db` dependency.
- **Two database roles:** `smayaa_owner` owns tables and runs migrations; the API connects as `smayaa_app`, which has only `SELECT/INSERT/UPDATE/DELETE` (granted automatically through default privileges in `grant_app_role.sql`). PostgreSQL row-level security does not apply to table owners, so this split is what will make RLS effective.
- **Web ↔ API:** in development the browser only talks to Vite (:5173), which proxies `/api` to FastAPI (:8000). In Docker/production nginx does the same. One origin for the browser keeps cookies simple.

## 9. API endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/health` | `{"status":"ok","database":"ok"}`; returns 503 with `"degraded"` if the database is unreachable |
| GET | `/api/v1/docs` | Swagger UI |

## 10. Data model

No tables yet. Migration `0001` is an empty baseline.

## 11. Quality gates and CI

- **pre-commit** (`.pre-commit-config.yaml`): blocks private/secret files, trims whitespace, fixes end-of-file, checks YAML/TOML, blocks large files and private keys, runs ruff lint + format on `api/`.
- **GitHub Actions** (`.github/workflows/ci.yml`) on every push to `main` and every pull request:
  - `api`: ruff, ruff format check, mypy (strict), create roles in a Postgres 16 service container, `alembic upgrade head`, pytest.
  - `web`: `npm ci`, oxlint, `tsc -b`, `vite build`.
  - `docker`: builds both Docker images so they never silently break.
- Tool versions: ruff `0.17.1` is pinned in both `api/pyproject.toml` and `.pre-commit-config.yaml`; change them together.

## 12. Conventions

- Configuration (parameters, formulas, limits, treatments, rules, modules) is data, never hard-coded.
- Permissions are checked as permission strings plus scope, never by role name.
- Formulas are evaluated only by the safe evaluator; never `eval`/`exec`.
- Type hints everywhere; `mypy --strict` and `ruff` must pass.
- Business logic lives in service modules, not in route functions.
- Migrations: autogenerate, then read and fix the generated file; they must be safe to run forward.
- Keep this guide and `LEARNING_JOURNAL.md` updated with every change.
