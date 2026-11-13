"""Persistence of scenarios, runs, routes, events and reports (SQLite)."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import Engine, text

from . import SIMULATION_MODEL_VERSION


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _j(v) -> str:
    return json.dumps(v, separators=(",", ":"), sort_keys=True)


def create_scenario(engine: Engine, *, cfg: dict, region: str, objective: str, site: dict, terrain_meta: dict) -> int:
    with engine.begin() as c:
        r = c.execute(text(
            "INSERT INTO mission_scenario (body_code, reference_region_code, objective_code, training_site_kind, "
            "training_site_region_id, training_site_json, terrain_json, data_status, config_json, model_version) "
            "VALUES ('moon', :region, :objective, :kind, NULL, :site, :terrain, 'synthetic', :cfg, :mv)"),
            {"region": region, "objective": objective, "kind": site["kind"], "site": _j(site),
             "terrain": _j(terrain_meta), "cfg": _j(cfg), "mv": SIMULATION_MODEL_VERSION})
        return int(r.lastrowid)


def get_scenario(engine: Engine, sid: int) -> dict | None:
    with engine.connect() as c:
        row = c.execute(text("SELECT * FROM mission_scenario WHERE id = :id"), {"id": sid}).mappings().first()
        if not row:
            return None
        runs = c.execute(text("SELECT id, case_label, comparison_group, status, started_at FROM mission_run "
                              "WHERE scenario_id = :id ORDER BY id"), {"id": sid}).mappings().all()
    d = dict(row)
    for k in ("training_site_json", "terrain_json", "config_json"):
        d[k.removesuffix("_json")] = json.loads(d.pop(k))
    d["runs"] = [dict(r) for r in runs]
    return d


def save_run(engine: Engine, *, scenario_id: int, version: int, case: str, group: str | None, result: dict,
             started_at: str) -> int:
    cfg, routes, sim = result["config"], result["routes"], result["sim"]
    if sim is None:
        status, summary, phases, frames = "NO_ROUTE", {"status": "NO_ROUTE", "reasons": routes["reasons"]}, [], []
    else:
        status, summary, phases, frames = sim["summary"]["status"], sim["summary"], sim["phases"], sim["frames"]
    with engine.begin() as c:
        rid = int(c.execute(text(
            "INSERT INTO mission_run (scenario_id, scenario_version, case_label, comparison_group, seed, "
            "config_snapshot_json, status, summary_json, phases_json, frames_json, simulation_version, started_at, ended_at) "
            "VALUES (:s, :v, :case, :g, :seed, :cfg, :status, :summary, :phases, :frames, :sv, :st, :en)"),
            {"s": scenario_id, "v": version, "case": case, "g": group, "seed": cfg["seed"], "cfg": _j(cfg),
             "status": status, "summary": _j(summary), "phases": _j(phases), "frames": _j(frames),
             "sv": SIMULATION_MODEL_VERSION, "st": started_at, "en": _now()}).lastrowid)
        meta = {"status": routes["status"], "reasons": routes["reasons"], "alternate_note": routes.get("alternate_note"),
                "demonstration_reason": routes.get("demonstration_reason")}
        for kind in ("recommended", "alternate"):
            rt = routes.get(kind)
            if rt is None and not (kind == "recommended"):
                continue
            c.execute(text(
                "INSERT INTO mission_route (run_id, kind, planner_version, weights_json, constraints_json, route_json, "
                "is_demonstration) VALUES (:r, :k, :pv, :w, :hc, :route, :demo)"),
                {"r": rid, "k": kind, "pv": routes["planner_version"], "w": _j(routes["weights"]),
                 "hc": _j(routes["hard_constraints"]), "route": _j({**(rt or {}), "meta": meta}),
                 "demo": 1 if routes["is_demonstration"] else 0})
        for e in (sim["events"] if sim else []):
            c.execute(text(
                "INSERT INTO mission_event (run_id, seq, sim_time_s, event_type, phase, x_m, y_m, payload_json, result) "
                "VALUES (:r, :seq, :t, :type, :ph, :x, :y, :p, :res)"),
                {"r": rid, "seq": e["seq"], "t": e["t"], "type": e["type"], "ph": e["phase"], "x": e["x"], "y": e["y"],
                 "p": _j(e["payload"]), "res": e["result"]})
    return rid


def get_run(engine: Engine, rid: int, with_frames: bool = True) -> dict | None:
    with engine.connect() as c:
        row = c.execute(text("SELECT * FROM mission_run WHERE id = :id"), {"id": rid}).mappings().first()
        if not row:
            return None
        routes = c.execute(text("SELECT * FROM mission_route WHERE run_id = :id ORDER BY kind DESC"),
                           {"id": rid}).mappings().all()
        events = c.execute(text("SELECT seq, sim_time_s, event_type, phase, x_m, y_m, payload_json, result "
                                "FROM mission_event WHERE run_id = :id ORDER BY seq"), {"id": rid}).mappings().all()
    d = dict(row)
    d["config"] = json.loads(d.pop("config_snapshot_json"))
    d["summary"] = json.loads(d.pop("summary_json"))
    d["phases"] = json.loads(d.pop("phases_json"))
    frames = json.loads(d.pop("frames_json"))
    if with_frames:
        d["frames"] = frames
    d["frame_count"] = len(frames)
    d["routes"] = {}
    for r in routes:
        route = json.loads(r["route_json"])
        d["routes"][r["kind"]] = {**route, "planner_version": r["planner_version"],
                                  "weights": json.loads(r["weights_json"]),
                                  "hard_constraints": json.loads(r["constraints_json"]),
                                  "is_demonstration": bool(r["is_demonstration"])}
    d["events"] = [{"seq": e["seq"], "t": e["sim_time_s"], "type": e["event_type"], "phase": e["phase"],
                    "x": e["x_m"], "y": e["y_m"], "payload": json.loads(e["payload_json"]), "result": e["result"]}
                   for e in events]
    return d


def runs_in_group(engine: Engine, scenario_id: int, group: str) -> list[int]:
    with engine.connect() as c:
        return [int(r[0]) for r in c.execute(text(
            "SELECT id FROM mission_run WHERE scenario_id = :s AND comparison_group = :g ORDER BY id"),
            {"s": scenario_id, "g": group})]


def latest_group(engine: Engine, scenario_id: int) -> str | None:
    with engine.connect() as c:
        return c.execute(text("SELECT comparison_group FROM mission_run WHERE scenario_id = :s AND "
                              "comparison_group IS NOT NULL ORDER BY id DESC LIMIT 1"), {"s": scenario_id}).scalar()


def save_report(engine: Engine, *, run_id: int, version: str, sha: str, path: str, has_snapshot: bool) -> dict:
    gen = _now()
    with engine.begin() as c:
        rid = int(c.execute(text(
            "INSERT INTO mission_report (run_id, report_version, generated_at, snapshot_sha256, artifact_path, "
            "has_viewer_snapshot) VALUES (:r, :v, :g, :sha, :p, :h)"),
            {"r": run_id, "v": version, "g": gen, "sha": sha, "p": path, "h": 1 if has_snapshot else 0}).lastrowid)
    return {"id": rid, "run_id": run_id, "report_version": version, "generated_at": gen, "snapshot_sha256": sha,
            "artifact_path": path, "has_viewer_snapshot": has_snapshot}


def get_report(engine: Engine, rep_id: int) -> dict | None:
    with engine.connect() as c:
        row = c.execute(text("SELECT * FROM mission_report WHERE id = :id"), {"id": rep_id}).mappings().first()
    return dict(row) if row else None


def now() -> str:
    return _now()
