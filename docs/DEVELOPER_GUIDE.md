# SMAYAA.ai – Developer Guide

For developers joining the project. This guide describes **only what exists in the code today**. Plans live in `CLAUDE.md` (product brief) and `docs/WORKLOG.md` (progress log).

_Last updated: 2026-10-19_

## 1. What SMAYAA.ai is

A multi-tenant SaaS platform for cooling-tower water intelligence. Companies (tenants) own plants; plant staff enter water-chemistry, thermal and filter readings; the platform checks them against limits, raises alerts with treatments, computes KPIs and shows predicted problems. Parameters, formulas, limits, rules and module screens are configuration stored in the database, not code. See `CLAUDE.md` for the full product brief.

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

- Docker Desktop (Windows: x86_64 build, WSL 2 backend)
- Git
- Node.js 20+ (for working on the web app outside Docker)

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
