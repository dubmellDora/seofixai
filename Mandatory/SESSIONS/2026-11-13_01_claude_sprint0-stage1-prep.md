# Session 01 (2026-11-13) — Sprint 0 prep for Stage 1 (agency-first MVP)

- **Date/time:** 2026-11-13
- **Tool / model:** claude (Claude Code), claude-sonnet-5-5
- **Branch / commit base:** sprint-1/database-multitenant-foundation (not modified)
- **User goal:** "review the usermanagement.md file and get ready to implement stage 1 rules sprint 0."

## Context read at start
Mandatory/README.md, RULES.md, IMPLEMENTATION_STATE.md, DECISIONS.md, sessions 02 (claude, 11-12), 04 (codex), 01 (codex), tail of HISTORY_LOGS.md, docs/User_ManagementSAAS.md (agency-first revision), seofixai/CLAUDE.md.

## Actions log
1. Read all mandatory files and the full plan. Read-only; no code changed.
2. Created this session file.
3. User approved S0-04 defaults (apex -> app.seofix.ai; old hostname keeps working without auth until Sprint 1; /health public, /version internal-only). Recorded as D-009.
4. Baseline: `.venv/Scripts/python.exe -m pytest -q -x -p no:cacheprovider` with .env DATABASE_URL -> local Docker Postgres (container seofixai-postgres-1 up).

## Files changed
| Path | Change | Summary |
|---|---|---|
| Mandatory/SESSIONS/2026-11-13_01_claude_sprint0-stage1-prep.md | add | This file |
| Mandatory/DECISIONS.md | edit (append) | D-009 |

## Commands run that changed state
None.

## Verification
Baseline test run before any change: 1241 passed, 1 warning (google.genai DeprecationWarning), 54s.

## Decisions
D-009 (S0-04 defaults), copied to DECISIONS.md.

## Open items / handoff
See the readiness summary given to the user (Sprint 0 scope S0-01..S0-05, open questions on hostnames, apex behavior, compat period).

## Addendum — domains
User gave production host https://seofixai.com/ moving to app/admin subdomains, marketing on a separate site. Clarified via questions: family seofixai.com, marketing on apex. Recorded as D-010 (supersedes D-009 item 1). Open: apex cutover plan (legacy app -> marketing), plan doc still says seofix.ai.

## Addendum — Sprint 0 audit written
- Read-only inspection of app/main.py, routes (route decorators grep), models.py (class/FK grep), scheduler.py, jobs/registry.py, database.py, search_console routes, .env.example, Dockerfile, docker-compose.yml, .github/workflows (deploy, backup-db, test), tests/conftest.py.
- Wrote `docs/Sprint0_Audit.md` (S0-01, S0-02, S0-03). User instruction: audits always go in docs/.
- Key findings: all routes unauthenticated/unscoped; deploy.yml polls public /version and smoke-tests / /settings /docs /version (conflicts with D-009 /version internal-only); keyword_workspaces.project_id nullable; global settings/app_logs need admin-only home; create_all() at startup; prod still SQLite with legacy migrations in deploy; GEMENI_KEY undocumented; plan task-ID/terminology inconsistencies.
- Files changed: docs/Sprint0_Audit.md (add), Mandatory/HISTORY_LOGS.md (append). No code changed; no tests re-run (docs only).
- Open: decide how deploy health check works once /version is internal-only (S0-04); update plan doc hostnames/IDs; next = S0-04 hostname matrix + S0-05 threat model docs.

## Addendum — teaching mode
- User said they need to learn to code: wants tasks, code, architecture, why and how; user writes the code, Claude reviews.
- Created `docs/learning/Lesson_01_Host_Routing.md` (S0-04 host classifier, middleware, tests, env docs). No app code written by Claude. Tests not run (docs only).

## 2026-11-14 - Lesson 1 format change
- User corrected the lesson format: Claude writes the code slowly and explains each piece (not "user writes, Claude reviews"). Memory updated.
- Created app/host_routing.py with only the HostKind enum (PUBLIC, ADMIN, LEGACY, UNKNOWN). Reason: first small teaching step of S0-04; no behaviour change, nothing imports it yet.

## 2026-11-14 - S0-04 step 2
- Added normalize_host() to app/host_routing.py (lowercase, strip port, strip trailing dot, IPv6-aware, empty->""). Taught to user; user answered check question (said 404, corrected: UNKNOWN -> 421; 404 is for wrong path on known host).

## 2026-11-14 - Performance audit
- Wrote docs/Performance_Audit.md (static read, no profiling). Findings P1-P10; recommended split: baseline timing + tenant-column indexes + pagination rule + pool settings inside Stage 1; frontend assets, caching, async/job moves, scheduler split deferred to a later performance pass.

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
