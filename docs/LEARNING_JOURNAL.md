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
