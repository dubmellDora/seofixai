# VtechysSEO SaaS Transformation
## Sprint Implementation Plan & Technical Specifications

**Document status:** Proposed  
**Project:** VtechysSEO / SEO Automation  
**Architecture:** FastAPI + SQLAlchemy, server-rendered Jinja2 + HTMX + Tailwind, with separate hostnames for the public app and admin portal  
**Initial infrastructure:** Existing AWS EC2  
**Initial database target:** PostgreSQL hosted on existing EC2  
**Future database option:** Amazon RDS PostgreSQL  
**Deployment constraint:** No staging environment currently exists.

---

# Part 0 — Project Findings and Recovery Record (READ THIS FIRST)

> **File history:** this document was `docs/User_ManagementSAAS.md` until 2026-11-14 and was renamed to `docs/SaaS_Master_Plan.md`. Older logs under `Mandatory/` still use the old name; that is history, not an error.
> **Purpose of Part 0:** if the project, the chat history or the machine is lost, this section plus the sections below it must be enough to understand what the product is, what was decided, what was found, where work stopped, and how to rebuild. Sections 1-16 are the original plan and are kept unchanged.
> **Last updated:** 2026-11-14.

## 0.1 Corrections that override the original plan text (Sections 1-16)

The original body below was written before several decisions. **Where it conflicts with this table, this table wins.**

| Original plan text | Correct value | Source |
|---|---|---|
| Hostnames `app.seofix.ai`, `admin.seofix.ai` | `app.seofixai.com`, `admin.seofixai.com` | D-010 |
| Apex redirects to the app | Apex `seofixai.com` becomes the **marketing site** (hosted outside this app). Until the cutover, the apex stays the legacy app host | D-010 |
| Frontend "React / shadcn/ui" (older drafts) | Jinja2 + HTMX + Tailwind inside FastAPI. No React | D-007 |
| "Organization" wording in Sprints 4-7 | The tenant is the **Agency**. Read "organization" as "agency" | Stage 1 model |
| Task IDs: Sprint 5 uses `S4-xx`, Sprint 6 uses `S5-xx`, Sprint 7 uses `S6-xx`, Later Stage uses `S3-xx` | IDs are duplicated in the original. Refer to tasks as "Sprint N, task title". Renumbering is still an open item | Audit §5 |
| Sprint table calls Sprint 3 "Production launch"; Section 15 calls Sprint 3 "multi-tenant identity" | Unresolved. Section 15 plus the critical release rule (Postgres cutover and tenancy ship separately) is the safer reading | Audit §5 |
| Roles: S0-05 lists `platform_admin`, `support_admin`, `customer`; S1-01 lists `agency_owner`, `agency_user`, `platform_admin` | **Unreconciled.** Needs one approved role table before S1-01 | Audit §5 |

## 0.2 What the product is (so it can be rebuilt)

**Product:** VtechysSEO / SEOFixAI. An SEO automation tool: crawl a site, find SEO issues, generate AI fix suggestions, and deploy approved fixes to WordPress through a companion plugin. It also does keyword research and rank tracking, backlinks, competitor and gap analysis, a content optimizer, AI-visibility checks, a security report and Google Search Console integration.

**Stack:** Python 3.10-3.12, FastAPI, SQLAlchemy, Alembic, Jinja2 + HTMX + Tailwind (both from CDN), APScheduler, crawl4ai + Playwright, Anthropic and Google GenAI, Semrush and DataForSEO providers.

**Layout** (workspace `VtechysSEO-Automation/` is not a git repo; `seofixai/` is):

```text
VtechysSEO-Automation/
  CLAUDE.md, AGENTS.md          entry points -> seofixai/Mandatory/
  ai-seo-connector/             WordPress plugin (PHP), separate upstream repo
  seofixai/                     the app (git repo)
    app/main.py                 FastAPI entry; 15 routers; scheduler in lifespan
    app/routes/                 thin HTTP handlers, one module per feature
    app/services/               feature business logic
    app/jobs/                   registry + runner (one subprocess per job) + handlers/
    app/scheduler.py            queues due Schedule rows into Job rows
    app/models.py               36 tables, root object = Project
    app/templates/              Jinja2 pages
    <adapters>.py               semrush, dataforseo, wordpress, google_search_console, claude, gemini
    alembic/                    schema changes (only mechanism from D-002)
    migrations/                 legacy numbered SQLite scripts, frozen history
    tests/                      ~55 files, 1241 passing tests (2026-11-13)
    docs/                       this plan, audits, lessons
    Mandatory/                  RULES, IMPLEMENTATION_STATE, DECISIONS, SESSIONS/, HISTORY_LOGS
```

**Run locally** (from `seofixai/`, venv active): `docker compose up -d postgres`, `alembic upgrade head`, `uvicorn app.main:app`. Tests: `python -m pytest -q` with `DATABASE_URL` set to the Docker Postgres. Local DB URL: `postgresql+psycopg2://seofixai:seofixai@localhost:5432/seofixai` in the gitignored `.env`.

**Production:** Docker on one AWS EC2 host, single uvicorn process, **still SQLite**. Deploy is the manual GitHub Actions workflow `deploy.yml` (tests gate it, SSM command, runs legacy `migrations/*.py`, smoke tests, auto-rollback). `backup-db.yml` snapshots the SQLite file daily and keeps 14.

## 0.3 Decisions made so far (full text: `Mandatory/DECISIONS.md`)

| ID | Decision |
|---|---|
| D-001 | PostgreSQL via psycopg2; `DATABASE_URL` from environment (SQLite fallback only for ad-hoc scripts). Same code for EC2 Postgres and a future RDS |
| D-002 | Alembic is the only schema-change mechanism. Baseline revision `e9d001b85a1c` (36 tables). Legacy `migrations/*.py` frozen |
| D-003 | One-off data copy lives in `scripts/migrate_sqlite_to_postgres.py` (FK order, primary keys preserved, sequences reset) |
| D-004 | **Production SQLite-to-Postgres cutover and multi-tenant schema ship as separate releases** |
| D-005 / D-008 | `Mandatory/` is the cross-tool source of truth and lives inside `seofixai/` |
| D-007 | Frontend stays Jinja2 + HTMX + Tailwind; HTTP-only session cookies with CSRF; no localStorage tokens |
| D-009 | Old hostname keeps working with no auth until Sprint 1; `/health` public; `/version` internal-only |
| D-010 | Domains: `app.seofixai.com` (customers), `admin.seofixai.com` (admin), marketing on the apex, local `app.localhost` / `admin.localhost`. Supersedes the `seofix.ai` names and the apex-redirect rule |

