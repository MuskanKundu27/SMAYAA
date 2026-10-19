# SMAYAA.ai – Developer Guide

For developers joining the project. This guide describes **only what exists in the code today**.

_Last updated: 2026-10-19_

## 1. What SMAYAA.ai is

A multi-tenant SaaS platform for cooling-tower water intelligence. Companies (tenants) own plants; plant staff enter water-chemistry, thermal and filter readings; the platform checks them against limits, raises alerts with treatments, computes KPIs and shows predicted problems. Parameters, formulas, limits, rules and module screens are configuration stored in the database, not code.

New to the project or to SaaS development? Read [LEARNING_JOURNAL.md](LEARNING_JOURNAL.md) first: it explains every step and decision in plain language.

## 2. Status

| Step | State |
|---|---|
| 0 – Foundation (API/web skeletons, DB roles, tooling, CI) | Done |
| 1 – Identity and tenancy (login, roles/permissions, companies, plants, users, RLS, audit) | Done (API) |
| 1b – Web app shell (login page, role-based menu, plant switcher, placeholder pages) | Done |
| 2 – Configuration engine (parameters, formulas, limits, rules) | Not started |

## 3. Repository layout

Repository: https://github.com/MuskanKundu27/SMAYAA (default branch `main`)

```
README.md
.env.example              Template for the local .env (copy it; never commit .env)
.pre-commit-config.yaml   Checks that run on every git commit
.github/workflows/ci.yml  GitHub Actions: API, web and Docker build jobs
docker-compose.yml        Optional full stack in Docker (not required for local dev)
docs/
  DEVELOPER_GUIDE.md      This file
  LEARNING_JOURNAL.md     Step-by-step "what and why" diary for junior developers
api/                      Backend (FastAPI, Python 3.12)
  app/
    main.py               App factory: middleware, error handlers, routers under /api/v1
    core/                 config, logging, middleware (request IDs), errors, security
                          (argon2 + JWT + refresh tokens), rate_limit
    db/                   base (declarative Base), session (engine + get_db),
                          tenant (TenantContext → Postgres RLS settings)
    models/               SQLAlchemy models: tenancy (Company, Plant), identity (User, Role,
                          RolePermission, RoleAssignment, OperatorProfile, RefreshToken), audit
    auth/                 principal (Principal), provider (AuthProvider, PasswordAuthProvider),
                          dependencies (get_principal, CurrentPrincipal, require)
    services/             Business rules: auth, companies, plants, users, audit
    schemas/              Pydantic request/response models
    routers/              HTTP endpoints: health, auth (+ /me), companies, plants, users
    scripts/seed_dev.py   Demo data for local development
  migrations/versions/    0001 baseline, 0002 identity + tenancy + RLS
  scripts/                create_dev_db.sql, grant_app_role.sql, docker-init-db.sh
  tests/                  pytest: conftest (test DB setup), helpers (data builders), test_*.py
web/                      Frontend (React 19 + TypeScript + Vite + react-router 7)
  src/
    main.tsx, App.tsx     Entry point; routes (login when signed out, AppLayout when signed in)
    api/client.ts         fetch wrapper: in-memory access token, auto refresh on 401, ApiError
    api/types.ts          API response types (Me, ...)
    auth/AuthContext.tsx  AuthProvider: session restore on load, login/logout, selected plant
    auth/useAuth.ts       useAuth() hook and AuthState type
    navigation.ts         Menu entries and the permission each one needs
    layout/AppLayout.tsx  Sidebar menu, top bar (company, plant switcher, user, logout)
    pages/                LoginPage, HomePage, PlaceholderPage (+ NoAccess, NotFound)
    *.test.ts             vitest tests
```

Some files exist only on the project owner's machine and are deliberately **not** in Git (internal brief, internal work log, reference designs). They are in `.gitignore`, and a pre-commit hook blocks them.

## 4. Prerequisites

Local development runs **natively, without Docker**:

- **Python 3.12** – Windows: `py install 3.12`, then use `py -3.12`.
- **PostgreSQL 16** – Windows: `winget install --id PostgreSQL.PostgreSQL.16 -e` (service `postgresql-x64-16`, port 5432; you choose the `postgres` superuser password during install).
- **Node.js 20+** and npm (CI uses Node 24).
- **Git**

