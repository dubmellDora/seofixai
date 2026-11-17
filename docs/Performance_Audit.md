# Performance Audit

**Date:** 2026-11-14 · **Method:** static read of `app/`, `requirements.txt`, `Dockerfile`, `docker-compose.yml`, templates. **No profiling or load test was run**, so everything below is a *suspected* cost, not a measured one. Step 0 below fixes that.

## The short version

"Python is slow" is not this app's problem. Almost all request time in a tool like this is spent **waiting**: on Semrush, DataForSEO, WordPress sites, LLM APIs and the database. Python's CPU speed barely matters. The speed levers are: fewer/shorter waits, indexed queries, small pages, caching, and keeping slow work out of the request.

## Findings (ranked by likely user impact)

| # | Finding | Evidence | Impact |
|---|---------|----------|--------|
| P1 | **Foreign keys have no indexes.** 46 `ForeignKey`s, 1 `index=True`, 0 `Index(...)`. | `app/models.py` | Postgres does not auto-index FKs. Every "pages for project X" / "issues for page Y" query scans the table. Slow as data grows, and every tenant-scoped query in Stage 1 will filter on these columns. |
| P2 | **Slow external calls inside request handlers.** Blocking `httpx` calls in `routes/security.py`, `routes/wordpress.py`, `audit.py`, plus `time.sleep` in `routes/wordpress.py:529`. | grep | A request holds a worker thread for the full upstream round trip (10-30 s timeouts). A few slow users exhaust the threadpool (default ~40). Need to confirm which of these run in a request vs a job. |
| P3 | **Tailwind CDN + htmx from unpkg on every page.** `base.html` loads `cdn.tailwindcss.com` (the in-browser JIT compiler, documented as not for production). | `app/templates/base.html:7-8` | Hundreds of KB of JS, runtime CSS compilation in the browser on every load, an extra third-party DNS/TLS hop, and a CDN outage breaks the UI. Likely the largest *perceived* slowness. |
| P4 | **No caching and no compression.** No cache headers, no ETag, no GZip, no in-memory cache. | grep | Static assets and repeated expensive reads are recomputed or re-downloaded each time. |
| P5 | **No pagination discipline.** 73 `.all()` calls vs 10 `limit`/`offset`. | grep | List endpoints return whole tables. Fine at 10 projects, painful at 500 pages x many projects. |
| P6 | **No eager loading.** 0 uses of `joinedload`/`selectinload`. | grep | Risk of N+1 queries when templates walk relationships. The routes that were checked (`onpage_semrush.py`) already batch with `IN (...)`, so this may be limited. Needs a query-count check, not a guess. |
| P7 | **Single uvicorn process; scheduler runs inside it.** | `Dockerfile` CMD, `main.py` lifespan | One CPU core serves everything. Adding `--workers N` today would start N schedulers and duplicate every job. Scaling blocked until the scheduler is split out. |
| P8 | **No DB pool tuning.** `create_engine(DATABASE_URL)` with SQLAlchemy defaults (pool 5 + 10 overflow). | `app/database.py` | OK for now; will need explicit size and `pool_pre_ping` under Postgres with more concurrency. |
| P9 | **Production is still SQLite.** | audit, deploy script | Single-writer; heavy while the scheduler writes. Postgres cutover (already planned) removes this. |
| P10 | **No latency measurement.** No timing middleware, no slow-query log. | grep | We cannot say which finding above matters most. |

## What is NOT a problem

- **189 routes are plain `def`, not `async def`.** In FastAPI a sync route runs in a threadpool and does not block the event loop, so this is correct for code that uses blocking libraries (SQLAlchemy sync, `httpx.get`). Converting everything to async would be a large risky rewrite with little gain. Make only the slow upstream calls non-blocking or move them to jobs (P2).
- **Job system runs crawls in subprocesses.** Good isolation; crawl work does not compete with web requests.

## Should this be in Stage 1 or later?

**Split it.** A few items are cheap now and expensive later; the rest are independent and can wait.

### Do inside Stage 1 (they ride on work Stage 1 already does)

1. **S0: baseline measurement (P10).** Add a timing middleware / log of request duration and slow queries, and record p50/p95 for the main pages before anything changes. Without this we cannot prove any later "faster" claim.
2. **S1: indexes on the new tenant columns (P1, partial).** Sprint 1 adds `agency_id` / ownership columns and migrates tables. Add indexes in the *same* migration. Doing it later means a second migration over big tables. Index every FK the tenant filter touches (`project_id`, `agency_id`, `page_id`).
3. **New list endpoints paginate from day one (P5, new code only).** Don't add more `.all()` calls in Stage 1 code.
4. **Postgres pool settings (P8)** with the Postgres cutover that is already in plan.
5. **Rule for new code:** no new blocking external call inside a request handler. Put it in a job.

### Defer to a dedicated performance pass (after Stage 1 is stable)

- P3: real Tailwind build step, self-host htmx, fingerprinted static files (a pure front-end task; it does not touch the auth/tenancy work).
- P4: GZip, cache headers, light caching of expensive reads.
- P2: move the remaining in-request upstream calls to jobs or async clients.
- P5/P6: paginate old endpoints, add eager loading where the measurements show N+1.
- P7: split the scheduler into its own process, then run multiple web workers.

**Why defer these:** mixing a front-end rebuild, async refactors and process splitting into the multi-tenant release makes failures hard to attribute and breaks the plan's own rule of shipping risky changes separately. Authentication will also change many pages, so polishing the old ones first is partly wasted.

**Exception worth considering now:** P3 is the cheapest big win for *perceived* speed and is isolated from Stage 1. It can be done as a standalone small task whenever you want a visible improvement.

## Suggested order for the performance pass

1. Measure (P10) -> 2. Indexes (P1) -> 3. Static assets/compression (P3, P4) -> 4. Move slow calls out of requests (P2) -> 5. Pagination/N+1 (P5, P6) -> 6. Scheduler split + workers (P7).

## Open questions

- Which of the `httpx` calls in `audit.py` run in a request vs a background job?
- What is the real data volume per project (pages, issues)? It decides how soon P1 and P5 bite.
