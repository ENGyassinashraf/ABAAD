"""Mission Lab API tests on a throwaway migrated database (synthetic runs only)."""

from __future__ import annotations

import base64
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import abaad_api.db as dbmod
from abaad_api.main import create_app

PNG_1PX = base64.b64encode(bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108020000009077"
    "53de0000000c4944415408d763f8ffff3f0005fe02fea7d6a4c90000000049454e44ae426082")).decode()


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    from .conftest import upgrade

    db = tmp_path_factory.mktemp("mission") / "api.sqlite"
    upgrade(db)
    mp = pytest.MonkeyPatch()
    mp.setenv("ABAAD_DB_PATH", str(db))
    dbmod.get_engine.cache_clear()
    yield TestClient(create_app(), raise_server_exceptions=False)
    mp.undo()
    dbmod.get_engine.cache_clear()


@pytest.fixture(scope="module")
def created(client):
    r = client.post("/api/v1/mission/scenarios", json={"config": {}})
    assert r.status_code == 200, r.text
    return r.json()


def test_catalog_and_training_site_selection_is_honest(client):
    c = client.get("/api/v1/mission/catalog").json()
    assert [b["code"] for b in c["bodies"] if b["available"]] == ["moon"]
    assert c["regions"][0]["bounds"]["basis"] == "project_curated"
    assert {s["id"] for s in c["sources"]} >= {"SRC-NASA-ARTEMIS3-REGIONS-2022", "SRC-NASA-LUGRE-2025"}
    s = client.get("/api/v1/mission/training-sites").json()
    assert s["candidates"] == [] and s["curated_record_counts"]["earth_analog_regions"] == 0
    assert s["selected"]["kind"] == "synthetic_environment" and s["selected"]["is_validated_lunar_analog"] is False


def test_create_scenario_saves_scenario_run_routes_and_events(client, created):
    sc, run = created["scenario"], created["run"]
    assert sc["data_status"] == "synthetic" and sc["training_site"]["label"] == "Synthetic / Demonstration"
    assert run["scenario_id"] == sc["id"] and run["case_label"] == "custom"
    assert run["routes"]["recommended"]["is_demonstration"] is True
    assert len(run["frames"]) == run["frame_count"] > 100
    assert [e["seq"] for e in run["events"]] == list(range(1, len(run["events"]) + 1))
    again = client.get(f"/api/v1/mission/runs/{run['id']}").json()
    assert again["events"] == run["events"] and again["summary"] == run["summary"]


def test_invalid_configuration_and_no_route_states(client):
    r = client.post("/api/v1/mission/scenarios", json={"config": {"comm_mode": "laser"}})
    assert r.status_code == 422 and r.json()["code"] == "invalid_configuration"
    assert client.post("/api/v1/mission/scenarios", json={"body": "mars"}).status_code == 422
    hz = client.get("/api/v1/mission/terrain").json()["hazards"][0]
    r = client.post("/api/v1/mission/scenarios", json={"config": {"target_xy": [hz["x"], hz["y"]]}}).json()
    assert r["run"]["status"] == "NO_ROUTE" and "no-go" in r["run"]["summary"]["reasons"][0]
    assert client.post(f"/api/v1/mission/runs/{r['run']['id']}/report").status_code == 409


def test_rerun_with_changed_controls_changes_results(client, created):
    sid = created["scenario"]["id"]
    r = client.post(f"/api/v1/mission/scenarios/{sid}/runs",
                    json={"case": "custom", "config": {"autonomy": False, "terrain_blockage": True}}).json()
    assert r["status"] == "SAFE_HOLD" and r["config"]["autonomy"] is False


def test_line_of_sight_endpoint_and_images(client):
    r = client.post("/api/v1/mission/los", json={"a": [150, 170], "b": [1060, 1040]}).json()
    assert r["status"] == "BLOCKED_BY_TERRAIN" and r["obstructions"] and r["profile"]
    assert "not an RF link budget" in r["model"]
    img = client.get("/api/v1/mission/terrain.png?layer=visibility")
    assert img.status_code == 200 and img.content.startswith(b"\x89PNG")
    assert client.get("/api/v1/mission/terrain.png?layer=rssi").status_code == 422


def test_comparison_and_report_from_the_exact_saved_run(client, created):
    sid = created["scenario"]["id"]
    cmp = client.post(f"/api/v1/mission/scenarios/{sid}/comparison").json()
    by = {r["case_label"]: r for r in cmp["runs"]}
    assert set(by) == {"baseline", "stress", "mitigated"}
    assert by["stress"]["status"] == "SAFE_HOLD" and by["mitigated"]["summary"]["science_result"] == "COMPLETED"
    rid = by["mitigated"]["id"]
    rep = client.post(f"/api/v1/mission/runs/{rid}/report", json={"viewer_snapshot_png": f"data:image/png;base64,{PNG_1PX}"}).json()
    assert rep["has_viewer_snapshot"] is True and len(rep["snapshot_sha256"]) == 64
    html = client.get(rep["url"]).text
    for n, name in enumerate(["Executive Mission Brief", "Earth Analog Selection Rationale", "Site and Terrain Data",
                              "Mission Objectives", "Training Scenario Configuration", "Recommended Route",
                              "Step-by-Step Field Operations Runbook", "Communication Plan", "Navigation and Autonomy Plan",
                              "Risks and Mitigations", "Mission Results", "Operational Recommendations",
                              "Assumptions and Limitations", "References and Provenance", "Appendix"], 1):
        assert f"<h2>{n}. {name}</h2>" in html, name
    assert f"Run #{rid}" in html and rep["snapshot_sha256"] in html
    assert "SYNTHETIC / DEMONSTRATION" in html and "no RSSI" in html
    assert "dBm" not in html.replace("no dBm", "")
    assert "baseline / stress / mitigated comparison" in html.lower()
    assert len(re.findall(r"<h3>Step \d+\.", html)) >= 12
    # regeneration from the same saved run gives the same snapshot hash
    rep2 = client.post(f"/api/v1/mission/runs/{rid}/report").json()
    assert rep2["snapshot_sha256"] == rep["snapshot_sha256"] and rep2["id"] != rep["id"]
    dl = client.get(f"{rep['url']}?download=true")
    assert "attachment" in dl.headers["content-disposition"]
    assert Path(rep["artifact_path"]).exists()


def test_report_rejects_non_png_snapshot_and_unknown_ids(client, created):
    rid = created["run"]["id"]
    bad = client.post(f"/api/v1/mission/runs/{rid}/report", json={"viewer_snapshot_png": base64.b64encode(b"hello").decode()})
    assert bad.status_code == 422
    assert client.get("/api/v1/mission/runs/999999").status_code == 404
    assert client.get("/api/v1/mission/reports/999999").json()["code"] == "not_found"
