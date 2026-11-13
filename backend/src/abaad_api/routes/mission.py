"""Mission Lab API: catalogue, scenarios, runs, comparison, line of sight and reports.

All mission calculations happen here on the server (``abaad_api.mission``);
the frontend only displays results and plays back saved frames.
"""

from __future__ import annotations

import base64
import binascii
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field

from ..config import get_settings
from ..db import get_engine
from ..errors import ApiError
from ..mission import REPORT_VERSION, store
from ..mission.catalog import OBJECTIVES, REGIONS, catalog, select_training_site
from ..mission.config import normalise, validate
from ..mission.los import line_of_sight
from ..mission.png import terrain_png
from ..mission.report import build_report, snapshot_sha256
from ..mission.service import comm_visibility, run_case, suggestions
from ..mission.terrain import BASE_XY, get_terrain

router = APIRouter(prefix="/mission", tags=["mission-lab"])


class ScenarioIn(BaseModel):
    body: str = "moon"
    region: str = "MOON-SOUTH-POLAR-6DEG"
    objective: str = "LUNAR-RECON-NAV"
    config: dict[str, Any] = Field(default_factory=dict)


class RunIn(BaseModel):
    case: str = "custom"
    config: dict[str, Any] | None = None


class LosIn(BaseModel):
    a: list[float]
    b: list[float]
    a_height_m: float = 1.5
    b_height_m: float = 3.0
    max_range_m: float | None = None


class ReportIn(BaseModel):
    viewer_snapshot_png: str | None = None  # data URL or base64 PNG from the 3D viewer


def _cfg_or_422(cfg: dict) -> dict:
    full = normalise(cfg)
    errors = validate(full)
    if errors:
        raise ApiError(422, "invalid_configuration", "Mission configuration is invalid.", errors)
    return full


def _scenario_or_404(sid: int) -> dict:
    sc = store.get_scenario(get_engine(), sid)
    if not sc:
        raise ApiError(404, "not_found", f"Scenario {sid} does not exist.")
    return sc


def _run_or_404(rid: int, frames: bool = True) -> dict:
    run = store.get_run(get_engine(), rid, with_frames=frames)
    if not run:
        raise ApiError(404, "not_found", f"Mission run {rid} does not exist.")
    return run


def _execute(sc: dict, cfg: dict, case: str, group: str | None) -> dict:
    started = store.now()
    result = run_case(cfg, case)
    rid = store.save_run(get_engine(), scenario_id=sc["id"], version=sc["version"], case=case, group=group,
                         result=result, started_at=started)
    return _run_or_404(rid)


@router.get("/catalog", summary="Destinations, reference regions, mission templates and sources")
def get_catalog() -> dict:
    return catalog()


@router.get("/training-sites", summary="Evidence-based Earth training-site selection for an objective")
def training_sites(objective: str = "LUNAR-RECON-NAV") -> dict:
    if objective not in {o["code"] for o in OBJECTIVES}:
        raise ApiError(404, "not_found", f"Unknown objective {objective}.")
    return select_training_site(get_engine(), objective)


@router.post("/scenarios", summary="Validate, plan routes, simulate and save a scenario with its first run")
def create_scenario(body: ScenarioIn) -> dict:
    if body.body != "moon":
        raise ApiError(422, "invalid_configuration", "Only the Moon is available in the Mission Lab MVP.")
    if body.region not in {r["code"] for r in REGIONS} or body.objective not in {o["code"] for o in OBJECTIVES}:
        raise ApiError(422, "invalid_configuration", "Unknown reference region or mission objective.")
    cfg = _cfg_or_422(body.config)
    site = select_training_site(get_engine(), body.objective)
    terrain = get_terrain(cfg["terrain_seed"], cfg["terrain_blockage"])
    sid = store.create_scenario(get_engine(), cfg=cfg, region=body.region, objective=body.objective,
                                site={**site["selected"], "curated_record_counts": site["curated_record_counts"]},
                                terrain_meta=terrain.metadata())
    sc = _scenario_or_404(sid)
    run = _execute(sc, cfg, "custom", None)
    return {"scenario": _scenario_or_404(sid), "run": run}


@router.get("/scenarios/{sid}")
def get_scenario(sid: int) -> dict:
    return _scenario_or_404(sid)


@router.get("/terrain", summary="Terrain grid, derived layers and template features (by terrain seed)")
def get_terrain_data(seed: int = 20261113, blockage: bool = False, step: int = Query(2, ge=1, le=8)) -> dict:
    t = get_terrain(seed, blockage)
    z = t.z[::step, ::step]
    return {
        "metadata": t.metadata(), "step": step, "rows": int(z.shape[0]), "cols": int(z.shape[1]),
        "spacing_m": t.cell * step, "origin_m": [t.cell / 2, t.cell / 2], "extent_m": t.extent_m,
        "elevation_m": [[round(float(v), 2) for v in row] for row in z],
        "hazards": t.hazards, "landmarks": t.landmarks, "base_xy": list(BASE_XY),
    }


