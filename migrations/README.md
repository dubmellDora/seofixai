# migrations/ (legacy, SQLite-era)

The numbered scripts in this folder (`001_*.py` through `028_*.py`) are
historical: a plain, idempotent, no-framework way of evolving the SQLite
schema (`python migrations/NNN_description.py`). They are kept as a record
of how the schema got to where it is — do not delete them, and do not add
new ones here.

As of the Postgres migration (sprint-1/database-multitenant-foundation),
schema changes go through Alembic instead: see `alembic/` at the repo root.
Use `alembic revision --autogenerate -m "..."` then `alembic upgrade head`.