**Security principle that must survive any rewrite:** a hostname, URL prefix, hidden menu or front-end check is never authorization. Every protected request is authorized server-side from the signed-in identity plus Agency/Project ownership.

## 0.4 Sprint 0 audit findings (full: `docs/Sprint0_Audit.md`)

Baseline: `python -m pytest -q` against local Postgres gave **1241 passed, 1 warning** (a google.genai deprecation notice), about 54 s.

1. **No authentication, users, sessions or tenancy exist.** About 100 routes are open to anyone who can reach the host. That includes project delete, WordPress deploy and rollback, provider-key activation and log clearing. Integer IDs in URLs load rows with no ownership check.
2. **Deploy conflicts with D-009.** `deploy.yml` polls the public `/version` and smoke-tests `/`, `/settings`, `/docs` and `/version` from a GitHub runner. Making `/version` internal-only, or adding auth, will fail deploys and trigger rollbacks. **Proposed (not yet approved):** keep `/health` public and minimal; verify `/version` over SSM from the server itself.
3. **Ownership gaps** that cannot be scoped by project today: `keyword_workspaces.project_id` is nullable; `semrush_onpage_snapshots` is keyed on Semrush IDs; `provider_settings`, `crawler_settings`, `site_audit_settings` and `app_logs` are global and need an admin-only home.
4. **Google OAuth redirect URI is fixed at Google.** `https://app.seofixai.com/gsc/callback` must be registered before the move; keep the old URI during the compatibility period. The OAuth `state` is signed but not bound to a session.
5. **The scheduler runs inside every app process.** Fine with one uvicorn process; it duplicates every job if workers or containers are added.
6. **`Base.metadata.create_all()` still runs at startup in `app/main.py`.** This bypasses Alembic and conflicts with D-002. Recorded, not changed.
7. **Production is SQLite and the deploy runs legacy migrations, not Alembic.**
8. **Env var `GEMENI_KEY` is misspelled in code** and missing from `.env.example`. Renaming would change behavior, so it is only recorded.
9. **Cookies are host-only.** Sessions on the legacy apex will not carry over to `app.seofixai.com`. No sessions exist yet, so nobody is logged out today.
10. Background code (`scheduler.py`, `jobs/runner.py`, `backlinks_provider.py`, one deploy task in `routes/wordpress.py`) opens its own DB sessions with no request identity, so it needs its own scoping rule.

## 0.5 Performance findings (full: `docs/Performance_Audit.md`)

Static read only, **no profiling was done**; these are suspected costs. Python's language speed is not the problem. Time goes on waiting for Semrush, DataForSEO, WordPress sites, LLM APIs and the database.

| # | Finding |
|---|---|
| P1 | 46 foreign keys but only one index. Postgres does not index foreign keys automatically |
| P2 | Blocking `httpx` calls and a `time.sleep` inside request handlers (`routes/security.py`, `routes/wordpress.py`, `audit.py`); which run in a request vs a job is unconfirmed |
| P3 | `base.html` loads the Tailwind CDN runtime compiler and htmx from unpkg on every page |
| P4 | No caching, cache headers or compression |
| P5 | 73 `.all()` calls versus 10 `limit`/`offset`, so no pagination discipline |
| P6 | No eager loading (`joinedload`/`selectinload`: 0); N+1 risk unmeasured |
| P7 | Single uvicorn process with the scheduler inside; cannot add workers safely |
| P8 | Default SQLAlchemy pool; needs tuning under Postgres |
| P9 | Production still SQLite (single writer) |
| P10 | No latency measurement at all |

The 189 plain `def` routes are **not** a problem: FastAPI runs them in a threadpool. Do not rewrite everything to async.

**Where it fits (proposed, pending approval):**
- **Inside Stage 1:** S0 request-timing baseline; indexes on the new `agency_id` / `project_id` columns in the same migration that adds them; new list endpoints paginate from day one; Postgres pool settings during the cutover; no new blocking external calls in request handlers.
- **Later performance pass:** real Tailwind build and self-hosted htmx, compression and caching, moving slow calls into jobs, fixing old pagination and N+1, splitting the scheduler and then adding workers. Order: measure, indexes, static assets, slow calls, pagination, scheduler split.
- **Open choice:** do the Tailwind fix (P3) as a small standalone task now, since it is isolated from Stage 1.

## 0.6 Progress and where work stopped (2026-11-14)

| Item | Status |
|---|---|
| DB-01 to DB-03 (local Postgres, compatibility, data-copy script) | Done locally |
| DB-04 EC2 Postgres, DB-05 RDS | Not started |
| S0-01, S0-02, S0-03 | Done: `docs/Sprint0_Audit.md`. `.env.example` still needs `GEMENI_KEY`, `APP_LOG_TO_DB` and the hostname variables |
| S0-04 hostname contract | **Code done, docs proposed.** `app/host_routing.py` (classifier, `host_guard_decision`, config loader, middleware) is installed in `app/main.py`, default OFF (`HOST_ENFORCEMENT`), with `/health`. Tests: 1312 passing in total (71 new). `docs/Hostname_Matrix.md` written, awaiting approval |
| S0-04 remaining | Approve the matrix; deploy health-check change (`/version` over SSM); name the TLS certificate owner; cutover date and marketing hosting |
| S0-05 threat model | **Written, awaiting approval:** `docs/Threat_Model.md` (proposed role model, response matrix, resource rule, 20 abuse cases). New finding: SSRF guard exists only in `services/page_evidence.py`; other URL fetchers are unguarded |
| Sprints 1-7 | Not started |

**Design of the host guard (so it can be rebuilt):** classify the `Host` header by **exact match** (never `endswith`, so `evilseofixai.com` and `app.seofixai.com.evil.com` are UNKNOWN). Unknown host returns **421**. A known host asking for the wrong path returns **404** (`/admin` on the public host; non-admin paths on the admin host), because 403 would confirm the admin area exists. The guard sits behind a `HOST_ENFORCEMENT` setting that defaults to off so the live site and the 1241 tests are unaffected. It is middleware, not a per-router dependency, so a forgotten router cannot leave a hole. It reads `Host` only; `X-Forwarded-Host` handling waits for S1-06. Planned settings: `PUBLIC_APP_ORIGIN`, `ADMIN_APP_ORIGIN`, `LEGACY_APP_HOSTS`, `HOST_ENFORCEMENT`, `ENVIRONMENT`.

