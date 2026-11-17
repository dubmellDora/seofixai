import os

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base

# Connection string lives in the environment (see .env.example). Defaults to
# the local SQLite file only so ad-hoc scripts/tests that don't set it up
# still work; real runs (app, alembic, docker-compose) always set DATABASE_URL.
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///seo_automation.db")

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=_connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    """WAL mode lets readers and writers run concurrently instead of
    exclusive-locking the whole file; busy_timeout makes a writer that loses
    a race retry instead of raising 'database is locked' immediately. Needed
    now that the scheduler (Task 2.4) writes from a background thread while
    request handlers write from the main thread. Guarded by dialect since
    PRAGMA is SQLite-only -- this becomes a no-op once Postgres (Task 6.1)
    replaces DATABASE_URL, so it doesn't need to be revisited then."""
    if engine.dialect.name != "sqlite":
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
