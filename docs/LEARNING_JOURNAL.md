# SMAYAA.ai – Learning Journal

**Who this is for:** junior developers joining the project.
**What it is:** a diary of every step we take building SMAYAA.ai, in plain language. Each entry says **what** we did, **why** we did it, and **what you can learn** from it. Read it from top to bottom and you will understand how a real SaaS product is built from zero.

The newest entries are at the bottom. If a word is unfamiliar, check the Glossary at the end.

---

## Entry 1 – Starting with a written plan (2026-10-19)

**What we did**
Before writing any code, the project owner wrote a detailed brief describing the product, the users, the rules and the order of work.

**Why**
Code is expensive to change once it is written. A written plan lets everyone agree on *what* to build before arguing about *how*. It also means a new person (or an AI assistant starting a fresh session) can catch up by reading one document.

**What to learn**
- Spend time on the plan first. Ten minutes of thinking saves hours of rewriting.
- When something in the plan is unclear and would be costly to undo later, **ask** instead of guessing. We asked the owner questions one at a time and wrote every answer down.

---

## Entry 2 – Putting the code on GitHub (2026-10-19)

**What we did**
- Created a Git repository and pushed it to GitHub: https://github.com/MuskanKundu27/SMAYAA
- Added a `.gitignore` file.
- Added a `.gitattributes` file.

**Why**
- **Git** records every change to the code, who made it and why. If something breaks, we can see exactly what changed and go back.
- **GitHub** keeps a copy online, lets several people work together, and can run automatic checks on every change (we will set this up later).
- **`.gitignore`** tells Git which files must *never* be uploaded. Examples: passwords (`.env` files), downloaded libraries (`node_modules/`, `.venv/`), and private working notes. Uploading a password to GitHub, even once, means it must be considered leaked.
- **`.gitattributes`** fixes "line endings". Windows ends each line of text with two invisible characters (CRLF); Linux uses one (LF). Our app will run on Linux servers, and scripts with Windows line endings break there. This file makes Git always store LF.

**What to learn**
- Before every commit, run `git status` and check that no secret or private file is listed.
- Write commit messages that explain the change, e.g. "Docs: native local setup prerequisites".

---

## Entry 3 – Setting up the computer without Docker (2026-10-19)

**What we did**
- Installed **Python 3.12** next to the Python 3.15 that was already on the computer.
- Installed **PostgreSQL 16** (the database) as a Windows service.
- Generated a random database password and saved it in a file that Git ignores.

