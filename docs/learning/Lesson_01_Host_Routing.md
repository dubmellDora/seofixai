# Lesson 1 — Host routing (plan task S0-04)

**You write the code. Claude reviews it.** Do the tasks in order. After each one, run the check command and paste the result back for review.

## 0. The big picture

One FastAPI app serves several hostnames (D-010):

```
 Browser ──> reverse proxy (TLS) ──> ONE FastAPI process
                                       │
   app.seofixai.com    -> "public"  (customers)
   admin.seofixai.com  -> "admin"   (platform staff)
   seofixai.com        -> "legacy"  (old URL, kept working during the move)
   anything else       -> "unknown" (rejected)
```

The app has to know which hostname a request came in on. That is **host classification**.

**Why it matters:** the plan says the hostname decides which portal you see. It never decides who you are. Permission checks come in Sprint 1. Hostname checks only stop customers and staff from landing in the wrong portal, and they stop requests with a fake `Host` header.

**Why not hard-code the names:** local, staging and production use different hosts. Hosts come from environment variables, so the same code runs everywhere (plan rule: "no hostname is hard-coded in route logic").

**Why default to OFF:** right now nothing has login. If the guard were on by default, every existing test and the live site would start returning errors. We ship the code switched off (`HOST_ENFORCEMENT=off`), prove it with tests, then switch it on per environment. This is how you add a risky rule to a live product.

## 1. Files you will touch

| File | Action |
|---|---|
| `app/host_routing.py` | **new** — config + classifier (pure logic, no FastAPI) |
| `tests/test_host_routing.py` | **new** — unit tests |
| `app/main.py` | edit — add one middleware |
| `tests/test_host_guard_middleware.py` | **new** — request-level tests |
| `.env.example` | edit — document the new variables |

Pattern from `seofixai/CLAUDE.md`: logic lives in a plain module, routes/middleware stay thin. Plain functions are easy to test without starting a server.

---

## Task 1 — The classifier (`app/host_routing.py`)

### What to build
1. An `Enum` called `HostKind` with `PUBLIC`, `ADMIN`, `LEGACY`, `UNKNOWN`.
2. A frozen dataclass `HostConfig` holding the allowed host names and the enforcement switch.
3. `HostConfig.from_env()` reads these variables (fill in `.env.example` in Task 5):
   - `PUBLIC_APP_ORIGIN`, e.g. `https://app.seofixai.com` or `http://app.localhost:8000`
   - `ADMIN_APP_ORIGIN`, e.g. `https://admin.seofixai.com`
   - `LEGACY_APP_HOSTS`, comma-separated, e.g. `seofixai.com`
   - `HOST_ENFORCEMENT`, `on` or `off` (default `off`)
4. `normalize_host(raw)` turns a raw `Host` header into a bare lowercase name.
5. `classify_host(raw, config)` returns a `HostKind`.

### Starter code
```python
"""Host classification: which portal did this request come in on?
The hostname is a navigation boundary only, never a permission (see plan 1.1 #11)."""
import os
from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlparse


class HostKind(str, Enum):
    PUBLIC = "public"
    ADMIN = "admin"
    LEGACY = "legacy"
    UNKNOWN = "unknown"


def normalize_host(raw: str | None) -> str:
    """'App.SeoFixAI.com:443.' -> 'app.seofixai.com'. Empty/None -> ''."""
    if not raw:
        return ""
    host = raw.strip().lower()
    # TODO 1: drop the port. Careful: only strip ':port', and the Host header
    #         has no scheme. Hint: host.rsplit(":", 1) when the part after ':' is digits.
    # TODO 2: drop a single trailing dot ("example.com." is the same host).
    return host


def _host_from_origin(origin: str) -> str:
    """'https://app.seofixai.com' -> 'app.seofixai.com'. Empty -> ''."""
    # TODO 3: use urlparse(origin).hostname (it already strips scheme and port
    #         and lowercases). Return "" when origin is empty/blank.
    ...


@dataclass(frozen=True)
class HostConfig:
    public_host: str
    admin_host: str
    legacy_hosts: frozenset[str]
    enforce: bool

    @classmethod
    def from_env(cls) -> "HostConfig":
        # TODO 4: build the config from os.environ (see list above).
        #   legacy: split on ",", normalize each, ignore empty pieces.
        #   enforce: True only when HOST_ENFORCEMENT.strip().lower() == "on".
        ...


def classify_host(raw: str | None, config: HostConfig) -> HostKind:
    host = normalize_host(raw)
    # TODO 5: if host is empty -> UNKNOWN. Compare to config.public_host,
    #         config.admin_host, config.legacy_hosts. Anything else -> UNKNOWN.
    #         Guard: an unset (empty) public_host/admin_host must NOT match an empty host.
    ...
```

