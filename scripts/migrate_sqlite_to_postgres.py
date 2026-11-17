"""
One-off data migration: copy every row from the local SQLite database into
PostgreSQL, preserving primary keys so foreign keys stay valid, then reset
each Postgres sequence to MAX(id)+1 so future inserts don't collide.

This is a one-time data copy, not a schema migration -- the schema itself
is created by Alembic (`alembic upgrade head`) against the target Postgres
database before this script runs.

Run against a COPY of seo_automation.db, never the live file:
    cp seo_automation.db /tmp/seo_automation_copy.db
    python scripts/migrate_sqlite_to_postgres.py /tmp/seo_automation_copy.db \
        postgresql+psycopg2://seofixai:seofixai@localhost:5432/seofixai
"""
import sys

from sqlalchemy import create_engine, inspect, text


def migrate(sqlite_url: str, postgres_url: str) -> None:
    sqlite_engine = create_engine(sqlite_url)
    postgres_engine = create_engine(postgres_url)

    sys.path.insert(0, ".")
    from app import models  # noqa: F401 -- registers tables on Base.metadata
    from app.database import Base

    # Base.metadata.sorted_tables is topologically sorted by FK dependency,
    # so parents are always inserted (and counted) before children.
    tables = Base.metadata.sorted_tables

    with sqlite_engine.connect() as src, postgres_engine.begin() as dst:
        inspector = inspect(sqlite_engine)
        existing = set(inspector.get_table_names())

        for table in tables:
            if table.name not in existing:
                print(f"skip {table.name}: not present in source SQLite db")
                continue

            rows = src.execute(table.select()).mappings().all()
            if not rows:
                print(f"{table.name}: 0 rows")
                continue

            dst.execute(table.insert(), [dict(row) for row in rows])
            print(f"{table.name}: copied {len(rows)} rows")

        for table in tables:
            int_pk_cols = [
                c.name
                for c in table.primary_key.columns
                if c.autoincrement and str(c.type).upper().startswith("INT")
            ]
            if not int_pk_cols:
                continue
            pk = int_pk_cols[0]
            seq = dst.execute(
                text("SELECT pg_get_serial_sequence(:table, :pk)"),
                {"table": table.name, "pk": pk},
            ).scalar()
            if seq is None:
                continue
            dst.execute(
                text(
                    f"SELECT setval(:seq, COALESCE((SELECT MAX({pk}) FROM {table.name}), 0) + 1, false)"
                ),
                {"seq": seq},
            )

    print("Migration complete.")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(
            "Usage: python scripts/migrate_sqlite_to_postgres.py "
            "<path-to-sqlite-copy.db> <postgres-url>"
        )
        sys.exit(1)

    sqlite_path, postgres_url = sys.argv[1], sys.argv[2]
    migrate(f"sqlite:///{sqlite_path}", postgres_url)