**Why**
- **Docker** packs an app and everything it needs into a "container" so it runs the same everywhere. It is great, but it was not installed, so we chose to install the two things we actually need directly. We will still add Docker files later for deployment.
- **Why Python 3.12 and not the newer 3.15?** Brand-new Python versions often lack ready-made packages for libraries we depend on (for example password hashing and the PostgreSQL driver). 3.12 is mature and well supported. Several Python versions can live side by side: `py -3.12` picks 3.12.
- **Why PostgreSQL?** It is a reliable, free database used by many large companies. It has two features we need: **JSONB** (store flexible values like `{"ph": 7.9, "hard": 650}` without changing table structure) and **row-level security** (the database itself refuses to show one company's rows to another company).
- **Why a random password in an ignored file?** Passwords must never be written in code or committed to Git. Code reads them from environment variables at runtime.

**What to learn**
- Pick stable, well-supported versions of tools over the newest ones.
- Secrets live in environment variables / `.env` files, never in code, never in Git.

---

## Entry 4 – Early product decisions and why they matter (2026-10-19)

**What we decided**
1. **Every customer (company) shares one database, but each row is labelled with its `company_id`.** This is called *multi-tenancy*.
2. **Users only see the plants they are assigned to.** A company admin sees all plants of their own company, never another company's.
3. **The super admin (us, the platform owner) creates the company admin accounts.** Customers cannot sign themselves up.
4. **When several predicted problems apply, show all of them**, highest probability first.

**Why**
- One shared database is cheaper and simpler to run than one database per customer. The risk is data leaking between customers, so we protect against it **twice**: in the application code *and* in the database (row-level security). If one layer has a bug, the other still blocks the leak.
- Checking "which plants can this person see" must happen **on the server, on every request**. Hiding a menu item in the browser is not security: anyone can call the API directly.
- Showing all matching problems gives the operator the full picture instead of hiding something important.

**What to learn**
- In a SaaS product, the worst bug is one customer seeing another customer's data. Design against it from day one.
- Never trust what the browser sends (for example a `company_id`). Take it from the logged-in user's verified identity.

---

## Entry 5 – Saving readings automatically, without a Save button (2026-10-19)

**What we decided**
When someone at a plant changes a value (for example hardness), the change must show up everywhere it matters: in the calculated values that use it, in the alerts, and in the Filter and Thermal screens, for everyone at that plant. There is **no Save button**. Instead:
- The value is saved automatically when the person **leaves the field** (clicks or tabs to the next box) or **presses Enter**.
- While they are still typing, **only they** see a preview of the new calculations.
- After saving, everyone else sees the change within a few seconds.
- A small note says "Saved ✓ by operator1 at 14:32".

**Why not save on every keystroke?**
Typing "600" happens as "6", then "60", then "600". If we saved each keystroke, other people would briefly see hardness = 6, get false alerts, and the history would fill with junk. Saving when the person leaves the field means only finished values are saved.

**Why does the server receive only the changed field?**
Imagine the operator changes hardness while the manager changes pH at the same moment. If each screen sent *all* values, the second save would overwrite the first person's change with an old number. Sending only the changed field and letting the server **merge** it into the latest reading means both changes survive.

**Why is every save a new record instead of updating the old one?**
We never overwrite readings. Each save becomes a new, time-stamped record, and "current values" simply means "the newest record". This gives us a full history for free (who changed what, and when), which is needed for trends, reports and audits.

**What to learn**
- Good user experience (no Save button) and correct data (no half-typed values) can both be achieved by choosing *when* to save carefully.
- Think about two people editing at once. Sending only what changed avoids accidentally erasing someone else's work.
- Storing events (new rows) instead of overwriting gives you history and an audit trail without extra work.

---

## Entry 6 – Step 0: building the foundation (2026-10-19)

This step has no visible features. It builds the "workshop" that every later feature will use. Skipping it is the most common reason projects become messy.

### 6.1 Two database users instead of one
**What:** We created two PostgreSQL logins: `smayaa_owner` (owns the tables, used only to change the table structure) and `smayaa_app` (used by the running API; can only read and write rows).
**Why:** PostgreSQL's row-level security (the rule "company A cannot see company B's rows") is **ignored for the table owner**. If the API logged in as the owner, that protection would silently do nothing. Separate users also mean a bug in the API can't drop a table.
**Learn:** Give each part of a system only the permissions it needs ("least privilege").

### 6.2 Settings come from the environment
**What:** `api/app/core/config.py` reads settings (database address, secret key, ...) from environment variables or a `.env` file. `.env.example` shows which settings exist, with fake values.
**Why:** The same code runs on a laptop, in testing and in production with different settings, and secrets never appear in the code. The program refuses to start if a required setting is missing or the secret is too short, so mistakes are caught at once.
**Learn:** Commit `.env.example`, never `.env`.

### 6.3 A health endpoint
**What:** `GET /api/v1/health` answers `{"status":"ok","database":"ok"}`.
**Why:** Servers in the cloud are watched by "load balancers" and monitoring tools. They call this address every few seconds; if it fails, they stop sending users to that server and alert us.
**Learn:** Every web service should be able to say "I'm alive and can reach my database".

### 6.4 Request IDs and structured logs
**What:** Every request gets a random ID. It is written on every log line and sent back in the `X-Request-ID` header. Logs are JSON, one line per request.
**Why:** When a customer says "I got an error at 14:32", we can find that exact request in thousands of log lines. JSON logs can be searched and filtered by tools; plain text is much harder.
**Learn:** Logs are for searching later, so make them structured. Never log passwords or tokens.

### 6.5 One error format
**What:** Every error from the API looks like `{"error": {"code": "not_found", "message": "...", "details": []}}`.
**Why:** The frontend needs one piece of code to show errors, not a different one per endpoint. Unexpected crashes return a polite message, while the technical details go only to our logs (showing them to users can leak information to attackers).

### 6.6 Database migrations (Alembic)
**What:** Alembic keeps numbered scripts (`api/migrations/versions/`) that change the database structure step by step. `alembic upgrade head` applies any missing ones. We started with an empty "baseline".
**Why:** Every developer's database, the test database and production must end up with exactly the same tables. Running scripts in order is repeatable; clicking around in a database tool is not.
**Learn:** Never change a production table by hand. Write a migration.

### 6.7 Automatic quality checks
**What:**
- **ruff** checks Python style and common bugs, and formats code.
- **mypy** (strict mode) checks that types match: for example, it caught that we passed arguments to `JSONResponse` in the wrong order.
- **pytest** runs the tests: they also caught the same bug, because a 404 page crashed.
- **pre-commit** runs checks automatically on every `git commit`. It also **refuses to commit secret or private files**.
- **GitHub Actions (CI)** runs everything again on GitHub for every push, on a clean machine with a fresh database.
**Why:** People forget things; machines don't. Bugs found by a tool in seconds are far cheaper than bugs found by a customer.
**Learn:** Real lesson from today: two independent tools (tests and type checker) both caught a real bug before anyone ran the app.

### 6.8 Frontend skeleton and the dev proxy
**What:** A React + TypeScript app created with Vite in `web/`. In development the browser talks only to Vite (port 5173), which forwards `/api/...` to the API (port 8000).
**Why:** To the browser, the page and the API look like one website. That avoids "CORS" problems and lets us safely use cookies for login later.

### 6.9 Careful with brand-new packages
**What:** We installed web packages with `npm install --before=2026-10-05`, used `create-vite` 9.2.1 instead of a version released that same day, and did not install an unfamiliar package that a warning suggested.
**Why:** Attackers sometimes publish malicious versions of popular packages or look-alike names. Waiting a couple of weeks lets the community spot problems first.
**Learn:** Pin versions, prefer well-known packages, and be suspicious of brand-new releases and unfamiliar names.

### 6.10 Docker files, even without Docker locally
**What:** `api/Dockerfile`, `web/Dockerfile` and `docker-compose.yml` exist, and CI builds the images on every push.
**Why:** We will deploy with containers. Building them in CI means they stay working even though nobody runs Docker on their laptop yet.

---

## Glossary

| Term | Meaning |
|---|---|
| **SaaS** | Software as a Service: customers use the app in a browser and pay a subscription; we run the servers. |
| **Tenant** | One customer company in a shared system. |
| **Multi-tenant** | Many customers share the same app and database, kept separate by rules. |
| **Repository (repo)** | A project folder tracked by Git. |
| **Commit** | A saved snapshot of changes with a message explaining them. |
| **Push** | Upload your commits to GitHub. |
| **Environment variable** | A setting given to a program from outside its code (e.g. a password). |
| **Docker / container** | A way to package an app with everything it needs so it runs the same anywhere. |
| **JSONB** | A PostgreSQL column type that stores JSON data efficiently and can be searched. |
| **Row-level security (RLS)** | A PostgreSQL feature that filters which rows each database session can see. |
| **Autosave** | Saving automatically at a sensible moment (here: when leaving a field) instead of pressing a button. |
| **Blur** | The browser event fired when the cursor leaves an input field. |
| **Polling** | The browser asking the server "anything new?" every few seconds. |
| **Least privilege** | Give each user or program only the permissions it really needs. |
| **Health endpoint** | A URL that reports whether the service and its database are working. |
| **Migration** | A numbered script that changes the database structure; applied in order. |
| **Linter** | A tool that checks code for style problems and common mistakes (ruff, oxlint). |
| **Type checker** | A tool that checks values are used with the right types (mypy, TypeScript). |
| **CI (Continuous Integration)** | Automatic build and test on a server for every change pushed. |
| **pre-commit hook** | A check Git runs automatically before accepting a commit. |
| **Proxy** | A server that forwards requests to another server. |
| **CORS** | Browser rule that limits which websites may call an API from JavaScript. |
| **Event (record)** | A row that is added and never changed, describing something that happened at a point in time. |