## 0.7 Open items

1. Deploy health-check approach once `/version` is internal-only (proposal in 0.4 item 2).
2. Apex cutover date and where the marketing site is hosted.
3. Reconcile the two role lists into one approved table.
4. Renumber duplicated task IDs and replace "organization" with "agency" in the original body.
5. Replace `seofix.ai` with `seofixai.com` in the original body (0.1 covers it until then).
6. Decide whether to move `host_routing.py` into a small `app/core/` package before anything imports it. The flat `app/` folder already holds about 30 loose modules.
7. Tailwind-now versus later (0.5).
8. Remove `create_all()` from startup in a separate controlled change.
9. Tests share the local development Postgres, so they write rows into development data.

## 0.8 How to resume or rebuild

1. Read `Mandatory/README.md` and follow its read order. Every session creates its own file in `Mandatory/SESSIONS/` and appends to `Mandatory/HISTORY_LOGS.md`.
2. Read this Part 0, then `docs/Sprint0_Audit.md`, `docs/Performance_Audit.md` and `Mandatory/DECISIONS.md`.
3. Start the local database, run `alembic upgrade head`, run the test suite and confirm 1241 pass before changing anything.
4. Get `docs/Hostname_Matrix.md` and `docs/Threat_Model.md` approved, reconcile the roles, then start Sprint 1.
5. If the code is lost but these documents survive: restore the app from the git repo, re-apply Alembic head `e9d001b85a1c`, then rebuild the host guard from the design in 0.6 and the original plan sections below.

**Working agreement:** the owner is learning to code. Claude writes the code in small steps, explains what each piece is, why it exists and how it works, and checks understanding before continuing. Audits go in `docs/`. Lessons go in `docs/learning/`.

---

# 1. Project Objectives

Transform the existing SEO automation product into a small, agency-first SaaS application with:

- One owner user per agency in the first release.
- Agency-controlled branding and application appearance.
- Multiple projects per agency.
- A Google Search Console mapping for each project.
- A later path to multiple agency users and project assignment.
- Secure authentication and authorization.
- Isolated customer projects, audits and reports.
- A small internal admin surface.
- Minimal infrastructure and operational complexity.

## 1.1 Architecture principles

1. Existing live customer functionality must not break.
2. Database configuration must be environment-driven.
3. Application code must not depend on EC2-hosted PostgreSQL versus RDS.
4. Customer data must be isolated at the backend.
5. Admin permissions must be enforced server-side.
6. New SaaS capabilities must be introduced incrementally.
7. Avoid introducing paid infrastructure until operationally justified.
8. Every production database change must have a backup and rollback plan.
9. An agency is the primary customer boundary; users and projects belong to an agency.
10. Stage 1 enforces one owner user per agency, while the schema remains ready for more users later.
11. Hostname separation is a navigation and deployment boundary; it is never the authorization boundary.
12. Every protected request is authorized server-side using the signed-in identity and agency/project ownership.

# 2. Overall Sprint Roadmap

| Sprint | Name | Primary outcome |
|---|---|---|
| Sprint 0 | Audit and MVP boundary | Existing application baseline and agency-first scope |
| Sprint 1 | Agency identity | Agency, owner user, login/logout and sessions |
| Sprint 2 | Agency workspace | Branding, projects and project-level GSC mapping |
| Sprint 3 | Production launch | PostgreSQL cutover, backups, deployment and smoke tests |
| Later | Agency users | Invitations, user roles and project assignment |
| Later | Commercial SaaS | Billing, usage limits and subscriptions |

Database migration runs as a parallel workstream:

| Workstream | Scope |
|---|---|
| DB-1 | PostgreSQL compatibility and local setup |
| DB-2 | SQLite data migration and integrity validation |
| DB-3 | Production EC2 PostgreSQL deployment |
| DB-4 | Optional future migration to RDS |

## MVP operating model

The first production release is intentionally smaller than a general-purpose multi-tenant SaaS platform.

```text
Agency
 ├── one owner User (Stage 1)
 ├── branding settings
 └── many Projects
       └── one or more GSC connections, according to the product rule for that project
```

The database should contain an `Agency` entity from the first release. Do not model the first release as a user-owned product with no agency table; that would make branding, project ownership and future users harder to add.

Stage 1 rules:

- A new registration creates one Agency and one owner User in one transaction.
- A Stage 1 agency has one active owner user. Additional users are disabled by product policy, not by deleting the future relationship model.
- Projects belong to the Agency through `agency_id`.
- A GSC connection belongs to both the Agency and a Project, and its refresh token is encrypted at rest.
- The owner can manage branding, projects and GSC mappings.
- Platform administrators are separate from agency users.

Stage 2 rules:

- Add multiple users under an Agency.
- Add invitations and membership status.
- Add project assignment through a `ProjectUser` relationship.
- Preserve all existing Agency, Project and GSC identifiers.

Explicitly deferred from the MVP: billing, subscriptions, usage metering, organization membership terminology, impersonation, complex role matrices, separate frontend deployment, microservices and RDS.

---

# 3. Sprint 0 — Technical Audit and Preparation

**Objective:** Understand the existing application before introducing new authentication, UI or database architecture.

## TASK S0-01 — Repository and architecture audit

Acceptance criteria:

- [ ] Identify frontend framework and current UI entry points.
- [ ] Document FastAPI application structure.
- [ ] Identify SQLAlchemy models and relationships.
- [ ] Identify all database access locations.
- [ ] Identify existing authentication and authorization logic.
- [ ] Identify existing API routes and background jobs.
- [ ] Identify scheduler ownership and execution model.
- [ ] Identify existing customer/project ownership fields.
- [ ] Identify deployment and environment configuration.
- [ ] Document existing production functionality.

## TASK S0-02 — Existing functionality baseline

Acceptance criteria:

- [ ] List current working SEO workflows.
- [ ] Identify existing customer-facing screens.
- [ ] Identify existing admin capabilities.
- [ ] Record current API behavior.
- [ ] Create regression test coverage for critical workflows.
- [ ] Record existing database tables and relationships.

## TASK S0-03 — Development environment

Acceptance criteria:

- [ ] Local application starts successfully.
- [ ] Environment variables are documented.
- [ ] Local development database is configured.
- [ ] Development and production secrets are separated.
- [ ] Existing application can be run without production credentials.

