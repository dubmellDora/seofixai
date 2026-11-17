# Session 01 — S1-02 passwords, admin bootstrap, last login

- **Date/time:** 2026-11-16 (local)
- **Tool / model:** claude, claude-sonnet-5-5
- **Branch / commit base:** current working branch (nothing committed; user chose to skip commit)
- **User goal:** "Skip the commit and start S1-02 straight away." (routing of seofixai.com -> app./admin. is being done by another department)

## Context read at start
Mandatory/README.md, RULES.md, SaaS_Master_Plan.md S1-02 section, app/models.py (Agency/User), app/services/accounts.py, alembic a1c5e0b7d301, tests/test_accounts.py, prior session 2026-11-15_01.

## Actions log (chronological)
- Found S1-01 schema already satisfies most S1-02 criteria (UUID id, unique lowercase email, display_name, is_active, email_verified_at, last_login_at, timestamps, platform_role default customer, role CHECKs). No new migration expected.
- Remaining work: Argon2 hashing service, dev-only admin bootstrap, last-login recording, tests.

## Files changed
(appended below as work proceeds)

## Decisions
(appended below)

## Open items / handoff

## Files changed
| Path | Change | Summary |
|---|---|---|
| app/services/passwords.py | add | Argon2id hash/verify/needs_rehash via argon2-cffi 25.1.0; length 10-256; dummy hash keeps unknown-email timing equal |
| app/services/accounts.py | edit | added authenticate() (generic None on any failure, sets last_login_at, rehashes weak hashes) and create_platform_staff() (needs ALLOW_ADMIN_BOOTSTRAP=1 and APP_ENV != production; no route calls it) |
| scripts/bootstrap_admin.py | add | CLI: email + name args, password from hidden getpass prompt |
| tests/test_passwords_auth.py | add | 21 tests (hashing, login, deactivated, last login, rehash, duplicate email case, bootstrap guards, A11, no route reaches bootstrap) |
| requirements.txt | edit | + argon2-cffi |
| .env.example | edit | documented ALLOW_ADMIN_BOOTSTRAP, APP_ENV |

## Commands run that changed state
.venv/Scripts/python.exe -m pip install argon2-cffi (25.1.0). No migration: S1-01 schema already had every S1-02 column/constraint.

## Verification
pytest tests/test_passwords_auth.py tests/test_accounts.py: 44 passed. Full suite: 1356 passed (1335 + 21).

## Decisions
- No new Alembic migration for S1-02 (schema already complete).
- Bootstrap guard lives inside the service function (env flags), not only in the script, so importing it from a route still fails by default.
- authenticate() ignores agency suspension; the 403 "account suspended" belongs to the S1-04 auth dependency.

## Open items / handoff
- Not run on Postgres (Docker down). Nothing committed (user choice).
- Acceptance item "document indexes in the migration": already done in a1c5e0b7d301 docstring.
- Next: S1-03 secure session lifecycle (server-side sessions, CSRF, rate limiting).

## S1-03a addendum (same session, user asked for teaching mode)
- Files: app/models.py (+UserSession), app/services/sessions.py (new), alembic/versions/b2d6f1c8e402_add_user_sessions.py (new, revises a1c5e0b7d301), tests/test_sessions.py (new, 16 tests).
- Design: DB-backed sessions; cookie holds random 256-bit token, only sha256 stored; per-session csrf_token column (used in 3c); host_kind app|admin so a cookie from one host is useless on the other. Lifetimes: app 14d absolute / 24h idle; admin 8h absolute / 30min idle. last_seen touched at most once a minute. rotate_session, revoke_session, revoke_all_for_user, delete_expired (cleanup job to be scheduled later).
- Verification: migration upgrade/check/downgrade OK on throwaway SQLite; full suite 1372 passed.
- Decision: lifetime numbers are proposals, easy to change in LIFETIMES. Nothing committed. Shell choked on long heredocs again, files created with Write tool.
- Next: 3b cookie helpers, 3c CSRF, 3d rate limit, 3e remaining tests.

## S1-03b addendum (cookie helpers)
- Files: app/services/session_cookies.py (new), tests/test_session_cookies.py (new, 16 tests), .env.example (COOKIE_SECURE).
- Cookie: name __Host-sfx_app / __Host-sfx_admin (plain sfx_* when COOKIE_SECURE=0), HttpOnly, Path=/, no Domain (host-only), Secure default ON (only 0/false/no/off disables), SameSite Lax for app and Strict for admin, Max-Age = absolute session lifetime. set/clear/read helpers; session_kind_for(HostKind) maps PUBLIC/LEGACY->app, ADMIN->admin, UNKNOWN raises.
- Decisions: Secure is deny-by-default (opposite polarity from the admin bootstrap flag, on purpose: forgetting config must be safe). Admin SameSite=Strict because admins have no need to arrive via cross-site links. No route uses the helpers yet (S1-05 wires login).
- Verification: 16 new tests pass; full suite result below in HISTORY_LOGS.

