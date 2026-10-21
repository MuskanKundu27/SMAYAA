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

## Entry 7 – Step 1: who are you, and what may you see? (2026-10-19)

This step answers three questions for every request: **who is this?** (authentication), **what may they do?** (permissions) and **which data may they touch?** (tenant isolation).

### 7.1 Passwords are never stored, only "fingerprints"
**What:** We store an **argon2id hash** of each password, never the password itself.
**Why:** A hash is a one-way fingerprint: you can check that a password matches it, but you cannot turn it back into the password. If the database ever leaks, attackers still don't get passwords. Argon2 is deliberately slow and memory-hungry, so guessing millions of passwords is impractically expensive.
**Learn:** Never invent your own password storage. Use a well-known library (here `argon2-cffi`).

### 7.2 Two tokens: a short-lived pass and a long-lived renewal card
**What:** Logging in gives you:
- an **access token** (a JWT, valid 15 minutes), sent with every request in the `Authorization` header;
- a **refresh token** (valid 7 days), kept in an **httpOnly cookie** that JavaScript cannot read. It is only used to get a new access token.

**Why:** If an access token is stolen, it stops working within 15 minutes. The refresh token is harder to steal (JavaScript can't read the cookie) and is **replaced every time it is used**. If someone uses an *old* refresh token again, we know it was copied, and we cancel the whole chain.
**Learn:** Short-lived credentials limit the damage when something leaks.

### 7.3 Stopping password guessing
**What:**
- After **5 wrong passwords in a row**, the account locks for 15 minutes.
- Each computer (IP address) may try to log in **20 times per minute**.
- A wrong password and an unknown username get **exactly the same message**, and take the same time to answer.

**Why:** Attackers try common passwords on many accounts. Locking and rate limits slow them down. Identical answers stop them from discovering which usernames exist.

### 7.4 Deactivated means locked out *now*
**What:** On every request we look the user up in the database again. If they (or their company) have been deactivated, the request is refused, even if their token hasn't expired yet.
**Why:** When a manager removes an operator, the operator must lose access immediately, not in 15 minutes.

### 7.5 Roles are bundles of permissions
**What:** The code never asks "is this a manager?". It asks "does this person have the `limits.write` permission?". Roles (super admin, company admin, manager, operator) are rows in the database, each linked to a list of permission strings.
**Why:** Customers will ask for things like "a supervisor who can edit limits but not create users". With permission strings, that's a new database row, not new code.
**Learn:** Check *capabilities*, not *job titles*.

### 7.6 The rank rule
**What:** You can only create or deactivate people **below** you: super admin → company admins; company admin → managers and operators; manager → operators in their own plant; operator → nobody. Each role has a number ("rank") to compare.
**Why:** It stops anyone from making themselves (or a friend) more powerful than they are.

### 7.7 Keeping companies apart: two locks on the same door
**What:**
1. **In the code:** every query is filtered to the user's company and plants. If you ask for something outside your scope, the answer is "not found" (404), not "forbidden" (403), so you can't even learn that it exists.
2. **In the database (row-level security):** at the start of every database transaction, the API tells PostgreSQL "this request belongs to company X, plants Y". PostgreSQL itself then hides every row from other companies. Even a hand-written SQL query with a forged company id returns nothing.

**Why:** One forgotten filter in the code would otherwise leak a customer's data to another customer. With the database also enforcing the rule, both would have to fail at the same time.
**Proof:** Our tests run raw SQL as the API's database user and check that company A's session sees zero rows of company B, and that inserting a row for company B is rejected by PostgreSQL.
**Learn:** For the most important rules, add a second, independent layer of protection.

### 7.8 "Fail closed"
**What:** A database session that hasn't been told which company it belongs to sees **nothing**.
**Why:** If a developer forgets to set the company, the bug shows up as "empty page" during testing instead of as "every customer's data" in production.

### 7.9 Delete means deactivate, and everything is recorded
**What:** Users, plants and companies are never deleted, only switched off. Every create/change/deactivate writes an **audit log** entry: who, what, when, before and after.
**Why:** Old readings must still show who entered them. And when a customer asks "who changed this?", we can answer.

### 7.10 Tests that prove the rules
**What:** 65 automatic tests, covering:
- login, lockout and token theft detection;
- what each role may and may not do;
- the rank rule;
- the "plant has no manager" warning;
- company isolation, both through the API and directly in SQL.

**Real lesson from today:** one test failed. The limiter code was right, but the *test* was flawed: it assumed time passes between two lines of code, which isn't true on a fast computer. The fix was to give the limiter a **replaceable clock**, so the test controls time exactly. Tests that depend on real time are "flaky"; make time an input instead.

---

## Entry 8 – A first web app: login and a menu that fits your role (2026-10-19)

**What we did**
- A **login page** in the browser.
- After logging in, a **sidebar menu that depends on your role**:
  - operator: Water Chemistry, Filter, Thermal;
  - manager: the same plus Limits and Users;
  - company admin: also Plants;
  - super admin: Companies, Configuration, Audit log, and never the plant modules.
- A **plant switcher** in the top bar for people with more than one plant.
- The other pages are **placeholders** that say which step will fill them in.

**Why build this before the "real" screens?**
The owner wanted something to click in the browser early. Login and roles were already finished in the backend, so a login page and menu could be built without fake data. The module screens wait until there is real data to show (steps 2–4), so they don't have to be rebuilt later.

**How the browser stays logged in (and why it's safe)**
- The short-lived access token is kept **only in the page's memory**, not in browser storage. Storage can be read by any script running on the page; memory disappears when the tab closes.
- When you reload the page, memory is empty. The app quietly asks the server for a new token using the **httpOnly refresh cookie**, which JavaScript can't read at all. If that works, you're still logged in.
- When a token expires in the middle of your work, the app renews it automatically and repeats your request. You never notice.
- If several requests notice the expiry at once, they **share one renewal** instead of each asking separately (asking twice would look like a stolen token, see entry 7.2).

**Menus are not security**
The menu is built from the permission list the server sends (`GET /me`). Hiding a menu item only keeps the screen tidy. Anyone can still type the address or call the API directly, so **the server checks permission on every request** anyway (that's what step 1 built).

**What to learn**
- Keep secrets out of places scripts can read.
- Build the frontend from what the backend says (permissions from `/me`), not from role names hard-coded in the browser.
- Test logic, not just looks: we tested the menu for each role and the token-renewal rules with a fake server (`fetch` replaced by a test double).

---

## Entry 9 – Step 2: the configuration engine (2026-10-21)

This step teaches SMAYAA everything it must know about a company **before** anyone types a reading: what is measured, how values are calculated, what counts as "good", what to do when something is wrong, and what each screen shows. All of it is **data in the database**, so one customer can be different from another without anybody changing code.

### 9.1 Parameters: the things a plant measures
**What:** Each company has its own list of parameters: pH, hardness, supply temperature, filter pressures, and so on. A parameter is either **typed in** by people, or **calculated** from others with a formula (e.g. Range = `tr - ts`).
**Why:** One customer may measure chloride, another may not. If parameters lived in code, every customer request would need a programmer. As rows in a table, the super admin just adds one.
**Detail worth knowing:** a parameter's short **key** (`hard`) can never be renamed, because stored readings will be labelled with it. Labels and units can change freely.

### 9.2 A calculator that cannot be tricked
**What:** Formulas are text typed by a person, for example `ph - 7.6 + (hard - 400) / 800`. We wrote a small calculator that reads the formula with Python's own parser and then **checks every piece** against an allow-list: numbers, names, `+ - * / **`, comparisons, `and/or/not`, and a few functions like `min`, `max`, `sqrt`. Anything else is refused before it runs.
**Why not just use Python's `eval()`?** `eval` runs *any* Python code. A formula like `__import__('os').system('delete everything')` would actually run on our server. Our calculator refuses it with "Unknown function '__import__'". Our tests try about 20 nasty tricks like this and check they're all refused.
**Also:**
- Missing data or dividing by zero gives "no result" instead of crashing the page.
- Huge powers like `9 ** 9 ** 9` are refused, so nobody can freeze the server with one formula.

**Learn:** Never run text from users as code. Parse it and allow only what you understand.

### 9.3 Checking formulas before saving
**What:** When the super admin saves a formula, we check:
1. Is it valid and safe?
2. Does every name in it exist and is it switched on?
3. Does it use itself?
4. Does it create a **loop**, like A = B + 1 while B = A − 1?
5. Does it give a number with typical sample values?

**Why:** A broken formula found at save time costs nothing. Found later, it means wrong numbers on a customer's screen.
**How loops are found:** we sort the formulas so each one comes after the ones it needs (a "topological sort"). If at some point no formula is ready, the rest must be waiting on each other in a loop.

### 9.4 Versions instead of rewriting history
**What:** Each time a formula changes, its **version number** goes up.
**Why:** Next step, every saved reading will remember which formula version calculated it. Then if someone improves the LSI formula tomorrow, last month's numbers don't silently change.

### 9.5 Switching off instead of deleting
**What:** Parameters, rules and modules are never deleted, only switched off. And you **can't** switch off a parameter that a formula or rule still uses. The answer tells you exactly which ones, e.g. "`ts` is still used by: parameter 'appr', parameter 'heat', parameter 'range'".
**Why:** Deleting would break old readings and other formulas. Telling the user *why* they can't do something is much friendlier than a vague error.

### 9.6 Limits per plant, with a safety net
**What:** Each plant can have its own four limits per parameter (warning min, good min, good max, warning max). If a plant hasn't set any, the company's default limits apply.
**The rule:** the **manager** edits limits. The **company admin** may edit them **only while the plant has no manager**. We don't store a "no manager" flag; we check the real situation every time. So the moment a new manager is added, the company admin automatically loses that right again.
**Learn:** Calculate facts from the source of truth instead of storing a copy that can go out of date.

### 9.7 Rules for predicted problems
**What:** Problems like "TH-P02 Fouling" are rules written with the same calculator, plus helpers such as `off('hard')` (is hardness out of range?) and `count_off(['lsi','hard','alk','mic'])` (how many are out of range?). Each rule has a condition, a probability formula and a recommended action.
**Why:** Later, trained machine-learning models can replace these rules **using the same codes**, and the screens won't need to change.
**Honesty:** the probabilities are simple demo rules, not engineering guarantees, and the treatment texts are samples that a water-treatment engineer must review. Both are marked in the data.

### 9.8 Screens described as data
**What:** Each module (Water Chemistry, Filter, Thermal) is stored as a list of **widgets**: "input tiles for the chemistry group", "KPI cards for dp, rem, bw", "predicted problems FLT-P01..P03". We check that every widget has a known type and the right fields.
**Why:** Adding a new calculation to the Filter screen is now a data change. Our tests do exactly that: add a "cycles" calculation and put it on the Filter module, with no code change.

### 9.9 Templates: a starter kit for new customers
**What:** The standard setup (26 parameters, 20 treatments, 5 rules, 3 modules) is a **template**. Every new company gets its own copy automatically. Applying it again only adds what's missing; it never overwrites a company's changes.
**Why:** Customers start with something useful on day one, and changing one customer never affects another.
**Testing the template itself:** a test checks the template is valid on its own: every formula and rule references real parameters, there are no loops, the limits are in order, and the sample values give the expected answers (e.g. Range = 8 °C, Approach = 5 °C).

### 9.10 Real lessons from today
Two tests failed the first time, and **both times the code was right and the test was wrong**:
- We expected `True` to be rejected by the calculator, but it's a harmless value. We changed the test.
- We expected the sample data to trigger a filter problem, but hardness isn't on the filter rule's list, so it correctly didn't.

When a test fails, don't automatically "fix" the code: first ask which one is wrong, the code or your expectation.

---

## Entry 10 – Step 3: readings and alerts (2026-10-21)

Now the configuration from step 2 comes alive: people enter values, and SMAYAA works out everything else.

### 10.1 Every save is a new row
**What:** When an operator changes hardness, we don't change the old record. We store a **new reading**: the full set of values after the change, everything calculated from them, which formula versions were used, the baseline used, which fields changed, who saved it, and when.
**Why:**
- **History for free:** trends and reports later just read old rows.
- **Trust:** last month's numbers can never silently change. A test proves it: we change the Range formula, and the old reading still shows the old result with "version 1".
- **Accountability:** every value has a name and a time attached.

**Extra protection:** the database itself refuses to change or delete readings. The API's database user simply isn't allowed to. A test tries it with raw SQL and gets "permission denied".

### 10.2 Merging changes from two people
**What:** The screen sends **only the field that changed**. The server takes the latest reading, applies the change, and saves the result.
**Why:** If the operator changes hardness while the manager changes pH, both changes survive. If the screen sent all values, the second save would put back the old hardness. (Same field at the same moment? The last save wins.)
**Small detail:** saving a value that didn't change creates nothing, so clicking in and out of a box doesn't fill the history with copies.

### 10.3 One brain for all screens
**What:** A single function (`build_state`) turns input values into "the plant's current state": all calculated values, each status (good / warning / alert), the alerts, and the predicted problems. The alert bar, the module screens and the live preview all ask this one function.
**Why:** If each screen calculated on its own, sooner or later two screens would disagree, and nobody would trust either. One brain means the manager and the operator always see exactly the same thing.

### 10.4 Alerts are calculated, not stored
**What:** An alert is never saved as a row. It's worked out from the latest values and the current limits whenever a screen asks.
**Why:** When the manager widens a limit, the alert disappears **immediately**, with no "clean-up" job needed. Our test does exactly that.
Each alert says:
- what is wrong (parameter, value and unit);
- how bad it is: **medium** = in the warning band, **high** = beyond it;
- which way it's wrong (too high or too low);
- which screens it affects;
- the likely cause, treatment and precautions, marked "needs review" while they're sample text.

### 10.5 "Which screens does this affect?" – answered from data
**What:** Instead of writing "chemistry affects Filter and Thermal" in code, we look at the configuration. A screen is affected by hardness if it shows hardness, shows a calculation built from hardness (like LSI), or shows a rule that uses hardness.
**Why:** If a customer adds a new screen or rule tomorrow, the answer updates itself.

### 10.6 Saying "I don't know" honestly
**What:** If a predicted-problem rule needs a value that's missing, we show **"insufficient data"** instead of a guess. The same goes for a screen tile whose parameter was switched off.
**Why:** A confident wrong answer is worse than an honest "not enough data". In industrial settings, people act on what the screen says.

### 10.7 Screens that only draw
**What:** For each module, the API sends the list of widgets **already filled with the data they need**: values, statuses, colours to use, problems, alerts.
**Why:** The browser never decides what is "good" or "bad"; only the server does. So the rules live in one place, and a future mobile app could draw the same screens without copying any logic.

### 10.8 What we checked
- 207 automatic tests in total (26 new).
- A walk-through on the real demo data:
  1. The operator sets hardness to 900 and TDS to 2300.
  2. Hardness, TDS and LSI alerts appear (LSI because it's calculated from hardness).
  3. The thermal fouling prediction rises from 35% to 55%, and a filter problem appears.
  4. The manager sees the same alerts.
  5. The manager widens the TDS limit, and that alert clears.

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
| **Authentication** | Proving who you are (e.g. username + password). |
| **Authorization** | Deciding what an authenticated person may do. |
| **Hash (password hash)** | A one-way fingerprint of a password; can be checked but not reversed. |
| **JWT** | JSON Web Token: a signed piece of text saying "this is user X, valid until Y". |
| **Access / refresh token** | Short-lived pass for each request / longer-lived card used only to get a new pass. |
| **httpOnly cookie** | A cookie the browser sends automatically but JavaScript cannot read. |
| **Rate limiting** | Allowing only a certain number of attempts per time window. |
| **Permission** | A named capability, e.g. `plants.manage`. Roles are bundles of permissions. |
| **Principal** | The logged-in user of the current request, with their scope and permissions. |
| **Scope** | The part of the data a user may touch (their company, their plants). |
| **Audit log** | Permanent record of who changed what and when. |
| **Fail closed** | When something is missing or broken, deny access rather than allow it. |
| **Flaky test** | A test that sometimes passes and sometimes fails without code changes. |
| **SPA (single-page app)** | A web app that loads once and then changes screens without full page reloads (React). |
| **Route** | A mapping from an address like `/limits` to the screen shown for it. |
| **Test double / mock** | A fake replacement (e.g. a fake server) used in tests to control what happens. |
| **Parameter** | A named value a plant measures or calculates (pH, hardness, approach…). |
| **Formula** | Text describing how to calculate a parameter from others, e.g. `tr - ts`. |
| **Parser / AST** | A parser turns text into a tree of pieces (the Abstract Syntax Tree) that a program can inspect. |
| **Allow-list (whitelist)** | Only the listed things are permitted; everything else is refused. Safer than a block-list. |
| **`eval`** | A Python function that runs any text as code. Dangerous with user input; we never use it. |
| **Topological sort** | Ordering items so each comes after the items it depends on. |
| **Template** | A ready-made bundle of configuration copied into each new company. |
| **Widget** | A building block of a screen (input tiles, KPI cards, a chart…). |
| **Immutable** | Never changed after it is created; changes are recorded as new items instead. |
| **Append-only** | You may add rows but never update or delete them. |
| **Derived data** | Data calculated from other data when needed, instead of being stored. |
| **Degrade gracefully** | When part of something is missing, show what you can and say what's missing, instead of failing. |
| **Event (record)** | A row that is added and never changed, describing something that happened at a point in time. |
