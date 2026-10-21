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
| 2 – Configuration engine (safe evaluator, parameters, formulas, limits, treatments, rules, modules, template) | Done (API) |
| 3 – Readings and alerts | Not started |

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
                          RolePermission, RoleAssignment, OperatorProfile, RefreshToken), audit,
                          config (Parameter, Limit, PlantSetting, Treatment, Rule, Module)
    auth/                 principal (Principal), provider (AuthProvider, PasswordAuthProvider),
                          dependencies (get_principal, CurrentPrincipal, require)
    engine/               Pure calculation code (no DB): evaluator (safe expressions),
                          status (limits → good/warn/bad), calculation (order, calculate, rules)
    templates/default.py  The default template (parameters, treatments, rules, modules) as data
    services/             Business rules: auth, companies, plants, users, audit, parameters,
                          rules, modules (+ treatments), templates, limits (+ plant settings),
                          config_common (shared helpers)
    schemas/              Pydantic request/response models (config.py has the widget types)
    routers/              HTTP endpoints: health, auth (+ /me), companies, plants, users,
                          config (company configuration), limits (plant limits + settings)
    scripts/seed_dev.py   Demo data for local development
  migrations/versions/    0001 baseline, 0002 identity + tenancy + RLS, 0003 configuration + RLS
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

(`limits.*`, `plant_settings.write` and `config.manage` are used since step 2. `readings.*`, `modules.view`, `alerts.view` and `operator_profiles.manage` are seeded; their endpoints come in steps 3–5.)

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
   | parameters, treatments, rules, modules | platform, or own company | **platform only** (super admin configures) |
   | limits, plant_settings | own company + visible plant (**no platform clause**) | same |

   Plant data (limits, plant settings, and readings from step 3) has **no** platform clause, so the super admin can never read it.

### 8.6 Audit log
`services/audit.record(...)` adds an `audit_log` row in the same transaction as the change (company/plant/user create, update, deactivate). `audit.snapshot()` produces JSON-safe before/after values.

### 8.6a Calculation engine (`app/engine/`)
Pure functions, no database, so they are easy to test and reuse.
- **`evaluator.py`:** `parse(source, functions=None)` turns text into a checked `Expression`. It uses Python's `ast` parser, then rejects everything not on a whitelist:
  - **Allowed:** numbers, strings (for helper arguments), names, `+ - * / **`, comparisons (chains allowed), `and/or/not`, lists, and calls to `min max abs round sqrt log exp if_else` (plus rule helpers when parsing rules).
  - **Rejected:** attributes, indexing, lambdas, comprehensions, keyword arguments, unknown functions, more than 500 characters, more than 200 nodes.

  `Expression.references` lists every parameter key used, including string arguments to helpers like `off('ph')`. `evaluate(expr, variables, functions)` **never raises for data problems**: a missing value, division by zero, `sqrt` of a negative, overflow, or an exponent above 100 all give `None` ("No data"). `if_else(cond, a, b)` evaluates only the chosen branch. **`eval`/`exec` are never used.**
