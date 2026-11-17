# Sprint 0 Audit — S0-01, S0-02, S0-03

**Date:** 2026-11-13 · **Session:** `Mandatory/SESSIONS/2026-11-13_01_claude_sprint0-stage1-prep.md`
**Method:** static read of the repo plus one test run. No application code was changed.
**Plan:** `docs/SaaS_Master_Plan.md` (agency-first MVP). **Domains:** D-010 (`app.seofixai.com`, `admin.seofixai.com`, marketing on the apex).

**Baseline:** `python -m pytest -q` against local Docker Postgres: **1241 passed, 1 warning** (google.genai DeprecationWarning), ~54 s.

---

## 1. S0-01 Repository and architecture audit

### 1.1 Frontend and UI entry points
- Server-rendered Jinja2 in `app/templates/`, HTMX and Tailwind both loaded from CDN in `base.html`. No build step, no `frontend/` directory. (D-007.)
- Pages: `index`, `project_detail`, `page_detail`, `keyword_research`, `keyword_workspaces`, `links`, `optimizer`, `competitors`, `visibility_*`, `security_*`, `onpage_semrush`, `onpage/`, `settings`, `settings_crawler`, `partials/`.
- There is one `base.html` layout. There is no separate admin layout and no shared form/alert macros yet (needed for S2-05).

### 1.2 FastAPI structure
- `app/main.py` builds one `FastAPI` app and includes 15 routers (projects, crawl, audit, suggestions, keywords, jobs, wordpress, onpage_semrush, settings, security, visibility, competitors, optimizer, links, search_console).
- Only inline route in `main.py`: `GET /version`.
- Lifespan starts and stops the APScheduler.
- No middleware at all: no host check, no session, no CSRF, no CORS, no trusted-proxy handling.
- Layers: `routes/` (thin) → `services/` → top-level provider adapters (`semrush.py`, `dataforseo.py`, `wordpress.py`, `google_search_console.py`, `claude.py`, `gemini.py`).

### 1.3 Models and relationships (`app/models.py`, 36 tables)
- Root object is `Project` (`id`, `name`, `base_url`, `project_type`, `created_at`, `default_max_crawl_pages`). It has no owner column of any kind.
- Directly keyed on `projects.id` (FK, not null): BusinessProfile (unique), Page, CrawlSnapshot, Issue, Suggestion, SuggestionRevision, WordPressConnection (unique), BacklinkSnapshot, BacklinkRecord, OnPageTask, PageLink, VisibilityCheck, Job, Schedule, Competitor, CompetitorSnapshot, CompetitorAnalysisRun, GoogleConnection (unique), LlmMentionSnapshot, ContentOptimizationRun, SuggestionOptimization.
- Reached through a parent: PageUnderstanding (page), CompetitorPageSnapshot and CompetitorGap (analysis run), TrackedKeyword/SavedKeyword (workspace), KeywordSnapshot (tracked keyword), SearchConsoleProperty (Google connection).
- **Ownership gaps** (cannot be scoped by project today):

| Table | Issue | Stage 1 handling needed |
|---|---|---|
| `keyword_workspaces` | `project_id` is **nullable**; workspaces can exist with no project | Needs `agency_id` or a decision on orphan workspaces |
| `semrush_onpage_snapshots` | Keyed on a Semrush project id, not a local `Project` | Decide: global cache or agency-scoped |
| `provider_settings`, `crawler_settings`, `site_audit_settings` | Global, singleton-style settings | Decide: platform-wide (admin) or per agency |
| `app_logs` | Global application log, readable from `/settings/logs.txt` | Admin-only; may contain customer URLs |

### 1.4 Database access locations
- Routes use `Depends(get_db)` (`app/database.py`). Direct `SessionLocal()` use outside request scope: `scheduler.py` (6 places), `jobs/runner.py`, `backlinks_provider.py`, `routes/settings.py:41`, `routes/wordpress.py:549` (background deploy task).
- Every one of these would need the agency/project scoping rule, since background code has no request identity.
- `main.py` still calls `Base.metadata.create_all(bind=engine)` at import. This conflicts with RULES §2 (Alembic only). Not changed in Sprint 0; recorded as an open item.
- `DATABASE_URL` is environment-driven. The fallback is `sqlite:///seo_automation.db`.