## 5. Getting started (Windows, first time)

Commands are run from the repository root in Git Bash unless noted.

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
.venv/Scripts/python.exe -m alembic upgrade head      # development database
.venv/Scripts/python.exe -m app.scripts.seed_dev      # demo company, plant and users
cd ..
# (The test database is migrated automatically when you run pytest.)

# 4. Web
cd web && npm ci && cd ..

# 5. Git hooks
api/.venv/Scripts/pre-commit.exe install
```

### Demo accounts (development only)

Created by `app/scripts/seed_dev.py` (refuses to run when `ENVIRONMENT=production`). All use password **`Demo@12345`**.

| Username | Role | Scope |
|---|---|---|
| `smayaaadmin` | super_admin | Platform |
| `companyadmin` | company_admin | Demo Power Ltd (all plants) |
| `manager1` | manager | Unit 1 – Cooling Tower |
| `operator1` | operator | Unit 1 – Cooling Tower |

Try it in the browser: run the API and the web app (section 6), open http://localhost:5173 and sign in.
Or in Swagger: open http://localhost:8000/api/v1/docs, call `POST /auth/login`, copy `access_token`, click **Authorize**, paste it.

## 6. Everyday commands

| Task | Command (from repo root) |
|---|---|
| Run the API (http://localhost:8000) | `cd api && .venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000` |
| API docs (Swagger) | http://localhost:8000/api/v1/docs |
| Run the web app (http://localhost:5173) | `cd web && npm run dev` |
| API tests | `cd api && .venv/Scripts/python.exe -m pytest` |
| API lint + format | `cd api && .venv/Scripts/python.exe -m ruff check . && .venv/Scripts/python.exe -m ruff format .` |
| API type check | `cd api && .venv/Scripts/python.exe -m mypy app tests migrations` |
| Web lint / types / tests / build | `cd web && npm run lint && npm run typecheck && npm test && npm run build` |
| New migration | `cd api && .venv/Scripts/python.exe -m alembic revision --autogenerate -m "describe change"` (review the file before committing) |
| Apply migrations | `cd api && .venv/Scripts/python.exe -m alembic upgrade head` |
| Seed demo data | `cd api && .venv/Scripts/python.exe -m app.scripts.seed_dev` |
| All commit checks | `api/.venv/Scripts/pre-commit.exe run --all-files` |

## 7. Configuration (environment variables)

Read by `api/app/core/config.py` from the process environment or the root `.env` file. See `.env.example`.

| Variable | Default | Purpose |
|---|---|---|
| `ENVIRONMENT` | `development` | `development`, `test` or `production` |
| `DATABASE_URL` | – | Runtime connection as **`smayaa_app`** (non-owner, so RLS applies) |
| `MIGRATION_DATABASE_URL` | – | Alembic and seed connection as **`smayaa_owner`** |
| `TEST_DATABASE_URL` / `TEST_MIGRATION_DATABASE_URL` | – | Same pair for `smayaa_test`, used by pytest |
| `JWT_SECRET` | – | Token signing secret, ≥ 32 characters |
| `CORS_ORIGINS` | empty | Comma-separated allowed browser origins |
| `LOG_LEVEL` | `INFO` | |
| `ACCESS_TOKEN_MINUTES` | `15` | Access token lifetime |
| `REFRESH_TOKEN_DAYS` | `7` | Refresh token lifetime |
| `LOGIN_MAX_FAILURES` | `5` | Wrong passwords in a row before the account locks |
| `LOGIN_LOCKOUT_MINUTES` | `15` | Lock duration |
| `LOGIN_RATE_LIMIT_PER_MINUTE` | `20` | Login attempts per client IP per minute (per API process) |

## 8. Architecture

### 8.1 Request flow
`RequestIdMiddleware` (ID + one JSON log line per request) → CORS → router → dependencies (`get_db`, `get_principal`) → service → database.

### 8.2 Errors
Every error response is `{"error": {"code", "message", "details"}}`. Services raise `AppError` subclasses from `app/core/errors.py`: `NotFoundError` 404, `PermissionDeniedError` 403, `ConflictError` 409, `UnauthorizedError` 401 (adds `WWW-Authenticate: Bearer`), `ValidationFailedError` 422, `TooManyRequestsError` 429. Request validation errors and unexpected exceptions use the same shape; unexpected ones are logged with a stack trace but not shown to the client.

### 8.3 Authentication
- `POST /auth/login` → `services/auth.login`:
  1. Finds the user with the SQL function `auth_find_user()` (the only RLS bypass; returns just id and company id).
  2. Checks lockout, verifies the password through an `AuthProvider` (`PasswordAuthProvider`, argon2id), counts failures and locks after `LOGIN_MAX_FAILURES`.
  3. Checks the user and company are active (only after a correct password, so inactive accounts are not revealed). All failures return the same message.
  4. Returns a JWT access token (HS256, claims `sub`, `cid`, `typ`, `exp`) and sets the refresh token as an **httpOnly** cookie `smayaa_refresh` (path `/api/v1/auth`, `SameSite=Strict`, `Secure` in production).
- Login is also rate-limited per client IP (`core/rate_limit.SlidingWindowLimiter`, in-memory).
- `POST /auth/refresh`: refresh tokens are stored as SHA-256 hashes, **rotated** on every use, and grouped in a `family_id`. Presenting an already-used token revokes the whole family (theft detection).
- `POST /auth/logout`: revokes the refresh token and clears the cookie.
- Swapping in SSO later = a new `AuthProvider`; permissions and tenancy do not change.

### 8.4 Principal, permissions and scope
`auth/dependencies.get_principal` runs on every authenticated request:
1. Decodes the access token.
2. `services/auth.load_principal` loads the user **from the database** and rejects inactive users or companies immediately, even with an unexpired token.
3. Loads role assignments and the union of their permissions.
4. Builds a `Principal`: `role_keys`, `rank`, `permissions`, `company_id`, `plant_ids` (`None` = all plants of the company), `is_platform`.
5. Narrows the database session to that scope (see 8.5).

Code checks **permission strings**, never role names: `principal.require("plants.manage")`, or `Depends(require("..."))` in a router. Roles are rows in `roles` with a `rank` and a `scope` (`platform` / `company` / `plant`); their permissions are rows in `role_permissions`. Both are seeded by migration 0002:

| Permission | super_admin | company_admin | manager | operator |
|---|:-:|:-:|:-:|:-:|
| companies.read / companies.manage | ✓ | | | |
| users.read | ✓ | ✓ | ✓ | |
| users.manage:company_admin | ✓ | | | |
| users.manage:manager | | ✓ | | |
| users.manage:operator | | ✓ | ✓ | |
| plants.read | | ✓ | ✓ | ✓ |
| plants.manage | | ✓ | | |
| config.manage | ✓ | | | |
| audit.read | ✓ | ✓ | | |
| readings.read | | ✓ | ✓ | ✓ |
| readings.write | | | ✓ | ✓ |
| limits.read | | ✓ | ✓ | |
| limits.write | | | ✓ | |
| limits.write_without_manager | | ✓ | | |
| plant_settings.write, operator_profiles.manage | | | ✓ | |
| modules.view, alerts.view | | ✓ | ✓ | ✓ |

(Permissions for readings, limits, modules and alerts are seeded now; the endpoints that use them come in later steps.)

**User management rule** (`services/users.py`): to create or deactivate a user with role R you need `users.manage:R` **and** R's rank must be lower than yours, **and** the target must be in your scope (company-wide users: own company; plant users: own plants; platform: company admins of any company). Deactivation sets `is_active = false`, records who/when, revokes refresh tokens, and returns a warning when a plant is left with no active user holding `limits.write` ("no manager").

### 8.5 Tenant isolation (two layers)
1. **Application:** services filter by `principal.company_id` / `principal.plant_ids` and return 404 for anything outside scope (never revealing it exists).
2. **Database (RLS):** `db/tenant.py` holds a `TenantContext` on the SQLAlchemy session. A listener on `Session.after_begin` writes it into Postgres settings with `set_config(..., true)` at the start of **every** transaction:

   | Setting | Value |
   |---|---|
   | `app.user_id` | current user |
   | `app.company_id` | current company (`''` for platform users) |
   | `app.plant_ids` | `*` (all plants of the company) or comma-separated plant ids |
   | `app.platform` | `on` for the super-admin path, else `off` |

   Policies in migration 0002 use helper functions `app_company_id()`, `app_user_id()`, `app_is_platform()`, `app_can_see_plant(id)`. A session with no context sees **no rows** (fails closed). The API connects as `smayaa_app`, which is not the table owner, so policies always apply.

   | Table | Read | Write |
   |---|---|---|
   | companies | platform, or own company | platform only |
   | plants | platform, or own company + visible plant | insert/update own company; no delete |
   | users | platform, own company, or own row | insert/update same; no delete |
   | role_assignments | platform, own company, or own | platform or own company |
   | operator_profiles | own company + visible plant | same |
   | audit_log | platform or own company | insert only (append-only) |
   | roles, role_permissions | everyone (no RLS) | nobody (privileges revoked) |
   | refresh_tokens | no RLS (hashes only, not tenant data) | |

   Future plant data (readings etc.) will **not** have a platform clause, so the super admin can never read it.

### 8.6 Audit log
`services/audit.record(...)` adds an `audit_log` row in the same transaction as the change (company/plant/user create, update, deactivate). `audit.snapshot()` produces JSON-safe before/after values.

### 8.7 Web ↔ API
In development the browser talks only to Vite (:5173), which proxies `/api` to FastAPI (:8000). In Docker/production nginx does the same. One origin keeps the refresh cookie simple.

### 8.8 Web app
- **Session:** `api/client.ts` keeps the access token **in memory only** (never in localStorage). On page load `AuthProvider` calls `POST /auth/refresh`; the httpOnly cookie restores the session silently. Any request that gets a 401 triggers one refresh and a retry; concurrent requests share one refresh call. If refresh fails, the app returns to the login page.
- **Menu:** `navigation.ts` lists menu entries with the permission each needs; `menuFor(me.permissions)` filters them. Routes for pages the user lacks permission for show "No access". This is convenience only: the API enforces permissions on every request.
- **Plant switcher:** shown in the top bar only when `/me` returns more than one plant. The choice is remembered in localStorage (wrapped in try/catch; purely a convenience).
- **Placeholders:** every menu page except Home is a placeholder that names the step that delivers it. The three module entries (Water Chemistry, Filter, Thermal) are hard-coded **temporarily**; from step 4 the module list comes from the API.
- **Styling:** plain CSS in `src/index.css` with CSS variables (navy/blue palette). To be aligned with the original SMAYAA demo design once available.

## 9. API endpoints (all under `/api/v1`)

| Method | Path | Who | Description |
|---|---|---|---|
| GET | `/health` | anyone | DB check; 503 when the DB is down |
| POST | `/auth/login` | anyone | `{username, password}` → `{access_token, token_type, expires_in}` + refresh cookie |
| POST | `/auth/refresh` | refresh cookie | New access token, rotated cookie |
| POST | `/auth/logout` | refresh cookie | 204, revokes refresh token |
| GET | `/me` | logged in | User, roles, permissions, company, visible plants (drives the UI menu) |
| GET | `/companies` | companies.read | Paginated (`limit` 1–200, `offset`) |
| POST | `/companies` | companies.manage | `{name, admin: {username, full_name, password}}` → company + its first company admin |
| PATCH | `/companies/{id}` | companies.manage | `{name?, is_active?}`; deactivating locks out its users |
| GET | `/plants` | plants.read | Plants visible to the caller |
| POST | `/plants` | plants.manage | `{name, location?}` in the caller's company |
| PATCH | `/plants/{id}` | plants.manage | `{name?, location?, is_active?}` |
| GET | `/users` | users.read | Users in the caller's scope, with roles and plant ids |
| POST | `/users` | users.manage:&lt;role&gt; | `{username, full_name, password, role, plant_id?, company_id?}` |
| DELETE | `/users/{id}` | users.manage:&lt;role&gt; | Deactivates; response `{user, warnings}` |

Password policy: at least 10 characters, a letter and a digit, must not contain the username. Usernames: 3–50 of `A–Z a–z 0–9 . _ -`, stored lower-case, unique across the platform.

## 10. Data model (migration 0002)

```
companies         id uuid PK, name unique, is_active, settings jsonb, created_at
plants            id, company_id → companies, name (unique per company), location, is_active,
                  settings jsonb, created_at, updated_at
