from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI

from . import build_info, host_routing, logging_setup, schema_check, scheduler as job_scheduler
from .auth import install_auth_guard
from .database import Base, engine
from .routes import auth as auth_routes
from .routes import audit, competitors, crawl, jobs, keywords, links, onpage_semrush, optimizer, projects, search_console, security, settings, suggestions, visibility, wordpress

logging_setup.configure_logging()   # timestamps + levels on every WARNING and above, before anything below can log
Base.metadata.create_all(bind=engine)
schema_check.log_drift_at_startup(engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    job_scheduler.start()
    yield
    job_scheduler.shutdown()


app = FastAPI(
    title="SeoFixAI",
    description="SEO automation platform with AI-powered crawling and analysis",
    version="2.0.0",
    lifespan=lifespan,
)

# Host guard (plan S0-04). Installed always, but does nothing unless
# HOST_ENFORCEMENT is on, so existing deployments behave exactly as before.
# Auth guard (plan S1-04). Same pattern: always installed, enforces nothing until
# AUTH_ENFORCEMENT=1, so existing deployments behave exactly as before.
# ORDER MATTERS: Starlette runs the LAST-added middleware FIRST. The host guard is
# added last so an unknown host is rejected (421) before any login lookup happens.
install_auth_guard(app)
host_routing.install_host_guard(app, host_routing.load_host_config())

app.include_router(auth_routes.router)
app.include_router(projects.router)
app.include_router(crawl.router)
app.include_router(audit.router)
app.include_router(suggestions.router)
app.include_router(keywords.router)
app.include_router(jobs.router)
app.include_router(wordpress.router)
app.include_router(onpage_semrush.router)
app.include_router(settings.router)
app.include_router(security.router)
app.include_router(visibility.router)
app.include_router(competitors.router)
app.include_router(optimizer.router)
app.include_router(links.router)
app.include_router(search_console.router)


@app.get("/health")
def health():
    """Minimal liveness check: the process is up and answering. Deliberately
    touches no database and reveals nothing (D-009: /health is public)."""
    return {"status": "ok"}


@app.get("/version")
def version():
    """Which commit this process is running (see build_info.py) and whether the
    database has every column the code expects (see schema_check.py). No auth and
    no writes -- safe for the deploy pipeline to poll, and to fail a deploy on
    schema.ok being false."""
    return {**build_info.get_build_info(), "schema": schema_check.schema_report(engine)}
