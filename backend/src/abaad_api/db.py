"""SQLite engine with the connection rules required by the plan.

Every connection gets ``PRAGMA foreign_keys=ON`` (SQLite defaults to OFF per
connection) and WAL journal mode. The SQLite runtime version is checked
because STRICT tables need 3.37.0 or later.
"""

from __future__ import annotations

import sqlite3
from functools import lru_cache
from pathlib import Path

from sqlalchemy import Engine, create_engine, event

from .config import MIN_SQLITE_VERSION, get_settings


class SQLiteVersionError(RuntimeError):
    """Raised when the SQLite runtime is too old for STRICT tables."""


def sqlite_runtime_version() -> tuple[int, int, int]:
    return tuple(int(p) for p in sqlite3.sqlite_version.split(".")[:3])  # type: ignore[return-value]


def assert_sqlite_supports_strict() -> None:
    if sqlite_runtime_version() < MIN_SQLITE_VERSION:
        need = ".".join(map(str, MIN_SQLITE_VERSION))
        raise SQLiteVersionError(
            f"SQLite {sqlite3.sqlite_version} is too old; STRICT tables need >= {need}."
        )


def _on_connect(dbapi_connection, _record) -> None:  # pragma: no cover - exercised via tests
    # Let SQLAlchemy emit BEGIN itself (see _on_begin) so DDL and DML are
    # always transactional; sqlite3's legacy mode skips BEGIN before DDL.
    dbapi_connection.isolation_level = None
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.execute("PRAGMA journal_mode = WAL")
    cursor.execute("PRAGMA busy_timeout = 5000")
    cursor.close()


def _on_begin(conn) -> None:  # pragma: no cover - exercised via tests
    conn.exec_driver_sql("BEGIN")


def make_engine(db_path: Path) -> Engine:
    """Create an engine for ``db_path`` with the ABAAD connection rules."""
    assert_sqlite_supports_strict()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    event.listen(engine, "connect", _on_connect)
    event.listen(engine, "begin", _on_begin)
    return engine


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return make_engine(get_settings().db_path)
