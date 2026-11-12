"""Alembic environment for SQLite.

Migrations run on one connection with ``PRAGMA foreign_keys=OFF`` so that
batch (copy-and-recreate) table rebuilds do not cascade or fail mid-way.
This is the table-rebuild procedure recommended by sqlite.org. After the
migration commits, ``PRAGMA foreign_key_check`` must return no rows or the
command fails. Application connections always run with foreign_keys=ON
(see abaad_api.db).
"""

from __future__ import annotations

from pathlib import Path

from alembic import context
from sqlalchemy import create_engine, event, text

from abaad_api.config import get_settings
from abaad_api.db import assert_sqlite_supports_strict

config = context.config

# Naming convention shared by every migration so constraints are always
# named (Alembic batch mode drops unnamed CHECK constraints on recreate).
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def _db_path() -> Path:
    override = context.get_x_argument(as_dictionary=True).get("db")
    return Path(override).resolve() if override else get_settings().db_path


def run_migrations_online() -> None:
    assert_sqlite_supports_strict()
    db_path = _db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}", future=True)

    # Python's sqlite3 driver does not open a transaction before DDL by
    # default, so a failed migration could leave tables or triggers half
    # changed. Take control of BEGIN so every migration is atomic
    # (SQLAlchemy's documented pysqlite recipe).
    @event.listens_for(engine, "connect")
    def _connect(dbapi_connection, _record):
        dbapi_connection.isolation_level = None
        cur = dbapi_connection.cursor()
        cur.execute("PRAGMA foreign_keys = OFF")  # outside any transaction
        cur.execute("PRAGMA journal_mode = WAL")
        cur.close()

    @event.listens_for(engine, "begin")
    def _begin(conn):
        conn.exec_driver_sql("BEGIN IMMEDIATE")

    with engine.connect() as connection:

        context.configure(
            connection=connection,
            target_metadata=None,
            render_as_batch=True,
            transaction_per_migration=True,
        )
        with context.begin_transaction():
            context.run_migrations()

        violations = connection.execute(text("PRAGMA foreign_key_check")).fetchall()
        connection.rollback()
        if violations:
            raise RuntimeError(f"Foreign key violations after migration: {violations}")
    engine.dispose()


if context.is_offline_mode():
    raise SystemExit("Offline (SQL script) migrations are not supported; run against a database file.")
run_migrations_online()