**Sprint 0 exit condition:** The existing application has a documented baseline and new work can proceed without guessing about current behavior.

## TASK S0-04 — Public and admin hostname/routing contract

**Decision to implement:** use `app.seofix.ai` as the customer application hostname and `admin.seofix.ai` as the administrative hostname in production. Use local equivalents such as `app.localhost` and `admin.localhost`, or explicit hosts-file names, during development. Keep `/admin/...` as an internal route namespace only where it helps organize FastAPI routes; the hostname and the path must both be checked by the application configuration.

This task creates the routing contract before portal UI work. It does not grant privileges. A customer who reaches `admin.seofix.ai` without an admin role must receive a server-side 403 or a safe redirect, and an admin must still be denied access to customer resources unless the relevant administrative capability allows it.

Acceptance criteria:

- [ ] Define `PUBLIC_APP_ORIGIN`, `ADMIN_APP_ORIGIN`, and `ENVIRONMENT` in `.env.example`; no hostname is hard-coded in route logic.
- [ ] Define the canonical host for each environment: local development, production, and future staging.
- [ ] Define whether the apex domain redirects to the public app, a marketing site, or a documented 404; record the choice before implementation.
- [ ] Define HTTP-to-HTTPS behavior and HSTS expectations for production.
- [ ] Define canonical redirects for requests with an unexpected `Host` header; do not create open redirects from user-controlled host values.
- [ ] Add a small host-resolution module that classifies a request as `public`, `admin`, or `unknown` from trusted configuration.
- [ ] Add middleware or dependencies that reject unknown hosts and reject admin-only endpoints on the public host where appropriate.
- [ ] Keep `/health` and `/version` behavior explicitly documented; decide whether they are public, internal-only, or protected by infrastructure.
- [ ] Ensure generated login, logout, password-reset, OAuth callback, and email links use the configured canonical origin for the relevant portal.
- [ ] Ensure cookies use an intentional domain policy. Prefer host-only cookies for admin and customer sessions unless cross-subdomain sharing is explicitly required.
- [ ] Define CSRF origin checking against the configured origins, not against a request-supplied value.
- [ ] Add tests for correct-host success, wrong-host rejection, unknown-host rejection, and safe redirect behavior.
- [ ] Document local DNS/hosts-file setup and the reverse-proxy rule that maps both hostnames to the FastAPI service.
- [ ] Document TLS certificate coverage for both hostnames and the renewal owner/process.
- [ ] Define a migration-safe compatibility period for the existing hostname so current users are not silently logged out or sent to a broken URL.

**TASK S0-04 deliverable:** a reviewed hostname matrix, environment variables, reverse-proxy contract, and automated host-routing tests. No production DNS or proxy change is included in this task.

**TASK S0-05 — Routing threat model and authorization boundary**

Acceptance criteria:

- [ ] Record that DNS, subdomains, URL prefixes, hidden navigation, and frontend checks are not authorization controls.
- [ ] Define platform roles (`platform_admin`, `support_admin`, `customer`) separately from organization roles (`owner`, `admin`, `member`).
- [ ] Define the expected response for unauthenticated, authenticated-but-wrong-role, suspended-user, suspended-organization, and unknown-host requests.
- [ ] Define a resource authorization rule for every root resource, beginning with `Project` and then its child records.
- [ ] Decide whether support administrators may impersonate customers; default to no impersonation until an audited, time-limited workflow exists.
- [ ] Add abuse cases for host-header manipulation, IDOR/object-ID substitution, cross-tenant access, cookie confusion, and CSRF.
- [ ] Use the threat model as the acceptance checklist for S1 and S2 implementation.

**Sprint 0 routing exit condition:** the hostname matrix and authorization boundary are approved in documentation before code adds portal-specific routing.

---

# 4. Sprint 1 — Agency Identity and Authentication Foundation

**Objective:** Establish the smallest production identity model: an Agency, one owner User, secure sessions, and server-side authorization.

**Dependency:** Sprint 0 TASK S0-04 and S0-05 must be complete. This sprint is deliberately backend-first; visual pages may be minimal test pages.

## TASK S1-01 — Agency and owner data model

Acceptance criteria:

- [ ] Create an `Agency` model through an Alembic migration only.
- [ ] Store agency name, slug, active status, branding fields, and timestamps.
- [ ] Create a `User` model with an `agency_id` foreign key.
- [ ] Store a normalized unique email, display name, password hash, role, active status, verification status, and timestamps.
- [ ] Define Stage 1 roles as `agency_owner`, `agency_user` (reserved for Stage 2), and `platform_admin`.
- [ ] Public registration can create only an Agency plus one `agency_owner`; it can never create a `platform_admin`.
- [ ] Create the Agency and owner User atomically so neither can exist without the other.
- [ ] Add a development-only procedure for bootstrapping the first platform admin.
- [ ] Add tests for duplicate email, duplicate agency slug, deactivated users, and attempted public admin creation.

## TASK S1-02 — User and platform-role behavior

Acceptance criteria:

- [ ] Use a stable UUID identifier for users where practical; do not use email as a foreign key.
- [ ] Store normalized, unique email addresses and preserve a display name separately.
- [ ] Store only Argon2 password hashes; never store plaintext passwords or reset tokens.
- [ ] Add active/deactivated status, email-verification status, created/updated timestamps, and last-login timestamp.
- [ ] Add a platform role with a safe default of `customer`; public registration can never select or submit an admin role.
- [ ] Add indexes and uniqueness constraints intentionally and document them in the migration.
- [ ] Add a development-only bootstrap procedure for the first admin that cannot run in a public registration request.
- [ ] Add tests for duplicate email normalization, deactivated users, and attempted public admin creation.

## TASK S1-03 — Secure session lifecycle

> **STATUS 2026-11-16 (D-018): CSRF, secure-cookie hardening and login rate limiting are DEFERRED by owner decision. The criteria below are kept for later and are not required for the first release. Built but unwired: app/services/csrf.py, rate_limit.py, session_cookies.py, sessions.py.**

Acceptance criteria:

- [ ] Choose a server-side session representation and document its expiration, rotation, invalidation, and cleanup behavior.
- [ ] Use HTTP-only, Secure-in-production, SameSite cookies with host-only scope by default.
- [ ] Never store credentials, session identifiers, or reset tokens in localStorage.
- [ ] Rotate the session identifier after login and privilege changes.
- [ ] Support logout and invalidation of the current session.
- [ ] Support invalidation of all sessions after password reset or account deactivation.
- [ ] Add CSRF tokens to every state-changing cookie-authenticated form/HTMX request.
- [ ] Use generic login and reset responses that do not reveal whether an email exists.
- [ ] Add rate limiting or an explicit deployment-layer rate-limit contract for login and reset endpoints.
- [ ] Add tests for expired sessions, tampered cookies, CSRF failures, logout, and password-reset invalidation.

## TASK S1-04 — Authentication dependencies and route guards

Acceptance criteria:

- [ ] Implement reusable `require_user`, `require_platform_admin`, and host-classification dependencies.
- [ ] Make authorization deny by default when identity, role, organization membership, or resource ownership is missing.
- [ ] Define consistent 401, 403, 404, and redirect behavior for browser and HTMX requests.
- [ ] Protect one low-risk route family end to end as the reference implementation.
- [ ] Ensure a user cannot access a resource by changing an integer or UUID in the URL.
- [ ] Ensure admin routes check platform role server-side even when requested from `admin.seofix.ai`.
- [ ] Ensure customer routes never trust an organization or project identifier supplied by the browser without a server-side membership check.
- [ ] Add direct request tests, not only navigation tests.

## TASK S1-05 — Login, logout, registration, and reset backend flows

Acceptance criteria:

- [ ] Implement customer login on the public host and admin login on the admin host.
- [ ] Implement logout on both hosts with the correct host-only cookie cleared.
- [ ] Implement registration behind a configuration flag so invitation-only mode is possible.
- [ ] Implement forgot-password and reset-password with expiring, single-use tokens stored safely.
- [ ] Implement password policy validation server-side.
- [ ] Redirect successful login only to an allowlisted canonical origin and path.
- [ ] Prevent an authenticated customer from entering the admin portal and prevent an unauthenticated user from reaching either dashboard.
- [ ] Add audit events for login success, login failure threshold, logout, reset request, reset completion, and admin bootstrap.

## TASK S1-06 — Routing integration and local verification

Acceptance criteria:

- [ ] Add the configured public/admin origins to local `.env.example` documentation.
- [ ] Verify `app.localhost` and `admin.localhost` (or the chosen local names) route to the same FastAPI service while retaining distinct request host classification.
- [ ] Add a reverse-proxy configuration example with TLS termination, forwarded-host handling, and trusted-proxy rules.
- [ ] Reject untrusted `X-Forwarded-Host` and `X-Forwarded-Proto` values unless the request came through a configured proxy.
- [ ] Verify canonical links, redirects, cookie behavior, and CSRF behavior on both hostnames.
- [ ] Keep existing SEO routes available behind the compatibility policy until their individual authorization migration is complete.
- [ ] Run the full regression suite and the new authentication/routing tests.

**Sprint 1 deliverable:** an Agency plus owner User, secure sessions, server-side role guards, and tested login/logout/reset flows. No dashboard metric is considered production-ready until it is protected by these guards.

---

# 5. Sprint 2 — Agency Workspace

**Objective:** Give the agency owner a useful branded workspace with projects and project-level Google Search Console mapping.

**Priority:** High  
**Estimated duration:** 5–7 working days.

**Dependency:** Sprint 1 must be complete. Portal pages may be built in parallel with visual design, but every data-bearing action must call the Sprint 1 authorization dependencies.

## TASK S2-01 — Agency branding

Acceptance criteria:

- [ ] Add agency branding fields to the Agency model through Alembic.
- [ ] Allow the owner to set agency display name, logo/icon, primary color, and application title.
- [ ] Validate uploaded logo type and size; store files outside source control.
- [ ] Render branding through one shared Jinja layout instead of duplicating templates.
- [ ] Apply safe defaults when branding is incomplete.
- [ ] Verify one agency cannot read or change another agency's branding.

## TASK S2-02 — Agency project management

Acceptance criteria:

- [ ] Add `agency_id` to Project through a defensive Alembic migration.
- [ ] Backfill existing projects into a documented default Agency.
- [ ] Owner can create, edit, archive, and list projects belonging to their Agency.
- [ ] Project detail and child records are loaded only after Agency ownership is checked.
- [ ] Changing a project ID cannot expose another Agency's project.
- [ ] Existing project IDs and SEO workflows remain functional.

## TASK S2-03 — Project-level Google Search Console mapping

Acceptance criteria:

- [ ] Associate each GSC connection with both `agency_id` and `project_id`.
- [ ] Encrypt refresh tokens at rest and never expose them in templates or logs.
- [ ] Owner can connect, select, verify, and disconnect a GSC property for an authorized project.
- [ ] Every callback validates the expected user/session state and target project ownership.
- [ ] GSC data requests derive Agency and Project from the server-side session and database, not from trusted browser IDs.
- [ ] A GSC connection from Agency A cannot be used for Agency B's project.
- [ ] Define whether MVP allows one or multiple GSC properties per project; implement only that rule.

## TASK S2-04 — Stage 1 owner workspace

Acceptance criteria:

- [ ] Owner sees Agency branding after login.
- [ ] Owner sees an empty state when no projects exist.
- [ ] Owner can move from project list to project detail and GSC settings.
- [ ] Customer-facing SEO routes receive the selected authorized project context.
- [ ] Admin pages remain separate from the owner workspace.
- [ ] Add direct-request tests for project, branding, and GSC authorization.

## TASK S2-05 — Frontend architecture and design system

Acceptance criteria:

- [ ] Establish reusable page layouts.
- [ ] Establish typography, colors, spacing and component standards.
- [ ] Create reusable form components.
- [ ] Create reusable input, button, alert and loading components.
- [ ] Establish responsive desktop and mobile layouts.
- [ ] Use consistent visual branding across both portals.
- [ ] Avoid duplicating shared components.

## TASK S2-06 — Customer login page

Route: `/login`

Acceptance criteria:

- [ ] Professional SaaS login interface.
- [ ] Email input.
- [ ] Password input.
- [ ] Show/hide password control.
- [ ] Remember-me option if supported by session policy.
- [ ] Forgot-password link.
- [ ] Sign-in button with loading state.
- [ ] Field validation and readable error messages.
- [ ] Responsive design.
- [ ] Clear brand identity.
- [ ] No exposure of internal admin functionality.
- [ ] Accessible labels, keyboard navigation and focus states.

Design direction:

- Premium, modern SaaS appearance.
- Clean light interface with restrained brand colors.
- Split-screen layout or compact centered authentication card.
- Strong visual hierarchy.
- Minimal distractions.
- Professional rather than generic template appearance.

## TASK S2-07 — Customer signup page

Route: `/register`

Acceptance criteria:

- [ ] Name field.
- [ ] Email field.
- [ ] Password and confirmation fields.
- [ ] Password strength feedback.
- [ ] Terms and privacy acknowledgement.
- [ ] Validation for invalid or duplicate email.
- [ ] Clear registration success state.
- [ ] Registration can be disabled through configuration if access is invitation-only.

## TASK S2-08 — Forgot-password interface

Route: `/forgot-password`

Acceptance criteria:

- [ ] Email input.
- [ ] Request reset button.
- [ ] Loading and success states.
- [ ] Generic response that does not reveal whether an account exists.
- [ ] Clear instructions to check email.
- [ ] Responsive layout.

## TASK S2-09 — Reset-password interface

Route: `/reset-password`

Acceptance criteria:

- [ ] Accept reset token from URL.
- [ ] Validate token through backend.
- [ ] New password and confirmation fields.
- [ ] Password policy feedback.
- [ ] Expired and invalid token states.
- [ ] Successful reset confirmation.
- [ ] Redirect to customer login after completion.

## TASK S2-10 — Admin login page

Route: `/admin/login`

Acceptance criteria:

- [ ] Separate admin login entry point.
- [ ] Professional administrative interface.
- [ ] Email and password fields.
- [ ] Validation and loading states.
- [ ] Error handling.
- [ ] Successful login redirects to admin dashboard.
- [ ] Customer accounts cannot access the admin portal.
- [ ] Admin access is enforced by backend authorization, not URL separation alone.

## TASK S2-11 — Customer dashboard shell

Route: `/dashboard`

Acceptance criteria:

- [ ] Customer navigation sidebar.
- [ ] Header and account menu.
- [ ] Project overview section.
- [ ] SEO audit summary placeholders.
- [ ] Recent activity section.
- [ ] Usage summary placeholder.
- [ ] Empty state for customers with no projects.
- [ ] Responsive navigation.
- [ ] Logout action.
- [ ] Dashboard must not expose another customer's data.

Initial navigation:

- Overview
- Projects
- SEO Audits
- Reports
- Settings
- Account

## TASK S2-12 — Admin dashboard shell

Route: `/admin/dashboard`

Acceptance criteria:

- [ ] Separate admin layout.
- [ ] Admin navigation.
- [ ] Customer count placeholder.
- [ ] Project count placeholder.
- [ ] Recent customer activity placeholder.
- [ ] System status placeholder.
- [ ] Account menu.
- [ ] Logout action.
- [ ] Admin-only access.

Initial navigation:

- Overview
- Customers
- Organizations
- Projects
- Jobs
- System Health
- Settings

## TASK S2-13 — Authentication integration

Acceptance criteria:

- [ ] Connect login and registration interfaces to backend authentication endpoints.
- [ ] Validate credentials server-side.
- [ ] Implement secure session handling.
- [ ] Implement logout.
- [ ] Redirect users according to their authorized role.
- [ ] Protect customer routes.
- [ ] Protect admin routes.
- [ ] Prevent access using expired sessions.
- [ ] Avoid storing session credentials in localStorage.
- [ ] Implement appropriate CSRF protection if cookie-based authentication is used.

## TASK S2-14 — Sprint 2 regression and demo

Acceptance criteria:

- [ ] Admin login flow tested.
- [ ] Customer login flow tested.
- [ ] Registration tested.
- [ ] Forgot-password interface tested.
- [ ] Reset-password interface tested.
- [ ] Logout tested.
- [ ] Unauthorized route access tested.
- [ ] Existing SEO workflows regression-tested.
- [ ] Mobile and desktop layouts verified.
- [ ] Demo accounts documented for development only.

**Sprint 2 deliverable:** Separate admin and customer portals on their canonical hostnames, with polished pages backed by the Sprint 1 authentication and authorization foundation.

---

# 6. Later Stage — Multiple Agency Users and Project Assignment

**Objective:** Extend the agency-owner MVP to support multiple users under one Agency and assign projects to one or more users.

**Dependency:** Stage 1 is live and stable. Do not combine this release with the initial production PostgreSQL cutover.

## TASK S3-01 — Agency user expansion

Acceptance criteria:

- [ ] Keep the existing `Agency` model as the tenant boundary; do not introduce a second Organization abstraction for this stage.
- [ ] Allow more than one active User under an Agency.
- [ ] Add invitation status, invited-at, accepted-at, and revoked-at fields or a documented equivalent.
- [ ] Preserve the Stage 1 owner as the Agency owner.

## TASK S3-02 — Agency membership and project assignment

Acceptance criteria:

- [ ] Create or activate membership rows linking Users to Agencies.
- [ ] Support owner, admin, and member roles independently of platform roles.
- [ ] Prevent duplicate active memberships.
- [ ] Add a `ProjectUser` relationship for project assignment.
- [ ] Allow one project to be assigned to one or more agency users.
- [ ] Define invitation, acceptance, revocation, and suspension states.
- [ ] Ensure membership changes invalidate or refresh relevant authorization context.

## TASK S3-03 — Agency authorization scope

Acceptance criteria:

- [ ] Keep agency ownership on `Project` and every root customer resource.
- [ ] Update service queries to scope by Agency and, where applicable, ProjectUser before applying user-supplied IDs.
- [ ] Add indexes for agency plus common lookup columns.
- [ ] Preserve existing identifiers and relationships.
- [ ] Add rollback and verification procedures before migration execution.

## TASK S3-04 — Tenant isolation tests

Acceptance criteria:

- [ ] Customer A cannot read or modify Customer B's projects, audits, reports, jobs, settings, or integrations.
- [ ] ID substitution, path manipulation, and direct POST requests fail safely.
- [ ] Admin access is explicitly tested and limited by platform role.
- [ ] Suspended users and organizations are denied according to the documented policy.
- [ ] Tests cover both public and admin hostnames.

**Later-stage deliverable:** multiple agency users, invitations, project assignment, and proven tenant isolation.

---

# 7. Sprint 4 — Customer Workspace

**Objective:** Make the customer portal useful for real SEO work.

## TASK S4-01 — Customer project management

Acceptance criteria:

