# Hostname Matrix and Routing Contract (S0-04 deliverable)

**Date:** 2026-11-14 · **Status:** PROPOSED, awaiting approval · **Decisions it implements:** D-009, D-010
**Code that implements it:** `app/host_routing.py` (installed in `app/main.py`, default OFF)

> The host guard picks the correct portal. It is **never** authorization. Every protected request is still checked server-side against the signed-in identity and Agency/Project ownership (plan principles 11 and 12).

## 1. Hostname matrix

| Environment | Customer host | Admin host | Legacy host | Notes |
|---|---|---|---|---|
| Local dev | `app.localhost` | `admin.localhost` | none | Browsers resolve `*.localhost` to 127.0.0.1. `127.0.0.1` itself is UNKNOWN while the guard is on |
| Production | `app.seofixai.com` | `admin.seofixai.com` | `seofixai.com` (until cutover) | HTTPS only; proxy terminates TLS |
| Future staging | documented equivalents | documented equivalents | none | Must never share production cookies or database |

After the cutover the apex `seofixai.com` is the **marketing site**, hosted outside this app, and leaves `LEGACY_APP_HOSTS`.

## 2. Request classification and behaviour (guard ON)

| Host kind | `/health` | `/admin` and `/admin/...` | Every other path |
|---|---|---|---|
| PUBLIC (`app.`) | 200 | 404 | served (auth applies from Sprint 1) |
| ADMIN (`admin.`) | 200 | served (auth applies from Sprint 1) | **404** |
| LEGACY (apex, temporary) | 200 | 404 | served as today, no auth until Sprint 1 |
| UNKNOWN (anything else, empty, look-alikes) | **421** | 421 | 421 |

Rules: exact string match on the normalized host (lowercase, no port, no trailing dot). 404 (not 403) hides that an admin area exists. 421 means "this server does not serve that hostname". Rejection bodies are generic JSON.

## 3. Settings (all in `.env.example`)

| Variable | Meaning | Default |
|---|---|---|
| `PUBLIC_APP_ORIGIN` | customer origin; host is extracted | `http://app.localhost:8000` |
| `ADMIN_APP_ORIGIN` | admin origin | `http://admin.localhost:8000` |
| `LEGACY_APP_HOSTS` | comma-separated hosts still serving the old app | empty |
| `HOST_ENFORCEMENT` | `1/true/yes/on` turns the guard on | off |
| `ENVIRONMENT` | planned by S0-04; **not added yet** because nothing reads it | n/a |

Hostnames are configuration. No hostname is hard-coded in route logic.

## 4. Apex and compatibility period (D-010)

| Phase | Apex `seofixai.com` | App reachable at | Action |
|---|---|---|---|
| A (now) | the app (LEGACY) | apex, no auth | none; guard off or LEGACY listed |
| B (prepare) | still the app | apex **and** `app.seofixai.com` | add DNS + TLS for `app.` and `admin.`; register the new GSC redirect URI; turn guard on in a test window |
| C (cutover) | switches to marketing | `app.seofixai.com` only | apex app URLs redirect to `app.seofixai.com` (fixed target, not built from `Host`); remove apex from `LEGACY_APP_HOSTS` |

Cutover date and marketing-site hosting are **open**. Cookies are host-only, so apex sessions do not carry over to `app.`. No sessions exist before Sprint 1, so nobody is logged out by Phase C today; this matters once login ships.

## 5. `/health` and `/version` (D-009)

- `/health`: public, minimal (`{"status":"ok"}`), no database, no build details. **Implemented.**
- `/version`: leaks commit and schema report; decision is internal-only. **Not enforced yet**, because `deploy.yml` polls it from a public runner and smoke-tests `/ /settings /docs /version`.
- **Proposal (needs approval):** the deploy workflow checks `/version` over SSM from the server itself (`curl localhost:8000/version`), and uses public `/health` for the external smoke test. Then restrict public `/version` at the proxy or behind a header token. Until `deploy.yml` changes, do not restrict `/version`.

## 6. HTTPS, HSTS, TLS

- All production traffic is HTTPS; the proxy redirects HTTP to HTTPS and sends `X-Forwarded-Proto`.
- HSTS: start with a short `max-age` on `app.` and `admin.` only. Do **not** use `includeSubDomains` or `preload` on the apex while it is a legacy app or a separately hosted marketing site.
- Certificates must cover `app.seofixai.com` and `admin.seofixai.com` (and the apex through Phase C). **Today no TLS or proxy configuration exists in this repo, and the certificate owner and renewal process are unknown.** Someone must name the owner (open item).

## 7. Reverse-proxy contract (documentation only; no proxy change in this task)

- Both hostnames route to the one FastAPI service (port 8000).
- The proxy forwards the original `Host` unchanged.
- The proxy overwrites, never appends to, any client-supplied `X-Forwarded-*` headers.
- The app currently trusts only `Host`. Trusting `X-Forwarded-Host/Proto` is deferred to S1-06 and only for a configured trusted proxy.
- Reject requests on any other server name at the proxy as well (defence in depth); the app guard is the second layer.

## 8. Cookies, CSRF, redirects, OAuth (rules for Sprint 1)

- Session cookies: host-only (no `Domain` attribute), `HttpOnly`, `Secure` in production, `SameSite=Lax` or stricter. Separate cookie names per portal, e.g. customer and admin (final names in S1-03; the `__Host-` prefix is a good fit for production).
- CSRF: tokens on every state-changing cookie-authenticated request, plus an `Origin`/`Referer` check against the **configured** origins, never against a request-supplied value.
- Redirects after login/logout only to an allowlist of configured origins and paths. Never build a redirect from the `Host` header.
- Generated links (reset email, OAuth callback) use the configured origin for the relevant portal.
- Google OAuth: register `https://app.seofixai.com/gsc/callback` at Google before Phase B; keep the old URI until Phase C. Local development needs its own registered redirect URI.

## 9. Acceptance checklist for S0-04

- [x] Host classification module and tests (45 + 26 tests)
- [x] Middleware rejecting unknown hosts and misplaced admin/customer paths, default off
- [x] `/health` defined and public
- [x] Settings documented in `.env.example`
- [x] Verified live with `app.localhost`, `admin.localhost`, `127.0.0.1`
- [x] Apex, compatibility period, `/health`/`/version` decisions recorded
- [ ] This matrix approved
- [ ] Deploy health-check change approved (section 5)
- [ ] TLS certificate owner/renewal named
- [ ] Cutover date and marketing hosting decided
