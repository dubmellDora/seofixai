# History Logs

## 2026-11-11

**Files changed:**
- `CLAUDE.md` (created)
- `HISTORY_LOGS.md` (created)

**Changes:**
- Created `CLAUDE.md` with a rule requiring every future change in this repo to be logged here.
- Created this `HISTORY_LOGS.md` file as the append-only tracker.

## 2026-11-12 — seofixai: Postgres + multi-tenant foundation (sprint 1)

**Branch:** `sprint-1/database-multitenant-foundation` (created from `main` in the `seofixai` repo).

**Files changed:**
- `seofixai/docker-compose.yml` — added a `postgres` service (`postgres:16` image, named volume `postgres-data`, port 5432, env-driven `POSTGRES_DB`/`POSTGRES_USER`/`POSTGRES_PASSWORD` with `seofixai`/`seofixai`/`seofixai` defaults); `app` service now gets `DATABASE_URL` wired to that service (hostname `postgres`, not `localhost`) and `depends_on: postgres`; removed the old `./data/seo_automation.db` volume mount.
- `seofixai/app/database.py` — `DATABASE_URL` now read from `os.environ.get("DATABASE_URL", "sqlite:///seo_automation.db")` instead of being hardcoded to SQLite; `connect_args={"check_same_thread": False}` is now only applied when the URL starts with `sqlite`, so Postgres connections don't get a SQLite-only arg. Existing WAL-pragma `event.listens_for` hook untouched (already dialect-guarded).
- `seofixai/.env.example` — documented new `DATABASE_URL`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` vars with a Postgres example value and a note on the SQLite fallback.
- `seofixai/.env` (gitignored, not committed) — added real local values: `POSTGRES_DB=seofixai`, `POSTGRES_USER=seofixai`, `POSTGRES_PASSWORD=seofixai`, `DATABASE_URL=postgresql+psycopg2://seofixai:seofixai@localhost:5432/seofixai`.
- `seofixai/requirements.txt` — added `alembic`.
- `seofixai/alembic.ini`, `seofixai/alembic/env.py`, `seofixai/alembic/script.py.mako`, `seofixai/alembic/README` — new Alembic setup (`alembic init alembic`). `env.py` was edited to: add the repo root to `sys.path`, `load_dotenv()`, import `app.models` (to populate `Base.metadata`) and `app.database.Base`/`DATABASE_URL`, set `target_metadata = Base.metadata`, and override `config.set_main_option("sqlalchemy.url", DATABASE_URL)` so the env var always wins over the static `alembic.ini` placeholder.
- `seofixai/alembic/versions/e9d001b85a1c_baseline_schema.py` — generated via `alembic revision --autogenerate -m "baseline schema"` against a fresh empty Postgres database; captures all 36 tables from `app/models.py` as the Postgres baseline (no manual edits needed — autogenerate matched the models cleanly).
- `seofixai/migrations/README.md` — new note: the old `migrations/NNN_*.py` SQLite scripts are kept as a historical record and are frozen; all future schema changes go through Alembic.
- `seofixai/scripts/migrate_sqlite_to_postgres.py` — new one-off data-copy script. Loads `app.models`/`app.database.Base`, iterates `Base.metadata.sorted_tables` (FK-dependency order) to copy every row from a SQLite file into the target Postgres DB, then resets each Postgres sequence to `MAX(id)+1` for integer-typed autoincrement PKs only (skips non-integer PKs like `provider_settings.provider`, and skips tables with no attached sequence) via `pg_get_serial_sequence`.

**Decisions / why:**
- Chose `postgresql+psycopg2` driver (psycopg2-binary was already in `requirements.txt`, unused until now).
- Kept the legacy `migrations/` scripts instead of deleting them — they're the historical record of the SQLite schema's evolution; new changes go through Alembic from this point.
- Data-copy script lives in `scripts/`, not `migrations/`, since it's a one-time data migration, not a schema change.
- `connect_args` is now conditional on dialect so the same `database.py` code path supports both Postgres (prod/new default) and a SQLite fallback (quick local runs without Docker).

