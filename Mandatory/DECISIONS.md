# DECISIONS — append-only decision records

Format: `D-NNN — title`, date, status (accepted / superseded by D-xxx / pending user), context, decision, consequences. Never edit an accepted entry; add a new one that supersedes it.

---

## D-001 — PostgreSQL via psycopg2, env-driven URL
- **Date:** 2026-11-12 · **Status:** accepted · **Source:** session 01
- **Decision:** `app/database.py` reads `DATABASE_URL` from the environment (SQLite fallback only for ad-hoc runs). Driver is `postgresql+psycopg2` (`psycopg2-binary` was already in requirements). Local Postgres runs as `postgres:16` in `seofixai/docker-compose.yml`.
- **Consequence:** same code works for EC2 Postgres and a future RDS.

## D-002 — Alembic is the only schema-change mechanism from now on
- **Date:** 2026-11-12 · **Status:** accepted · **Source:** session 01
- **Decision:** Baseline migration `e9d001b85a1c_baseline_schema.py` (36 tables). Legacy `migrations/NNN_*.py` scripts are kept, frozen, as history.

## D-003 — One-off data copy lives in scripts/, not migrations/
- **Date:** 2026-11-12 · **Status:** accepted · **Source:** session 01
- **Decision:** `scripts/migrate_sqlite_to_postgres.py` copies rows in FK order with PKs preserved and resets sequences. It is data movement, not schema change.

## D-004 — Postgres cutover and tenancy ship as separate releases
- **Date:** 2026-11-12 · **Status:** accepted (from `User_ManagementSAAS.md` §14)
- **Decision:** Production SQLite→Postgres migration first, behavior unchanged. Tenant ownership and authorization in a later, separate release.

## D-005 — Mandatory/ folder as cross-tool source of truth
- **Date:** 2026-11-12 · **Status:** accepted · **Source:** session 02
- **Context:** Multiple coding tools use this repo; each only auto-reads its own entry file.
- **Decision:** All rules, state, decisions and per-session logs live in `Mandatory/`. `CLAUDE.md` and `AGENTS.md` are thin pointers. `HISTORY_LOGS.md` stays as the global summary log.
- **Consequence:** `Mandatory/` sits at the workspace root, outside the `seofixai/` git repo. If `seofixai` is ever cloned alone (e.g. on EC2), the folder is absent there. See open item in session 02.

## D-006 — Frontend direction for the SaaS portals
- **Date:** 2026-11-12 · **Status:** resolved by D-007
- **Context:** Audit found the UI is server-rendered Jinja2 + HTMX + Tailwind (CDN), no React, no build step. The plan doc assumed React + shadcn/ui "subject to repository audit".
- **Options:** (1) stay on Jinja2/HTMX/Tailwind with session cookies — recommended; (2) add a separate React frontend + JSON API layer.
- Resolved: see D-007.

## D-007 — Frontend stays Jinja2 + HTMX + Tailwind (resolves D-006)
- **Date:** 2026-11-12 · **Status:** accepted · **Source:** session 02, user answer
- **Decision:** Customer and admin portals are server-rendered Jinja2 templates with HTMX and Tailwind, inside the existing FastAPI app. No React, no separate frontend build. Auth uses HTTP-only session cookies with CSRF protection (no localStorage tokens). shadcn/ui is not used; reusable Jinja components/macros replace it.
- **Consequence:** `User_ManagementSAAS.md` §11 "React / shadcn/ui" is overridden by this decision. Shared layouts go in `app/templates/` (separate base layouts for customer and admin, shared component macros in `partials/`).

## D-008 — Mandatory/ and HISTORY_LOGS.md live inside seofixai/
- **Date:** 2026-11-12 · **Status:** accepted · **Source:** session 03 (user moved the folder)
- **Decision:** `Mandatory/` now lives at `seofixai/Mandatory/` and `HISTORY_LOGS.md` was moved to `seofixai/Mandatory/HISTORY_LOGS.md`, so both are version-controlled and writable by any tool started inside `seofixai/`. Root `CLAUDE.md`/`AGENTS.md` point to `seofixai/Mandatory/`; `seofixai/CLAUDE.md`/`AGENTS.md` point to `Mandatory/`.
- **Supersedes:** the "Consequence" of D-005 (folder outside the git repo). Older session files keep their original wording as history.

## D-009 — Sprint 0 hostname defaults (S0-04)
- **Date:** 2026-11-13 · **Status:** accepted · **Source:** session 2026-11-13_01, user answer
- **Decision:** (1) Apex `seofix.ai` redirects to `app.seofix.ai`. (2) The existing hostname keeps working with no auth until Sprint 1 (compatibility period). (3) `/health` is public; `/version` is internal-only.
- **Consequence:** the S0-04 hostname matrix and host-classification module implement these; the compat hostname must be listed as an allowed host until retired. Exact current production hostname still to be recorded.

## D-010 — Domain family is seofixai.com; apex serves marketing (supersedes D-009 item 1 and the seofix.ai hostnames in the plan)
- **Date:** 2026-11-13 · **Status:** accepted · **Source:** session 2026-11-13_01, user answers
- **Decision:** Customer host `app.seofixai.com`, admin host `admin.seofixai.com`, marketing site on the `seofixai.com` apex (hosted outside this FastAPI app). The current production app at `https://seofixai.com/` moves to `app.seofixai.com`. Local: `app.localhost` / `admin.localhost`.
- **Still valid from D-009:** old hostname keeps working with no auth until Sprint 1; `/health` public, `/version` internal-only.
- **Consequence:** the apex can no longer be both the legacy app and the marketing site. Cutover needs a defined window: until the move, the apex stays the compat host for the app; at the move, the apex DNS/proxy switches to marketing and apex app URLs need redirects to `app.seofixai.com`. Plan doc text using `seofix.ai` is to be updated to `seofixai.com`. Exact marketing hosting and cutover date are open.

