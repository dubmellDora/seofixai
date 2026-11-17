# RULES — guardrails for all coding tools

Binding on every tool and human. If a user instruction conflicts with a rule here, say so and ask; do not silently break the rule.

## 1. Logging (mandatory)

- Every session has its own file in `SESSIONS/`, created at the start (see `README.md`).
- Every code change, file add/remove/rename, config change, command that changed state (migrations, installs, docker, data copies) and every decision is recorded in that session file as it happens, not reconstructed afterwards.
- Every session also appends a summary to `HISTORY_LOGS.md` (in this folder) before finishing. Entry fields: date/time, files changed (paths), changes made, decisions and why.
- Logs are append-only. Never delete or rewrite earlier entries or earlier session files. Corrections are new entries that reference the old one.
- Detail level: someone with only the logs and the base repo must be able to reproduce the change. Name exact files, functions, columns, commands, versions.
- Never put secrets, tokens, passwords or customer data in logs.

## 2. Do-not-break guardrails

- Live customer functionality must keep working. Run `python -m pytest -q` (from `seofixai/`, venv active) before and after non-trivial changes and report real results. If tests fail, say so; do not hide or skip them.
- Schema changes go through Alembic only (`seofixai/alembic/`). The legacy `seofixai/migrations/NNN_*.py` scripts are frozen history. Migrations must be additive and defensive: defaults keep existing rows behaving as before.
- **Release rule:** the production SQLite→PostgreSQL migration and the multi-tenant schema migration are separate releases. Do not combine them.
- Every production database change needs a backup and a rollback plan first.
- Database config is environment-driven (`DATABASE_URL`). No code may depend on EC2-hosted Postgres vs RDS.
- No staging environment exists. Treat anything that touches production as high risk: confirm with the user first.

## 3. Security guardrails

- Authorization is enforced server-side. URL separation (`/admin/...`) is never the control.
- Deny by default. Customer data is isolated by organization on the backend; never trust IDs from the client.
- Passwords: Argon2, never plaintext, never logged. Reset tokens: expiring, single-use. Responses must not reveal whether an account exists.
- Sessions: HTTP-only cookies, secure flags in production, CSRF protection. No credentials in localStorage.
- Admin privilege can never be granted through public registration.
- Never commit `.env`, API keys, production credentials or the `.db` file with real data. Only `.env.example` carries placeholders.
- Never log passwords, tokens or provider keys (see `seofixai/app/redact.py`).

## 4. Code conventions

Follow `CLAUDE.md` (repo root of seofixai). In particular: thin routes, logic in `app/services/`, one adapter module per external provider, ok / no_data / error outcomes, jobs never raise, regression test for every bug fix.

## 5. Scope and safety of actions

- Work incrementally: one small, verified step at a time. The user has asked to go slowly.
- Ask before destructive or outward-facing actions (deleting data, force-pushing, deploying, touching AWS, sending email, publishing).
- Do not provision paid infrastructure (e.g. RDS) without explicit approval.
- Do not make changes beyond the task asked; record out-of-scope findings under "Open items" in the session file instead.
- Work on a feature branch inside `seofixai/` (its own git repo); never commit straight to `main`. Commit only when the user asks.

## 6. Definition of done

Acceptance criteria verified; relevant tests pass; existing functionality not broken; migrations included if schema changed; config documented (`.env.example`); no secrets committed; demo/test procedure documented; session file and `HISTORY_LOGS.md` updated.