### Why each design choice
- **Frozen dataclass:** the config can't be changed by accident mid-request.
- **Read env in `from_env()`, not at import:** tests can change env vars and get a fresh config.
- **Exact match, no `endswith`:** `endswith("seofixai.com")` would accept `evilseofixai.com`. Exact comparison against an allow-list is the safe default.
- **Unknown by default:** deny by default is rule 4 of the plan's principles.

### Check
```
python -c "from app.host_routing import normalize_host as n; print(n('App.SeoFixAI.com:443.'))"
```
Expected: `app.seofixai.com`

---

## Task 2 — Unit tests (`tests/test_host_routing.py`)

Write tests first for the cases that bite. Use `pytest.mark.parametrize` for a table of inputs.

```python
import pytest
from app.host_routing import HostConfig, HostKind, classify_host, normalize_host

CFG = HostConfig(
    public_host="app.seofixai.com",
    admin_host="admin.seofixai.com",
    legacy_hosts=frozenset({"seofixai.com"}),
    enforce=True,
)

@pytest.mark.parametrize("raw,expected", [
    ("app.seofixai.com", HostKind.PUBLIC),
    ("APP.seofixai.com:443", HostKind.PUBLIC),     # case + port
    ("admin.seofixai.com", HostKind.ADMIN),
    ("seofixai.com", HostKind.LEGACY),
    ("seofixai.com.", HostKind.LEGACY),            # trailing dot
    ("evilseofixai.com", HostKind.UNKNOWN),        # suffix trick
    ("app.seofixai.com.evil.com", HostKind.UNKNOWN),
    ("", HostKind.UNKNOWN),
    (None, HostKind.UNKNOWN),
    # TODO: add 3 more cases of your own (e.g. 'localhost', an IP, 'admin.seofixai.com:8000')
])
def test_classify(raw, expected):
    assert classify_host(raw, CFG) == expected

def test_empty_config_matches_nothing():
    empty = HostConfig("", "", frozenset(), False)
    assert classify_host("", empty) == HostKind.UNKNOWN

def test_from_env(monkeypatch):
    monkeypatch.setenv("PUBLIC_APP_ORIGIN", "http://app.localhost:8000")
    monkeypatch.setenv("ADMIN_APP_ORIGIN", "http://admin.localhost:8000")
    monkeypatch.setenv("LEGACY_APP_HOSTS", "seofixai.com, ,Old.Example.com")
    monkeypatch.setenv("HOST_ENFORCEMENT", "ON")
    cfg = HostConfig.from_env()
    assert cfg.public_host == "app.localhost"
    assert cfg.legacy_hosts == {"seofixai.com", "old.example.com"}
    assert cfg.enforce is True
    # TODO: add a test that HOST_ENFORCEMENT unset -> enforce is False
```

### Check
```
python -m pytest tests/test_host_routing.py -q
```

---

## Task 3 — The middleware (`app/main.py`)

