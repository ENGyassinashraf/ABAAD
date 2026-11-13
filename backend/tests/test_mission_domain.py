"""Mission Lab domain tests: terrain, line of sight, delay, navigation, planner,
link segments, safety policy and the end-to-end simulation. All inputs are
synthetic test terrain (the MVP has no real terrain data)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from abaad_api.mission.comms import end_to_end, one_way_light_time_s, round_trip_estimate_s
from abaad_api.mission.config import normalise, validate
from abaad_api.mission.engine import beacon_spacing_m
from abaad_api.mission.los import BLOCKED_BY_TERRAIN, LINE_OF_SIGHT, OUT_OF_RANGE, UNKNOWN, line_of_sight
from abaad_api.mission.navigation import NavParams, NavState
from abaad_api.mission.planner import DEFAULT_WEIGHTS, plan_routes
from abaad_api.mission.service import comm_visibility, plan, run_case
from abaad_api.mission.terrain import BASE_XY, DEFAULT_START_XY, DEFAULT_TARGET_XY, Terrain, TerrainSpec, get_terrain


def flat_terrain(n=200, cell=10.0) -> Terrain:
    z = np.zeros((n, n))
    return Terrain(spec=TerrainSpec(seed=0, n=n, cell_m=cell), z=z, slope_deg=np.zeros_like(z),
                   roughness_m=np.zeros_like(z), nogo=np.zeros_like(z, dtype=bool))


# ---------------------------------------------------------------- terrain
def test_terrain_is_deterministic_and_labelled_synthetic():
    a = get_terrain(123)
    get_terrain.cache_clear()
    b = get_terrain(123)
    assert a.sha256 == b.sha256
    assert get_terrain(124).sha256 != a.sha256
    meta = a.metadata()
    assert meta["status"] == "synthetic" and meta["label"] == "Synthetic / Demonstration"
    assert "not geo-referenced" in meta["frame"]


def test_injected_blockage_changes_the_terrain():
    assert get_terrain(20261113, True).sha256 != get_terrain(20261113, False).sha256


# ---------------------------------------------------------------- line of sight
def test_los_flat_terrain_includes_lunar_curvature():
    t = flat_terrain()
    # 1500 m apart: the curvature bulge at mid-path is 750^2 / (2 * 1737.4 km) = 0.162 m
    low = line_of_sight(t, (200, 1000), 0.05, (1700, 1000), 0.05, 5000)
    high = line_of_sight(t, (200, 1000), 0.5, (1700, 1000), 0.5, 5000)
    assert low["status"] == BLOCKED_BY_TERRAIN
    assert high["status"] == LINE_OF_SIGHT
    assert high["min_clearance_m"] == pytest.approx(0.5 - 750 ** 2 / (2 * 1_737_400), abs=0.02)


def test_los_detects_a_ridge_and_reports_the_obstruction():
    t = flat_terrain()
    t.z[:, 95:105] = 20.0  # wall across the path at x = 950..1050 m
    r = line_of_sight(t, (500, 1000), 1.5, (1500, 1000), 3.0, 5000, with_profile=True)
    assert r["status"] == BLOCKED_BY_TERRAIN
    assert 950 <= r["obstructions"][0]["x"] <= 1050
    assert r["profile"], "profile requested"


def test_los_range_and_unknown_states():
    t = flat_terrain()
    assert line_of_sight(t, (100, 100), 2, (1900, 1900), 2, 1000)["status"] == OUT_OF_RANGE
    assert line_of_sight(t, (100, 100), 2, (5000, 100), 2, 1e6)["status"] == UNKNOWN


def test_moving_an_endpoint_changes_visibility_on_the_mission_terrain():
    t = get_terrain()
    assert line_of_sight(t, BASE_XY, 3, DEFAULT_TARGET_XY, 1.5, 2000)["status"] == BLOCKED_BY_TERRAIN
    assert line_of_sight(t, BASE_XY, 3, DEFAULT_START_XY, 1.5, 2000)["status"] == LINE_OF_SIGHT


# ---------------------------------------------------------------- delay and link segments
def test_propagation_delay_uses_distance_and_speed_of_light():
    assert one_way_light_time_s(384_400_000) == pytest.approx(1.2822, abs=1e-4)
    assert round_trip_estimate_s(384_400_000) == pytest.approx(2 * one_way_light_time_s(384_400_000))


def test_relay_cannot_restore_the_earth_path_when_base_to_earth_is_down():
    segs = {"rover_base": {"available": False}, "rover_relay": {"available": True},
            "relay_base": {"available": True}, "base_earth": {"available": False}}
    r = end_to_end(segs, "relay")
    assert r["local_link"] is True and r["active_path"] == "relay" and r["earth_path"] is False
    segs["relay_base"]["available"] = False
    assert end_to_end(segs, "relay")["local_link"] is False
    segs["base_earth"]["available"] = True
    assert end_to_end(segs, "direct")["earth_path"] is False


# ---------------------------------------------------------------- navigation
def test_dead_reckoning_uncertainty_grows_with_distance_and_corrections_reduce_it():
    nav = NavState(NavParams(drift_fraction=0.03), np.random.default_rng(1))
    nav.initialise("NOMINAL")
    nav.step(100, 10)
    assert nav.sigma_m == 1.0  # external fixes keep it bounded
    nav.mode = "GNSS_UNAVAILABLE"
    nav.step(100, 10)
    nav.step(100, 10)
    assert nav.sigma_m == pytest.approx(1.0 + 0.03 * 200)
    before = nav.correct(1.5)
    assert before == pytest.approx(7.0) and nav.sigma_m == 1.5
    assert math.hypot(*nav.err) <= nav.sigma_m * 1.2 + 1e-9


def test_beacon_spacing_is_derived_from_the_drift_model():
    cfg = normalise({})
    assert beacon_spacing_m(cfg) == pytest.approx(0.8 * (15.0 - 1.5) / 0.03)


# ---------------------------------------------------------------- planner
def _route(cfg_over=None):
    cfg = normalise(cfg_over or {})
    return cfg, plan(cfg)


def test_route_is_connected_reaches_target_and_respects_hard_constraints():
    cfg, r = _route()
    assert r["status"] == "ok"
    rec = r["recommended"]
    t = get_terrain()
    path = rec["path"]
    assert path[0] == list(t.centre(*t.cell_of(*DEFAULT_START_XY)))
    assert path[-1] == list(t.centre(*t.cell_of(*DEFAULT_TARGET_XY)))
    for (x0, y0), (x1, y1) in zip(path, path[1:]):
        assert max(abs(x1 - x0), abs(y1 - y0)) <= t.cell + 1e-6  # 8-connected steps only
    for x, y in path:
        rc = t.cell_of(x, y)
        assert t.slope_deg[rc] <= 20.0 and not t.nogo[rc]
    assert sum(rec["cost_breakdown"].values()) == pytest.approx(rec["total_cost"], abs=0.5)
    assert rec["max_slope_deg"] <= 20.0 and r["is_demonstration"] is True


def test_alternate_route_is_genuinely_different():
    _cfg, r = _route()
    alt = r["alternate"]
    assert alt is not None and alt["shared_cell_fraction"] < 0.6
    assert alt["total_cost"] >= r["recommended"]["total_cost"]


def test_no_route_states_are_explicit():
    t = get_terrain()
    h = t.hazards[0]
    _cfg, r = _route({"target_xy": [h["x"], h["y"]]})
    assert r["status"] == "no_route" and "no-go" in r["reasons"][0]
    _cfg, r = _route({"advanced": {"max_slope_deg": 5.0}})
    assert r["status"] == "no_route"


def test_changing_constraints_changes_the_route():
    _c, a = _route()
    _c, b = _route({"advanced": {"weights": {**DEFAULT_WEIGHTS, "communication": 0.0}}})
    assert a["recommended"]["path"] != b["recommended"]["path"]
    _c, c = _route({"target_xy": [1000, 1100]})
    assert c["recommended"]["path"][-1] != a["recommended"]["path"][-1]


def test_relay_extends_planned_communication_visibility():
    direct = comm_visibility(normalise({}))
    relay = comm_visibility(normalise({"comm_mode": "relay", "relay_xy": [764.0, 524.0]}))
    assert (relay == 1).sum() > (direct == 1).sum()


def test_planner_uses_hard_slope_limit_on_moves():
    t = flat_terrain(n=40, cell=10.0)
    t.z[:, 20:] = 10.0  # 10 m step: impassable at a 20 deg limit
    t.slope_deg = np.degrees(np.arctan(np.hypot(*np.gradient(t.z, t.cell))))
    vis = np.ones_like(t.z, dtype=np.uint8)
    r = plan_routes(t, (50, 200), (350, 200), max_slope_deg=20, weights=DEFAULT_WEIGHTS, comm_vis=vis, speed_mps=0.1)
    assert r["status"] == "no_route"


# ---------------------------------------------------------------- simulation
@pytest.fixture(scope="module")
def cases():
    cfg = normalise({})
    return {c: run_case(cfg, c) for c in ("baseline", "stress", "mitigated")}


def test_config_validation():
    assert validate(normalise({})) == []
    errs = validate(normalise({"speed_profile": "warp", "outages": [{"segment": "x", "start_s": 0, "duration_s": 0}]}))
    assert len(errs) == 2


def test_same_seed_and_config_reproduce_identical_runs():
    cfg = normalise({"nav_mode": "GNSS_UNAVAILABLE", "comm_mode": "relay", "relay_xy": [764.0, 524.0]})
    a = run_case(cfg, "custom")["sim"]
    b = run_case(cfg, "custom")["sim"]
    assert a["events"] == b["events"] and a["frames"] == b["frames"]
    c = run_case({**cfg, "seed": 7}, "custom")["sim"]
    assert c["frames"] != a["frames"]


def test_frames_follow_the_route_and_time_is_monotonic(cases):
    sim = cases["baseline"]["sim"]
    ts = [f["t"] for f in sim["frames"]]
    assert ts == sorted(ts)
    path = np.array(cases["baseline"]["routes"]["recommended"]["path"])
    for f in sim["frames"][::50]:
        d = np.min(np.hypot(path[:, 0] - f["x"], path[:, 1] - f["y"]))
        assert d < 45.0  # on the route (or the candidate-site extension)


def test_cases_differ_meaningfully(cases):
    s = {k: v["sim"]["summary"] for k, v in cases.items()}
    assert s["baseline"]["science_result"] == "COMPLETED"
    assert s["stress"]["status"] == "SAFE_HOLD" and s["stress"]["science_result"] == "NOT_ATTEMPTED"
    assert s["mitigated"]["science_result"] == "COMPLETED"
    assert s["mitigated"]["status"] in ("COMPLETED", "COMPLETED_WITH_DEVIATIONS")
    assert s["mitigated"]["nav_corrections"] > 0
    assert s["mitigated"]["earth_path_unavailable_s"] < s["baseline"]["earth_path_unavailable_s"]
    # same mission and comparable initial conditions
    cfgs = [v["config"] for v in cases.values()]
    assert len({(tuple(c["start_xy"]), tuple(c["target_xy"]), c["seed"]) for c in cfgs}) == 1


def test_required_event_types_appear_in_the_timelines(cases):
    types = {e["type"] for v in cases.values() for e in v["sim"]["events"]}
    required = {"LOS_LOST", "COMM_BLOCKED", "POSITIONING_UNAVAILABLE", "NAV_UNCERTAINTY_INCREASING", "NAV_CORRECTION",
                "AUTONOMOUS_FALLBACK", "SAFETY_PAUSE", "SAFE_HOLD", "REROUTE", "COMM_RECOVERED", "DATA_TRANSMITTED",
                "SCIENCE_COMPLETE"}
    assert required <= types, required - types


def test_safety_policy_without_autonomy_stops_on_link_loss(cases):
    ev = [e["type"] for e in cases["stress"]["sim"]["events"]]
    assert ev.index("COMM_BLOCKED") < ev.index("SAFETY_PAUSE") < ev.index("SAFE_HOLD")
    assert "PRELOADED_COMMANDS_ACTIVE" not in ev


def test_autonomy_continues_on_preloaded_commands(cases):
    ev = [e["type"] for e in cases["baseline"]["sim"]["events"]]
    assert "PRELOADED_COMMANDS_ACTIVE" in ev and "SAFE_HOLD" not in ev


def test_science_fails_when_position_uncertainty_exceeds_the_science_limit():
    sim = run_case(normalise({"nav_mode": "DEGRADED"}), "custom")["sim"]
    assert sim["summary"]["science_result"] == "FAILED"
    assert any(e["type"] == "SCIENCE_FAILED" for e in sim["events"])


def test_timed_earth_outage_blocks_only_the_earth_path_during_the_window():
    sim = run_case(normalise({"outages": [{"segment": "base_earth", "start_s": 500, "duration_s": 900}]}), "custom")["sim"]
    types = [e["type"] for e in sim["events"]]
    assert "OUTAGE_START" in types and "OUTAGE_END" in types
    during = [f for f in sim["frames"] if 520 <= f["t"] < 1390]
    assert during and all(f["local"] and not f["earth"] for f in during)
    after = [f for f in sim["frames"] if 1400 <= f["t"] < 2000]
    assert after and all(f["earth"] for f in after)


def test_phases_are_reported_in_order(cases):
    phases = cases["baseline"]["sim"]["phases"]
    assert [p["phase"] for p in phases] == list(range(1, 9))
    assert all(p["status"] == "completed" for p in phases)
    starts = [p["start_s"] for p in phases]
    assert starts == sorted(starts)
    stress = cases["stress"]["sim"]["phases"]
    assert stress[2]["status"] == "halted" and stress[3]["status"] == "not_reached"
