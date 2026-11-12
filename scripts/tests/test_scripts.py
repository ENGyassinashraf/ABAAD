"""Tests for the operational scripts: verify-data, backup/restore, port check
and the GIS import/smoke checks used by `make doctor`."""

from __future__ import annotations

import argparse
import hashlib
import json
import socket
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import backup as backup_mod  # noqa: E402
import verify_data  # noqa: E402


def _migrated(db: Path) -> Path:
    cfg = Config(str(ROOT / "backend" / "alembic.ini"))
    cfg.cmd_opts = argparse.Namespace(x=[f"db={db}"])
    command.upgrade(cfg, "head")
    return db


# --- verify-data ------------------------------------------------------------

def test_repository_data_dir_is_clean_phase1():
    ok, messages = verify_data.verify(ROOT / "data")
    assert ok, messages
    assert any("No data files yet" in m for m in messages)


def _data_dir(tmp_path: Path, files: dict[str, bytes], listed: dict[str, bytes]) -> Path:
    d = tmp_path / "data"
    d.mkdir()
    for rel, content in files.items():
        (d / rel).parent.mkdir(parents=True, exist_ok=True)
        (d / rel).write_bytes(content)
    entries = [{"path": rel, "sha256": hashlib.sha256(c).hexdigest(), "bytes": len(c)} for rel, c in listed.items()]
    (d / "manifest.json").write_text(json.dumps({"schema_version": 1, "files": entries}))
    return d


def test_verify_data_accepts_matching_checksums(tmp_path):
    d = _data_dir(tmp_path, {"raw/a.bin": b"abc"}, {"raw/a.bin": b"abc"})
    ok, msgs = verify_data.verify(d)
    assert ok and msgs == ["OK        raw/a.bin"]


@pytest.mark.parametrize(
    ("files", "listed", "marker"),
    [
        ({"raw/a.bin": b"abd"}, {"raw/a.bin": b"abc"}, "CHECKSUM"),
        ({}, {"raw/a.bin": b"abc"}, "MISSING"),
        ({"raw/b.bin": b"x"}, {}, "UNLISTED"),
        ({"raw/a.bin": b"abcd"}, {"raw/a.bin": b"abc"}, "SIZE"),
    ],
)
def test_verify_data_detects_problems(tmp_path, files, listed, marker):
    ok, msgs = verify_data.verify(_data_dir(tmp_path, files, listed))
    assert not ok and any(m.startswith(marker) for m in msgs)


# --- backup / restore ---------------------------------------------------------

def test_backup_and_restore_round_trip(tmp_path, monkeypatch):
    # Migration 0004 now seeds planetary_body (earth/mars/moon), so the fixture
    # relies on that seed instead of inserting a synthetic row with a colliding id.
    db = _migrated(tmp_path / "live.sqlite")
    backups = tmp_path / "backups"
    path = backup_mod.backup(db, backups)
    # 20 real tables (8 Phase 1 + 9 Phase 2 + 3 comparison) + alembic_version = 21, at head revision 0006.
    assert path.exists() and backup_mod.describe(path) == {"integrity": "ok", "tables": 21, "revision": "0006"}

    with sqlite3.connect(db) as c:  # damage the live data after the backup
        c.execute("DELETE FROM planetary_body")
    monkeypatch.setattr(backup_mod, "backend_running", lambda: False)
    backup_mod.restore(db, path, backups, yes=True, force=False)

    with sqlite3.connect(db) as c:
        codes = {row[0] for row in c.execute("SELECT code FROM planetary_body")}
        assert codes == {"earth", "mars", "moon"}
        assert "STRICT" in c.execute("SELECT sql FROM sqlite_master WHERE name='measurement'").fetchone()[0]
    assert len(list(backups.glob("pre-restore-*.sqlite"))) == 1


def test_restore_refuses_while_backend_running(tmp_path, monkeypatch):
    db = _migrated(tmp_path / "live.sqlite")
    path = backup_mod.backup(db, tmp_path / "b")
    monkeypatch.setattr(backup_mod, "backend_running", lambda: True)
    with pytest.raises(SystemExit, match="backend is running"):
        backup_mod.restore(db, path, tmp_path / "b", yes=True, force=False)


def test_restore_rejects_corrupt_backup(tmp_path):
    bad = tmp_path / "bad.sqlite"
    bad.write_bytes(b"not a database")
    with pytest.raises(Exception):
        backup_mod.restore(tmp_path / "live.sqlite", bad, tmp_path, yes=True, force=True)


# --- port check -----------------------------------------------------------------

def test_portcheck_reports_busy_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        port = s.getsockname()[1]
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "portcheck.py"), str(port)],
                           capture_output=True, text=True)
    assert r.returncode == 1 and f"port {port} is already in use" in r.stderr


def test_portcheck_free_port_ok():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "portcheck.py"), str(port)], capture_output=True)
    assert r.returncode == 0


# --- GIS stack (Phase 1 install/import requirement) -----------------------------

def test_gis_stack_imports_and_smoke():
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "doctor.py")], capture_output=True, text=True)
    for check in ("numpy import + array maths", "pyproj IAU_2015 Mars CRS + transform",
                  "shapely WKT parse + validity", "rasterio GeoTIFF write/read in a Mars CRS",
                  "SQLite >= 3.37.0 (STRICT)"):
        assert f"| {check} | PASS |" in r.stdout, r.stdout