## IT routing result check (read-only, 2026-11-16)
- User reported IT finished routing. GET https://{app.,admin.,}seofixai.com/ all return 200 with the app's own "Projects - SeoFixAI" page, served via Cloudflare (server: cloudflare). All three resolve to the same Cloudflare IPv6 address.
- /health returns 404 on all three: the deployed code predates /health (it exists only in the uncommitted/undeployed branch). /admin returns 404 everywhere (no such route in old code, so NOT proof the host guard works).
- Finding: /settings, /docs and /openapi.json return 200 on admin.seofixai.com with no login. Pre-existing (no auth exists yet) but now reachable on three hostnames. Reported to user; no code changed.
- Open: confirm with IT what sits behind Cloudflare (origin, TLS mode Full(strict)?), and whether Cloudflare Access can gate admin. host guard HOST_ENFORCEMENT not active on live.

## S1-03c/3d addendum (CSRF rule + login throttling)
- Files: app/services/csrf.py (new; csrf_ok(): safe methods pass, else session csrf_token must match header X-CSRF-Token or form field csrf_token via hmac.compare_digest, plus Origin must be one of our hosts when present), tests/test_csrf.py (17), app/models.py (+LoginAttempt), app/services/rate_limit.py (new; 5 failures/email or 20/IP per 15 min; email stored as sha256), alembic/versions/c3e7a2d9f503_add_login_attempts.py (new, revises b2d6f1c8e402), tests/test_rate_limit.py (9).
- Verification: migration up/check/down OK on throwaway SQLite; full suite 1414 passed.
- User instruction mid-turn: "no need to do so many security build in, they want fast less secure version" (goal: a UI to validate before pushing to AWS). Decision: STOP adding new hardening pieces. Build the minimal login/guard/UI path next on top of what exists. Keep already-built free protections (Argon2, HttpOnly cookie, server-side sessions). CSRF enforcement and rate-limit wiring will sit behind env flags that default OFF for local validation. RULES.md section 3 (CSRF, secure sessions) still binds production: flags must be ON before any deploy to AWS. Recorded so it is not forgotten.

## Owner decision D-018 (2026-11-16)
- User: "keep in the document but we dont need CSRF protection and secure sessions and rate limit on this application". Recorded as D-018 in DECISIONS.md (supersedes RULES.md section 3 for those items only). docs/SaaS_Master_Plan.md S1-03 marked DEFERRED (note added under the heading; criteria untouched). RULES.md itself NOT edited. Replaces my earlier "env flags default off" idea: nothing will be wired, so no flags are needed. Code already written stays in the repo, unwired.

## Incident: plan file encoding damage, repaired (2026-11-16)
- My PowerShell edit of docs/SaaS_Master_Plan.md read it with the wrong encoding and rewrote it, turning 61 non-ASCII characters (em dashes etc.) into mojibake ("â€”"). The intended replace also did not match. Repaired by reversing the exact conversion (UTF-8 text -> cp1252 bytes -> UTF-8): 0 mojibake and 0 replacement characters remain; file written as UTF-8 without BOM. Backup of the damaged version kept in the scratchpad (plan_damaged_backup.md). The DEFERRED note was then added with the Edit tool. Lesson: use the Edit tool for existing text files, not Get-Content/Set-Content.

## S1-04 / S1-05 (minimal) / S1-06 local verification (same session)
- Files added: app/auth.py (AuthUser, guard_decision, install_auth_guard middleware, require_user, require_platform_admin, safe_next, AUTH_ENFORCEMENT and REGISTRATION_ENABLED switches), app/routes/auth.py (GET/POST /login, POST /logout, GET/POST /register, GET /admin), app/templates/auth/{layout,login,register,admin_home}.html, tests/test_auth_flow.py (31 tests).
- Files edited: app/main.py (install_auth_guard BEFORE install_host_guard so the host guard is outermost; include auth router), app/host_routing.py (ALWAYS_ALLOWED_PATHS += /login, /logout; admin host "/" redirects to /admin when the guard is enforcing), app/templates/partials/sidebar.html (signed-in user + Log out button, guarded with "request is defined and request.state is defined" because tests/test_sidebar.py renders it with a fake request), .env.example (documented flags + local two-host run).
- Bugs found by driving the REAL app with curl on a scratch DB (not by the unit tests), then fixed and covered by new tests: (a) /login was blocked on the admin host by the host guard -> staff could not sign in; (b) auth guard ran before the host guard so unknown hosts got a login redirect instead of 421 and /admin on the app host redirected instead of 404; (c) admin host "/" gave a bare 404. Also my first sidebar edit broke 50 existing tests (fake request without .state); fixed by the guard above.
- Verification: full suite 1446 passed. Live check on scratch SQLite (never the real db): anon redirect, HTMX/API 401 (tests), customer login/logout, staff login on admin host, wrong portal -> generic 401, staff cookie useless on app host, unknown host 421, //evil.com next ignored (tested; Git Bash rewrites // in curl args), smuggled platform_role ignored at signup. Local server left running on port 8765 for the user to click through (scratch db in scratchpad; test accounts only).
- Scratch accounts (local only, not real): boss@vtechys.test / owner@acme.test with throwaway passwords stated in chat.
- NOT done in S1: password reset flow (forgot/reset), audit events, Postgres run of migrations, Alembic head currently c3e7a2d9f503. S1-03 hardening deferred by D-018.
