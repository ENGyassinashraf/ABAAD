"""Comparison engine: API behaviour on the real curated data, and the
database rules that keep dimension assessments traceable (Guide §06, §14)."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import load_curation  # noqa: E402

from abaad_api import db as dbmod

from .conftest import raw


@pytest.fixture
def loaded_db(migrated_db: Path) -> Path:
    load_curation.load_all(migrated_db)
    return migrated_db


@pytest.fixture
def client(monkeypatch, loaded_db: Path) -> TestClient:
    monkeypatch.setenv("ABAAD_DB_PATH", str(loaded_db))
    monkeypatch.delenv("ABAAD_ALLOW_UNPUBLISHED_API", raising=False)
    dbmod.get_engine.cache_clear()
    from abaad_api.main import create_app
    yield TestClient(create_app(), raise_server_exceptions=False)
    dbmod.get_engine.cache_clear()


def _compare(client, reference, task):
    r = client.get("/api/v1/compare", params={"reference": reference, "task": task})
    assert r.status_code == 200, r.text
    return r.json()


def _cand(body, code):
    return next(c for c in body["candidates"] if c["region"]["code"] == code)


# --- options --------------------------------------------------------------------

def test_options_list_scope_references_with_valid_tasks(client):
    body = client.get("/api/v1/compare/options").json()
    refs = {r["region"]["code"]: r for r in body["references"]}
    for code in ("MARS-GALE-CRATER", "MARS-BAGNOLD-DUNES", "MARS-JEZERO-CRATER", "MOON-SOUTH-POLE", "MOON-SHACKLETON-CRATER"):
        assert code in refs
    assert {t["code"] for t in refs["MOON-SOUTH-POLE"]["tasks"]} == {"rover_mobility"}  # only 'both' tasks for the Moon
    assert "aeolian_geomorphology" in {t["code"] for t in refs["MARS-BAGNOLD-DUNES"]["tasks"]}
    assert refs["MARS-GALE-CRATER"]["region"]["geometry"]["lat"] == -5.44
    assert refs["MARS-BAGNOLD-DUNES"]["region"]["geometry"] is None
    assert refs["MARS-BAGNOLD-DUNES"]["region"]["geometry_gap"]


# --- the three Project Scope MVP comparisons -------------------------------------

def test_western_desert_vs_bagnold_aeolian(client):
    body = _compare(client, "MARS-BAGNOLD-DUNES", "aeolian_geomorphology")
    wd = _cand(body, "EG-WD")
    assert wd["status"] == "ranked" and wd["rank"] == 1
    assert wd["score"] == 64.3 and wd["coverage"] == 70.0
    assessed = {d["dimension"]: d for d in wd["dimensions"] if d["similarity"] is not None}
    assert assessed["surface_processes"]["rubric_level"] == "close"
    assert assessed["surface_processes"]["analog_source"]["doi"] == "10.1029/JB084iB14p08205"
    assert assessed["surface_processes"]["reference_source"]["url"].endswith("two-types-of-dunes/")
    unknown = {d["dimension"] for d in wd["dimensions"] if d["similarity"] is None}
    assert unknown == {"environment", "geology_materials"}  # unknown, not zero


def test_dakhla_vs_jezero_fluvial(client):
    dk = _cand(_compare(client, "MARS-JEZERO-CRATER", "fluvial_paleohydrology"), "EG-WD-DAKHLA")
    assert dk["status"] == "ranked" and dk["score"] == 41.7 and dk["coverage"] == 60.0
    assert dk["claims"] and dk["claims"][0]["reference_pairing_basis"] == "project_decision_provisional"


def test_gilf_kebir_gpr_ranked_vs_jezero_but_insufficient_vs_gale(client):
    jz = _cand(_compare(client, "MARS-JEZERO-CRATER", "shallow_subsurface_gpr"), "EG-WD-GILF-KEBIR")
    assert jz["status"] == "ranked" and jz["score"] == 45.0 and jz["coverage"] == 50.0
    gale = _cand(_compare(client, "MARS-GALE-CRATER", "shallow_subsurface_gpr"), "EG-WD-GILF-KEBIR")
    assert gale["status"] == "insufficient_evidence" and gale["score"] is None and gale["rank"] is None
    assert gale["coverage"] == 10.0


def test_moon_reports_documented_mismatch_and_ranks_nobody(client):
    body = _compare(client, "MOON-SOUTH-POLE", "rover_mobility")
    assert all(c["rank"] is None and c["score"] is None for c in body["candidates"])
    gk = _cand(body, "EG-WD-GILF-KEBIR")
    env = next(d for d in gk["dimensions"] if d["dimension"] == "environment")
    assert env["rubric_level"] == "mismatch" and env["similarity"] == 0.0


# --- ordering, grouping, contract -----------------------------------------------------

def test_egyptian_candidates_first_among_unranked(client):
    body = _compare(client, "MARS-GALE-CRATER", "rover_mobility")
    groups = [c["region"]["group"] for c in body["candidates"]]
    assert groups[:3] == ["egyptian"] * 3
    assert set(groups[3:]) == {"global"}


def test_all_earth_analogs_are_candidates(client):
    body = _compare(client, "MARS-GALE-CRATER", "rover_mobility")
    codes = {c["region"]["code"] for c in body["candidates"]}
    assert {"EG-WD", "EG-WD-DAKHLA", "EG-WD-GILF-KEBIR", "CL-ATACAMA-ARADS-SITE", "IS-HOLUHRAUN", "AQ-MDV"} <= codes
    assert not any(c.startswith("MARS-") or c.startswith("MOON-") for c in codes)


def test_draft_claim_text_hidden_without_local_gate(client):
    dk = _cand(_compare(client, "MARS-JEZERO-CRATER", "fluvial_paleohydrology"), "EG-WD-DAKHLA")
    claim = dk["claims"][0]
    assert claim["unpublished"] is True and claim["supported_claim"] is None
    assert claim["limitations"]  # cautions are always shown
    assert claim["claim_evidence_class"]["label"]


def test_draft_claim_text_shown_with_local_gate(client, monkeypatch):
    monkeypatch.setenv("ABAAD_ALLOW_UNPUBLISHED_API", "1")
    dk = _cand(_compare(client, "MARS-JEZERO-CRATER", "fluvial_paleohydrology"), "EG-WD-DAKHLA")
    assert dk["claims"][0]["supported_claim"]


def test_method_and_limitations_always_present_and_no_bare_percentage(client):
    body = _compare(client, "MARS-BAGNOLD-DUNES", "aeolian_geomorphology")
    assert "Coverage" in body["method"]["coverage_formula"]
    assert body["limitations"]
    assert "not a percentage similarity" in body["method"]["not_a_similarity_percentage"]
    for c in body["candidates"]:  # a score is only ever reported next to its coverage and status
        assert set(c) == {"region", "status", "score", "coverage", "rank", "dimensions", "claims"}


@pytest.mark.parametrize(
    ("params", "status"),
    [
        ({"reference": "NOPE", "task": "aeolian_geomorphology"}, 404),
        ({"reference": "MARS-GALE-CRATER", "task": "nope"}, 404),
        ({"reference": "EG-WD", "task": "aeolian_geomorphology"}, 422),
        ({"reference": "MOON-SOUTH-POLE", "task": "aeolian_geomorphology"}, 422),
        ({"reference": "MARS-GALE-CRATER"}, 422),
    ],
)
def test_compare_errors_use_error_shape(client, params, status):
    r = client.get("/api/v1/compare", params=params)
    assert r.status_code == status
    assert set(r.json()) == {"code", "message", "details"}


def test_compare_is_get_only(client):
    assert client.post("/api/v1/compare").status_code == 405


# --- database rules for assessments -------------------------------------------------

def _ids(conn, *codes):
    return [conn.execute("SELECT id FROM region WHERE code = ?", (c,)).fetchone()[0] for c in codes]


INSERT = (
    "INSERT INTO dimension_assessment (analog_region_id, reference_region_id, dimension_id, rubric_level, similarity,"
    " evidence_basis, rationale, analog_publication_id, analog_locator, reference_publication_id, reference_locator)"
    " VALUES (?, ?, (SELECT id FROM comparison_dimension WHERE code = 'geology_materials'), ?, ?, 'hypothesized', 'x', 1, 'x', 1, 'x')"
)


def test_similarity_must_match_rubric_level(loaded_db):
    conn = raw(loaded_db)
    analog, ref = _ids(conn, "EG-WD", "MARS-GALE-CRATER")
    with pytest.raises(sqlite3.IntegrityError, match="similarity_matches_rubric"):
        conn.execute(INSERT, (analog, ref, "close", 0.9))
    conn.execute(INSERT, (analog, ref, "close", 0.75))


def test_assessment_roles_enforced(loaded_db):
    conn = raw(loaded_db)
    mars_a, mars_b = _ids(conn, "MARS-GALE-CRATER", "MARS-JEZERO-CRATER")
    with pytest.raises(sqlite3.IntegrityError, match="analog must be an Earth analog"):
        conn.execute(INSERT, (mars_a, mars_b, "weak", 0.25))


def test_region_immutable_once_assessed(loaded_db):
    conn = raw(loaded_db)
    with pytest.raises(sqlite3.IntegrityError, match="dimension_assessment references"):
        conn.execute("UPDATE region SET region_role = 'analog' WHERE code = 'MARS-BAGNOLD-DUNES'")