**What was run / verified (not committed as files, but part of this change):**
- Started Docker Desktop, ran `docker compose up -d postgres` (local Postgres 16 container, `seofixai-postgres-1`).
- `pip install alembic` into `seofixai/.venv`.
- `alembic revision --autogenerate -m "baseline schema"` against the empty Postgres DB → clean autogenerate, no manual fixes needed (confirms `app/models.py` has no SQLite-only types; a grep for `sqlite3|INSERT OR IGNORE|INSERT OR REPLACE|PRAGMA|AUTOINCREMENT` across `app/` found none outside `app/database.py`'s existing dialect-guarded WAL hook).
- `alembic upgrade head` → all 36 tables created in Postgres successfully.
- Copied `seo_automation.db` to a scratch copy and ran `scripts/migrate_sqlite_to_postgres.py` against it → 1 `projects` row copied (the only non-empty table in local dev data at the time), all other 35 tables empty, 0 errors on second run (first run hit a bug in the sequence-reset step for the non-integer `provider_settings.provider` PK, fixed in the script, then re-run cleanly after truncating the partially-inserted `projects` row).
- `app.schema_check.find_schema_drift()` against the new Postgres engine returned `{}` (no drift).
- `python -m pytest -q` with `DATABASE_URL` pointed at the Docker Postgres → **1241 passed**, 1 pre-existing unrelated deprecation warning.
- Booted `uvicorn app.main:app` against Postgres: `GET /` → 200, `GET /version` → `{"schema":{"ok":true,"missing":{}}}`, confirming the live app also sees no schema drift.

## 2026-11-12 — Sprint 0 audit + Mandatory/ cross-tool rules folder (session 02)

**Files changed:**
- `Mandatory/README.md`, `Mandatory/RULES.md`, `Mandatory/IMPLEMENTATION_STATE.md`, `Mandatory/DECISIONS.md` (all new)
- `Mandatory/SESSIONS/_TEMPLATE.md`, `Mandatory/SESSIONS/2026-11-12_01_claude_postgres-alembic-foundation.md` (backfilled from the entry above), `Mandatory/SESSIONS/2026-11-12_02_claude_sprint0-audit-and-mandatory-folder.md` (all new)
- `AGENTS.md` (root, new), `seofixai/AGENTS.md` (new) — entry pointers for Codex/Cursor/Copilot/Gemini-style tools.
- `CLAUDE.md` (root) — added a "MANDATORY: read Mandatory/ first" section above the existing history rule (existing rule kept).
- `seofixai/CLAUDE.md` — added a pointer block at the top only.

**Changes:**
- Created `Mandatory/` as the single source of truth for rules, current implementation state, decision records (D-001..D-006) and one-file-per-chat session logs. Tool entry files only point to it.
- Read-only Sprint 0 audit findings recorded in `IMPLEMENTATION_STATE.md`: UI is Jinja2 + HTMX + Tailwind CDN (no React); no auth/users/orgs/tenancy exist; 15 routers with no auth dependency; jobs run as subprocesses via APScheduler.
- No application code, schema or config changed.

**Decisions / why:**
- D-005: one shared folder, because several tools each read only their own entry file. HISTORY_LOGS.md kept as the global summary log (append-only, per the existing rule).
- D-006 (frontend: Jinja2/HTMX vs React) left PENDING for the user; no portal/auth work until answered.
- Open risk: `Mandatory/` is outside the `seofixai` git repo (workspace root is not a git repo), so it is unversioned and absent from a standalone seofixai clone. User to decide how to handle.

## 2026-11-12 — D-006 resolved: Jinja2/HTMX (session 02 addendum)

**Files changed:** `Mandatory/DECISIONS.md` (D-006 status -> resolved; D-007 added), `Mandatory/IMPLEMENTATION_STATE.md` (progress row), `Mandatory/SESSIONS/2026-11-12_02_...md` (addendum).
**Decision:** user chose to keep Jinja2 + HTMX + Tailwind with session cookies; React/shadcn/ui from the plan doc is overridden (D-007). No code changed.

## 2026-11-12 — Mandatory/ relocated into seofixai/ (session 03)

**Files changed:** `HISTORY_LOGS.md` moved from workspace root to `seofixai/Mandatory/HISTORY_LOGS.md` (content untouched); path edits in `AGENTS.md`, `CLAUDE.md` (root), `seofixai/AGENTS.md`, `seofixai/CLAUDE.md`, `Mandatory/README.md`, `RULES.md`, `IMPLEMENTATION_STATE.md`, `SESSIONS/_TEMPLATE.md`; `Mandatory/DECISIONS.md` (D-008 added); `Mandatory/SESSIONS/2026-11-12_03_claude_mandatory-relocation.md` (new).
**Decision (D-008):** user moved `Mandatory/` into `seofixai/`; the log moved with it so both are version-controlled and writable from the repo. No application code changed.

## 2026-11-12 — Codex architecture review: SaaS and PostgreSQL

**Files changed:** `Mandatory/SESSIONS/2026-11-12_04_codex_architecture-review.md` (new); this entry appended to `Mandatory/HISTORY_LOGS.md`.

**Changes:** Advisory, read-only review of `docs/User_ManagementSAAS.md` and the current app/database setup. No application code, schema, deployment or configuration changed. Tests were not run.

**Findings:** The actual app still registers all 15 feature routers without auth; no user, session, organization or tenant model exists, and resource routes are not scoped by identity. `app/main.py` invokes `Base.metadata.create_all()` at startup despite the Alembic-only schema rule. The SaaS plan puts working authentication in Sprint 1 and identity/auth foundations in Sprint 2, which is an unsafe/unclear dependency order. Local Compose Postgres lacks a readiness healthcheck and publishes 5432; its default credentials are only suitable for local development. Production remains SQLite; production cutover and tenancy must remain separate releases.

**Recommendation:** First correct the work sequence: establish identity/session/auth server-side, test one protected route family, then build authenticated dashboards and incrementally scope resources. Keep organization tenancy and its data backfill in a later separate release. Treat production DB cutover as its own release with a backup, restore rehearsal, rollback and verification plan. No decision made on the user's behalf.

## 2026-11-12 — Codex revised SaaS plan: hostname-first routing and detailed acceptance criteria

**Files changed:** `docs/User_ManagementSAAS.md`; `Mandatory/SESSIONS/2026-11-12_04_codex_architecture-review.md`.

**Changes:** Revised the sprint order so routing and authentication foundation precede portal UI, and organization tenancy follows both. Added detailed acceptance criteria for `app.seofix.ai` and `admin.seofix.ai`, local hostname equivalents, host classification, canonical redirects, reverse proxy/TLS, cookie scope, CSRF origins, trusted forwarded headers, routing threat modeling, user/session models, server-side guards, login/reset flows, and tenant isolation. Updated the plan to reflect the accepted Jinja2/HTMX architecture and renumbered later sprints.

**Decision guidance:** Use separate hostnames as a clear product/deployment boundary, but never treat the hostname as permission. Authorization remains server-side and resource-scoped. No DNS, proxy, production, schema, or application-code changes were made.

## 2026-11-13 — Codex simplified plan to agency-first MVP

**Files changed:** `docs/User_ManagementSAAS.md`; `Mandatory/SESSIONS/2026-11-12_04_codex_architecture-review.md`.

**Changes:** Reframed the plan around the product model: an Agency owns branding, Users, Projects, and GSC connections. Stage 1 creates one Agency and one owner User, supports agency branding, many projects, and project-level GSC mapping. Later work adds multiple agency users, invitations, and ProjectUser assignments. Replaced the broad SaaS roadmap with a smaller MVP sequence and explicitly deferred billing, usage metering, complex organization terminology, impersonation, microservices, and RDS.

**Decision guidance:** Keep the Agency entity in the first schema even though Stage 1 has one user per agency; this preserves a simple production path and avoids rebuilding ownership when agencies add users. No application code, database, DNS, or deployment changes were made.

## 2026-11-14 — Codex read-only review of SaaS Master Plan

**Files changed:** `Mandatory/SESSIONS/2026-11-14_01_codex_master-plan-review.md` (new); this entry appended to `Mandatory/HISTORY_LOGS.md`.

**Changes:** Reviewed `docs/SaaS_Master_Plan.md` against D-010, the agency-first MVP model, current host-routing implementation, deployment audit, and PostgreSQL/tenancy release rules. No application or plan changes were made. Recommendations were recorded in the session log and delivered to the user: resolve hostname naming, sprint/task numbering, role vocabulary, `/version` deployment behavior, and release sequencing before treating the plan as executable.

## 2026-11-13 — Claude: Sprint 0 prep and test baseline

**Files changed:** `Mandatory/SESSIONS/2026-11-13_01_claude_sprint0-stage1-prep.md` (new), `Mandatory/DECISIONS.md` (D-009 appended), this entry.
**Changes:** No application code changed. Ran baseline `pytest -q` against local Docker Postgres: 1241 passed, 1 warning.
**Decisions:** D-009 — apex redirects to app.seofix.ai; old hostname works without auth until Sprint 1; /health public, /version internal-only.

## 2026-11-13 — Claude: domain decision D-010

**Files changed:** `Mandatory/DECISIONS.md` (D-010), session file addendum, this entry. No code changed.
**Decision:** app.seofixai.com / admin.seofixai.com; marketing on the seofixai.com apex; supersedes D-009 item 1. Apex cutover timing open.

## 2026-11-13 — Claude: Sprint 0 audit (S0-01..S0-03)

**Files changed:** `docs/Sprint0_Audit.md` (new), session file addendum, this entry. No code changed.
**Content:** repo/architecture audit, route inventory, model ownership gaps, scheduler ownership, deployment/env inventory, baseline (1241 passed), ranked findings, plan inconsistencies.
**Decision/standing instruction:** audits are always written to `seofixai/docs/`. Notable finding: deploy pipeline depends on public `/version`, conflicting with D-009; must be resolved in S0-04.

## 2026-11-13 — Claude: Lesson 1 (host routing) for the user to implement

**Files changed:** `docs/learning/Lesson_01_Host_Routing.md` (new), session file addendum, this entry. No application code changed.
**Decision:** teaching mode — user implements S0-04 code themselves; Claude reviews. Middleware ships with `HOST_ENFORCEMENT=off` default so existing behavior and tests are unaffected.

## 2026-11-14 - S0-04 step 1
- Files: app/host_routing.py (new, HostKind enum only); memory user-learning-to-code updated.
- Decision: Claude writes code in small explained steps per user request.

## 2026-11-14 - S0-04 step 2
- Files: app/host_routing.py (added normalize_host). No behaviour change; not yet imported by the app.

## 2026-11-14 - Performance audit
- Files: docs/Performance_Audit.md (new). No code changes.
- Decision (proposed, pending user): partial inclusion in Stage 1 (S0 baseline, S1 indexes, pagination rule, pool), rest deferred.

## 2026-11-14 - Plan renamed and recovery section added
- Renamed docs/User_ManagementSAAS.md -> docs/SaaS_Master_Plan.md.
- Inserted "Part 0 - Project Findings and Recovery Record" (144 lines) after the header: override table (seofixai.com, agency wording, task-ID and role conflicts), product/stack/layout/run steps, decisions D-001..D-010 summary, Sprint 0 audit findings, performance findings and Stage 1 placement, progress (S0-04 in progress), open items, resume/rebuild steps. Original sections 1-16 verified byte-identical.
- Updated live references in AGENTS.md (root and seofixai), Mandatory/README.md, Mandatory/IMPLEMENTATION_STATE.md, docs/Sprint0_Audit.md. Left append-only logs and DECISIONS.md with the old name (history).
- Decision: Part 0 added above, not merged into, the original body so the plan text stays intact; Part 0 table wins on conflicts.

## 2026-11-14 - S0-04 step 3
- Added frozen HostConfig dataclass (public_host, admin_host, legacy_hosts) to app/host_routing.py. User answered the endswith check correctly (evilseofixai.com). No behaviour change.

## 2026-11-14 - S0-04 step 4
- Added classify_host(raw_host, config) -> HostKind to app/host_routing.py: normalize, empty->UNKNOWN, exact == for public/admin, `in` over legacy tuple, else UNKNOWN. Manually verified against 12 hosts incl. evilseofixai.com and app.seofixai.com.evil.com. No behaviour change yet (not imported by app). Tests next.

## 2026-11-14 - S0-04 step 5
- Added tests/test_host_routing.py (27 cases: normalize_host table, classify_host table incl. look-alikes evilseofixai.com / app.seofixai.com.evil.com / @ and / tricks, no-legacy config, frozen config). 27 passed. Full suite not re-run (no app code touched).

## 2026-11-14 - DB-03 started: local rehearsal of SQLite->Postgres copy
- No repo files changed. Local only; production untouched.
- Took a consistent snapshot of seo_automation.db via the sqlite3 backup API (read-only open) into the session scratchpad: integrity ok, 0 FK violations, 35 tables, only `projects` has data (1 row).
- Created scratch DB `seofixai_rehearsal` in the local Docker Postgres (kept separate from dev DB `seofixai`, which the test suite shares). `python -m alembic upgrade head` -> baseline e9d001b85a1c, 36 public tables.
- Ran existing scripts/migrate_sqlite_to_postgres.py: copied 1 row, sequence reset OK (next projects id = 2).
- Findings: (1) script fails on a re-run with UniqueViolation (not idempotent; no empty-target check), (2) no validation step (counts, FK orphans, sequences) which DB-03 requires, (3) takes the Postgres URL (with password) as a CLI argument, (4) SQLite snapshot has 35 tables vs 36 in Postgres, difference not yet explained, (5) one row proves little: need a real production snapshot or a synthetic dataset, (6) `alembic` is not on PATH here; use `.venv/Scripts/python.exe -m alembic`.
- Decision: all DB-03 work stays local, against snapshots and scratch databases only; harden script + add verify step next.

## 2026-11-14 2026-11-14 18:34 - Skeptical business critique
- Reviewed the repo's stated product scope and SaaS implementation status, then compared it with current Google guidance, Search Console capabilities, Semrush and Ahrefs positioning/pricing, and SEOFix.ai's public agent-first audit offering/pricing.
- Main risks surfaced: broad undifferentiated feature bundle against scaled incumbents; likely weak standalone willingness to pay for audit/AI visibility without demonstrated measurable outcomes; focused direct competitor overlaps agent-ready technical auditing and similar name; SaaS account/billing groundwork is not product-market validation.
- No application/product changes and no tests run. Read-only market assessment; sources cited in the response.


## 2026-11-14 - S0-04 step 6
- Added host_guard_decision(kind, path) -> 421/404/None plus ADMIN_PATH_PREFIX, ALWAYS_ALLOWED_PATHS (/health) and _is_admin_path (exact /admin or /admin/ prefix) to app/host_routing.py. Rules: UNKNOWN->421; ADMIN host serves only /admin...; PUBLIC and LEGACY hide /admin...(404); /health allowed on any known host. Added 18 test rows to tests/test_host_routing.py. Pure logic, not wired into app yet (middleware + env config next). Decision: LEGACY treated like PUBLIC for /admin paths.

## 2026-11-14 - S0-04 wiring complete (host guard installed, default OFF)
- Files: app/host_routing.py (HostConfig.enforce; host_from_origin, load_host_config, install_host_guard + JSON 421/404 bodies; imports fastapi), app/main.py (import host_routing; install_host_guard(app, load_host_config()) right after FastAPI(); new GET /health -> {"status":"ok"}, no DB), .env.example (PUBLIC_APP_ORIGIN, ADMIN_APP_ORIGIN, LEGACY_APP_HOSTS, HOST_ENFORCEMENT=0 documented), tests/test_host_guard_middleware.py (new, 26 cases: throwaway-app guard table, generic bodies, off=passthrough, config parsing, real-app /health and guard toggle).
- Config lives on app.state.host_config so tests can swap it. HOST_ENFORCEMENT defaults off: existing deployments behave identically. ENVIRONMENT var from plan S0-04 intentionally NOT added yet (nothing reads it).
- Verified: full suite 1312 passed (1241 baseline + 71 new), 1 pre-existing warning. Live uvicorn on :8765 with HOST_ENFORCEMENT=1: app.localhost /health 200; admin.localhost /health 200; app.localhost /admin/login 404; admin.localhost / 404; 127.0.0.1 /health 421; evil.com 421; app.localhost.evil.com 421. Server stopped.
- Known limits recorded: guard reads Host only (X-Forwarded-Host handling is S1-06); path is matched as given, so "//admin/x" on the public host passes the guard but matches no route (revisit in S1-04); /version still public (D-009 internal-only not enforced yet); deploy.yml still polls /version.

## 2026-11-14 - S0-04 matrix and S0-05 threat model written (proposals)
- Files: docs/Hostname_Matrix.md (new: hostname matrix, classification table, settings, apex phases A/B/C, /health and /version proposal, HSTS/TLS, reverse-proxy contract, cookie/CSRF/redirect/OAuth rules, acceptance checklist), docs/Threat_Model.md (new: proposed two-field role model platform_role + agency_role, response matrix per state, resource authorization rule per table, 20 abuse cases A1-A20, open decisions), docs/SaaS_Master_Plan.md Part 0 status rows updated.
- Finding: SSRF guard exists only in app/services/page_evidence.py; audit.py, crawler.py, routes/security.py, dataforseo_onpage.py and wordpress.py fetch user-supplied URLs with follow_redirects=True and no guard. Recorded as A17 (confirmed partial); proposed fix = one shared guarded-fetch helper in Sprint 1.
- Decisions proposed, NOT approved: role model, 404-not-403 for cross-agency, /version over SSM for deploy checks, platform-wide global settings. No code changed in this step.

## 2026-11-15 - Decisions D-011..D-017 approved; S1-01 started
- Files: Mandatory/DECISIONS.md (appended D-011..D-017), Mandatory/SESSIONS/2026-11-15_01_claude_s1-01-agency-user-models.md (new).
- User approved: two-field role model, 404 for cross-agency, /health public + /version over SSM, platform-wide settings, shared SSRF helper, keyword workspaces owned by creating agency. Semrush snapshot ownership left provisional (D-017).

## 2026-11-15 - S1-01 Agency and User models (partial)
- Files: app/models.py (Agency, User + role constants, imports), app/services/accounts.py (new), alembic/versions/a1c5e0b7d301_add_agencies_and_users.py (new, revises e9d001b85a1c), tests/test_accounts.py (new, 23 tests).
- Schema: agencies(id uuid pk, name, slug unique, is_active, logo_url, brand_color, created_at, updated_at; slug lowercase CHECK). users(id uuid pk, agency_id fk nullable + index, email unique + lowercase CHECK, display_name, password_hash, platform_role default customer CHECK, agency_role CHECK, is_active, email_verified_at, last_login_at, timestamps; customer must have agency+role CHECK).
- Registration: register_agency_with_owner takes no role parameter, creates Agency + owner User in one transaction, rolls back on duplicate email/slug.
- Verified: 1335 tests pass; migration upgrade/check/downgrade OK on throwaway SQLite. Postgres run pending (Docker not running).
- Decisions: models live in app/models.py so Alembic and Base.metadata keep seeing them; timestamps use naive UTC DateTime like existing tables; password hashing and the admin bootstrap deferred to S1-02 (argon2-cffi not installed).

## 2026-11-16 - S1-02 passwords, authenticate, admin bootstrap
- Files: app/services/passwords.py (new), app/services/accounts.py (authenticate, create_platform_staff), scripts/bootstrap_admin.py (new), tests/test_passwords_auth.py (new, 21 tests), requirements.txt (+argon2-cffi), .env.example (ALLOW_ADMIN_BOOTSTRAP, APP_ENV), Mandatory/SESSIONS/2026-11-16_01_claude_s1-02-passwords-bootstrap.md (new).
- Argon2id via argon2-cffi 25.1.0; password length 10-256; verify never raises; dummy-hash verify for unknown emails (timing); weak hashes upgraded on login. authenticate() returns None for every failure cause and sets last_login_at only on success. create_platform_staff refuses unless ALLOW_ADMIN_BOOTSTRAP=1 and APP_ENV != production.
- No migration (S1-01 schema already complete). Full suite 1356 passed. Nothing committed per user. Decision: agency-suspension check deferred to S1-04.

## 2026-11-16 - S1-03a server-side sessions
- Files: app/models.py (UserSession), app/services/sessions.py (new), alembic/versions/b2d6f1c8e402_add_user_sessions.py (new), tests/test_sessions.py (new, 16 tests), session file addendum.
- Table user_sessions(id uuid pk, user_id fk idx, token_hash unique, csrf_token, host_kind app|admin CHECK, created_at, last_seen_at, expires_at, revoked_at). Only the sha256 of the cookie token is stored. Lifetimes app 14d/24h idle, admin 8h/30min idle (proposed). Rotate, revoke, revoke-all, cleanup implemented.
- Verified: migration up/check/down on SQLite; 1372 tests pass. Postgres run still pending (Docker off). Not committed.

## 2026-11-16 - S1-03b session cookie helpers
- Files: app/services/session_cookies.py (new), tests/test_session_cookies.py (new, 16 tests), .env.example (COOKIE_SECURE), session file addendum.
- HttpOnly, host-only (never Domain), __Host- name prefix when Secure, Secure default on, SameSite Lax (app) / Strict (admin), Max-Age = session absolute lifetime. Env COOKIE_SECURE=0 disables Secure/prefix for local http only. Not wired to routes yet.

## 2026-11-16 - Routing verification (no code change)
- Read-only curl of app./admin./apex seofixai.com: all serve the old live app via Cloudflare; /health 404 (old build); /settings, /docs, /openapi.json open (200) on admin host without login. Logged in session file. Nothing changed.

## 2026-11-16 - S1-03c CSRF rule and S1-03d login throttling; scope reduced by user
- Files: app/services/csrf.py, app/services/rate_limit.py, app/models.py (LoginAttempt), alembic/versions/c3e7a2d9f503_add_login_attempts.py, tests/test_csrf.py (17), tests/test_rate_limit.py (9). Full suite 1414 passed.
- User asked for a faster, less-secure version to validate the UI before AWS. Decision: no further hardening steps now; CSRF and rate-limit enforcement go behind default-off env flags for local testing and must be switched on before production (RULES.md section 3). Nothing committed.

## 2026-11-16 - D-018 owner waives CSRF, secure-session hardening, login rate limiting
- Files: Mandatory/DECISIONS.md (D-018 appended), docs/SaaS_Master_Plan.md (DEFERRED note under S1-03 heading), session file.
- Why: user wants a fast version to validate the UI before AWS. Risk accepted by owner is spelled out in D-018. Existing csrf/rate_limit/session_cookies code kept, unwired. RULES.md unchanged (still lists them; D-018 supersedes for these items).

- Correction to the entry above: the DEFERRED note in docs/SaaS_Master_Plan.md first failed and corrupted the file's encoding; it was repaired (see session file "Incident") and the note re-added with the Edit tool. No content lost.

## 2026-11-16 - S1-04/S1-05/S1-06 minimal auth guard, login/logout/register, local two-host verification
- Files: app/auth.py (new), app/routes/auth.py (new), app/templates/auth/{layout,login,register,admin_home}.html (new), app/main.py, app/host_routing.py, app/templates/partials/sidebar.html, .env.example, tests/test_auth_flow.py (new, 31 tests), Mandatory/DECISIONS.md (D-019), session file.
- Behaviour: AUTH_ENFORCEMENT=1 makes every route require a session (deny by default; /login /register /logout /health /version public). Customer login on app host, staff on admin host, wrong portal = generic 401. Registration off unless REGISTRATION_ENABLED=1. Host guard now outermost. Admin host / redirects to /admin.
- Verified: full suite 1446 passed; live curl walk-through against the real app on a scratch SQLite db for both hostnames. Three real bugs found that way and fixed (see session file).
- Known gaps recorded in D-019: no per-agency isolation until S2-02; /settings still reachable by customers; no reset flow or audit events. Nothing committed.
