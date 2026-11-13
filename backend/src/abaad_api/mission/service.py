"""Orchestration: config -> terrain -> comm visibility -> routes -> simulation."""

from __future__ import annotations

from functools import lru_cache

import numpy as np

from .config import SPEED_PROFILES, case_config
from .engine import Simulation, beacon_spacing_m, suggest_beacon_sites, suggest_relay_site
from .los import LINE_OF_SIGHT, line_of_sight, visibility_grid
from .planner import plan_routes
from .terrain import BASE_XY, get_terrain


@lru_cache(maxsize=32)
def _vis(seed: int, blockage: bool, src: tuple, src_h: float, rover_h: float, rng_m: float) -> np.ndarray:
    return visibility_grid(get_terrain(seed, blockage), src, src_h, rover_h, rng_m)


def comm_visibility(cfg: dict) -> np.ndarray:
    a = cfg["advanced"]
    seed, blk = cfg["terrain_seed"], cfg["terrain_blockage"]
    vis = _vis(seed, blk, BASE_XY, a["base_antenna_m"], a["rover_antenna_m"], a["max_link_range_m"])
    if cfg["comm_mode"] == "relay" and cfg.get("relay_xy"):
        t = get_terrain(seed, blk)
        relay = tuple(cfg["relay_xy"])
        if line_of_sight(t, relay, a["relay_antenna_m"], BASE_XY, a["base_antenna_m"],
                         a["max_link_range_m"])["status"] == LINE_OF_SIGHT:
            rv = _vis(seed, blk, relay, a["relay_antenna_m"], a["rover_antenna_m"], a["max_link_range_m"])
            vis = np.where((vis == 1) | (rv == 1), 1, vis).astype(np.uint8)
    return vis


def plan(cfg: dict) -> dict:
    t = get_terrain(cfg["terrain_seed"], cfg["terrain_blockage"])
    return plan_routes(t, tuple(cfg["start_xy"]), tuple(cfg["target_xy"]),
                       max_slope_deg=cfg["advanced"]["max_slope_deg"], weights=cfg["advanced"]["weights"],
                       comm_vis=comm_visibility(cfg), speed_mps=SPEED_PROFILES[cfg["speed_profile"]])


def suggestions(cfg: dict) -> dict:
    """Derived relay and beacon sites for this terrain and mission (computed, not sourced)."""
    direct = {**cfg, "comm_mode": "direct"}
    routes = plan(direct)
    if routes["status"] != "ok":
        return {"relay_xy": None, "beacons": [], "beacon_spacing_m": None}
    t = get_terrain(cfg["terrain_seed"], cfg["terrain_blockage"])
    path = routes["recommended"]["path"]
    return {"relay_xy": suggest_relay_site(t, cfg, path), "beacons": suggest_beacon_sites(cfg, path),
            "beacon_spacing_m": round(beacon_spacing_m(cfg), 1),
            "basis": "derived from the recommended direct-mode route on this synthetic terrain"}


def run_case(base_cfg: dict, case: str) -> dict:
    cfg = base_cfg
    sugg = None
    if case in ("stress", "mitigated", "baseline"):
        sugg = suggestions({**base_cfg, "terrain_blockage": True})
        cfg = case_config(base_cfg, case, sugg["relay_xy"], sugg["beacons"])
    if cfg["comm_mode"] == "relay" and not cfg.get("relay_xy"):
        sugg = sugg or suggestions(cfg)
        cfg = {**cfg, "relay_xy": sugg["relay_xy"]}
    routes = plan(cfg)
    if routes["status"] != "ok":
        return {"case": case, "config": cfg, "routes": routes, "sim": None}
    t = get_terrain(cfg["terrain_seed"], cfg["terrain_blockage"])
    sim = Simulation(t, cfg, routes["recommended"]).run()
    return {"case": case, "config": cfg, "routes": routes, "sim": sim}
