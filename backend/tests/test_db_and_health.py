"""Connection pragmas, SQLite version gate, health endpoint and error shape."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from abaad_api import db as dbmod
from abaad_api.config import MIN_SQLITE_VERSION
from abaad_api.routes import health as health_mod


def make_client(monkeypatch, db_path: Path) -> TestClient:
    monkeypatch.setenv("ABAAD_DB_PATH", str(db_path))
    dbmod.get_engine.cache_clear()
    from abaad_api.main import create_app
    return TestClient(create_app(), raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _reset_engine():
    yield
    dbmod.get_engine.cache_clear()


def test_runtime_sqlite_supports_strict():
    assert dbmod.sqlite_runtime_version() >= MIN_SQLITE_VERSION


def test_version_gate_rejects_old_sqlite(monkeypatch):
    monkeypatch.setattr(dbmod, "sqlite_runtime_version", lambda: (3, 36, 0))
    with pytest.raises(dbmod.SQLiteVersionError):
        dbmod.assert_sqlite_supports_strict()


def test_every_connection_has_foreign_keys_and_wal(migrated_db: Path):
    engine = dbmod.make_engine(migrated_db)
    for _ in range(3):  # several pooled/new connections
        with engine.connect() as conn:
            assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1
            assert conn.execute(text("PRAGMA journal_mode")).scalar() == "wal"
    engine.dispose()


def test_health_ok_on_migrated_db(monkeypatch, migrated_db: Path):
    r = make_client(monkeypatch, migrated_db).get("/api/v1/health")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "ok"
    assert body["database"]["connected"] is True
    assert body["database"]["foreign_keys"] is True
    assert body["database"]["journal_mode"] == "wal"
    assert body["database"]["schema_revision"] == health_mod.expected_schema_revision() == "0003"
    assert body["database"]["schema_up_to_date"] is True


def test_health_degraded_when_not_migrated(monkeypatch, tmp_path: Path):
    r = make_client(monkeypatch, tmp_path / "empty.sqlite").get("/api/v1/health")
    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "degraded"
    assert body["database"]["connected"] is True
    assert body["database"]["schema_revision"] is None


def test_unknown_route_uses_error_shape(monkeypatch, migrated_db: Path):
    r = make_client(monkeypatch, migrated_db).get("/api/v1/does-not-exist")
    assert r.status_code == 404
    assert set(r.json()) == {"code", "message", "details"}
    assert r.json()["code"] == "not_found"


def test_wrong_method_uses_error_shape(monkeypatch, migrated_db: Path):
    r = make_client(monkeypatch, migrated_db).post("/api/v1/health")
    assert r.status_code == 405
    assert r.json()["code"] == "method_not_allowed"


def test_openapi_is_published(monkeypatch, migrated_db: Path):
    client = make_client(monkeypatch, migrated_db)
    spec = client.get("/api/v1/openapi.json").json()
    assert "/api/v1/health" in spec["paths"]
    assert client.get("/api/v1/docs").status_code == 200


def test_validation_and_unhandled_errors_use_error_shape(monkeypatch, migrated_db: Path):
    client = make_client(monkeypatch, migrated_db)
    app = client.app

    @app.get("/api/v1/_test/needs-int")  # test-only route, not part of the API
    def _needs_int(n: int) -> dict:
        return {"n": n}

    @app.get("/api/v1/_test/boom")  # test-only route, not part of the API
    def _boom() -> dict:
        raise RuntimeError("boom")

    r = client.get("/api/v1/_test/needs-int", params={"n": "abc"})
    assert r.status_code == 422
    assert r.json()["code"] == "validation_error" and r.json()["details"]
    r = client.get("/api/v1/_test/boom")
    assert r.status_code == 500
    assert r.json() == {"code": "internal_error", "message": "An unexpected error occurred.", "details": None}
