# SMAYAA.ai – Developer Guide

For developers joining the project. This guide describes **only what exists in the code today**.

_Last updated: 2026-10-21_

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
| 3 – Readings and alerts (readings as events, merge on save, preview, alerts, predicted problems, module screens) | Done (API) |
| 4 – Module renderer (React widget registry, module screens, autosave + live preview, alert bar, polling) | Done (first version; visual design to be aligned with the original demo) |
| 5 – Management screens (Users, Plants, Limits + plant settings, Operator profiles, Companies, Configuration editors with live tests, Audit log) | Done (first version) |
| Production deployment (single Ubuntu server, section 14) | Deployed and verified in both modes: Caddy (fresh server) and nginx (shared server next to another site, custom API port) |

## 3. Repository layout

Repository: https://github.com/MuskanKundu27/SMAYAA (default branch `main`)

```
README.md
.env.example              Template for the local .env (copy it; never commit .env)
.pre-commit-config.yaml   Checks that run on every git commit
.github/workflows/ci.yml  GitHub Actions: API, web and Docker build jobs
docker-compose.yml        Optional full stack in Docker (not required for local dev)
deploy/                   Production on one Ubuntu server (section 14): setup-server.sh, Caddyfile,
                          nginx-smayaa.conf, smayaa-api.service, backup.sh, update-api.sh, push-web.ps1
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
                          config (Parameter, Limit, PlantSetting, Treatment, Rule, Module),
                          readings (Reading)
    auth/                 principal (Principal), provider (AuthProvider, PasswordAuthProvider),
                          dependencies (get_principal, CurrentPrincipal, require)
    engine/               Pure calculation code (no DB): evaluator (safe expressions),
                          status (limits → good/warn/bad), calculation (order, calculate, rules)
    templates/default.py  The default template (parameters, treatments, rules, modules) as data
    services/             Business rules: auth, companies, plants, users, audit (+ listing), operator_profiles, parameters,
                          rules, modules (+ treatments), templates, limits (+ plant settings),
                          config_common (shared helpers), readings, plant_state (values,
                          statuses, alerts, predicted problems), plant_views (module screens)
    schemas/              Pydantic request/response models (config.py has the widget types;
                          admin.py: operator profiles, audit entries)
    routers/              HTTP endpoints: health, auth (+ /me), companies, plants, users,
                          config (company configuration), limits (plant limits + settings),
                          readings (readings, alerts, plant modules), operator_profiles, audit
    scripts/seed_dev.py   Demo data for local development
    scripts/create_platform_admin.py  Creates the first platform admin (all environments)
  migrations/versions/    0001 baseline, 0002 identity + tenancy + RLS, 0003 configuration + RLS,
                          0004 readings + RLS
  scripts/                create_dev_db.sql, grant_app_role.sql, docker-init-db.sh
  tests/                  pytest: conftest (test DB setup), helpers (data builders), test_*.py
web/                      Frontend (React 19 + TypeScript + Vite + react-router 7)
  src/
    main.tsx, App.tsx     Entry point; routes (login when signed out, AppLayout when signed in)
    api/client.ts         fetch wrapper: in-memory access token, auto refresh on 401, ApiError
    api/types.ts          API response types (Me, Tile, WidgetView, ModuleView, Alert, ...)
    api/plant.ts          Plant endpoints: modules, module view, alerts, latest, save, preview
    api/admin.ts          Management endpoints: users, plants, companies, limits, settings, operator
                          profiles, configuration (parameters, formulas, treatments, rules, modules,
                          template), audit log
    admin/                Management screens: UsersPage, PlantsPage, LimitsPage (+ plant settings),
                          OperatorProfilesPage, CompaniesPage, AuditLogPage, config/ (ConfigurationPage
                          with Parameters, Treatments, Rules, Modules, Template tabs); useLoad.ts
                          (load + reload + errorMessage), ui.tsx (ErrorText, Notice, Loading,
                          StatusBadge), limits.ts (limit draft parsing)
    auth/AuthContext.tsx  AuthProvider: session restore on load, login/logout, selected plant
    auth/useAuth.ts       useAuth() hook and AuthState type
    plant/                PlantDataProvider (module list, alerts, polling → `version`), usePlantData
    modules/ModulePage.tsx  A module screen: loads the view, drafts, autosave, live preview
    modules/editing.ts    ModuleEditing context shared by widgets (drafts, commit, preview)
    modules/widgets.tsx   Widget components (tiles, inputs summary, problems, alerts, trend, note)
    modules/registry.ts   Widget registry: widget type → component (+ UnknownWidget fallback)
    components/           TileCard, StatusPill, RangeBar, AlertBar
    format.ts             Display helpers (numbers, times, limits text, range bar, input parsing)
    navigation.ts         Fixed menu pages and the permission each needs (modules come from API);
                          manageableRoles (from users.manage:<role>), roleNeedsPlant
    layout/AppLayout.tsx  Sidebar (modules from API + fixed pages), top bar, alert bar
    pages/                LoginPage, HomePage, StatusPages (NoAccess, NotFound)
    *.test.ts             vitest tests
```

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