- [ ] Customer can create a project.
- [ ] Customer can edit project details.
- [ ] Customer can archive a project.
- [ ] Customer can view only authorized projects.
- [ ] Project ownership is enforced server-side.
- [ ] Existing project records remain accessible after migration.

## TASK S4-02 — SEO audit interface

Acceptance criteria:

- [ ] Customer can start an authorized audit.
- [ ] Audit status is displayed.
- [ ] Running, completed and failed states are supported.
- [ ] Customer can view audit results.
- [ ] Customer can view issue summaries.
- [ ] Customer can view recommendations.
- [ ] Audit records are tenant-scoped.

## TASK S4-03 — Reports and history

Acceptance criteria:

- [ ] Customer can view historical audits.
- [ ] Customer can open individual reports.
- [ ] Reports are associated with the correct project and organization.
- [ ] Report access is authorized server-side.
- [ ] Existing report formats are preserved where practical.

## TASK S4-04 — Customer account settings

Acceptance criteria:

- [ ] View profile.
- [ ] Update permitted profile fields.
- [ ] Change password.
- [ ] View organization information.
- [ ] View membership role.
- [ ] Logout and session management.

**Sprint 4 deliverable:** Customers can manage their projects and use core SEO functionality independently.

---

# 8. Sprint 5 — Admin Management

**Objective:** Provide platform operators with centralized management capabilities.

## TASK S4-01 — Customer management

Acceptance criteria:

- [ ] List customers.
- [ ] Search by name and email.
- [ ] View customer details.
- [ ] View organization memberships.
- [ ] Activate and suspend accounts.
- [ ] Record administrative actions.
- [ ] Prevent accidental deletion of customer data.

## TASK S4-02 — Organization management

Acceptance criteria:

- [ ] List organizations.
- [ ] View organization details.
- [ ] View members.
- [ ] View associated projects.
- [ ] Suspend and reactivate organizations.
- [ ] Preserve historical data.

## TASK S4-03 — Project and job monitoring

Acceptance criteria:

- [ ] List platform projects.
- [ ] View job status.
- [ ] View failed jobs.
- [ ] View execution history.
- [ ] Retry eligible failed jobs.
- [ ] Prevent duplicate job execution.
- [ ] Record administrative retries.

## TASK S4-04 — System monitoring

Acceptance criteria:

- [ ] Display application health.
- [ ] Display database connectivity.
- [ ] Display scheduler status.
- [ ] Display background-job status.
- [ ] Display resource and error summaries where available.
- [ ] Avoid exposing secrets or sensitive customer information.

## TASK S4-05 — Audit logging

Acceptance criteria:

- [ ] Record important admin actions.
- [ ] Record actor and timestamp.
- [ ] Record affected resource.
- [ ] Record action outcome.
- [ ] Protect audit logs from unauthorized modification.
- [ ] Avoid logging passwords, tokens or sensitive credentials.

**Sprint 4 deliverable:** Functional platform administration.

---

# 9. Sprint 6 — Billing and Subscription Foundation

**Objective:** Prepare the product for commercial SaaS subscriptions.

## TASK S5-01 — Subscription data model

Acceptance criteria:

- [ ] Define subscription plans.
- [ ] Define subscription status.
- [ ] Associate subscriptions with organizations.
- [ ] Record subscription start and end dates.
- [ ] Support trial, active, past-due and cancelled states.
- [ ] Preserve historical subscription records.

## TASK S5-02 — Usage tracking

Acceptance criteria:

- [ ] Define billable usage metrics.
- [ ] Track audit consumption.
- [ ] Track applicable project limits.
- [ ] Associate usage with organizations.
- [ ] Prevent cross-tenant usage leakage.
- [ ] Support usage reporting.

## TASK S5-03 — Payment integration

Acceptance criteria:

- [ ] Integrate selected payment provider.
- [ ] Verify payment webhooks.
- [ ] Handle successful and failed payments.
- [ ] Handle subscription cancellation.
- [ ] Make webhook processing idempotent.
- [ ] Do not store raw card details.
- [ ] Record payment events.

## TASK S5-04 — Subscription enforcement

Acceptance criteria:

- [ ] Enforce plan limits server-side.
- [ ] Define behavior for expired subscriptions.
- [ ] Define behavior for payment failures.
- [ ] Display subscription status to customers.
- [ ] Allow authorized plan changes.
- [ ] Preserve customer data when subscriptions expire.

**Sprint 5 deliverable:** Subscription and monetization foundation.

---

# 10. Sprint 7 — Production Hardening

**Objective:** Prepare the SaaS architecture for reliable production operation.

## TASK S6-01 — Security review

Acceptance criteria:

- [ ] Review authentication implementation.
- [ ] Review role and tenant authorization.
- [ ] Review password reset security.
- [ ] Review cookie and CSRF configuration.
- [ ] Review rate limiting.
- [ ] Review input validation.
- [ ] Review secrets management.
- [ ] Review API access controls.
- [ ] Test common authorization bypass scenarios.

## TASK S6-02 — Database backup and recovery

Acceptance criteria:

- [ ] Configure automated PostgreSQL backups.
- [ ] Define retention policy.
- [ ] Verify backup integrity.
- [ ] Perform a restore test.
- [ ] Document recovery steps.
- [ ] Document database migration rollback.

## TASK S6-03 — Performance and scalability

Acceptance criteria:

- [ ] Configure database connection pooling.
- [ ] Review slow queries.
- [ ] Add appropriate indexes.
- [ ] Review background job concurrency.
- [ ] Ensure scheduler is not duplicated across application workers.
- [ ] Test concurrent customer requests.
- [ ] Identify infrastructure scaling thresholds.

## TASK S6-04 — Production deployment

Acceptance criteria:

- [ ] Prepare production deployment checklist.
- [ ] Back up the current production database.
- [ ] Apply reviewed migrations.
- [ ] Deploy application changes incrementally.
- [ ] Run smoke tests.
- [ ] Verify customer and admin authentication.
- [ ] Verify existing SEO workflows.
- [ ] Monitor errors after deployment.
- [ ] Retain a documented rollback procedure.

**Sprint 6 deliverable:** Production-ready SaaS foundation.

---

# 11. Parallel Database Migration Workstream

This workstream must not be coupled to the visual portal implementation.

## TASK DB-01 — PostgreSQL local environment

Acceptance criteria:

- [ ] PostgreSQL runs locally through Docker Compose or an equivalent setup.
- [ ] Database connection is environment-configured.
- [ ] SQLAlchemy connects through the configured database URL.
- [ ] Local development does not require AWS.
- [ ] Existing SQLite development workflows remain available during migration.