@router.get("/terrain.png", summary="Terrain map image (hillshade, slope or communication visibility)")
def terrain_image(seed: int = 20261113, blockage: bool = False, layer: str = "hillshade", comm_mode: str = "direct",
                  relay_x: float | None = None, relay_y: float | None = None, max_slope_deg: float = 20.0) -> Response:
    if layer not in ("hillshade", "slope", "visibility"):
        raise ApiError(422, "validation_error", "layer must be hillshade, slope or visibility")
    cfg = normalise({"terrain_seed": seed, "terrain_blockage": blockage, "comm_mode": comm_mode,
                     "relay_xy": [relay_x, relay_y] if relay_x is not None and relay_y is not None else None,
                     "advanced": {"max_slope_deg": max_slope_deg}})
    t = get_terrain(seed, blockage)
    vis = comm_visibility(cfg) if layer == "visibility" else None
    return Response(terrain_png(t, layer, vis, max_slope_deg), media_type="image/png",
                    headers={"Cache-Control": "max-age=3600"})


@router.post("/los", summary="Geometric line of sight between two points, with terrain cross-section")
def los(body: LosIn, seed: int = 20261113, blockage: bool = False) -> dict:
    if len(body.a) != 2 or len(body.b) != 2:
        raise ApiError(422, "validation_error", "a and b must be [x, y] in metres")
    t = get_terrain(seed, blockage)
    out = line_of_sight(t, body.a, body.a_height_m, body.b, body.b_height_m, body.max_range_m or 1500.0,
                        with_profile=True)
    out["model"] = "geometric line of sight with lunar curvature; not an RF link budget; no signal strength"
    return out


@router.post("/suggestions", summary="Derived relay and beacon sites for a configuration (computed, not sourced)")
def get_suggestions(body: ScenarioIn) -> dict:
    return suggestions(_cfg_or_422(body.config))


@router.post("/scenarios/{sid}/runs", summary="Run the scenario again (custom or a comparison case)")
def create_run(sid: int, body: RunIn) -> dict:
    sc = _scenario_or_404(sid)
    if body.case not in ("custom", "baseline", "stress", "mitigated"):
        raise ApiError(422, "validation_error", "case must be custom, baseline, stress or mitigated")
    cfg = _cfg_or_422({**sc["config"], **(body.config or {})}) if body.config else sc["config"]
    return _execute(sc, cfg, body.case, None)


@router.post("/scenarios/{sid}/comparison", summary="Baseline, stress and mitigated runs of the same mission")
def comparison(sid: int) -> dict:
    sc = _scenario_or_404(sid)
    group = uuid.uuid4().hex[:12]
    runs = [_execute(sc, sc["config"], case, group) for case in ("baseline", "stress", "mitigated")]
    return {"group": group, "runs": [{k: v for k, v in r.items() if k != "frames"} for r in runs],
            "run_ids": [r["id"] for r in runs]}


@router.get("/runs/{rid}", summary="A saved mission run with routes, events and state frames")
def get_run(rid: int, frames: bool = True) -> dict:
    return _run_or_404(rid, frames)


def _report_dir() -> Path:
    d = get_settings().db_path.parent / "reports"
    d.mkdir(parents=True, exist_ok=True)
    return d


@router.post("/runs/{rid}/report", summary="Generate the Mission Operations Report for this exact saved run")
def create_report(rid: int, body: ReportIn | None = None) -> dict:
    run = _run_or_404(rid)
    if run["status"] == "NO_ROUTE":
        raise ApiError(409, "conflict", "This run has no route; there is nothing to report.")
    sc = _scenario_or_404(run["scenario_id"])
    eng = get_engine()
    group = store.latest_group(eng, sc["id"])
    comp = [store.get_run(eng, i, with_frames=False) for i in store.runs_in_group(eng, sc["id"], group)] if group else None
    png = None
    if body and body.viewer_snapshot_png:
        raw = body.viewer_snapshot_png.split(",", 1)[-1]
        try:
            data = base64.b64decode(raw, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ApiError(422, "validation_error", "viewer_snapshot_png is not valid base64") from exc
        if not data.startswith(b"\x89PNG") or len(data) > 6_000_000:
            raise ApiError(422, "validation_error", "viewer_snapshot_png must be a PNG under 6 MB")
        png = base64.b64encode(data).decode()
    sha = snapshot_sha256(run)
    tmp_path = _report_dir() / f"run-{rid}-{uuid.uuid4().hex[:8]}.html"
    rec = store.save_report(eng, run_id=rid, version=REPORT_VERSION, sha=sha, path=str(tmp_path), has_snapshot=bool(png))
    tmp_path.write_text(build_report(run, sc, comp, png, report_id=rec["id"]), encoding="utf-8")
    return {**rec, "url": f"/api/v1/mission/reports/{rec['id']}"}


@router.get("/reports/{rep_id}", summary="The generated report (print-ready HTML)", response_class=HTMLResponse)
def get_report(rep_id: int, download: bool = False) -> HTMLResponse:
    rec = store.get_report(get_engine(), rep_id)
    if not rec or not Path(rec["artifact_path"]).exists():
        raise ApiError(404, "not_found", f"Report {rep_id} does not exist.")
    headers = {"Content-Disposition": f'attachment; filename="abaad-mission-report-run{rec["run_id"]}-{rep_id}.html"'} \
        if download else {}
    return HTMLResponse(Path(rec["artifact_path"]).read_text(encoding="utf-8"), headers=headers)