The seed also gives Demo Power Ltd the default template and the plant a first reading with the sample values (entered by `manager1`).

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
   | readings | own company + visible plant (**no platform clause**) | insert only; UPDATE/DELETE privileges revoked (append-only) |

   Plant data (limits, plant settings, and readings from step 3) has **no** platform clause, so the super admin can never read it.

### 8.6 Audit log
`services/audit.record(...)` adds an `audit_log` row in the same transaction as the change (company/plant/user create, update, deactivate). `audit.snapshot()` produces JSON-safe before/after values.

### 8.6a Calculation engine (`app/engine/`)
Pure functions, no database, so they are easy to test and reuse.
- **`evaluator.py`:** `parse(source, functions=None)` turns text into a checked `Expression`. It uses Python's `ast` parser, then rejects everything not on a whitelist:
  - **Allowed:** numbers, strings (for helper arguments), names, `+ - * / **`, comparisons (chains allowed), `and/or/not`, lists, and calls to `min max abs round sqrt log exp if_else coalesce` (plus the time functions, and the rule helpers when parsing rules). `coalesce(a, b, ...)` returns the first argument with a value, e.g. `coalesce(load, 100)` for an optional input.
  - **Rejected:** attributes, indexing, lambdas, comprehensions, keyword arguments, unknown functions, more than 500 characters, more than 200 nodes.

  `Expression.references` lists every parameter key used, including string arguments to helpers like `off('ph')` and time functions like `rate('dp', 24)`. `Expression.required` is the subset whose **current** value must exist: keys used only inside `coalesce(...)` or a time function are optional. `Expression.history_hours` is how much history the time functions in it need (0 = none). `evaluate(expr, variables, functions)` **never raises for data problems**: a missing value, division by zero, `sqrt` of a negative, overflow, or an exponent above 100 all give `None` ("No data"). `if_else(cond, a, b)` evaluates only the chosen branch. **`eval`/`exec` are never used.**
