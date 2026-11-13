"""Mission configuration: defaults, validation and the three comparison cases."""

from __future__ import annotations

import copy

from .planner import DEFAULT_WEIGHTS
from .terrain import DEFAULT_START_XY, DEFAULT_TARGET_XY

SPEED_PROFILES = {"cautious": 0.05, "nominal": 0.10, "fast": 0.20}  # m/s, assumed training values
COMM_MODES = ("direct", "relay")
NAV_MODES = ("NOMINAL", "DEGRADED", "GNSS_UNAVAILABLE", "LOCAL_NAVIGATION")
OUTAGE_SEGMENTS = ("rover_base", "base_earth")
CASES = ("custom", "baseline", "stress", "mitigated")

DEFAULT_CONFIG: dict = {
    "terrain_seed": 20261113,
    "seed": 42,
    "start_xy": list(DEFAULT_START_XY),
    "target_xy": list(DEFAULT_TARGET_XY),
    "speed_profile": "nominal",
    "comm_mode": "direct",
    "relay_xy": None,          # None -> use the derived suggested relay site
    "beacons": [],             # [[x, y], ...] local navigation beacons (known positions)
    "nav_mode": "NOMINAL",
    "nav_event_time_s": 1200.0,  # when the injected positioning change starts
    "autonomy": True,
    "terrain_blockage": False,
    "outages": [],             # [{"segment": "rover_base"|"base_earth", "start_s": .., "duration_s": ..}]
    "advanced": {
        "max_slope_deg": 20.0,
        "weights": dict(DEFAULT_WEIGHTS),
        "rover_antenna_m": 1.5,
        "base_antenna_m": 3.0,
        "relay_antenna_m": 2.5,
        "max_link_range_m": 1500.0,
        "uncertainty_threshold_m": 15.0,
        "science_uncertainty_m": 5.0,
        "correction_request_m": 5.0,
        "drift_fraction": 0.03,
        "dt_s": 10.0,
        "downlink_mb_per_s": 0.5,
        "survey_data_mb": 120.0,
        "science_data_mb": 40.0,
        "command_timeout_s": 1800.0,
        "operator_response_s": 600.0,
        "earth_moon_distance_m": 384_400_000.0,
        "max_sim_time_s": 50_000.0,
    },
}


def _merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def normalise(cfg: dict | None) -> dict:
    return _merge(DEFAULT_CONFIG, cfg or {})


def validate(cfg: dict) -> list[str]:
    e: list[str] = []
    if cfg["speed_profile"] not in SPEED_PROFILES:
        e.append(f"speed_profile must be one of {sorted(SPEED_PROFILES)}")
    if cfg["comm_mode"] not in COMM_MODES:
        e.append(f"comm_mode must be one of {list(COMM_MODES)}")
    if cfg["nav_mode"] not in NAV_MODES:
        e.append(f"nav_mode must be one of {list(NAV_MODES)}")
    for b in cfg.get("beacons", []):
        if not (isinstance(b, (list, tuple)) and len(b) == 2):
            e.append("each beacon must be [x, y] in metres")
    if len(cfg.get("beacons", [])) > 8:
        e.append("at most 8 beacons")
    for key in ("start_xy", "target_xy", "relay_xy"):
        v = cfg.get(key)
        if v is None and key == "relay_xy":
            continue
        if not (isinstance(v, (list, tuple)) and len(v) == 2 and all(isinstance(c, (int, float)) for c in v)):
            e.append(f"{key} must be [x, y] in metres")
    for o in cfg.get("outages", []):
        if o.get("segment") not in OUTAGE_SEGMENTS or o.get("duration_s", 0) <= 0 or o.get("start_s", -1) < 0:
            e.append("each outage needs segment in rover_base/base_earth, start_s >= 0 and duration_s > 0")
    a = cfg["advanced"]
    if not 5 <= a["max_slope_deg"] <= 35:
        e.append("advanced.max_slope_deg must be between 5 and 35")
    if any(w < 0 for w in a["weights"].values()):
        e.append("route weights must be non-negative")
    if a["dt_s"] <= 0 or a["dt_s"] > 60:
        e.append("advanced.dt_s must be in (0, 60]")
    return e


def case_config(base: dict, case: str, suggested_relay, suggested_beacons) -> dict:
    """Baseline / stress / mitigated variants of the SAME mission (same start, target, seed)."""
    cfg = copy.deepcopy(base)
    if case == "baseline":
        cfg.update(nav_mode="NOMINAL", comm_mode="direct", outages=[], terrain_blockage=False,
                   autonomy=True, beacons=[])
    elif case == "stress":
        cfg.update(nav_mode="GNSS_UNAVAILABLE", comm_mode="direct", terrain_blockage=True,
                   autonomy=False, beacons=[])
    elif case == "mitigated":
        cfg.update(nav_mode="GNSS_UNAVAILABLE", comm_mode="relay", terrain_blockage=True, autonomy=True,
                   relay_xy=list(suggested_relay) if suggested_relay else None,
                   beacons=[list(b) for b in (suggested_beacons or [])])
    return cfg
