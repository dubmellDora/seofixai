# Routing Threat Model and Authorization Boundary (S0-05 deliverable)

**Date:** 2026-11-14 · **Status:** PROPOSED, awaiting approval · **Used as:** the acceptance checklist for Sprints 1 and 2
**Based on:** `docs/Sprint0_Audit.md` (no auth, no ownership checks, ~100 open routes) and `docs/Hostname_Matrix.md`

## 1. What is and is not a security control

Not controls: DNS, subdomains, URL prefixes, hidden navigation, frontend checks, `Host` classification. They only choose the portal.
Controls: server-side identity from a signed session, role checks, and an ownership check on every resource.

## 2. Roles (PROPOSAL: the plan has two conflicting lists and needs one approved table)

The plan lists `platform_admin`, `support_admin`, `customer` (S0-05) and `agency_owner`, `agency_user`, `platform_admin` (S1-01). Proposed reconciliation: two independent fields on `User`.

| Field | Values | Stage 1 use |
|---|---|---|
| `platform_role` | `customer` (default), `platform_admin`, `support_admin` | `platform_admin` only; `support_admin` reserved, no powers yet |
| `agency_role` | `owner`, `member` | `owner` only; `member` reserved for the later stage |

Rules: public registration can only create `customer` + `owner` of a new Agency. No request can set `platform_role`. Platform admins are created only by a development-only bootstrap. The plan's Stage 1 names (`agency_owner`, `agency_user`) map to `owner`/`member`. **Needs your approval before S1-01.**

## 3. Expected response for each state

| Situation | Browser page | HTMX request | JSON/API | Notes |
|---|---|---|---|---|
| Unknown host | 421 | 421 | 421 | before any auth |
| Wrong portal path (e.g. `/admin` on public host) | 404 | 404 | 404 | host guard |
| Unauthenticated | redirect to that portal's login | 401 + `HX-Redirect` to login | 401 | never reveal whether a resource exists |
| Authenticated, wrong role (customer on an admin route) | 403 | 403 | 403 | generic message |
| Authenticated, resource of another agency | **404** | 404 | 404 | 404 not 403, so existence is not confirmed |
| Suspended user | treated as unauthenticated, sessions invalidated | 401 | 401 | login shows a generic message |
| Suspended agency | 403 "account suspended" page | 403 | 403 | data preserved |
| Expired or tampered session | as unauthenticated | 401 | 401 | cookie cleared |
| Missing/invalid CSRF token | 403 | 403 | 403 | state-changing requests only |

## 4. Resource authorization rule

Root rule: **a request may touch a resource only if `resource.project.agency_id == session.agency_id`**, resolved from the database, never from a browser-supplied agency or project id. Child records are checked through their parent chain. Deny by default when identity, role, agency or ownership is missing.

| Resource | Check |
|---|---|
| Project | `agency_id` equals the session's agency |
| Page, Issue, Suggestion, SuggestionRevision, CrawlSnapshot, Backlink*, PageLink, VisibilityCheck, Competitor*, ContentOptimizationRun | via `project_id` (and `page_id`/`issue_id`) up to Project |
| Job, Schedule | via `project_id` |
| WordPressConnection, GoogleConnection, SearchConsoleProperty | via `project_id`, plus the connection's own `agency_id`; a connection from Agency A can never serve Agency B |
| KeywordWorkspace and keyword children | **gap:** `project_id` is nullable; every workspace needs an owner (decision required) |
| `semrush_onpage_snapshots` | **gap:** keyed on Semrush IDs; decide global cache vs agency-scoped |
| `provider_settings`, `crawler_settings`, `site_audit_settings`, `app_logs`, `/settings/*` | platform-admin only |

Routes that take a bare child id with no project in the path (suggestion accept/reject/edit/deploy, `/revisions/{id}`, GSC `/properties/{id}/select`, all `/keywords/...`) must **join up to the project** before acting. Global list pages (`/security`, `/visibility`, `/onpage-semrush`) currently list every project and must filter to the caller's agency.

Background code (`scheduler.py`, `jobs/runner.py`, `backlinks_provider.py`, the WordPress deploy task) has no request identity. It acts on a Job/Schedule row that already carries `project_id`, so the agency is derived from that row, and enqueueing re-checks ownership.