### Rules the middleware implements
| Request host | Path | Result |
|---|---|---|
| enforcement off | anything | pass through (today's behavior) |
| `unknown` | anything | **421** "Unknown host" |
| `public` | starts with `/admin` | **404** (the admin portal does not exist on this host) |
| `admin` | not `/admin...` and not `/health` | **404** |
| `legacy` | anything | pass through (compatibility period, D-010) |
| `public` / `admin` | otherwise | pass through |

**Why 404 and not 403 for the wrong portal:** a 403 confirms "an admin area exists here". A 404 says nothing.
**Why 421:** "Misdirected Request" is the standard status for a host the server doesn't serve.

**Why we read the `Host` header and not `X-Forwarded-Host`:** anyone can send `X-Forwarded-Host`. Trusting it needs a configured trusted proxy list. That is task S1-06, so for now we only use `Host`. The reverse proxy must pass the original `Host` through.

### Starter code (add near the top of `main.py`, after `app = FastAPI(...)`)
```python
from fastapi import Request
from fastapi.responses import PlainTextResponse
from .host_routing import HostConfig, HostKind, classify_host


@app.middleware("http")
async def host_guard(request: Request, call_next):
    config = HostConfig.from_env()
    if not config.enforce:
        return await call_next(request)

    kind = classify_host(request.headers.get("host"), config)
    path = request.url.path

    # TODO 1: UNKNOWN -> PlainTextResponse("Unknown host", status_code=421)
    # TODO 2: PUBLIC and path is "/admin" or startswith "/admin/" -> 404
    # TODO 3: ADMIN and path is not "/admin"/"/admin/..." and path != "/health" -> 404
    # (careful: "/administrator" must NOT count as an admin path)
    return await call_next(request)
```

### Why a middleware and not a dependency
A middleware runs for every request, including routes added later and 404s. A dependency has to be attached to each router, and one forgotten router is a hole.

---

## Task 4 — Request-level tests (`tests/test_host_guard_middleware.py`)

```python
import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture(autouse=True)
def hosts(monkeypatch):
    monkeypatch.setenv("PUBLIC_APP_ORIGIN", "http://app.localhost")
    monkeypatch.setenv("ADMIN_APP_ORIGIN", "http://admin.localhost")
    monkeypatch.setenv("LEGACY_APP_HOSTS", "legacy.localhost")
    monkeypatch.setenv("HOST_ENFORCEMENT", "on")

def client(host):
    return TestClient(app, base_url=f"http://{host}")

def test_public_host_serves_normal_route():
    assert client("app.localhost").get("/version").status_code == 200

def test_unknown_host_rejected():
    assert client("evil.example.com").get("/version").status_code == 421

def test_admin_path_hidden_on_public_host():
    assert client("app.localhost").get("/admin/login").status_code == 404

def test_non_admin_path_hidden_on_admin_host():
    assert client("admin.localhost").get("/version").status_code == 404

def test_enforcement_off_changes_nothing(monkeypatch):
    monkeypatch.setenv("HOST_ENFORCEMENT", "off")
    assert client("evil.example.com").get("/version").status_code == 200

# TODO: legacy host passes; '/administrator' on public host is NOT treated as admin
#       (it should reach the router, so expect the app's normal 404, but prove the guard didn't
#       produce it: check response.text != "Not Found" or add a distinct body for guard 404s).
```

### Check
```
python -m pytest tests/test_host_guard_middleware.py tests/test_host_routing.py -q
python -m pytest -q
```
The full suite must still show **1241 passed plus your new tests**, with zero failures. Existing tests don't set `HOST_ENFORCEMENT`, so they are untouched. If any existing test fails, the guard is on by default somewhere. Stop and ask.

---

## Task 5 — Document the variables (`.env.example`)

Add a "Hostnames" section with all four variables, local values by default, and one comment line each explaining production values from D-010. Keep `HOST_ENFORCEMENT=off`.

## Task 6 — Run it for real
1. In `.env` set the four variables to the `app.localhost` / `admin.localhost` values and `HOST_ENFORCEMENT=on`.
2. `uvicorn app.main:app --reload`
3. Open `http://app.localhost:8000/version`, then `http://admin.localhost:8000/version`, then `http://127.0.0.1:8000/version`. You should see 200, 404, 421. (Chrome resolves `*.localhost` itself; no hosts-file edit is needed.)
4. Put `HOST_ENFORCEMENT=off` back.

## Definition of done for Lesson 1
- [ ] Unit and middleware tests written by you and passing
- [ ] Full suite green, nothing existing changed
- [ ] `.env.example` updated
- [ ] Manual 200 / 404 / 421 check done
- [ ] Claude reviewed your diff

## Concepts you just learned
`Host` header · allow-list vs suffix matching · deny by default · feature flag for safe rollout · pure-logic module + thin middleware · parametrized tests · 404 vs 403 vs 421.

## Next lessons
2. Hostname matrix doc + `/health` route + deploy health check change
3. S0-05 threat model (you write the abuse-case table, I review)
4. Sprint 1: Agency + User models and your first Alembic migration