users             id, company_id → companies (NULL = platform user), username unique (lower-case),
                  full_name, password_hash, is_active, created_by, created_at, deactivated_by,
                  deactivated_at, last_login_at, failed_login_count, locked_until
roles             key PK, name, rank, scope (platform|company|plant)
role_permissions  (role_key, permission) PK
role_assignments  id, user_id, role_key, company_id NULL, plant_id NULL
                  (check: plant_id requires company_id; unique per user/role/company/plant)
operator_profiles (user_id, plant_id) PK, company_id, visible_modules[] NULL, visible_parameters[] NULL,
                  can_edit_readings, show_alerts          (table only; no endpoints yet. No row = all allowed)
refresh_tokens    id, user_id, family_id, token_hash unique, expires_at, revoked_at, created_at
audit_log         id, company_id NULL, actor_id, action, entity, entity_id, before jsonb, after jsonb, created_at
```

All primary keys are UUIDs generated by Postgres (`gen_random_uuid()`), so ids cannot be guessed.

## 11. Testing

- `tests/conftest.py`: the app runs against `smayaa_test` as **`smayaa_app`**, so RLS is active in tests. The schema is migrated once per run (as the owner). After each test, tenant tables are truncated.
- `tests/helpers.py`: `make_company`, `make_plant`, `make_user`, `make_tenant` (company + 2 plants + admin/manager/operator), `login`. Test data is written as the owner role.
- Test files: `test_auth` (login, lockout, rate limit, refresh rotation and reuse detection, logout, deactivated users), `test_me_and_permissions` (per-role access matrix), `test_companies_and_plants`, `test_users` (rank rule, validation, deactivation, last-manager warning), `test_isolation` (company/plant isolation via API **and via raw SQL under RLS**), `test_rate_limit`, `test_health`.
- In the test environment password hashing uses deliberately cheap argon2 parameters for speed.
- **Web:** `npm test` (vitest). `navigation.test.ts` checks the menu per role; `api/client.test.ts` checks token storage, refresh-and-retry, shared refresh, and session end (with a mocked `fetch`).

## 12. Quality gates and CI

- **pre-commit** (`.pre-commit-config.yaml`): blocks private/secret files, whitespace/EOF fixes, YAML/TOML checks, large files, private keys, ruff lint + format on `api/`.
- **GitHub Actions** (`.github/workflows/ci.yml`) on push to `main` and pull requests:
  - `api`: ruff, format check, mypy (strict), create DB roles in a Postgres 16 service, migrate up → down → up, pytest.
  - `web`: `npm ci`, oxlint, `tsc -b`, vitest, `vite build`.
  - `docker`: builds both images.
- ruff `0.17.1` is pinned in both `api/pyproject.toml` and `.pre-commit-config.yaml`; change them together.

## 13. Conventions

- Configuration (parameters, formulas, limits, treatments, rules, modules) is data, never hard-coded.
- Check permissions (`principal.require("x.y")`), never role names. The single named role in code is `COMPANY_OWNER_ROLE` in `services/companies.py` (the role given to a new company's first admin).
- Out-of-scope resources return **404**, not 403, so their existence is not revealed. Missing permission returns 403.
- Business rules live in `services/`; routers only translate HTTP ↔ service calls.
- Every change to companies, plants or users writes an audit entry in the same transaction.
- Delete = deactivate for users, plants and companies.
- Formulas are evaluated only by the safe evaluator (coming in step 2); never `eval`/`exec`.
- Type hints everywhere; `mypy --strict` and `ruff` must pass.
- Migrations: autogenerate, then read and fix the file; hand-written SQL (RLS) goes in the same migration; downgrades must work (CI runs up → down → up).
- Keep this guide and `LEARNING_JOURNAL.md` updated with every change.