### 1.5 Existing authentication and authorization
- None. No password hashing, user model, session, cookie, token check, role or ownership check in `app/`.
- Every route is reachable by anyone who can reach the host. This includes state-changing and cost-incurring routes (crawl, audit, `delete`, deploy, rollback, schedule run-now, provider key activation, `/settings/logs/clear`).
- Routes take integer IDs from the URL and load rows directly (`db.get(models.Project, project_id)`). There is no ownership filter anywhere, so IDOR is total today.

### 1.6 API routes (about 100) by family
| Family | Representative routes | Notes |
|---|---|---|
| Projects | `GET /`, `POST /projects`, `GET /projects/{id}`, `POST /projects/{id}/delete`, business profile, crawl settings, backlinks, pages | Project delete is an unauthenticated POST |
| Crawl / audit | `POST /projects/{id}/crawl`, `/crawl-single`, `/audit`, `/pages/{pid}/reaudit`, `POST /api/validate-rule` | Cost and CPU heavy |
| Suggestions | `/projects/{id}/pages/{pid}/issues/{iid}/suggest`, `/api/suggest`, `/api/suggestions/manual`, `/suggestions/{id}/accept|reject|edit` | Suggestion routes take a bare `suggestion_id` with no project in the path |
| WordPress | connect, test, resolve, `/suggestions/{id}/deploy`, `/revisions/{id}/verify|rollback`, `/downloads/ai-seo-connector` | Deploy and rollback write to customer sites. `/revisions/{id}` has no project in the path |
| Keywords | `/keywords/...` (workspace-id based, ~20 routes) | Not under `/projects/`, so cannot be scoped by path prefix |
| Competitors, optimizer, links, visibility, security, onpage_semrush | `/projects/{id}/...` | Project-scoped paths; global listing pages `/security`, `/visibility`, `/onpage-semrush` list **every** project |
| Search Console | `/projects/{id}/gsc`, `/connect`, `/properties/{id}/select`, `/disconnect`, `/gsc/callback` | Callback has no project in the path; project travels in a Fernet-signed `state` (10 min TTL), because there is no session. Properties are selected by bare `property_id` |
| Settings | `/settings`, provider activation, `/settings/logs.txt`, `/settings/logs/clear`, crawler toggle | Global; must become admin-only |
| Health | `GET /version` | Public, unauthenticated, returns commit + schema report |

### 1.7 Background jobs and scheduler
- `app/jobs/registry.py` maps six job types: `crawl`, `rank_check`, `keyword_refresh`, `backlink_pull`, `audit`, `verify_deploy`. Each runs in its own subprocess (`jobs/runner.py`) so a hung crawl can be killed.
- `app/scheduler.py`: APScheduler `BackgroundScheduler` (thread-based), started in the FastAPI lifespan. Jobs: `dispatch_due_schedules` (60 s), crawl lane and light lane workers (10 s each), two reconcilers. All use `max_instances=1, coalesce=True`.
- **Scheduler ownership:** it starts inside every app process. With one uvicorn process this is correct. With multiple workers or containers the scheduler would be duplicated. The Dockerfile starts a single uvicorn process, so today this holds. It must stay a single process, or the scheduler must move out, before scaling (plan task S6-03).
- Jobs and schedules carry `project_id`. Agency ownership will follow once `projects.agency_id` exists.

### 1.8 Customer/project ownership fields
- None above `Project`. After S2-02, `projects.agency_id` becomes the single root. Every table in 1.3 inherits from it. The gaps in the 1.3 table must be resolved first.