Impersonation: **not allowed** until an audited, time-limited workflow exists.

## 5. Abuse cases (each becomes a test)

| # | Abuse | Expected result | Test |
|---|---|---|---|
| A1 | Send `Host: admin.seofixai.com` from a public network without an admin session | admin routes still return 401/403 (host is not trust) | direct request, correct host, no cookie |
| A2 | `Host: evilseofixai.com` or `app.seofixai.com.evil.com` | 421 | covered by `test_host_routing.py` |
| A3 | `X-Forwarded-Host: admin.seofixai.com` on the public host | ignored; classification uses `Host` only | S1-06 test |
| A4 | Open redirect via `Host` or `next=` after login | redirect only to allowlisted configured origins | S1-05 test |
| A5 | IDOR: change `/projects/1` to `/projects/2` | 404 for another agency's project | per route family |
| A6 | IDOR on bare child ids (`/suggestions/9/deploy`, `/revisions/4/rollback`) | 404 unless the parent project belongs to the caller | per route |
| A7 | Cross-tenant use of a GSC or WordPress connection by passing another project's id | rejected; connection must match project and agency | S2-03 test |
| A8 | Customer calls `/settings/*`, `/settings/logs.txt`, `/settings/logs/clear` | 403 | S1-04 test |
| A9 | Cookie confusion: customer session cookie sent to the admin host, or the reverse | not accepted; separate names, host-only scope | S1-03 test |
| A10 | CSRF: cross-site POST to delete project/deploy | 403 without a valid token and allowed Origin | S1-03 test |
| A11 | Registration with `platform_role=platform_admin` in the body | field ignored; user is `customer` | S1-01 test |
| A12 | Session fixation: reuse a pre-login session id | id rotated at login | S1-03 test |
| A13 | Login/reset account enumeration | identical responses and timing class for existing and unknown emails | S1-03/S1-05 test |
| A14 | Brute-force login/reset | rate limited | S1-03 test |
| A15 | Forged/replayed OAuth callback for another project (`state` is signed but not session-bound today) | rejected unless `state` matches the signed-in user, session and project | S2-03 test |
| A16 | Customer A lists all projects via `/`, `/security`, `/visibility`, `/onpage-semrush` | only own agency's projects | S1/S2 test |
| A17 | **SSRF through crawl/audit/security URLs:** the app fetches user-supplied URLs with `httpx` and several calls use `follow_redirects=True` | block private/loopback/link-local ranges (incl. the cloud metadata address) and re-check every redirect hop | **CONFIRMED PARTIAL (2026-11-14):** a correct guard exists only in `app/services/page_evidence.py` (resolves the host, rejects non-global addresses, follows redirects by hand). `audit.py`, `crawler.py`, `routes/security.py`, `dataforseo_onpage.py` (image fetch) and `wordpress.py` (user-supplied `site_url`) call `httpx.get(..., follow_redirects=True)` without it. Fix: one shared guarded fetch helper, used by all of them |
| A18 | Mass assignment: extra form fields change `agency_id` on create/update | server sets `agency_id` from the session only | per create/update route |
| A19 | Suspended user or agency keeps working via an old session | sessions invalidated; requests denied | S1-03 test |
| A20 | Background job runs for a project whose agency was suspended | job skipped or rejected | S1/S2 test |

## 6. Open decisions needed

1. Approve the two-field role model in section 2.
2. Owner rule for project-less keyword workspaces and for Semrush on-page snapshots.
3. Whether global settings stay platform-wide (recommended) or become per-agency.
4. Confirm 404-not-403 for cross-agency access.
5. SSRF (A17) is confirmed as partially unguarded: approve building one shared guarded-fetch helper in Sprint 1, built on the existing `page_evidence.py` guard. Until then every unauthenticated route that fetches a user-supplied URL is exposed.
6. Support-admin powers (none in Stage 1 unless you decide otherwise).

## 7. Exit condition

Sprint 0 routing exit: the hostname matrix and this authorization boundary are approved before any portal-specific code beyond the guard already added.
