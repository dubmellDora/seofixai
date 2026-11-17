# AGENTS.md

**STOP. Before reading or changing any file, read `Mandatory/README.md` and follow it.**

The `Mandatory/` folder holds the rules, current implementation state, decision records and per-session logs for every AI coding tool and human working here. It is version-controlled in this repo. If it is missing in your checkout, stop and ask the user.

Non-negotiable summary (full text in `Mandatory/RULES.md`):

1. Read `Mandatory/README.md`, `RULES.md`, `IMPLEMENTATION_STATE.md`, `DECISIONS.md`, and the newest files in `Mandatory/SESSIONS/` first.
2. Create your own session file in `Mandatory/SESSIONS/` before doing work; log every change, command and decision in it as you go.
3. Before finishing, append a summary to `Mandatory/HISTORY_LOGS.md`. Logs are append-only.
4. Do not break live functionality. Alembic only for schema changes. Server-side authorization. No secrets committed or logged.
5. Small verified steps. Ask before destructive, production or paid-infrastructure actions.

App conventions: `CLAUDE.md` in this folder. SaaS plan: `docs/SaaS_Master_Plan.md`.