## TASK DB-02 — PostgreSQL compatibility

Acceptance criteria:

- [ ] Audit SQLAlchemy models for PostgreSQL compatibility.
- [ ] Audit raw SQL queries.
- [ ] Review SQLite-specific SQL behavior.
- [ ] Introduce or reconcile Alembic migrations.
- [ ] Test schema creation from migrations.
- [ ] Run automated database tests.

## TASK DB-03 — SQLite data migration

Acceptance criteria:

- [ ] Create a consistent SQLite database copy.
- [ ] Migrate schema and data to PostgreSQL.
- [ ] Preserve primary keys and relationships.
- [ ] Validate record counts.
- [ ] Validate foreign-key integrity.
- [ ] Validate indexes and constraints.
- [ ] Test all critical SEO workflows against PostgreSQL.

## TASK DB-04 — EC2 PostgreSQL deployment

Acceptance criteria:

- [ ] Install or deploy PostgreSQL on the existing EC2 infrastructure.
- [ ] Configure persistent database storage.
- [ ] Restrict database network access.
- [ ] Configure credentials outside source code.
- [ ] Configure backups.
- [ ] Verify restore procedure.
- [ ] Monitor database resources.

## TASK DB-05 — Optional RDS portability

Acceptance criteria:

- [ ] Application can connect to RDS using environment configuration.
- [ ] No application code changes are required solely for the database host change.
- [ ] Validate connection pooling.
- [ ] Validate TLS and network connectivity.
- [ ] Document EC2 PostgreSQL to RDS migration.
- [ ] Do not provision RDS until cost and operational benefits justify it.

---

# 12. Authentication Technical Standards

## Recommended implementation

Frontend:
- Server-rendered Jinja2 templates.
- HTMX for incremental interactions.
- Tailwind CSS using the existing project approach.
- Reusable Jinja macros and partials for forms, alerts, navigation, and tables.

Backend:
- FastAPI.
- SQLAlchemy.
- Pydantic validation.
- Argon2 password hashing through a maintained password-hashing library.
- Secure HTTP-only session cookies.
- Server-side authorization dependencies.

Email:
- Existing transactional email provider, if suitable.
- Password reset and email verification links.
- Expiring, single-use reset tokens.

## Required authentication capabilities

- Login.
- Logout.
- Registration.
- Email verification.
- Forgot password.
- Reset password.
- Change password.
- Session expiration.
- Session invalidation.
- Role-based access.
- Account deactivation.

## Security acceptance requirements

- Passwords must never be stored in plaintext.
- Password reset tokens must be time-limited and single-use.
- Password reset requests must not disclose account existence.
- Login endpoints must have rate limiting.
- Sessions must use secure cookie settings in production.
- Password reset should invalidate other active sessions.
- Administrative privileges must never be granted through customer-controlled registration.
- Admin accounts should support stronger authentication controls.
- All protected APIs must validate authorization server-side.

---

# 13. Hostname and Portal Route Specification

## Hostnames

| Environment | Customer host | Admin host | Notes |
|---|---|---|---|
| Local | `app.localhost` | `admin.localhost` | Same FastAPI process; host classification remains active |
| Production | `app.seofix.ai` | `admin.seofix.ai` | HTTPS only; reverse proxy terminates TLS |
| Future staging | documented staging equivalents | documented staging equivalents | Must never share production cookies or database |

Hostname rules:

- [ ] Hostnames are configuration, not constants hidden in route functions.
- [ ] DNS and reverse proxy route both hosts to the application service.
- [ ] Host classification does not replace role checks.
- [ ] Cookies are host-only unless a written decision requires otherwise.
- [ ] Canonical redirects are allowlisted and do not reflect arbitrary `Host` values.
- [ ] Public and admin sessions use distinct cookie names and scopes.
- [ ] OAuth and password-reset callbacks use the correct canonical host.

## Customer

| Route | Purpose |
|---|---|
| `/login` | Customer login |
| `/register` | Customer registration |
| `/forgot-password` | Password recovery |
| `/reset-password` | Set new password |
| `/dashboard` | Customer overview |
| `/projects` | Project list |
| `/projects/:id` | Project details |
| `/audits` | SEO audit history |
| `/reports` | Customer reports |
| `/settings` | Account settings |

## Admin

| Route | Purpose |
|---|---|
| `/admin/login` | Admin login |
| `/admin/dashboard` | Admin overview |
| `/admin/customers` | Customer management |
| `/admin/organizations` | Organization management |
| `/admin/projects` | Project management |
| `/admin/jobs` | Job monitoring |
| `/admin/system` | System health |
| `/admin/settings` | Admin settings |

---

# 14. Definition of Done

A task is complete only when:

1. Implementation is committed to the appropriate feature branch.
2. Acceptance criteria are verified.
3. Relevant automated tests pass.
4. Existing functionality is not broken.
5. Security checks are completed where applicable.
6. Database migrations are included where required.
7. Configuration changes are documented.
8. No secrets or production credentials are committed.
9. A demo or test procedure is documented.
10. Changes are reviewed before production deployment.

# 15. Release Strategy

- Sprint 0: Audit and baseline.
- Sprint 1: Hostname contract, identity, sessions, and authorization foundation.
- Sprint 2: Authenticated customer/admin portal UI.
- Sprint 3: Multi-tenant identity and authorization.
- Sprint 4: Customer SEO workspace.
- Sprint 5: Admin management.
- Sprint 6: Billing.
- Sprint 7: Production hardening.

Database migration must have its own controlled release sequence.

**Critical release rule:** Do not combine the production SQLite-to-PostgreSQL migration with the multi-tenant schema migration in one release. First migrate the database while preserving existing application behavior; then introduce tenant ownership and authorization in a separate release.

# 16. Initial Sprint 2 Demo Criteria

At the end of Sprint 2, demonstrate:

1. Customer login page.
2. Customer registration page.
3. Forgot-password page.
4. Reset-password page.
5. Customer dashboard.
6. Separate admin login page.
7. Admin dashboard.
8. Role-protected navigation.
9. Login/logout flow.
10. Responsive layouts.

The dashboards may initially use clearly identified placeholder metrics, but authentication and authorization must not be simulated in production.

**Final objective:** Build a SaaS-ready foundation without unnecessarily increasing infrastructure cost or disrupting the live VtechysSEO product.

