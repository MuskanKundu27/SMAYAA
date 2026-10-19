# SMAYAA.ai – Developer Guide

For developers joining the project. This guide describes **only what exists in the code today**.

_Last updated: 2026-10-19_

## 1. What SMAYAA.ai is

A multi-tenant SaaS platform for cooling-tower water intelligence. Companies (tenants) own plants; plant staff enter water-chemistry, thermal and filter readings; the platform checks them against limits, raises alerts with treatments, computes KPIs and shows predicted problems. Parameters, formulas, limits, rules and module screens are configuration stored in the database, not code.

## 2. Status

Project initialised. **No application code yet.** The sections below will be filled in as each part is built.

## 3. Repository layout

Repository: https://github.com/MuskanKundu27/SMAYAA (default branch `main`)

```
README.md               Short project intro
.gitignore              Ignored files (secrets, build artefacts, private working files)
.gitattributes          Line endings forced to LF (needed for scripts run in Docker)
docs/
  DEVELOPER_GUIDE.md    This file
```

Some files exist only on the project owner's machine and are deliberately **not** in Git: the internal product brief, internal work log and reference designs. Do not commit them; they are listed in `.gitignore`.

## 4. Prerequisites

Local development currently runs **natively, without Docker**:

- **Python 3.12** – on Windows: `py install 3.12`, then use `py -3.12`.
- **PostgreSQL 16** – on Windows: `winget install --id PostgreSQL.PostgreSQL.16 -e` (runs as service `postgresql-x64-16` on port 5432; you choose the `postgres` superuser password during install).
- **Node.js 20+** and npm – for the web app.
- **Git**

Docker files will be provided for deployment and optional local use, but are not required.

## 5. Getting started

_Not yet available – will be added with step 0 (Foundation)._

## 6. Architecture

_To be written when the API and web app exist._

## 7. Data model

_To be written with the first migration._

## 8. Conventions

- Configuration (parameters, formulas, limits, treatments, rules, modules) is data, never hard-coded.
- Permissions are checked as permission strings plus scope, never by role name.
- Formulas are evaluated only by the safe evaluator; never `eval`/`exec`.
- Every change updates `docs/WORKLOG.md`, and this guide when architecture, setup or conventions change.
