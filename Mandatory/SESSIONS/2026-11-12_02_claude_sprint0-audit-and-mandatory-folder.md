# Session 02 — Sprint 0 audit and Mandatory/ folder

- **Date:** 2026-11-12
- **Tool / model:** claude (Claude Code), claude-sonnet-5-5
- **Branch:** none touched (all changes are at the workspace root, outside the `seofixai` git repo)
- **User goal:** turn `seofixai/docs/User_ManagementSAAS.md` into a SaaS, going slowly. Then: create a Mandatory folder so every coding tool picks up rules, decisions and per-session logs.

## Context read at start
`seofixai/docs/User_ManagementSAAS.md`, root `CLAUDE.md`, `seofixai/CLAUDE.md`, tail of `HISTORY_LOGS.md`.

## Actions log
1. Read the SaaS plan in full.
2. Read-only repo audit (listing, grep, `app/main.py`, `app/models.py` class list, `templates/base.html`). Findings: Jinja2 + HTMX + Tailwind CDN UI (no React); no auth, users, orgs or tenancy anywhere; 15 unauthenticated routers; jobs as subprocesses with APScheduler. Recorded in `IMPLEMENTATION_STATE.md`.
3. Raised the frontend question to the user; recorded as D-006 (pending).
4. User asked whether work was logged and asked for the Mandatory folder. Answer given: session 01's DB work was already in HISTORY_LOGS.md; the audit changed no files.
5. Created the Mandatory/ folder and entry-point files (below).

## Files changed
| Path | Change | Summary |
|---|---|---|
| `Mandatory/README.md` | add | Read order, layout, start/end checklists |
| `Mandatory/RULES.md` | add | Logging duty, do-not-break, security, scope, definition of done |
| `Mandatory/IMPLEMENTATION_STATE.md` | add | Living snapshot of stack, layout, DB, plan progress |
| `Mandatory/DECISIONS.md` | add | D-001..D-006 |
| `Mandatory/SESSIONS/_TEMPLATE.md` | add | Per-session template |
| `Mandatory/SESSIONS/2026-11-12_01_claude_postgres-alembic-foundation.md` | add | Backfilled from HISTORY_LOGS.md |
| `Mandatory/SESSIONS/2026-11-12_02_claude_sprint0-audit-and-mandatory-folder.md` | add | This file |
| `CLAUDE.md` (root) | edit | Now points to Mandatory/; original history rule kept |
| `AGENTS.md` (root) | add | Pointer for Codex, Cursor, Copilot, Gemini and similar |
| `seofixai/AGENTS.md` | add | Same pointer, for tools launched from inside seofixai/ |
| `seofixai/CLAUDE.md` | edit | Added a pointer block at the top only |
| `HISTORY_LOGS.md` | append | Entry for this session |

## Commands run that changed state
None. Only file writes.

## Verification
No code changed; tests not run. Files checked to exist after writing.

## Decisions
D-005 (Mandatory folder), D-006 (frontend direction, pending).

## Open items / handoff
- **D-006 must be answered by the user** before any portal/auth work.
- `Mandatory/` is outside the `seofixai` git repo, so it is not version-controlled and would be missing in a standalone clone of `seofixai`. Options: make the workspace root a git repo, or move/duplicate `Mandatory/` into `seofixai/`. Needs the user's call.
- `seofixai/AGENTS.md` and the edit to `seofixai/CLAUDE.md` are inside the seofixai repo and are uncommitted; they reference `../Mandatory/`.
- Optional next: write `seofixai/docs/Sprint0_Audit.md`, then start the auth foundation slice.

## Addendum — user answered D-006
- User chose Jinja2/HTMX. Added D-007 to `DECISIONS.md`, marked D-006 resolved, updated the progress row in `IMPLEMENTATION_STATE.md`. No code changed.
- User asked how other tools will see Mandatory/. Explained discovery mechanics; flagged that `../Mandatory` is outside the seofixai git root, which can break discovery/write access for tools launched inside `seofixai/`. Recommended moving `Mandatory/` into `seofixai/`. Awaiting user decision.
