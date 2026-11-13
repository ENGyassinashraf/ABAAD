"""Grid A* rover route planner ("Recommended Route", not a global optimum).

Hard constraints (a cell or move is rejected): outside the grid, inside a
configured no-go zone, cell slope above the maximum traversable slope, or a
move whose grade |dz|/length exceeds that maximum.

Soft preferences (added cost per metre of travel):
  total_cost = distance_cost + slope_penalty + roughness_penalty
               + hazard_penalty + communication_penalty
with
  distance_cost         = L
  slope_penalty         = L * w_slope * (slope / max_slope)^2
  roughness_penalty     = L * w_rough * min(roughness / 1 m, 1)
  hazard_penalty        = L * w_hazard * proximity (1 at a no-go edge, 0 beyond the buffer)
  communication_penalty = L * w_comm * (1 if the cell has no communication visibility else 0)
L is the 3-D length of a move between neighbouring cell centres. No energy
model is implemented, so energy is not part of the cost.

The alternate route is the same search with an extra diversity penalty on
cells near the recommended route; it is reported only if it is genuinely
different (shares less than 60 % of its cells).
"""

from __future__ import annotations

import heapq
import math

import numpy as np

from . import PLANNER_VERSION
from .terrain import Terrain

DEFAULT_WEIGHTS = {"slope": 2.0, "roughness": 1.0, "hazard": 3.0, "communication": 1.5}
HAZARD_BUFFER_M = 40.0
NEIGHBOURS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


def hazard_proximity(t: Terrain) -> np.ndarray:
    n, cell = t.n, t.cell
    coords = (np.arange(n) + 0.5) * cell
    X, Y = np.meshgrid(coords, coords)
    prox = np.zeros((n, n))
    for h in t.hazards:
        d = np.hypot(X - h["x"], Y - h["y"]) - h["radius_m"]
        prox = np.maximum(prox, np.clip(1 - d / HAZARD_BUFFER_M, 0, 1))
    return prox


def _passable(t: Terrain, max_slope_deg: float, extra_nogo: np.ndarray | None) -> np.ndarray:
    ok = (t.slope_deg <= max_slope_deg) & ~t.nogo
    if extra_nogo is not None:
        ok &= ~extra_nogo
    return ok


