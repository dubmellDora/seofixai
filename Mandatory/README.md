# MANDATORY — read this before touching anything

This folder is the single source of truth for every coding tool (Claude Code, Codex, Cursor, Copilot, Gemini, humans) working in this repo. Tool-specific entry files (`CLAUDE.md`, `AGENTS.md`) only point here.

## Read order (every session, no exceptions)

1. `RULES.md` — guardrails and the logging obligation. Binding.
2. `IMPLEMENTATION_STATE.md` — what exists right now (stack, layout, how to run, what is done / not done).
3. `DECISIONS.md` — why things are the way they are. Do not re-litigate without adding a new entry.
4. `SESSIONS/` — newest 2–3 files, to see what the previous chats did and left unfinished.
5. `docs/SaaS_Master_Plan.md` — the SaaS sprint plan being executed.
6. `CLAUDE.md` (repo root of seofixai) — engineering conventions of the app code itself.

## Layout

| Path | Purpose | Edit rule |
|---|---|---|
| `RULES.md` | Guardrails / harness | Change only with explicit user approval |
| `IMPLEMENTATION_STATE.md` | Living snapshot of current implementation | Update in place when reality changes |
| `DECISIONS.md` | Numbered decision records (ADR-style) | Append-only |
| `SESSIONS/` | One file per chat session | Create at session start, append during, never rewrite old sessions |
| `SESSIONS/_TEMPLATE.md` | Copy this for a new session | — |
| `HISTORY_LOGS.md` (in this folder) | Global chronological change log (pre-existing) | Append-only |

## Start-of-session checklist

1. Read the files above.
2. Copy `SESSIONS/_TEMPLATE.md` to `SESSIONS/YYYY-MM-DD_NN_<tool>_<topic>.md` (NN = next number that day, tool = claude / codex / cursor / human ...).
3. Fill the header immediately, before doing work.

## End-of-session checklist

1. Session file complete: files changed, commands run, verification, decisions, open items.
2. New decisions copied into `DECISIONS.md`.
3. One summary entry appended to `HISTORY_LOGS.md` (in this folder).
4. `IMPLEMENTATION_STATE.md` updated if anything it describes changed.
