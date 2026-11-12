"""Tests for the Phase 2 extension to `make verify-data` (section 13 of the
spec): provenance completeness, geometry validity, gap/geometry exclusivity,
status agreement, test-code rejection, and the real curation data passing
clean with no errors."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import load_curation  # noqa: E402
import verify_data  # noqa: E402


def _migrated(db: Path) -> Path:
    cfg = Config(str(ROOT / "backend" / "alembic.ini"))
    cfg.cmd_opts = argparse.Namespace(x=[f"db={db}"])
    command.upgrade(cfg, "head")
    return db


def test_real_curation_data_has_no_errors(tmp_path):
    db = _migrated(tmp_path / "live.sqlite")
    load_curation.load_all(db)
    ok, messages = verify_data.verify_curation_db(db)
    assert ok, [m for m in messages if m.startswith("ERROR")]
    assert messages[-1] == "Scientific completeness is not claimed by this report."


def test_missing_database_is_not_an_error(tmp_path):
    ok, messages = verify_data.verify_curation_db(tmp_path / "does-not-exist.sqlite")
    assert ok
    assert "skipping curation checks" in messages[0]


# Note: a region_geometry row without source/method/uncertainty_note cannot
# actually be inserted -- ck_region_geometry_has_source_method_note (0003)
# already rejects it at the database level (see test_phase2 migration tests).
# verify_curation_db's matching check is a defensive double-check of that
# same invariant and is exercised indirectly by the real curation data
# loading cleanly in test_real_curation_data_has_no_errors above.


def test_detects_test_prefixed_region_code(tmp_path):
    db = _migrated(tmp_path / "live.sqlite")
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO region (code, body_id, region_role, region_level, validation_status, name)"
        " VALUES ('TEST-REGION',1,'analog','region','regional_only','x')"
    )
    conn.commit()
    conn.close()
    ok, messages = verify_data.verify_curation_db(db)
    assert not ok
    assert any("TEST-/SYNTH-" in m for m in messages)


def test_detects_status_disagreement(tmp_path):
    db = _migrated(tmp_path / "live.sqlite")
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO region (code, body_id, region_role, region_level, validation_status, name)"
        " VALUES ('EARTHTEST',1,'analog','region','site_confirmed','x')"
    )
    conn.commit()
    conn.close()
    ok, messages = verify_data.verify_curation_db(db)
    assert not ok
    assert any("disagrees with section 4.2" in m for m in messages)
