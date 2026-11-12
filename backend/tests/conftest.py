"""Shared fixtures. Every database here is a throwaway file under pytest's
tmp_path; rows inserted by tests are synthetic test fixtures only."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from abaad_api.config import REPO_ROOT

ALEMBIC_INI = REPO_ROOT / "backend" / "alembic.ini"


def alembic_config(db_path: Path) -> Config:
    cfg = Config(str(ALEMBIC_INI))
    cfg.cmd_opts = argparse.Namespace(x=[f"db={db_path}"])
    return cfg


def upgrade(db_path: Path, revision: str = "head") -> None:
    command.upgrade(alembic_config(db_path), revision)


def downgrade(db_path: Path, revision: str) -> None:
    command.downgrade(alembic_config(db_path), revision)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test.sqlite"


@pytest.fixture
def migrated_db(db_path: Path) -> Path:
    upgrade(db_path)
    return db_path


def raw(db_path: Path) -> sqlite3.Connection:
    """Plain sqlite3 connection with foreign keys ON (like the app)."""
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
