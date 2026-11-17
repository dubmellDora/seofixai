# Session 03 — Relocate Mandatory/ into seofixai/, explain auth terms

- **Date:** 2026-11-12 · **Tool:** claude (claude-sonnet-5-5) · **Branch:** none created or committed
- **User goal:** (a) user moved `Mandatory/` into `seofixai/`; (b) asked what Alembic, Argon2, session cookies and require_user/require_admin are.

## Actions
1. Verified `seofixai/Mandatory/` exists; root `HISTORY_LOGS.md` was still at the workspace root.
2. Moved `HISTORY_LOGS.md` (plain `mv`, content untouched) to `seofixai/Mandatory/HISTORY_LOGS.md`, so tools started in `seofixai/` can write it.
3. Rewrote paths in live docs via `sed`: `seofixai/AGENTS.md`, `seofixai/CLAUDE.md` (`../Mandatory/` -> `Mandatory/`, `../HISTORY_LOGS.md` -> `Mandatory/HISTORY_LOGS.md`); root `AGENTS.md`, `CLAUDE.md` (`Mandatory/` -> `seofixai/Mandatory/`); `Mandatory/README.md`, `RULES.md`, `SESSIONS/_TEMPLATE.md`, `IMPLEMENTATION_STATE.md` (layout block).
4. Added D-008. Left sessions 01/02 untouched (historical wording, e.g. "outside the git repo", is now superseded by D-008).
5. Explained the four auth terms to the user (no code).

## Files changed
`HISTORY_LOGS.md` (moved), the files listed in action 3, `DECISIONS.md` (D-008 appended), this file (new).

## Verification
Grep of the four entry files shows consistent paths. No code touched, tests not run.

## Open items
Uncommitted in the seofixai repo: `Mandatory/`, `AGENTS.md`, `CLAUDE.md` edit. Commit only when the user asks. Next slice: auth foundation (users table via Alembic, Argon2, session cookies, require_user/require_admin) — awaiting user go-ahead.