### 1.9 Deployment and environment
- **Runtime:** Docker (`python:3.12-slim`, Playwright Chromium), single uvicorn process on port 8000, published as port 80 in `docker-compose.yml`.
- **Deploy:** `.github/workflows/deploy.yml`, manual (`workflow_dispatch`), tests gate the deploy, SSM command to the EC2 host `/opt/seo-automation`, builds image, stops app, runs every `migrations/*.py`, brings app up, then smoke tests and auto-rolls back to the previous image.
- **Backup:** `backup-db.yml` takes a daily snapshot of the **SQLite** file over an SSM tunnel and keeps 14.
- **Tests:** `test.yml` runs pytest on pull requests. `.githooks/pre-push` exists.
- **No TLS, proxy or host config exists in this repo.** No nginx or Caddy file, no `X-Forwarded-*` handling, and no hostnames appear in code. Production TLS is outside the repo, so its owner and renewal process are unknown (S0-04 asks for this).
- Production data is still SQLite. The deploy workflow does not run Alembic and does not write `DATABASE_URL` into `.env`.

### 1.10 Existing production functionality
Crawl and page audit; issue detection and classification; AI fix suggestions (Claude/Gemini) with accept/reject/edit; WordPress auto-deploy, verify and rollback via the companion plugin; keyword research, tracking and rank checks (Semrush with DataForSEO fallback); backlinks; Semrush on-page; competitor analysis and gap analysis; content optimizer; AI visibility and LLM mentions; security report; Google Search Console connect and property selection; scheduled jobs.

---

## 2. S0-02 Existing functionality baseline

### 2.1 Working workflows
1. Create project → business profile → crawl → pages and issues.
2. Audit and re-audit a page.
3. Generate, edit, accept or reject a suggestion.
4. Connect WordPress → deploy suggestion → verify → rollback.
5. Keyword workspace → track keyword → scheduled rank check.
6. Backlink pull; Semrush on-page site audit.
7. Competitors → analysis → gap analysis → draft action.
8. Content optimizer run.
9. AI visibility check and LLM mentions.
10. GSC connect → callback → select property.
11. Schedules → jobs → worker lanes.

### 2.2 Customer-facing screens and admin capabilities
- Every screen is currently open to anyone. There is no customer/admin distinction.
- The closest thing to admin is `/settings` (provider keys, crawler toggle, logs). It must become admin-only.

### 2.3 Regression coverage
- 1241 passing tests across ~55 files in `tests/`. Covered areas include suggestions, optimizer, competitor gap, GSC routes and UI, WordPress, jobs and auto-recheck, keyword provider and scoring, schema check, redact, and the sidebar.
- **Not covered:** authentication, hostnames, CSRF, tenant isolation (none of it exists yet). No test crawls a real site end to end.
- `tests/conftest.py` sets `APP_LOG_TO_DB=0` so tests never write to the real app database.
- Tests run against whatever `DATABASE_URL` is set in `.env` (the shared local Postgres). Tests that write rows share state with development data. Recorded as a risk, not changed.

### 2.4 Database
- Schema = Alembic baseline `e9d001b85a1c`, 36 tables; relationships in 1.3.
- Local drift check (`schema_check.find_schema_drift()`) returned `{}` in session 01.

---

## 3. S0-03 Development environment

| Check | Result |
|---|---|
| Local app starts | Yes, `uvicorn app.main:app --reload` (README line 96) |
| Local DB | Docker Postgres 16 (`seofixai-postgres-1` up); `DATABASE_URL` in gitignored `.env` |
| Runs without production credentials | Yes for boot and tests; provider features show "not configured" |
| Dev/prod secrets separated | Partly. `.env` is gitignored; production `.env` is generated by `deploy.yml` from GitHub secrets |