## D-011 — Role model: two independent fields
- **Date:** 2026-11-15 · **Status:** accepted · **Source:** session 2026-11-15_01, user approved the proposal in docs/Threat_Model.md §2
- **Decision:** `User.platform_role` in (`customer` default, `platform_admin`, `support_admin`) and `User.agency_role` in (`owner`, `member`). Stage 1 uses `customer`+`owner` and `platform_admin`; `support_admin` and `member` are reserved with no powers. No request can set `platform_role`. Plan names `agency_owner`/`agency_user` map to `owner`/`member`. Supersedes the conflicting role lists in S0-05 and S1-01.

## D-012 — Cross-agency access returns 404, not 403
- **Date:** 2026-11-15 · **Status:** accepted · **Source:** session 2026-11-15_01
- **Decision:** A resource owned by another agency returns 404 so its existence is not confirmed. Wrong role on a route it can see returns 403.

## D-013 — Deploy health check
- **Date:** 2026-11-15 · **Status:** accepted · **Source:** session 2026-11-15_01
- **Decision:** Public `/health` for outside smoke tests; `/version` checked from the server itself over SSM. Closes the open item from D-009. `deploy.yml` change is still to do before any deploy of this branch.

## D-014 — Global settings and logs are platform-wide, admin-only
- **Date:** 2026-11-15 · **Status:** accepted · **Source:** session 2026-11-15_01
- **Decision:** `provider_settings`, `crawler_settings`, `site_audit_settings`, `app_logs` and `/settings/*` stay platform-wide and `platform_admin` only.

## D-015 — One shared guarded-fetch helper in Sprint 1 (SSRF, abuse case A17)
- **Date:** 2026-11-15 · **Status:** accepted · **Source:** session 2026-11-15_01
- **Decision:** Build one SSRF-safe fetch helper based on the guard in `app/services/page_evidence.py` and use it in audit.py, crawler.py, routes/security.py, dataforseo_onpage.py and wordpress.py.

## D-016 — Keyword workspaces without a project belong to the creating agency
- **Date:** 2026-11-15 · **Status:** accepted · **Source:** session 2026-11-15_01
- **Decision:** Every KeywordWorkspace gets an owner agency (its creator's). Schema change lands with the S1 tenancy migration.

## D-017 — Semrush on-page snapshots: shared cache vs per-agency
- **Date:** 2026-11-15 · **Status:** PROVISIONAL, not explicitly answered · **Source:** session 2026-11-15_01
- **Decision:** Treated as an open question; not needed for S1-01. Recommend deciding before S2. Leaning per-agency to avoid one customer's lookups leaking to another.


## D-018 — CSRF protection, secure-session hardening and login rate limiting are NOT required for this application
- **Date:** 2026-11-16 · **Status:** accepted (explicit user instruction) · **Source:** session 2026-11-16_01
- **Decision:** The owner does not want CSRF protection, secure-session hardening (Secure/SameSite/__Host- cookie flags, session rotation and expiry rules beyond basic login) or login rate limiting enforced in this application. The goal is a fast version to validate the UI before pushing to AWS. This supersedes RULES.md section 3 for those items only; the rest of section 3 still binds (Argon2 passwords, no plaintext secrets, admin never granted through public registration, server-side authorization, deny by default).
- **What stays:** the code already written (app/services/csrf.py, rate_limit.py, session_cookies.py, sessions.py and their tests) stays in the repo, unwired and available. The S1-03 and S1-05 items for these remain in docs/SaaS_Master_Plan.md marked DEFERRED, not deleted, so they can be switched on later.
- **Risk accepted by the owner:** without CSRF a malicious site can make a logged-in user's browser submit actions; without rate limiting passwords can be guessed at full speed; without Secure cookies sessions can travel over plain http. Cloudflare in front of the app gives partial cover only.


## D-019 — Auth guard design for the first release (S1-04/S1-05)
- **Date:** 2026-11-16 · **Status:** accepted for local validation, review before AWS · **Source:** session 2026-11-16_01
- **Decision:** One middleware (app/auth.py) protects every route, deny by default; public paths are only /login, /register, /logout, /health, /version. It is OFF unless AUTH_ENFORCEMENT=1, so existing behaviour and the 1300+ existing tests are untouched. Login is per portal: customers on the app host, staff on the admin host; the wrong portal gets the same generic "Invalid email or password." Sessions are server-side (app/services/sessions.py). Public registration is OFF unless REGISTRATION_ENABLED=1. Host guard runs before the auth guard (middleware order). Login/logout are reachable on every trusted host.
- **Known gaps (accepted for now):** (1) no per-agency data isolation until the S2-02 tenancy migration, so any logged-in customer sees ALL projects; (2) /settings (API keys) is still reachable by customers because per D-014 it belongs under the admin portal, which is not built yet; (3) no CSRF/rate limit per D-018; (4) no password-reset flow or audit events yet.
- **Why registration defaults off:** with gap (1), anyone who could register would see every customer's projects.