- **`status.py`:** `status_of(value, Limits)` returns `good` / `warn` (+ direction) / `bad` (+ direction) / `na`, exactly per the brief (inclusive bounds; no limits = always good). `SEVERITY_POINTS` gives 20 for warn and 40 for bad.
- **`calculation.py`:**
  - `calculation_order(formulas)` sorts formulas topologically (Kahn's algorithm) and raises `CycleError` on loops.
  - `calculate(inputs, formulas, base)` computes every calculated key in that order. `base` is the reserved name for the plant's clean baseline approach.
  - `RuleContext` provides the rule helpers `value`, `status`, `off`, `sev` and `count_off`. A missing value counts as **not off**, so no data never raises a prediction.
  - `parse_rule` and `evaluate_rule` work like `parse` and `evaluate`, with those helpers.

### 8.6b Company configuration (super admin)
All under `/companies/{company_id}/...`, permission `config.manage`, platform database context. Services: `parameters.py`, `rules.py`, `modules.py` (modules + treatments), `templates.py`; shared helpers in `config_common.py`.
- **Parameters:** `kind` is `input` (typed) or `calculated` (has `formula`). The **key never changes** after creation (readings will store values by key). Keys must match `^[a-z][a-z0-9_]{0,39}$` and must not be reserved (`base`, function and helper names, `and/or/not`, …). Each parameter can have a `sample_value` and **default limits**.
- **Formula validation on save** (`parameters.validate_formula`):
  1. The formula passes the whitelist.
  2. It doesn't reference its own parameter.
  3. Every reference is an **active** parameter or `base`.
  4. It creates no loop (`calculation_order`).
  5. It gives a result with the sample values (inputs without a sample use 1.0; `base` uses the company default).

  Failures return **422** with `details[0].field = "formula"` and a human-readable message.
- **Versioning:** changing a formula increments `formula_version`. Changing an expression of a rule increments `rule.version`.
- **Deactivation:** `PATCH {"is_active": false}`. Refused with **409** while an active formula or rule references the parameter; `details` lists them (`parameter 'appr'`, `rule 'TH-P02'`). Nothing is ever hard-deleted.
- **Rules:** `condition_expr` and `probability_expr` are parsed with the rule helpers; references must be active parameters. `POST /rules/test` evaluates a rule on given input values (calculated values are derived, default limits used).
- **Formula test:** `POST /formulas/test` evaluates a formula on sample values (or given `values`) without saving.
- **Modules:** `layout = {"widgets": [...]}` validated against the widget types in `schemas/config.py`: `input_group` (needs `group` or `params`), `value_tiles`, `trend_chart`, `predicted_problems`, `alert_list`, `inputs_summary`, `text_note`. Unknown types are rejected (422). References to missing or inactive parameters/rules are **allowed**, and returned as `warnings` (the UI will show "insufficient data"). **Adding a widget type = a new Pydantic model in that union + a frontend component.**
- **Treatments:** one per parameter + direction (`high`/`low`), with `needs_review` (true for template text).
- **Audit:** every create/update writes `audit_log` (`parameter.*`, `rule.*`, `module.*`, `treatment.upsert`, `template.apply`).

### 8.6c Templates (`app/templates/default.py`)
- The default template is plain Python data: 26 parameters (18 inputs, 8 calculated, with units, sample values and default limits), 20 treatments (flagged `needs_review`), 5 rules (FLT-P01/P02/P03, TH-P01/P02), 3 modules (Water Chemistry, Filter, Thermal), and plant-setting defaults (`clean_baseline_approach = 4.0`, stored in `companies.settings["plant_setting_defaults"]`).
- `services/templates.apply_template(db, company, template, actor_id)` **adds only what is missing** (by parameter key, rule code, module key, treatment parameter+direction), so it is safe to run again and keeps a company's own edits.
- `POST /companies` applies the default template automatically. `POST /companies/{id}/apply-template` re-applies it (adds anything missing). The dev seed applies it to Demo Power Ltd.
- `tests/test_template.py` checks that the template is valid on its own: references, no loops, ordered limits, rules evaluate, and widgets reference existing items.

### 8.6d Plant limits and settings
`services/limits.py`, endpoints under `/plants/{plant_id}/...`; the plant must be in the caller's scope (else 404).
- **Effective limits** (`plant_limits(db, plant_id)`): the plant's own `limits` row if present, otherwise the parameter's default limits, otherwise none. Step 3 uses the same function for statuses and alerts.
- **Who may edit:** `limits.write` (manager), **or** `limits.write_without_manager` (company admin) **only while `plant_has_active_manager()` is false**, checked at request time. `GET` returns `has_manager` and `can_edit`, so the UI knows. `PUT` takes a list of `{parameter_key, warn_min, good_min, good_max, warn_max}`; ordering is enforced by Pydantic and by a database check constraint. `DELETE /limits/{key}` reverts to the default.
- **Plant settings:** known settings live in `PLANT_SETTING_TYPES` (currently `clean_baseline_approach: float`). Each value is the plant's own value, else the company default. Editing uses the same rule with `plant_settings.write` (manager) or the no-manager fallback.

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
| GET / POST | `/companies/{id}/parameters` | config.manage | List all (incl. inactive) / create (validated) |
| PATCH | `/companies/{id}/parameters/{key}` | config.manage | Update; `is_active: false` refused (409) while used |
| POST | `/companies/{id}/formulas/test` | config.manage | `{formula, values?, base?}` → `{ok, result, references, error}` |
| GET / PUT | `/companies/{id}/treatments` | config.manage | List / upsert by `parameter_key` + `direction` |
| GET / POST | `/companies/{id}/rules` | config.manage | List / create |
| PATCH | `/companies/{id}/rules/{code}` | config.manage | Update (version +1 when an expression changes) |
| POST | `/companies/{id}/rules/test` | config.manage | `{condition_expr, probability_expr?, values, base?}` → `{ok, matched, probability, references, error}` |
| GET / POST | `/companies/{id}/modules` | config.manage | List / create (layout validated; `warnings` for missing references) |
| PATCH | `/companies/{id}/modules/{key}` | config.manage | Update title, order, layout, active |
| POST | `/companies/{id}/apply-template?template=default` | config.manage | Add missing template items → `{template, added}` |
| GET | `/plants/{id}/limits` | limits.read | Effective limits + `has_manager`, `can_edit` |
| PUT | `/plants/{id}/limits` | limits.write, or company admin without manager | `{items: [...]}` |
| DELETE | `/plants/{id}/limits/{key}` | same | Revert one parameter to its default limits |
| GET | `/plants/{id}/settings` | limits.read | e.g. `clean_baseline_approach` with `source` |
| PUT | `/plants/{id}/settings` | plant_settings.write, or company admin without manager | `{values: {clean_baseline_approach: 4.5}}` |

Password policy: at least 10 characters, a letter and a digit, must not contain the username. Usernames: 3–50 of `A–Z a–z 0–9 . _ -`, stored lower-case, unique across the platform.

## 10. Data model (migrations 0002–0003)

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

-- 0003 configuration
parameters        id, company_id, key (unique per company), label, unit, group_key, kind (input|calculated),
                  formula (required iff calculated), formula_version, precision, sort_order, is_active,
                  sample_value, default_warn_min/good_min/good_max/warn_max (all or none)
limits            (plant_id, parameter_id) PK, company_id, warn_min, good_min, good_max, warn_max
                  (check: ordered), updated_by, updated_at
plant_settings    (plant_id, key) PK, company_id, value jsonb, updated_by, updated_at
treatments        id, company_id, parameter_id, direction (high|low) (unique per parameter+direction),
                  cause, treatment, precautions, needs_review, updated_at
rules             id, company_id, code (unique per company), title, kind (predicted_problem),
                  condition_expr, probability_expr, action_text, affects_modules[], is_active, version,
                  sort_order, created_at, updated_at
modules           id, company_id, key (unique per company), title, sort_order, is_active,
                  layout jsonb {"widgets": [...]}, created_at, updated_at
companies.settings["plant_setting_defaults"]   company-wide defaults for plant settings
```

All primary keys are UUIDs generated by Postgres (`gen_random_uuid()`), so ids cannot be guessed.

## 11. Testing

- `tests/conftest.py`: the app runs against `smayaa_test` as **`smayaa_app`**, so RLS is active in tests. The schema is migrated once per run (as the owner). After each test, tenant tables are truncated.
- `tests/helpers.py`: `make_company`, `make_plant`, `make_user`, `make_tenant` (company + 2 plants + admin/manager/operator; manager and operator at plant A only), `with_template` (applies the default template), `login`. Test data is written as the owner role.
- Step 2 tests: `test_engine` (evaluator incl. unsafe expressions, statuses, calculation order, rule helpers), `test_template` (the template is valid; companies get it; re-applying adds nothing), `test_config_api` (formula validation, cycles, reserved keys, versioning, deactivation blocked by dependents, rules, modules, treatments, tenant users get 403), `test_limits` (manager edits, operator 403, company-admin fallback, plant/company isolation, settings, RLS).
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
- Every change to companies, plants, users or configuration writes an audit entry in the same transaction.
- Delete = deactivate for users, plants, companies, parameters, rules and modules. (A plant's own limit row may be removed to fall back to the default.)
- Formulas and rules are evaluated only by `app/engine/evaluator.py`; never `eval`/`exec`.
- New tenant tables: add `company_id` (+ `plant_id`), enable RLS in the same migration, and add them to `TENANT_TABLES` in `tests/conftest.py`.
- Type hints everywhere; `mypy --strict` and `ruff` must pass.
- Migrations: autogenerate, then read and fix the file; hand-written SQL (RLS) goes in the same migration; downgrades must work (CI runs up → down → up).
- Keep this guide and `LEARNING_JOURNAL.md` updated with every change.
