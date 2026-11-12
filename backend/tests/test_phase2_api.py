"""Read-only API tests for the Phase 2 endpoints: bodies, regions, tasks,
claims, sources, datasets, assets and coverage. All GET, same error shape
as Phase 1, no numeric score field, unpublished/class-C claims hidden by
default, missing values never rendered as zero/empty."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import load_curation  # noqa: E402

from abaad_api import db as dbmod


@pytest.fixture
def client(monkeypatch, migrated_db: Path) -> TestClient:
    load_curation.load_all(migrated_db)
    monkeypatch.setenv("ABAAD_DB_PATH", str(migrated_db))
    dbmod.get_engine.cache_clear()
    from abaad_api.main import create_app
    c = TestClient(create_app(), raise_server_exceptions=False)
    yield c
    dbmod.get_engine.cache_clear()


@pytest.fixture
def local_client(monkeypatch, client: TestClient) -> TestClient:
    """Hardening F-09: include_unpublished=true needs this env var set; it is
    restricted to local/test use, never a production default."""
    monkeypatch.setenv("ABAAD_ALLOW_UNPUBLISHED_API", "1")
    return client


def test_bodies_lists_three(client):
    r = client.get("/api/v1/bodies")
    assert r.status_code == 200
    assert {b["code"] for b in r.json()} == {"earth", "mars", "moon"}


def test_tasks_footer_explains_evidence_classes(client):
    r = client.get("/api/v1/tasks")
    body = r.json()
    assert len(body["items"]) == 8  # 7 Phase 2 tasks + rover_mobility (0006)
    assert "claim_evidence_class" in body["footer"] and "evidence_grade" in body["footer"]


def test_regions_paging_and_filters(client):
    r = client.get("/api/v1/regions", params={"body": "mars", "role": "reference"})
    body = r.json()
    assert body["total"] == 6  # 3 Phase 2 + Gale, Bagnold Dunes, Jezero (Project Scope)
    assert all(item["body"] == "mars" for item in body["items"])


def test_region_detail_includes_hierarchy_and_alias(client):
    r = client.get("/api/v1/regions/EG-WD-GILF-KEBIR")
    body = r.json()
    assert body["name"] == "Gilf Kebir crater-like structures"
    assert body["origin_status"] == "disputed"
    assert body["parent_code"] == "EG-WD"
    assert body["aliases"] == [{"alias": "Gilf Kebir Crater Field", "alias_kind": "legacy", "language": None}]


def test_region_not_found_uses_error_shape(client):
    r = client.get("/api/v1/regions/does-not-exist")
    assert r.status_code == 404
    assert set(r.json()) == {"code", "message", "details"}


def test_arads_site_has_source_traced_point_geometry(client):
    r = client.get("/api/v1/regions/CL-ATACAMA-ARADS-SITE/geometries")
    geoms = r.json()
    assert len(geoms) == 1
    assert geoms[0]["geometry_status"] == "source_traced"
    assert geoms[0]["geometry_role"] == "point_locator"


def test_claims_hide_drafts_and_class_c_by_default(local_client):
    r = local_client.get("/api/v1/claims")
    assert r.json()["total"] == 0  # every seeded claim is still 'draft'

    r2 = local_client.get("/api/v1/claims", params={"include_unpublished": "true"})
    body = r2.json()
    assert body["total"] == 11
    assert all(item["unpublished"] for item in body["items"])
    classes = {item["claim_evidence_class"]["code"] for item in body["items"]}
    # Zero class-A claims is intentional (no supporting source read to completion);
    # C3 moved from C to B once S02's abstract was verified via Crossref.
    assert classes == {"B"}
    for item in body["items"]:
        assert item["claim_evidence_class"]["label"]  # never a bare letter
        assert item["reference_body"] == "mars"


def test_include_unpublished_forbidden_without_local_gate(client):
    r = client.get("/api/v1/claims", params={"include_unpublished": "true"})
    assert r.status_code == 403
    assert r.json()["code"] == "forbidden"


def test_claim_evidence_class_never_a_bare_letter(client):
    r = client.get("/api/v1/claims/1")
    body = r.json()
    assert body["claim_evidence_class"] == {"code": "B", "label": "Direct but partially accessible evidence"}


def test_no_numeric_score_field_anywhere(client):
    r = client.get("/api/v1/claims", params={"include_unpublished": "true"})
    text_ = r.text.lower()
    for forbidden in ("similarity_score", "\"score\"", "percent_similar"):
        assert forbidden not in text_


def test_atacama_arads_claim_never_attached_to_yungay(local_client):
    r = local_client.get("/api/v1/claims", params={"include_unpublished": "true", "region": "CL-ATACAMA-YUNGAY"})
    tasks = {item["task_code"] for item in r.json()["items"]}
    assert "life_detection_drilling" not in tasks


def test_sources_paged(client):
    r = client.get("/api/v1/sources", params={"limit": 2})
    body = r.json()
    assert body["limit"] == 2 and len(body["items"]) == 2 and body["total"] == 23


def test_datasets_list_and_detail(client):
    r = client.get("/api/v1/datasets")
    codes = {d["code"] for d in r.json()}
    assert codes == {"DS-01", "DS-03", "DS-04", "DS-05"}

    r2 = client.get("/api/v1/datasets/DS-05")
    assert r2.status_code == 200
    assert r2.json()["body"] == "moon"
    assert r2.json()["asset_count"] == 0


def test_dataset_not_found(client):
    r = client.get("/api/v1/datasets/DS-99")
    assert r.status_code == 404


def test_coverage_never_renders_missing_as_zero(client):
    r = client.get("/api/v1/coverage", params={"body": "earth"})
    for cell in r.json():
        assert cell["status"] in ("present", "gap", "not_yet_curated")
        if cell["status"] == "gap":
            assert cell["gap"]["reason"]


def test_coverage_marks_arabia_terra_geometry_present(client):
    r = client.get("/api/v1/coverage", params={"body": "mars"})
    cells = {(c["region_code"], c["slot"]): c["status"] for c in r.json()}
    assert cells[("MARS-ARABIA-TERRA", "geometry")] == "present"
    assert cells[("MARS-NORTH-POLAR-SAND-SEA", "geometry")] == "gap"


def test_assets_endpoint_no_file_serving_and_404_when_absent(client):
    r = client.get("/api/v1/assets/1")
    assert r.status_code == 404


def test_only_get_is_allowed(client):
    r = client.post("/api/v1/regions")
    assert r.status_code == 405


def test_openapi_lists_phase2_paths(client):
    spec = client.get("/api/v1/openapi.json").json()
    for path in ("/api/v1/regions", "/api/v1/claims", "/api/v1/datasets", "/api/v1/coverage"):
        assert path in spec["paths"]