- **`status.py`:** `status_of(value, Limits)` returns `good` / `warn` (+ direction) / `bad` (+ direction) / `na`, exactly per the brief (inclusive bounds; no limits = always good). `SEVERITY_POINTS` gives 20 for warn and 40 for bad.
- **`calculation.py`:**
  - `calculation_order(formulas)` sorts formulas topologically (Kahn's algorithm) and raises `CycleError` on loops.
  - `parse_formula(source)` parses a formula (math functions + time functions). `calculate(inputs, formulas, base, history=None)` computes every calculated key in that order. `base` is the reserved name for the plant's clean baseline approach. Without `history`, time functions give `None`.
  - `RuleContext(values, statuses, history=None)` provides the rule helpers `value`, `status`, `off`, `sev` and `count_off`, plus the time functions. A missing value counts as **not off**, so no data never raises a prediction.
  - `parse_rule` and `evaluate_rule` work like `parse` and `evaluate`, with those helpers.
- **`history.py` (time functions):** formulas and rules can look back at the plant's earlier readings. One general mechanism, so trend KPIs are configuration, not code. `History(now, points)` holds earlier readings (oldest first, each with its stored input and calculated values); `TimeFunctions` binds the functions to a history and the current values:

  | Function | Meaning |
  |---|---|
  | `change('k', h)` | k now minus k at the oldest reading in the last h hours |
  | `rate('k', h)` | that change per hour (× 24 for per day) |
  | `avg('k', h)` | average over the window, including now |
  | `total('k', h)` | time integral over the window (m³/h → m³), trapezoid rule |
  | `events('e', h)` | how many times on/off input e switched on (≥ 0.5) in the window |
  | `hours_since('e')` | hours since e last switched on |
  | `before_event('k', 'e')` / `after_event('k', 'e')` | k just before e last started / just after it last ended |

  `change` and `rate` need readings spanning at least 10 % of the window (`MIN_SPAN_FRACTION`); otherwise `None`, because autosaves seconds apart would turn tiny differences into absurd rates. Windows are capped at 90 days; event functions look back 30 days. "Now" is the time of the reading being calculated.

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
- The default template is plain Python data and follows the engineering note's Thermal Efficiency and Side-Stream Filtration modules:
  - **Inputs (31):** chemistry (pH, conductivity, TDS, hardness, alkalinity, silica, microbial count); thermal (supply/return temperature, wet-bulb, circulating flow, fan power, fan speed, pump speed, pump power, pump discharge pressure, process load); side-stream filter (inlet/outlet pressure, side-stream flow, inlet/outlet turbidity, inlet/outlet TSS, cleaning/backwash status, backwash flow and time, oil-in-water, bypass valve status, side-stream pump status). Optional inputs have no limits; on/off inputs use 1 = yes.
  - **Calculated (21):** LSI (demo); thermal: range, approach, heat load, expected approach (**demo model**: clean baseline scaled for process load and fan speed), approach residual (actual − expected), fan response (6 h), specific fan energy; filter: ΔP, removal efficiency, ΔP rate of change, ΔP forecast 6 h / 24 h, time to clean (P50, to 1.2 bar), solids load proxy, cleanings and average cleaning interval (7 days), time since last cleaning, ΔP recovery, water per cleaning, m³ treated per cleaning (7 days). Trend KPIs use the time functions.
  - **Rules (13):** FLT-P01..P07 and TH-P01..P06 as named in the note. Conditions use today's values where possible and trends (with `coalesce(..., 0)` where a missing trend should count as "no change"). Probabilities are demo heuristics.
  - **Modules (3):** Water Chemistry (data entry), Side-Stream Filtration and Thermal Efficiency (KPI tiles, a 7-day trend chart, inputs used, predicted problems, notes).
  - 20 treatments (flagged `needs_review`) and plant-setting defaults (`clean_baseline_approach = 4.0`, stored in `companies.settings["plant_setting_defaults"]`).
- `services/templates.apply_template(db, company, template, actor_id, update_existing=False)` **adds only what is missing** (by parameter key, rule code, module key, treatment parameter+direction), so it is safe to run again and keeps a company's own edits. With **`update_existing=True`** ("update to the latest template") it also refreshes the template's own existing parameters (label, unit, group, formula with a version bump, precision, default limits), rules (title, expressions with a version bump, action, affected modules) and modules (title, layout). Items the company added itself and treatments are never touched; the change is audited.
- `POST /companies` applies the default template automatically. `POST /companies/{id}/apply-template` re-applies it (adds anything missing); `?update_existing=true` updates to the latest template. The dev seed applies it to Demo Power Ltd.
- `tests/test_template.py` checks that the template is valid on its own: references, no loops, ordered limits, rules evaluate, and widgets reference existing items.

### 8.6d Plant limits and settings
`services/limits.py`, endpoints under `/plants/{plant_id}/...`; the plant must be in the caller's scope (else 404).
- **Effective limits** (`plant_limits(db, plant_id)`): the plant's own `limits` row if present, otherwise the parameter's default limits, otherwise none. Step 3 uses the same function for statuses and alerts.
- **Who may edit:** `limits.write` (manager), **or** `limits.write_without_manager` (company admin) **only while `plant_has_active_manager()` is false**, checked at request time. `GET` returns `has_manager` and `can_edit`, so the UI knows. `PUT` takes a list of `{parameter_key, warn_min, good_min, good_max, warn_max}`; ordering is enforced by Pydantic and by a database check constraint. `DELETE /limits/{key}` reverts to the default.
- **Plant settings:** known settings live in `PLANT_SETTING_TYPES` (currently `clean_baseline_approach: float`). Each value is the plant's own value, else the company default. Editing uses the same rule with `plant_settings.write` (manager) or the no-manager fallback.

### 8.6e Readings (`services/readings.py`)
- **A reading is an immutable event.** `POST /plants/{id}/readings` takes **only the changed values** (`{"values": {"hard": 650}}`; `null` clears a value).
- The server merges them onto the latest reading's inputs, recalculates every calculated parameter with the **current** formulas and the plant's baseline, and inserts a **new row** with:
  - `input_values`: the full merged set;
  - `calculated_values`;
  - `formula_versions`: the version of each formula used;
  - `settings_used`: e.g. the baseline value;
  - `changed_keys`;
  - `created_by` and `recorded_at`.
- Two people saving different fields at the same time both keep their change; for the same field, last save wins. If nothing actually changed, no row is added (`created: false`, HTTP 200 instead of 201).
- **Validation:** only active **input** parameters may be sent (unknown/inactive or calculated keys → 422 with per-field details); values must be finite numbers or `null`.
- **Who may save:** `readings.write` (manager, operator; the company admin is view-only) **and**, if an `operator_profiles` row exists for the user at that plant, `can_edit_readings`. No row = allowed.
- `POST .../readings/preview` returns tiles, alerts and problems for unsaved values (used for the live preview while typing). Nothing is stored.
- `GET .../readings/latest` returns the newest reading (or `null`); screens poll it and reload when the id changes. `GET .../readings?from=&to=&limit=&offset=` returns history, newest first, **with values exactly as stored** at save time. So changing a formula never rewrites history (tested).

### 8.6f Plant state, alerts, predicted problems (`services/plant_state.py`)
`build_state(db, plant, inputs, now=None)` is the one function that turns input values into a `PlantState`: active parameters, effective limits, all values (inputs + calculated with **current** formulas and baseline) and statuses. `now` is the moment the inputs belong to (the latest reading's time for live screens; the current time for saving and preview). If any active formula or rule uses time functions, `load_history` loads the plant's readings from the needed window before `now` (newest 5,000 at most) and passes them to the calculation and the rule helpers. Saving a reading stores calculated values computed with that history too. The alert bar, module screens and preview all use it, so they always agree. Live screens therefore reflect formula, limit or baseline changes immediately, while history keeps the stored values.
- **Alerts** (`alerts(db, state)`): every parameter whose status is `warn` (severity `medium`) or `bad` (severity `high`), with value, unit, direction, limits, cause/treatment/precautions from `treatments` (or `FALLBACK_TREATMENT`), `needs_review`, and **modules affected**. Sorted most severe first.
- **Modules affected** (`affected_modules`) are worked out from configuration, not hard-coded. A module is affected by parameter X if:
  - it shows X or any calculation that (indirectly) uses X; or
  - it shows a rule that uses X; or
  - a rule using X lists the module in `affects_modules`.

  Example: hardness → Water Chemistry (shown there) + Thermal (TH rules and LSI use it) + Side-Stream Filtration (the fouling rule TH-P02 lists it in `affects_modules`).
- **Predicted problems** (`predicted_problems`): every active rule is evaluated with the rule helpers and time functions. A rule is reported as **insufficient data** instead of guessing when a value it needs right now (`Expression.required`) is missing (no data, or an inactive parameter), or when its condition can't be decided (e.g. a trend without enough history). Matches are sorted by probability (0–100, rounded), highest first. All matches are shown (no first-match logic).

### 8.6g Module screens for plant users (`services/plant_views.py`)
- `GET /plants/{id}/modules` lists the company's active modules, filtered by the operator profile's `visible_modules` if one exists. Needs `modules.view`.
- `GET /plants/{id}/modules/{key}` returns the layout with **the data each widget needs**, so the frontend only draws (it never calculates statuses):

  | Widget | Data returned |
  |---|---|
  | `input_group` | tiles for the group's (or listed) input parameters; `editable` if the user may save readings |
  | `value_tiles`, `inputs_summary` | tiles for listed parameters |
  | `predicted_problems` | matched problems for the listed rules + `insufficient_rules` |
  | `alert_list` | current alerts (optionally filtered by `modules`/`params`) |
  | `trend_chart` | series of `{t, v}` from readings in the last `hours` (max 500 points) with limits |
  | `text_note` | the text |

  A tile has key, label, unit, precision, kind, value, status (`good|warn|bad|na`), direction, limits, editable, and `insufficient_data` (true when the parameter is missing or inactive). This is how widgets **degrade gracefully** instead of failing.
- `GET /plants/{id}/alerts` is for the alert bar: the latest reading's summary ("saved by X at …") + alerts. Needs `alerts.view`; empty if an operator profile has `show_alerts = false`.
- The super admin has none of these permissions, and RLS gives the platform path no access to readings.

### 8.7 Web ↔ API
In development the browser talks only to Vite (:5173), which proxies `/api` to FastAPI (:8000). In Docker/production nginx does the same. One origin keeps the refresh cookie simple.

### 8.8 Web app
- **Session:** `api/client.ts` keeps the access token **in memory only** (never in localStorage). On page load `AuthProvider` calls `POST /auth/refresh`; the httpOnly cookie restores the session silently. Any request that gets a 401 triggers one refresh and a retry; concurrent requests share one refresh call. If refresh fails, the app returns to the login page.
- **Menu:** `navigation.ts` lists menu entries with the permission each needs; `menuFor(me.permissions)` filters them. Routes for pages the user lacks permission for show "No access". This is convenience only: the API enforces permissions on every request.
- **Plant switcher:** shown in the top bar only when `/me` returns more than one plant. The choice is remembered in localStorage (wrapped in try/catch; purely a convenience).
- **Module menu from the API:** `PlantDataProvider` loads `GET /plants/{id}/modules` for the selected plant; the sidebar's "Modules" section and the Home tiles list them (route `/m/:moduleKey`). Nothing about modules is hard-coded in the web app.
- **Polling for shared updates:** `PlantDataProvider` polls `GET /plants/{id}/readings/latest` every 5 s (`POLL_INTERVAL_MS`). When the reading id changes (anyone saved), it increments `version` and reloads the alerts; module screens re-fetch when `version` changes. After your own save, `refresh()` triggers this immediately. Data is tagged with its plant id, so switching plants never shows the previous plant's data.
- **Module screens** (`modules/ModulePage.tsx`): fetch `GET /plants/{id}/modules/{key}` and render each widget through the **registry** (`modules/registry.ts`). The browser never decides statuses; the API sends them on each tile. Unknown widget types render `UnknownWidget` instead of breaking. `ModulePage` is keyed by plant + module, so switching gives a fresh screen.
- **Autosave and live preview** (owner decision): an editable tile is a text box.
  - **While typing:** after 400 ms the page calls `POST .../readings/preview` with all current drafts. Tiles (including calculated ones) show the previewed values and statuses; only this user sees them.
  - **On blur or Enter:** the draft is parsed (`format.parseInput`; empty clears the value). If it differs from the saved value, `POST .../readings` sends **only that field**. The tile shows "Saving…" then "Saved ✓".
  - **Escape** cancels the draft.
  - **After a save:** the typed text is kept until the refreshed screen arrives (no flicker), and errors are shown on the tile.
  - The header shows "Last updated by X at HH:MM".
- **Alert bar** (`components/AlertBar.tsx`): on every page for users with `alerts.view` and a selected plant. It shows a green "all within range" or a count with the top alerts (↑/↓), plus who updated last. Expanding it shows each alert's limits, affected modules, cause/treatment/precautions, and a "sample guidance – to be reviewed" note when `needs_review`.
- **Management screens** (`admin/`), one per fixed menu entry; `App.tsx` maps each path in `MENU` to its page (`PAGES`):
  - **Users:** list in scope; create form offers only the roles from the caller's `users.manage:<role>` permissions (plant for plant roles; company for a platform admin creating a company admin); deactivate with confirmation, showing the API's warnings (e.g. "plant has no manager").
  - **Plants** (company admin): create, rename, deactivate/reactivate; calls `reloadMe()` afterwards so the plant switcher and forms see the change.
  - **Limits** (selected plant): table grouped by parameter group with the four thresholds and the source (this plant / company default); editable only when the API says `can_edit` (manager, or company admin while there is no manager, with a banner explaining it); "Use default" per row; plant settings (clean baseline approach) below.
  - **Operator profiles** (manager): per operator, "all modules" or a chosen list, may enter readings, sees alerts; save or reset to defaults.
  - **Companies** (platform admin): create with the first company admin (gets the default template), deactivate/reactivate, link to Configuration.
  - **Configuration** (platform admin, `?company=&tab=` in the URL): Parameters & formulas (editor with live formula test on sample values, default limits, deactivate), Treatments (pick parameter + direction, needs-review flag), Rules (editor with module checkboxes and a test panel with editable input values), Modules (title, order, active, layout as validated JSON, warnings for missing references), Template (apply default; adds only what is missing).
  - **Audit log:** newest first, filter by company (platform) and entity, paging, changed fields per entry.
- **Labels:** predicted problems show "Probabilities are demo heuristics, not engineering guarantees."
- **Styling:** plain CSS in `src/index.css` with CSS variables (navy/blue palette; status colours good/warn/bad/na). To be aligned with the original SMAYAA demo design once the reference files are available.

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
| POST | `/companies/{id}/apply-template?template=default` | config.manage | Add missing template items → `{template, added, updated}`; `&update_existing=true` also updates the template's existing parameters, rules and modules (audited) |
| GET | `/plants/{id}/limits` | limits.read | Effective limits + `has_manager`, `can_edit` |
| PUT | `/plants/{id}/limits` | limits.write, or company admin without manager | `{items: [...]}` |
| DELETE | `/plants/{id}/limits/{key}` | same | Revert one parameter to its default limits |
| GET | `/plants/{id}/settings` | limits.read | e.g. `clean_baseline_approach` with `source` |
| PUT | `/plants/{id}/settings` | plant_settings.write, or company admin without manager | `{values: {clean_baseline_approach: 4.5}}` |
| POST | `/plants/{id}/readings` | readings.write (+ operator profile) | `{values: {key: number|null}}` (changed fields only) → 201 `{reading, created: true}` or 200 if unchanged |
| POST | `/plants/{id}/readings/preview` | readings.write | Same body → tiles, alerts, problems; nothing stored |
| GET | `/plants/{id}/readings/latest` | readings.read | Newest reading or `null` (for polling) |
| GET | `/plants/{id}/readings` | readings.read | History, newest first; `from`, `to`, `limit`, `offset` |
| GET | `/plants/{id}/alerts` | alerts.view | `{reading, alerts}` for the alert bar |
| GET | `/plants/{id}/modules` | modules.view | Modules the user may open |
| GET | `/plants/{id}/modules/{key}` | modules.view + readings.read | Widgets with their data (see 8.6g) |
| GET | `/plants/{id}/operator-profiles` | operator_profiles.manage | Lower-ranked users at the plant (that the caller may manage) with their profile; `is_default` when no restrictions are stored |
| PUT | `/plants/{id}/operator-profiles/{user_id}` | operator_profiles.manage | `{visible_modules: [...] | null, can_edit_readings, show_alerts}` (`null` = all modules, incl. future ones; unknown modules → 422) |
| DELETE | `/plants/{id}/operator-profiles/{user_id}` | operator_profiles.manage | Remove restrictions (back to defaults) |
| GET | `/audit-log` | audit.read | Newest first, paginated; `entity=`; `company_id=` (platform users only). Non-platform users see their own company only. Actor shown as name, "SMAYAA platform" (outside the viewer's company) or "System" |

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

-- 0004 readings (append-only)
readings          id, company_id, plant_id, recorded_at, created_by, source (manual|seed|…),
                  input_values jsonb, calculated_values jsonb, formula_versions jsonb,
                  settings_used jsonb, changed_keys[]      index (plant_id, recorded_at DESC)
```

All primary keys are UUIDs generated by Postgres (`gen_random_uuid()`), so ids cannot be guessed.

## 11. Testing

- `tests/conftest.py`: the app runs against `smayaa_test` as **`smayaa_app`**, so RLS is active in tests. The schema is migrated once per run (as the owner). After each test, tenant tables are truncated.
- `tests/helpers.py`: `make_company`, `make_plant`, `make_user`, `make_tenant` (company + 2 plants + admin/manager/operator; manager and operator at plant A only), `with_template` (applies the default template), `login`. Test data is written as the owner role.
- Step 2 tests: `test_engine` (evaluator incl. unsafe expressions, statuses, calculation order, rule helpers), `test_template` (the template is valid; companies get it; re-applying adds nothing), `test_config_api` (formula validation, cycles, reserved keys, versioning, deactivation blocked by dependents, rules, modules, treatments, tenant users get 403), `test_limits` (manager edits, operator 403, company-admin fallback, plant/company isolation, settings, RLS).
- Time functions and KPIs: `test_engine` (change/rate/avg/total/event functions, minimum span, required references, coalesce), `test_template` (trend KPIs from a sample history, every rule decidable with history, sample snapshot predicts only TH-P02, update to latest template), `test_readings::test_trend_kpis_and_predictions_use_the_plant_history` (ΔP rate, time to clean and FLT-P01 from stored history).
- Step 3 tests (`test_readings`): saving and merging (two users, different fields), no-op saves, validation, clearing values, **history unchanged after a formula change**, preview stores nothing, latest/history filters, permissions (company admin view-only, super admin 403, operator profile), alerts (severity, direction, treatment, fallback, modules affected; a limit change clears an alert; manager and operator see the same), module screens (layout from configuration, Filter/Thermal react to chemistry, insufficient data, **a new calculation appears in a module without code changes**), and the database layer (readings can't be updated/deleted; other companies and the platform see none).
- Step 5 tests (`test_operator_profiles_and_audit`): manager lists/restricts/resets operators and it is enforced on modules and saving; unknown modules rejected; other plants, self and other companies refused; operators and company admins get 403; audit log scoped per company, platform sees all and filters; plant users get 403. `test_create_platform_admin`: the CLI command.
- Test files: `test_auth` (login, lockout, rate limit, refresh rotation and reuse detection, logout, deactivated users), `test_me_and_permissions` (per-role access matrix), `test_companies_and_plants`, `test_users` (rank rule, validation, deactivation, last-manager warning), `test_isolation` (company/plant isolation via API **and via raw SQL under RLS**), `test_rate_limit`, `test_health`.
- In the test environment password hashing uses deliberately cheap argon2 parameters for speed.
- **Web:** `npm test` (vitest). `navigation.test.ts` checks the fixed menu per role; `api/client.test.ts` checks token storage, refresh-and-retry, shared refresh, and session end (with a mocked `fetch`); `format.test.ts` checks number formatting, input parsing, range-bar positions and limits text; `admin/limits.test.ts` checks limit-draft parsing (order, empty rows); `modules/modules.test.ts` checks the widget registry covers every API widget type, the unknown-type fallback, and the live-preview tile overlay. (No component rendering tests yet; adding React Testing Library is a later improvement.)

## 12. Quality gates and CI

- **pre-commit** (`.pre-commit-config.yaml`): blocks secret files (`.env`), whitespace/EOF fixes, YAML/TOML checks, large files, private keys, ruff lint + format on `api/`.
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

## 14. Production deployment (one Ubuntu server)

The first production setup runs everything on **one Ubuntu 24.04 server**, without Docker, to keep memory use low on a small instance (1 GB RAM is enough):

```
Internet ──443/80──► Caddy or nginx ──/api/*──► uvicorn (127.0.0.1:8000, systemd "smayaa-api") ──► PostgreSQL (local)
                       └── everything else ──► /var/www/smayaa (built web app)
```

**Shared servers.** The script only adds its own pieces (user `smayaa`, `/opt/smayaa`, database `smayaa` and its two roles, service `smayaa-api`, one web-server site), so it can run next to other applications:
- If **nginx is already installed**, it uses nginx (`WEB_SERVER=nginx`): adds one site for the SMAYAA hostname, runs `nginx -t` before reloading (and removes our site again if the test fails), and lets certbot add HTTPS to that site only. Other sites are not modified.
- If **PostgreSQL is already installed**, it reuses that server (reads its port) and only adds the `smayaa` database and roles.
- If **port 8000 is taken**, it stops and asks for another: `sudo API_PORT=8010 bash setup-server.sh <hostname>`.
- It adds a swap file only when the server has no swap at all.

| Piece | Where |
|---|---|
| Code (git checkout of `main`) | `/opt/smayaa/app`, owned by system user `smayaa` |
| Python environment | `/opt/smayaa/venv` (API installed editable from `/opt/smayaa/app/api`) |
| Settings | `/opt/smayaa/app/.env` (mode 600; generated once with random DB passwords and `JWT_SECRET`; `ENVIRONMENT=production`) |
| Database | local PostgreSQL 16, database `smayaa`, roles `smayaa_owner` / `smayaa_app` (same model as development) |
| API service | `/etc/systemd/system/smayaa-api.service` (from `deploy/`, port filled in), one uvicorn worker on `127.0.0.1:$API_PORT` (default 8000), `--proxy-headers` so the login rate limiter sees real client IPs |
| Web server / HTTPS | **Caddy** (`/etc/caddy/Caddyfile` from `deploy/Caddyfile`, automatic certificates) on a fresh server, or **nginx** (`/etc/nginx/sites-available/smayaa` from `deploy/nginx-smayaa.conf`, certificate via `certbot --nginx`, auto-renewed by certbot's timer) when nginx is already installed. Both add security headers incl. CSP and HSTS |
| Setup choices | `/opt/smayaa/deploy.env` (`WEB_SERVER`, `API_PORT`, `HOST`), reused by re-runs and `update-api.sh` |
| Web app files | `/var/www/smayaa` (built on a developer machine and uploaded; the server does not need Node) |
| Backups | `/var/backups/smayaa`, nightly 02:30 UTC via `/etc/cron.d/smayaa-backup`, 14 days kept |

**Hostname.** Without a bought domain, use the free wildcard DNS service sslip.io: `smayaa.<ip-with-dashes>.sslip.io` resolves to that IP (e.g. `smayaa.3-110-175-240.sslip.io`). A real domain can replace it later by pointing it at the server and re-running the setup script with the new name (then update `CORS_ORIGINS` in `.env`). If the server's public IP changes (an AWS instance that is stopped and started without an Elastic IP), the hostname changes too.

**Network.** Open only 22 (SSH, ideally restricted to known IPs), 80 (certificate challenge + redirect) and 443. PostgreSQL and the API listen on localhost only. Log in with an SSH key; password login stays disabled (AWS default).

**First deployment**

```bash
# On the server (as the default "ubuntu" user):
curl -fsSLO https://raw.githubusercontent.com/MuskanKundu27/SMAYAA/main/deploy/setup-server.sh
sudo bash setup-server.sh smayaa.3-110-175-240.sslip.io

# On a developer machine (Windows PowerShell, repo root): build and upload the web app
powershell -ExecutionPolicy Bypass -File deploy\push-web.ps1 -Server 3.110.175.240 -Key $HOME\.ssh\smayaa-key.pem

# On the server: create the first platform admin (prompts for username and password)
cd /opt/smayaa/app/api && sudo -u smayaa /opt/smayaa/venv/bin/python -m app.scripts.create_platform_admin
```

The platform admin then creates companies (each gets the default template) and their company admins through the app. `seed_dev` refuses to run in production, so no demo accounts exist there.

**Updates**

| What changed | Run |
|---|---|
| API code or migrations (after pushing to `main`) | on the server: `sudo bash /opt/smayaa/app/deploy/update-api.sh` (backs up the database first, pulls, installs, migrates, restarts, checks `/api/v1/health`) |
| Web app | on a developer machine: `deploy\push-web.ps1` (as above; for password/other-port servers: `-Server <ip> -Port <ssh-port> -User <user>` without `-Key`) |
| Web-server config | on the server: re-run `setup-server.sh <hostname>` (every step is idempotent; `.env` is never overwritten; earlier `WEB_SERVER`/`API_PORT` choices are kept) |

**Operations**

| Task | Command (server) |
|---|---|
| API status / logs | `systemctl status smayaa-api` / `journalctl -u smayaa-api -f` |
| Web server logs | Caddy: `sudo tail -f /var/log/caddy/smayaa.log`; nginx: `sudo tail -f /var/log/nginx/smayaa.access.log` |
| Backup now | `sudo /usr/local/bin/smayaa-backup` |
| Restore a backup | `sudo -u postgres pg_restore --clean -d smayaa /var/backups/smayaa/<file>.dump` |

Backups live on the same disk as the database, so they protect against mistakes (bad migration, deleted data) but not against losing the server. Copy a recent dump to another machine from time to time (`scp`).
