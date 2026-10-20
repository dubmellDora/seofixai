# CLAUDE.md

Engineering orientation for anyone (human or Claude Code) picking up this
repo. Read this before making non-trivial changes.

## Architecture at a glance

- `app/main.py` — FastAPI app entrypoint.
- `app/routes/` — HTTP route handlers, one module per feature area (audit,
  keywords, links, wordpress, settings, ...). Routes stay thin: they call
  into `app/services/` or the top-level provider/adapter modules, they don't
  contain business logic themselves.
- `app/services/` — feature-level business logic (action plans, competitor
  analysis, content optimization, AI visibility scoring, etc).
- Top-level adapter modules (`semrush.py`, `dataforseo.py`, `wordpress.py`,
  `google_search_console.py`, `claude.py`, `gemini.py`) — one per external
  integration. Nothing outside the adapter should know that integration's
  request/response shape.
- `app/jobs/` — the job system. `registry.py` maps a `job_type` string to its
  handler function; `runner.py` executes a single job as a subprocess (not a
  thread — Playwright-based crawls were observed to hang un-killably on a
  background thread, so every job gets a fresh process the parent can
  actually kill on timeout); `handlers/` holds one handler per job type.
  Adding a new job type is one registry entry plus a handler module.
- `app/scheduler.py` — the tick that queues due `Schedule` rows as `Job` rows
  and dispatches them across independent worker lanes (so one slow crawl job
  can't starve fast API-backed jobs queued behind it).
- `migrations/NNN_description.py` — plain, numbered, idempotent SQLite
  migrations (no ORM migration framework). Each one is a standalone script:
  `python migrations/NNN_description.py`. Read a recent one before writing a
  new one — they follow a consistent shape (docstring explaining the *why*,
  a `DEFAULT_DB_PATH`/`DB_PATH` constant, defaults chosen so existing rows
  keep their current behavior).
- `ai-seo-connector/` — the companion WordPress plugin (PHP), kept in this
  same repo. It talks to the app over a small REST tool-dispatcher API
  (`app/wordpress.py`); its own `README.md` covers the plugin side in detail.

## Conventions worth knowing before you change code

- **Provider fallback, not provider failure.** Anywhere two data providers
  exist for the same thing (Semrush/DataForSEO for keywords, for example),
  the pattern is: try the primary, fall back to the secondary on
  error/timeout/rate-limit, and only report "no data" if both genuinely have
  nothing. See `app/keyword_provider.py` for the reference implementation —
  nothing above that module is allowed to know which provider actually
  answered.
- **Three-outcome discipline: ok / no_data / error.** Functions that fetch
  external data return one of these three states explicitly (see
  `NormalizedKeyword.status` in `app/schemas.py`, and `WordPressResult` in
  `app/wordpress.py`) rather than returning `None` or an empty list for both
  "nothing to show" and "something went wrong." Silent collapsing of those
  two cases is the bug class this convention exists to prevent — preserve it
  when adding new providers or adapters.
- **Jobs never raise.** Every job handler owns its own `Job` row's status
  transitions (`running`/`completed`/`failed`) and is expected to catch its
  own failures and record them on the row, not let an exception propagate
  out of the handler.
- **Migrations are additive and defensive.** New columns get defaults chosen
  so existing rows keep behaving the way they did before the migration ran;
  don't change the meaning of an existing column in place.

## Testing

- `python -m pytest -q` runs the full suite.
- `tests/conftest.py` disables DB-backed logging before any test imports
  `app.main`, specifically so tests never write into the real app database.
  Follow that pattern for any new test that touches logging or persistence.
- A bug fix should ship with a regression test that reproduces the exact
  failure (real payload shape, real input), not a generic happy-path test.
