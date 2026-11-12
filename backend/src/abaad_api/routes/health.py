"""Health endpoint: application status, database connectivity and schema revision."""

from __future__ import annotations

import sqlite3
from functools import lru_cache
from typing import Literal

from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text

from ..config import API_VERSION, MIN_SQLITE_VERSION, REPO_ROOT
from ..db import get_engine, sqlite_runtime_version

router = APIRouter(tags=["system"])

ALEMBIC_INI = REPO_ROOT / "backend" / "alembic.ini"


@lru_cache(maxsize=1)
def expected_schema_revision() -> str | None:
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(REPO_ROOT / "backend" / "migrations"))
    return ScriptDirectory.from_config(cfg).get_current_head()


class DatabaseStatus(BaseModel):
    connected: bool
    sqlite_version: str
    strict_supported: bool
    foreign_keys: bool | None = None
    journal_mode: str | None = None
    schema_revision: str | None = None
    expected_revision: str | None = None
    schema_up_to_date: bool = False
    error: str | None = None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    service: str = "abaad-api"
    version: str = API_VERSION
    database: DatabaseStatus


@router.get(
    "/health",
    response_model=HealthResponse,
    responses={503: {"model": HealthResponse, "description": "Database unavailable or schema not migrated"}},
    summary="Application and database health",
)
def health() -> JSONResponse:
    db = DatabaseStatus(
        connected=False,
        sqlite_version=sqlite3.sqlite_version,
        strict_supported=sqlite_runtime_version() >= MIN_SQLITE_VERSION,
        expected_revision=expected_schema_revision(),
    )
    try:
        with get_engine().connect() as conn:
            db.connected = True
            db.foreign_keys = bool(conn.execute(text("PRAGMA foreign_keys")).scalar())
            db.journal_mode = str(conn.execute(text("PRAGMA journal_mode")).scalar())
            has_version_table = conn.execute(
                text("SELECT 1 FROM sqlite_master WHERE type='table' AND name='alembic_version'")
            ).scalar()
            if has_version_table:
                db.schema_revision = conn.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar()
    except Exception as exc:  # report, never crash the health check
        db.error = f"{type(exc).__name__}: {exc}"

    db.schema_up_to_date = (
        db.connected and db.schema_revision is not None and db.schema_revision == db.expected_revision
    )
    ok = db.connected and db.schema_up_to_date and db.strict_supported and bool(db.foreign_keys)
    body = HealthResponse(status="ok" if ok else "degraded", database=db)
    return JSONResponse(status_code=200 if ok else 503, content=body.model_dump())
