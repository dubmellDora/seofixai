# IMPLEMENTATION STATE — living snapshot

Last verified: 2026-11-12 (session 02, by static inspection; DB facts from session 01 verification). Update in place whenever reality changes, and note the date.

## Workspace layout

```
VtechysSEO-Automation/            (not a git repo)
  CLAUDE.md, AGENTS.md            tool entry points -> seofixai/Mandatory/
  Release Notes/
  ai-seo-connector/               WordPress plugin (PHP); separate repo upstream (dubmellDora/ai-seo-connector)
  seofixai/                       the app; its own git repo (.git, .githooks, .github)
    Mandatory/                    this folder (rules, state, decisions, SESSIONS/, HISTORY_LOGS.md)
```

## Application (seofixai/)

- **Stack:** FastAPI, SQLAlchemy, Jinja2 templates + HTMX + Tailwind (both loaded from CDN in `app/templates/base.html`), APScheduler, crawl4ai/Playwright, Alembic. Python 3.10–3.12.
- **Entry:** `app/main.py`. Mounts 15 routers (projects, crawl, audit, suggestions, keywords, jobs, wordpress, onpage_semrush, settings, security, visibility, competitors, optimizer, links, search_console). No router has an auth dependency.
- **Layers:** `app/routes/` thin handlers → `app/services/` logic → top-level adapters (`semrush.py`, `dataforseo.py`, `wordpress.py`, `google_search_console.py`, `claude.py`, `gemini.py`).
- **Jobs:** `app/jobs/` (registry, runner = one subprocess per job, handlers/). `app/scheduler.py` queues due `Schedule` rows into `Job` rows across worker lanes.
- **UI:** server-rendered pages in `app/templates/` (index, project_detail, page_detail, keyword_*, links, optimizer, competitors, visibility_*, security_*, settings*, onpage/, partials/). No frontend build step, no `frontend/` dir.
- **Models:** `app/models.py`, 36 tables, root object is `Project`. Others: BusinessProfile, Page, CrawlSnapshot, Issue, Suggestion, KeywordWorkspace/TrackedKeyword/KeywordSnapshot/SavedKeyword, WordPressConnection, SuggestionRevision, Backlink*, SemrushOnPageSnapshot, OnPageTask, PageLink, CrawlerSettings, SiteAuditSettings, ProviderSetting, VisibilityCheck, Job, Schedule, PageUnderstanding, Competitor*, GoogleConnection, SearchConsoleProperty, AppLog, LlmMentionSnapshot, ContentOptimizationRun, SuggestionOptimization.
- **Auth / users / orgs / tenancy:** none exist. No password hashing, sessions, user model or org/tenant column anywhere in `app/`.

## Database

- Local dev: Postgres 16 in Docker (`docker compose up -d postgres`), `DATABASE_URL=postgresql+psycopg2://seofixai:seofixai@localhost:5432/seofixai` in the gitignored `.env`.
- Schema via Alembic, head revision `e9d001b85a1c` (baseline). Check drift with `app.schema_check.find_schema_drift()` (returned `{}`).
- `seo_automation.db` (SQLite) still present in the repo dir as the legacy source; only 1 `projects` row locally.
- Production (EC2) is still SQLite. Production cutover (DB-04) not done.

## Verified status

- `python -m pytest -q` against Postgres: 1241 passed (session 01).
- `GET /` 200 and `GET /version` schema ok against Postgres (session 01).

## SaaS plan progress (`seofixai/docs/SaaS_Master_Plan.md`)

| Item | Status |
|---|---|
| DB-01, DB-02, DB-03 | done locally |
| DB-04 EC2 Postgres, DB-05 RDS | not started |
| Sprint 0 audit | findings captured here; no standalone audit doc yet |
| Sprints 1–6 | not started; unblocked: D-007 chose Jinja2/HTMX; next slice = auth foundation |

## How to run (local)

From `seofixai/` with `.venv` active: `docker compose up -d postgres`, `alembic upgrade head`, `uvicorn app.main:app`. Tests: `python -m pytest -q` with `DATABASE_URL` set to the Docker Postgres.
