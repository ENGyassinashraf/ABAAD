"""Tests for the curation loader: the committed curation/*.json files load
cleanly and idempotently, and the session's evidence-class correction
("never assign A from an abstract alone") is enforced at load time."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import load_curation as lc  # noqa: E402


def _migrated(db: Path) -> Path:
    cfg = Config(str(ROOT / "backend" / "alembic.ini"))
    cfg.cmd_opts = argparse.Namespace(x=[f"db={db}"])
    command.upgrade(cfg, "head")
    return db


def test_real_curation_files_load_cleanly(tmp_path):
    db = _migrated(tmp_path / "live.sqlite")
    counts = lc.load_all(db)
    assert counts["sources"] == 11
    assert counts["regions"] == 12
    assert counts["datasets"] == 4

    conn = sqlite3.connect(db)
    assert conn.execute("SELECT count(*) FROM site_task_claim").fetchone()[0] == 8
    assert conn.execute("SELECT count(*) FROM region_alias").fetchone()[0] == 1
    assert conn.execute("SELECT count(*) FROM coverage_gap").fetchone()[0] == 10
    # Session correction 1: no claim exists on CL-ATACAMA itself (the former "C4"
    # Atacama-wide drilling claim is removed), and the ARADS feature carries
    # exactly one claim sourced only from Stoker et al. 2023 (S08). Hardening
    # F-06 downgrades it from A to B: S08 was read to only ~80%, so it is
    # 'partial_full_text', not 'full_text_checked'.
    atacama_claims = conn.execute(
        "SELECT count(*) FROM site_task_claim stc JOIN region r ON r.id = stc.analog_region_id"
        " WHERE r.code = 'CL-ATACAMA'"
    ).fetchone()[0]
    assert atacama_claims == 0
    arads_class = conn.execute(
        "SELECT stc.claim_evidence_class FROM site_task_claim stc JOIN region r ON r.id = stc.analog_region_id"
        " WHERE r.code = 'CL-ATACAMA-ARADS-SITE'"
    ).fetchone()
    assert arads_class == ("B",)
    arads_reference_body = conn.execute(
        "SELECT b.code FROM site_task_claim stc JOIN region r ON r.id = stc.analog_region_id"
        " JOIN planetary_body b ON b.id = stc.reference_body_id WHERE r.code = 'CL-ATACAMA-ARADS-SITE'"
    ).fetchone()
    assert arads_reference_body == ("mars",)
    yungay_life_detection_claims = conn.execute(
        "SELECT count(*) FROM site_task_claim stc JOIN region r ON r.id = stc.analog_region_id"
        " JOIN research_task t ON t.id = stc.task_id"
        " WHERE r.code = 'CL-ATACAMA-YUNGAY' AND t.code = 'life_detection_drilling'"
    ).fetchone()[0]
    assert yungay_life_detection_claims == 0
    conn.close()


def test_loading_twice_is_idempotent(tmp_path):
    db = _migrated(tmp_path / "live.sqlite")
    lc.load_all(db)
    lc.load_all(db)
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT count(*) FROM region").fetchone()[0] == 12
    assert conn.execute("SELECT count(*) FROM site_task_claim").fetchone()[0] == 8
    assert conn.execute("SELECT count(*) FROM site_task_claim_source").fetchone()[0] == 11
    conn.close()


def test_class_a_rejected_without_full_text_support(tmp_path, monkeypatch):
    """The session correction: class A must never rest on an abstract-only source."""
    db = _migrated(tmp_path / "live.sqlite")

    def _bad_claims(_name: str) -> dict:
        return {
            "claims": [
                {
                    "code": "BAD-1", "analog_region_code": "EG-WD", "task_code": "aeolian_geomorphology",
                    "reference_region_code": None, "reference_body": "mars", "claim_evidence_class": "A",
                    "reference_pairing_basis": "body_level_only",
                    "supported_claim": "x", "similarities": "x", "differences": "x",
                    "not_supported": "x", "spatial_scale": "x", "limitations": "x",
                    "sources": [{"source_code": "S01", "role": "supports", "locator": "abstract"}],
                }
            ]
        }

    conn = sqlite3.connect(db, isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON")
    source_codes = lc.load_sources(conn)
    region_codes = lc.load_regions(conn)

    monkeypatch.setattr(lc, "_load_json", lambda name: _bad_claims(name) if name == "claims.json" else lc._load_json(name))
    with pytest.raises(lc.CurationError, match="class A requires"):
        lc.load_claims(conn, region_codes, source_codes)
    conn.close()


def test_missing_required_field_is_rejected(tmp_path, monkeypatch):
    db = _migrated(tmp_path / "live.sqlite")

    def _incomplete_regions(_name: str) -> dict:
        return {"regions": [{"code": "X", "body": "earth"}]}  # missing region_role, etc.

    conn = sqlite3.connect(db, isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON")
    monkeypatch.setattr(lc, "_load_json", _incomplete_regions)
    with pytest.raises(lc.CurationError, match="missing required field"):
        lc.load_regions(conn)
    conn.close()


def test_curation_files_are_valid_json():
    for name in ("sources.json", "regions.json", "geometries.json", "claims.json", "datasets.json"):
        json.loads((ROOT / "curation" / name).read_text())