### 3.1 Environment variables (as read by code)
| Variable | Used by | In `.env.example`? |
|---|---|---|
| `DATABASE_URL` | `database.py` | yes |
| `POSTGRES_DB/USER/PASSWORD` | docker-compose | yes |
| `ANTHROPIC_API_KEY` | `claude.py`, settings | yes |
| `GEMENI_KEY` (sic, misspelled) | `gemini.py`, `routes/settings.py` | **no** |
| `SEMRUSH_API_KEY` | `semrush.py`, `semrush_audit.py` | yes |
| `DATAFORSEO_LOGIN/PASSWORD` | `dataforseo*.py` | yes |
| `WP_TOKEN_KEY` | `wordpress.py` | yes |
| `GOOGLE_OAUTH_CLIENT_ID/SECRET/REDIRECT_URI` | `google_search_console.py` | yes |
| `GSC_TOKEN_KEY` | `google_search_console.py` | yes |
| `APP_COMMIT` | `build_info.py` | no (set by deploy) |
| `APP_LOG_TO_DB` | `logging_setup.py` | no |
| `SUPABASE_URL/KEY` | `supabase_client.py` (no callers) | yes |
| `APP_URL` (GitHub repo variable, not app env) | `deploy.yml` smoke tests | n/a |

Variables the plan requires and that do not exist yet: `PUBLIC_APP_ORIGIN`, `ADMIN_APP_ORIGIN`, `ENVIRONMENT`, plus session and CSRF secrets and the registration flag.

---

## 4. Findings that affect Stage 1 (ranked)

1. **Every route is unauthenticated and unscoped.** Security rests entirely on the future guards. Until Sprint 1 ships, the plan's compatibility policy (D-009/D-010: legacy host open) means production stays exposed as it is today.
2. **`/version` conflicts with the deploy pipeline.** D-009 makes `/version` internal-only. `deploy.yml` polls `${APP_URL}/version` and smoke-tests `/ /settings /docs /version` from a GitHub runner on the public internet. Making `/version` internal-only will break deploys and trigger automatic rollbacks unless the pipeline is changed first (internal check over SSM, or a token header). Needs a decision in S0-04.
3. **Smoke-tested paths `/settings` and `/docs` will become protected** once auth exists; the smoke test must be updated to expect 401/302 or to use the public health route.
4. **GSC redirect URI is fixed at Google.** `GOOGLE_OAUTH_REDIRECT_URI` must be registered for `https://app.seofixai.com/gsc/callback` before the move, and the legacy URI kept during the compatibility period. The OAuth state is signed but has no session binding (S2-03 requires session/state validation).
5. **Global settings and logs** (`provider_settings`, `app_logs`, `/settings/*`) are not agency data and need an admin-only home.
6. **Keyword workspaces can be project-less**, and Semrush on-page snapshots are keyed on Semrush IDs. Both need an explicit ownership rule.
7. **`create_all()` at startup** bypasses Alembic. Needs a separate controlled change.
8. **Production is still SQLite and the deploy path runs legacy `migrations/*.py`, not Alembic.** The release rule (D-004) means the Postgres cutover happens first and separately.
9. **Single-process assumption** for the in-process scheduler (see 1.7).
10. **Env var typo** `GEMENI_KEY` is undocumented; renaming would be a behavior change, so it is only recorded.
11. **Cookie scope:** the legacy apex and the new `app.` host are different cookie hosts. Existing apex sessions will not carry over (no sessions exist today, so no one is logged out; relevant only after Sprint 1).

## 5. Plan inconsistencies to fix in the plan document
- Task IDs repeat: Sprint 5 uses `S4-xx`, Sprint 6 uses `S5-xx`, Sprint 7 uses `S6-xx`; the later stage is labelled `S3`.
- "Organization" is used in later sections while Stage 1 uses "Agency".
- S0-05 platform roles (`platform_admin`, `support_admin`, `customer`) vs S1-01 roles (`agency_owner`, `agency_user`, `platform_admin`) need one reconciled table.
- Hostnames in the plan say `seofix.ai`; D-010 says `seofixai.com`.
- The sprint table calls Sprint 3 "Production launch", while §15 says Sprint 3 is multi-tenant identity.

## 6. Sprint 0 checklist status
| Task | Status |
|---|---|
| S0-01 audit | Done (this document) |
| S0-02 baseline | Done for listing and baseline run; regression tests for auth/hostname are written in S0-04 |
| S0-03 dev environment | Mostly done; `.env.example` needs `GEMENI_KEY`, `APP_LOG_TO_DB`, and the three hostname variables (added in S0-04) |
| S0-04 hostname contract | Next |
| S0-05 threat model | After S0-04 |
