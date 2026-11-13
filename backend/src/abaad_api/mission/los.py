"""Geometric line-of-sight (Communication Visibility).

This is terrain visibility only: a straight ray between two antenna tips,
checked against bilinear terrain elevations plus the curvature bulge of a
spherical body (d1 * d2 / 2R). It is NOT an RF propagation model, does not
include diffraction or Fresnel-zone clearance, and produces no signal
strength. Results are called "Communication Visibility" / "Geometric Link
Availability".
"""

from __future__ import annotations

import math

import numpy as np

from .terrain import Terrain

MOON_RADIUS_M = 1_737_400.0  # IAU 2015 lunar reference sphere (as used in Phase 1)

LINE_OF_SIGHT = "LINE_OF_SIGHT"
BLOCKED_BY_TERRAIN = "BLOCKED_BY_TERRAIN"
OUT_OF_RANGE = "OUT_OF_RANGE"
UNKNOWN = "UNKNOWN"


def line_of_sight(t: Terrain, a_xy, a_h: float, b_xy, b_h: float, max_range_m: float,
                  radius_m: float = MOON_RADIUS_M, with_profile: bool = False) -> dict:
    ax, ay = float(a_xy[0]), float(a_xy[1])
    bx, by = float(b_xy[0]), float(b_xy[1])
    if not (t.inside(ax, ay) and t.inside(bx, by)):
        return {"status": UNKNOWN, "reason": "endpoint outside terrain coverage", "distance_m": None,
                "obstructions": [], "min_clearance_m": None, "profile": []}
    dist = math.hypot(bx - ax, by - ay)
    za = float(t.elevation(ax, ay)) + a_h
    zb = float(t.elevation(bx, by)) + b_h
    if dist < 1e-6:
        return {"status": LINE_OF_SIGHT, "reason": "coincident endpoints", "distance_m": 0.0,
                "obstructions": [], "min_clearance_m": None, "profile": []}
    step = t.cell / 2
    k = max(2, int(dist / step))
    f = np.linspace(0, 1, k + 1)[1:-1]
    xs = ax + f * (bx - ax)
    ys = ay + f * (by - ay)
    d1 = f * dist
    ground = t.elevation(xs, ys) + d1 * (dist - d1) / (2 * radius_m)
    ray = za + f * (zb - za)
    clearance = ray - ground
    blocked = clearance < 0
    obstructions = []
    if blocked.any():
        idx = np.flatnonzero(blocked)
        # report the worst point of each contiguous blocked run
        runs = np.split(idx, np.flatnonzero(np.diff(idx) > 1) + 1)
        for run in runs:
            i = int(run[np.argmin(clearance[run])])
            obstructions.append({"x": round(float(xs[i]), 1), "y": round(float(ys[i]), 1),
                                 "distance_m": round(float(d1[i]), 1),
                                 "excess_m": round(float(-clearance[i]), 2)})
    if dist > max_range_m:
        status, reason = OUT_OF_RANGE, f"distance {dist:.0f} m exceeds configured maximum link range {max_range_m:.0f} m"
    elif obstructions:
        status, reason = BLOCKED_BY_TERRAIN, f"terrain rises above the ray at {len(obstructions)} place(s)"
    else:
        status, reason = LINE_OF_SIGHT, "ray clears terrain"
    out = {"status": status, "reason": reason, "distance_m": round(dist, 1), "obstructions": obstructions,
           "min_clearance_m": round(float(clearance.min()), 2) if clearance.size else None}
    if with_profile:
        every = max(1, len(f) // 200)
        out["profile"] = [{"d": round(float(d1[i]), 1), "ground": round(float(ground[i]), 2),
                           "ray": round(float(ray[i]), 2)} for i in range(0, len(f), every)]
        out["endpoints"] = {"a_tip_m": round(za, 2), "b_tip_m": round(zb, 2)}
    else:
        out["profile"] = []
    return out


def visibility_grid(t: Terrain, src_xy, src_h: float, rover_h: float, max_range_m: float,
                    radius_m: float = MOON_RADIUS_M, samples: int = 96) -> np.ndarray:
    """Per-cell code: 1 visible, 0 blocked by terrain, 2 out of range."""
    n, cell = t.n, t.cell
    coords = (np.arange(n) + 0.5) * cell
    X, Y = np.meshgrid(coords, coords)
    sx, sy = float(src_xy[0]), float(src_xy[1])
    zs = float(t.elevation(sx, sy)) + src_h
    zt = t.z + rover_h
    dist = np.hypot(X - sx, Y - sy)
    f = np.linspace(0, 1, samples + 2)[1:-1][None, None, :]
    xs = sx + f * (X[..., None] - sx)
    ys = sy + f * (Y[..., None] - sy)
    d1 = f * dist[..., None]
    ground = t.elevation(xs, ys) + d1 * (dist[..., None] - d1) / (2 * radius_m)
    ray = zs + f * (zt[..., None] - zs)
    vis = (ray - ground >= 0).all(axis=-1)
    out = np.where(vis, 1, 0).astype(np.uint8)
    out[dist > max_range_m] = 2
    return out