def _search(t, start, goal, passable, cell_cost, tan_max):
    n, cell = t.n, t.cell
    z = t.z
    INF = math.inf
    g = np.full((n, n), INF)
    parent = -np.ones((n, n), dtype=np.int64)
    sr, sc = start
    gr, gc = goal
    g[sr, sc] = 0.0
    heap = [(0.0, 0.0, sr, sc)]
    closed = np.zeros((n, n), dtype=bool)
    while heap:
        _f, gcur, r, c = heapq.heappop(heap)
        if closed[r, c]:
            continue
        closed[r, c] = True
        if (r, c) == (gr, gc):
            break
        for dr, dc in NEIGHBOURS:
            nr, nc = r + dr, c + dc
            if not (0 <= nr < n and 0 <= nc < n) or closed[nr, nc] or not passable[nr, nc]:
                continue
            horiz = cell * (1.4142135623730951 if dr and dc else 1.0)
            dz = z[nr, nc] - z[r, c]
            if abs(dz) / horiz > tan_max:
                continue
            length = math.sqrt(horiz * horiz + dz * dz)
            ng = gcur + length * 0.5 * (cell_cost[r, c] + cell_cost[nr, nc])
            if ng < g[nr, nc]:
                g[nr, nc] = ng
                parent[nr, nc] = r * n + c
                h = cell * math.hypot(gr - nr, gc - nc)
                heapq.heappush(heap, (ng + h, ng, nr, nc))
    if not math.isfinite(g[gr, gc]):
        return None
    path = [(gr, gc)]
    while path[-1] != (sr, sc):
        p = int(parent[path[-1]])
        path.append((p // n, p % n))
    return path[::-1]


def _rdp(points, eps):
    if len(points) < 3:
        return list(range(len(points)))
    a, b = np.array(points[0]), np.array(points[-1])
    ab = b - a
    norm = np.hypot(*ab) or 1.0
    d = [abs(ab[0] * (p[1] - a[1]) - ab[1] * (p[0] - a[0])) / norm for p in points[1:-1]]
    i = int(np.argmax(d)) + 1
    if d[i - 1] > eps:
        left = _rdp(points[: i + 1], eps)
        right = _rdp(points[i:], eps)
        return left[:-1] + [x + i for x in right]
    return [0, len(points) - 1]


def evaluate_path(t: Terrain, cells, weights, max_slope_deg, comm_vis, prox, speed_mps) -> dict:
    z, cell = t.z, t.cell
    pts = [t.centre(r, c) for r, c in cells]
    terms = {"distance_cost": 0.0, "slope_penalty": 0.0, "roughness_penalty": 0.0,
             "hazard_penalty": 0.0, "communication_penalty": 0.0}
    dist = visible_len = hazard_len = 0.0
    for (r0, c0), (r1, c1) in zip(cells, cells[1:]):
        horiz = cell * (math.sqrt(2) if (r0 != r1 and c0 != c1) else 1.0)
        length = math.hypot(horiz, z[r1, c1] - z[r0, c0])
        dist += length
        s = 0.5 * (t.slope_deg[r0, c0] + t.slope_deg[r1, c1])
        ro = 0.5 * (t.roughness_m[r0, c0] + t.roughness_m[r1, c1])
        hz = 0.5 * (prox[r0, c0] + prox[r1, c1])
        vis = 0.5 * ((comm_vis[r0, c0] == 1) + (comm_vis[r1, c1] == 1))
        terms["distance_cost"] += length
        terms["slope_penalty"] += length * weights["slope"] * (s / max_slope_deg) ** 2
        terms["roughness_penalty"] += length * weights["roughness"] * min(ro / 1.0, 1.0)
        terms["hazard_penalty"] += length * weights["hazard"] * hz
        terms["communication_penalty"] += length * weights["communication"] * (1 - vis)
        visible_len += length * vis
        if hz > 0:
            hazard_len += length
    slopes = [float(t.slope_deg[r, c]) for r, c in cells]
    keep = _rdp(pts, eps=12.0)
    waypoints = []
    for k, i in enumerate(keep):
        r, c = cells[i]
        waypoints.append({"id": "START" if k == 0 else ("TARGET" if k == len(keep) - 1 else f"W{k}"),
                          "x": round(pts[i][0], 1), "y": round(pts[i][1], 1),
                          "elevation_m": round(float(z[r, c]), 2), "slope_deg": round(slopes[i], 1),
                          "comm_visible": bool(comm_vis[r, c] == 1),
                          "hazard_proximity": round(float(prox[r, c]), 2), "path_index": i})
    return {
        "distance_m": round(float(dist), 1),
        "max_slope_deg": round(max(slopes), 1),
        "mean_slope_deg": round(float(np.mean(slopes)), 1),
        "estimated_duration_s": round(float(dist / speed_mps), 0),
        "assumed_speed_mps": speed_mps,
        "comm_visible_fraction": round(float(visible_len / dist), 3) if dist else 0.0,
        "hazard_exposure_m": round(float(hazard_len), 1),
        "cost_breakdown": {k: round(float(v), 1) for k, v in terms.items()},
        "total_cost": round(float(sum(terms.values())), 1),
        "waypoints": waypoints,
        "path": [[round(x, 1), round(y, 1)] for x, y in pts],
    }


def plan_routes(t: Terrain, start_xy, target_xy, *, max_slope_deg: float, weights: dict,
                comm_vis: np.ndarray, speed_mps: float, extra_nogo: np.ndarray | None = None) -> dict:
    tan_max = math.tan(math.radians(max_slope_deg))
    base = {"planner_version": PLANNER_VERSION, "weights": dict(weights),
            "hard_constraints": {"max_slope_deg": max_slope_deg, "no_go_zones": len(t.hazards),
                                 "move_grade_limit_deg": max_slope_deg, "must_reach_target": True},
            "is_demonstration": True,
            "demonstration_reason": "planned on synthetic 8 m terrain; valid for this training environment only"}
    passable = _passable(t, max_slope_deg, extra_nogo)
    problems = []
    for name, (x, y) in (("start", start_xy), ("target", target_xy)):
        if not t.inside(x, y):
            problems.append(f"{name} point is outside the terrain")
            continue
        r, c = t.cell_of(x, y)
        if t.nogo[r, c] or (extra_nogo is not None and extra_nogo[r, c]):
            problems.append(f"{name} point is inside a no-go zone")
        elif t.slope_deg[r, c] > max_slope_deg:
            problems.append(f"{name} point slope {t.slope_deg[r, c]:.1f} deg exceeds the {max_slope_deg:.0f} deg limit")
    if problems:
        return {**base, "status": "no_route", "reasons": problems, "recommended": None, "alternate": None}

    prox = hazard_proximity(t)
    rough_n = np.minimum(t.roughness_m / 1.0, 1.0)
    cost = (1 + weights["slope"] * (t.slope_deg / max_slope_deg) ** 2 + weights["roughness"] * rough_n
            + weights["hazard"] * prox + weights["communication"] * (comm_vis != 1))
    s, g = t.cell_of(*start_xy), t.cell_of(*target_xy)
    primary = _search(t, s, g, passable, cost, tan_max)
    if primary is None:
        return {**base, "status": "no_route",
                "reasons": ["no connected traversable path satisfies the hard constraints"],
                "recommended": None, "alternate": None}
    rec = evaluate_path(t, primary, weights, max_slope_deg, comm_vis, prox, speed_mps)

    # Alternate: diversity penalty near the recommended route
    near = np.zeros_like(passable)
    for r, c in primary:
        near[max(0, r - 4):r + 5, max(0, c - 4):c + 5] = True
    alt_cost = cost + near * 4.0
    alt_cells = _search(t, s, g, passable, alt_cost, tan_max)
    alternate, alt_note = None, None
    if alt_cells is not None:
        shared = len(set(alt_cells) & set(primary)) / len(alt_cells)
        if shared < 0.6:
            alternate = evaluate_path(t, alt_cells, weights, max_slope_deg, comm_vis, prox, speed_mps)
            alternate["shared_cell_fraction"] = round(shared, 2)
        else:
            alt_note = f"best alternate shares {shared:.0%} of cells with the recommended route; not reported"
    else:
        alt_note = "no second connected route exists under the hard constraints"

    rec["explanation"] = _explain(rec, alternate)
    return {**base, "status": "ok", "reasons": [], "recommended": rec, "alternate": alternate,
            "alternate_note": alt_note}


def _explain(rec: dict, alt: dict | None) -> str:
    cb = rec["cost_breakdown"]
    top = max((k for k in cb if k != "distance_cost"), key=lambda k: cb[k])
    text = (f"Lowest total weighted cost found by A* ({rec['total_cost']:.0f}) under the hard constraints. "
            f"{rec['distance_m']:.0f} m long, mean slope {rec['mean_slope_deg']:.1f} deg, "
            f"{rec['comm_visible_fraction']:.0%} of its length has communication visibility. "
            f"Largest soft penalty: {top.replace('_', ' ')}.")
    if alt:
        text += (f" The alternate route costs {alt['total_cost']:.0f} ({alt['distance_m']:.0f} m, "
                 f"{alt['comm_visible_fraction']:.0%} visible, max slope {alt['max_slope_deg']:.1f} deg).")
    return text
