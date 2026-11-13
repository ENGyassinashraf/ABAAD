"""Mission simulation engine: one deterministic run of the 8-phase mission.

Given a terrain, a normalised config and the planned routes, the engine steps
simulated time (``dt_s``), moves the rover along the recommended route and
evaluates, every step, communication visibility per link segment, injected
outages, navigation uncertainty and the safety policy. It returns the event
timeline, per-step state frames and summary metrics. Same inputs + same seed
-> identical output.
"""

from __future__ import annotations

import math

import numpy as np

from . import SIMULATION_MODEL_VERSION
from .comms import end_to_end, one_way_light_time_s, outage_active, round_trip_estimate_s
from .config import SPEED_PROFILES
from .los import BLOCKED_BY_TERRAIN, LINE_OF_SIGHT, line_of_sight
from .navigation import NavParams, NavState
from .terrain import BASE_XY, Terrain

PHASES = [
    (1, "Rover deployment and system checks"),
    (2, "Route planning"),
    (3, "Traverse toward the target"),
    (4, "Terrain survey"),
    (5, "Candidate target selection"),
    (6, "Simulated science operation (sampling)"),
    (7, "Store and transmit mission data"),
    (8, "Return to a safe point or enter safe hold"),
]


class _Halt(Exception):
    pass


def suggest_relay_site(t: Terrain, cfg: dict, route_path: list) -> list | None:
    """Derived (not sourced) relay site: a traversable high point with line of sight to the
    base that sees the largest share of the recommended route."""
    a = cfg["advanced"]
    pts = route_path[:: max(1, len(route_path) // 40)]
    n = t.n
    best, best_score = None, -1
    elev_cut = np.quantile(t.z, 0.80)
    for r in range(2, n - 2, 3):
        for c in range(2, n - 2, 3):
            if t.nogo[r, c] or t.slope_deg[r, c] > a["max_slope_deg"] or t.z[r, c] < elev_cut:
                continue
            xy = t.centre(r, c)
            if line_of_sight(t, xy, a["relay_antenna_m"], BASE_XY, a["base_antenna_m"],
                             a["max_link_range_m"])["status"] != LINE_OF_SIGHT:
                continue
            score = sum(line_of_sight(t, p, a["rover_antenna_m"], xy, a["relay_antenna_m"],
                                      a["max_link_range_m"])["status"] == LINE_OF_SIGHT for p in pts)
            if score > best_score:
                best, best_score = [round(xy[0], 1), round(xy[1], 1)], score
    return best


def beacon_spacing_m(cfg: dict) -> float:
    """Derived spacing: 80 % of the distance over which dead-reckoning drift takes the
    uncertainty from the beacon fix level to the safety threshold."""
    a = cfg["advanced"]
    p = NavParams(drift_fraction=a["drift_fraction"])
    return 0.8 * (a["uncertainty_threshold_m"] - p.sigma_beacon_m) / a["drift_fraction"]


def suggest_beacon_sites(cfg: dict, route_path: list) -> list:
    """Derived beacon sites ON the recommended route: every ``beacon_spacing_m`` from the
    start, plus one 120 m before the target for sample-location accuracy."""
    if len(route_path) < 2:
        return []
    cum = [0.0]
    for (x0, y0), (x1, y1) in zip(route_path, route_path[1:]):
        cum.append(cum[-1] + math.hypot(x1 - x0, y1 - y0))
    total, spacing = cum[-1], beacon_spacing_m(cfg)
    marks = [k * spacing for k in range(1, int(total // spacing) + 1)]
    marks.append(max(0.0, total - 120.0))
    out = []
    for m in sorted(set(round(v, 1) for v in marks)):
        i = min(range(len(cum)), key=lambda j: abs(cum[j] - m))
        pt = [round(route_path[i][0], 1), round(route_path[i][1], 1)]
        if not out or math.dist(out[-1], pt) > 60:
            out.append(pt)
    return out[:8]


class Simulation:
    def __init__(self, t: Terrain, cfg: dict, route: dict):
        self.t, self.cfg, self.a = t, cfg, cfg["advanced"]
        self.rng = np.random.default_rng(cfg["seed"])
        self.speed = SPEED_PROFILES[cfg["speed_profile"]]
        self.dt = float(self.a["dt_s"])
        self.path = [tuple(p) for p in route["path"]]
        self.waypoints = route["waypoints"]
        self._build_arclength()
        self.s = 0.0
        self.time = 0.0
        self.phase = 1
        self.phase_log: dict[int, dict] = {}
        self.events: list[dict] = []
        self.frames: list[dict] = []
        self.nav = NavState(NavParams(drift_fraction=self.a["drift_fraction"]), self.rng)
        self.queue_mb = 0.0
        self.max_queue_mb = 0.0
        self.transmitted_mb = 0.0
        self.safety = "NOMINAL"
        self.driven_m = 0.0
        self.comm = None
        self.prev_local = None
        self.prev_rover_base_status = None
        self.last_contact_s = None
        self.outage_s = 0.0
        self.nav_event_done = False
        self.sigma_flags: set = set()
        self.used_landmarks: set = set()
        self.beacon_used_at: dict = {}
        self.preloaded_announced = False
        self.wp_reached: set = set()
        self.counters = {"safety_pauses": 0, "fallback_actions": 0, "reroutes": 0, "nav_corrections": 0}
        self.science = "NOT_ATTEMPTED"
        self.status = None
        self.halt_reason = None
        self.max_sigma = 0.0
        self.deviations: list[str] = []
        self.relay_xy = cfg.get("relay_xy")
        self.beacons = [tuple(b) for b in cfg.get("beacons", [])]
        self.earth_one_way_s = one_way_light_time_s(self.a["earth_moon_distance_m"])

    # ---------- geometry helpers
    def _build_arclength(self):
        self.cum = [0.0]
        for (x0, y0), (x1, y1) in zip(self.path, self.path[1:]):
            self.cum.append(self.cum[-1] + math.hypot(x1 - x0, y1 - y0))
        self.length = self.cum[-1]

    def pos_at(self, s):
        s = min(max(s, 0.0), self.length)
        i = max(1, int(np.searchsorted(self.cum, s)))
        i = min(i, len(self.path) - 1)
        s0, s1 = self.cum[i - 1], self.cum[i]
        f = 0 if s1 == s0 else (s - s0) / (s1 - s0)
        (x0, y0), (x1, y1) = self.path[i - 1], self.path[i]
        return (x0 + f * (x1 - x0), y0 + f * (y1 - y0)), math.degrees(math.atan2(x1 - x0, y1 - y0)) % 360

    @property
    def xy(self):
        return self.pos_at(self.s)[0]

    # ---------- bookkeeping
    def event(self, etype: str, result: str = "", **payload):
        x, y = self.xy
        self.events.append({"seq": len(self.events) + 1, "t": round(self.time, 1), "type": etype,
                            "x": round(x, 1), "y": round(y, 1), "phase": self.phase,
                            "payload": payload, "result": result})

    def start_phase(self, n: int):
        if self.phase in self.phase_log and "end_s" not in self.phase_log[self.phase]:
            self.phase_log[self.phase].update(end_s=round(self.time, 1), status="completed")
        self.phase = n
        self.phase_log[n] = {"phase": n, "name": PHASES[n - 1][1], "start_s": round(self.time, 1)}
        self.event("PHASE_STARTED", PHASES[n - 1][1], phase_number=n)

    # ---------- communication
    def evaluate_comm(self, xy=None):
        a, t = self.a, self.t
        xy = xy or self.xy
        outs = self.cfg.get("outages", [])
        rb = line_of_sight(t, xy, a["rover_antenna_m"], BASE_XY, a["base_antenna_m"], a["max_link_range_m"])
        segs = {"rover_base": {"geometry": rb["status"], "obstructions": rb["obstructions"][:3],
                               "distance_m": rb["distance_m"],
                               "injected_outage": outage_active(outs, "rover_base", self.time)}}
        segs["rover_base"]["available"] = rb["status"] == LINE_OF_SIGHT and not segs["rover_base"]["injected_outage"]
        if self.cfg["comm_mode"] == "relay" and self.relay_xy:
            rr = line_of_sight(t, xy, a["rover_antenna_m"], self.relay_xy, a["relay_antenna_m"], a["max_link_range_m"])
            rlb = line_of_sight(t, self.relay_xy, a["relay_antenna_m"], BASE_XY, a["base_antenna_m"], a["max_link_range_m"])
            segs["rover_relay"] = {"geometry": rr["status"], "distance_m": rr["distance_m"],
                                   "obstructions": rr["obstructions"][:3],
                                   "available": rr["status"] == LINE_OF_SIGHT}
            segs["relay_base"] = {"geometry": rlb["status"], "distance_m": rlb["distance_m"],
                                  "available": rlb["status"] == LINE_OF_SIGHT}
        be_out = outage_active(outs, "base_earth", self.time)
        segs["base_earth"] = {"geometry": "ASSUMED_AVAILABLE", "injected_outage": be_out, "available": not be_out}
        return {"segments": segs, **end_to_end(segs, self.cfg["comm_mode"])}

    def _comm_transitions(self):
        c = self.comm
        rb = c["segments"]["rover_base"]
        if self.prev_rover_base_status == LINE_OF_SIGHT and rb["geometry"] == BLOCKED_BY_TERRAIN:
            self.event("LOS_LOST", "rover moved behind terrain; direct line of sight to base lost",
                       obstructions=rb["obstructions"])
        self.prev_rover_base_status = rb["geometry"]
        if self.prev_local is True and not c["local_link"]:
            cause = "injected outage" if rb["injected_outage"] else rb["geometry"]
            self.event("COMM_BLOCKED", f"local link unavailable ({cause})", cause=cause)
        elif self.prev_local is False and c["local_link"]:
            self.event("COMM_RECOVERED", f"local link restored via {c['active_path']} path", path=c["active_path"])
        self.prev_local = c["local_link"]

    # ---------- world step
    def tick(self, moved_m: float = 0.0):
        self.time += self.dt
        if self.time > self.a["max_sim_time_s"]:
            self.safe_hold("maximum simulated mission time reached")
        self._nav_injection()
        self.nav.step(abs(moved_m), self.dt)
        self.driven_m += abs(moved_m)
        self.comm = self.evaluate_comm()
        self._comm_transitions()
        self._outage_edges()
        if self.comm["earth_path"]:
            self.last_contact_s = self.time
            if self.queue_mb > 0:
                sent = min(self.queue_mb, self.a["downlink_mb_per_s"] * self.dt)
                self.queue_mb -= sent
                self.transmitted_mb += sent
                if self.queue_mb <= 1e-9:
                    self.queue_mb = 0.0
                    self.event("DATA_TRANSMITTED", "data queue emptied to Earth", transmitted_mb=round(self.transmitted_mb, 1))
        elif self.phase >= 2:
            self.outage_s += self.dt
        self._corrections()
        self._sigma_watch()
        self.record()

    def _outage_edges(self):
        for o in self.cfg.get("outages", []):
            if abs(self.time - o["start_s"]) < self.dt / 2 + 1e-9:
                self.event("OUTAGE_START", f"injected {o['segment']} outage for {o['duration_s']:.0f} s", **o)
            end = o["start_s"] + o["duration_s"]
            if abs(self.time - end) < self.dt / 2 + 1e-9:
                self.event("OUTAGE_END", f"injected {o['segment']} outage ended", **o)

    def _nav_injection(self):
        mode = self.cfg["nav_mode"]
        if self.nav_event_done or mode == "NOMINAL" or self.nav.mode == "UNKNOWN":
            return
        if self.time >= self.cfg["nav_event_time_s"]:
            self.nav_event_done = True
            if mode == "DEGRADED":
                self.nav.mode = "DEGRADED"
                self.event("POSITIONING_DEGRADED", "external positioning degraded (injected training event)")
            else:
                self.nav.mode = "GNSS_UNAVAILABLE"
                self.event("POSITIONING_UNAVAILABLE", "external positioning unavailable (injected); dead reckoning only")
                if mode == "LOCAL_NAVIGATION" or self.cfg["autonomy"]:
                    self.nav.mode = "LOCAL_NAVIGATION"
                    self.counters["fallback_actions"] += 1
                    self.event("LOCAL_NAVIGATION_ENABLED", "switched to local navigation (dead reckoning + landmark/beacon corrections)")

    def _corrections(self, force: bool = False):
        """Request a landmark/beacon fix when uncertainty exceeds the request level."""
        if self.nav.mode != "LOCAL_NAVIGATION":
            return
        a, t, p = self.a, self.t, self.nav.params
        if not force and self.nav.sigma_m <= a.get("correction_request_m", 5.0):
            return
        xy = self.xy
        for k, b in enumerate(self.beacons):
            if self.time - self.beacon_used_at.get(k, -1e9) < 600 or self.nav.sigma_m <= p.sigma_beacon_m * 1.5:
                continue
            if math.dist(xy, b) <= p.beacon_range_m and line_of_sight(
                    t, xy, a["rover_antenna_m"], b, 1.0, p.beacon_range_m)["status"] == LINE_OF_SIGHT:
                before = self.nav.correct(p.sigma_beacon_m)
                self.beacon_used_at[k] = self.time
                self.counters["nav_corrections"] += 1
                self.event("NAV_CORRECTION", f"local beacon B{k + 1} range fix", source="beacon", beacon=f"B{k + 1}",
                           sigma_before_m=round(before, 2), sigma_after_m=round(self.nav.sigma_m, 2))
                return
        for lm in t.landmarks:
            if lm["id"] in self.used_landmarks:
                continue
            if math.dist(xy, (lm["x"], lm["y"])) <= p.landmark_range_m and self.nav.sigma_m > p.sigma_landmark_m * 1.5:
                if line_of_sight(t, xy, a["rover_antenna_m"], (lm["x"], lm["y"]), 0.5,
                                 p.landmark_range_m)["status"] == LINE_OF_SIGHT:
                    before = self.nav.correct(p.sigma_landmark_m)
                    self.used_landmarks.add(lm["id"])
                    self.counters["nav_corrections"] += 1
                    self.event("NAV_CORRECTION", f"landmark observation ({lm['id']})", source="landmark",
                               landmark=lm["id"], sigma_before_m=round(before, 2), sigma_after_m=round(self.nav.sigma_m, 2))
                    return

    def _sigma_watch(self):
        s = self.nav.sigma_m
        self.max_sigma = max(self.max_sigma, s)
        for level in (5.0, 10.0):
            if s > level and level not in self.sigma_flags:
                self.sigma_flags.add(level)
                self.event("NAV_UNCERTAINTY_INCREASING", f"position uncertainty above {level:.0f} m", sigma_m=round(s, 2))
            elif s < level * 0.6 and level in self.sigma_flags:
                self.sigma_flags.discard(level)

    def record(self):
        (x, y), hdg = self.pos_at(self.s)
        c = self.comm
        rb = c["segments"]["rover_base"]
        obstruction = rb["obstructions"][0] if rb["obstructions"] else None
        self.frames.append({
            "t": round(self.time, 1), "x": round(x, 2), "y": round(y, 2), "hdg": round(hdg, 1),
            "ex": round(x + self.nav.err[0], 2), "ey": round(y + self.nav.err[1], 2),
            "sigma": round(self.nav.sigma_m, 2), "nav": self.nav.mode, "phase": self.phase,
            "wp": self._current_wp(), "los": rb["geometry"], "local": c["local_link"], "earth": c["earth_path"],
            "path": c["active_path"], "relay_ok": c["segments"].get("rover_relay", {}).get("available"),
            "queue": round(self.queue_mb, 2), "safety": self.safety, "dist": round(self.driven_m, 1),
            "obs": [obstruction["x"], obstruction["y"]] if obstruction else None,
            "since_contact": None if self.last_contact_s is None else round(self.time - self.last_contact_s, 1),
        })

    def _current_wp(self):
        for w in self.waypoints:
            if self.cum[min(w["path_index"], len(self.cum) - 1)] > self.s + 1e-6:
                return w["id"]
        return self.waypoints[-1]["id"] if self.waypoints else None

    # ---------- policies
    def safe_hold(self, reason: str):
        self.safety = "SAFE_HOLD"
        self.halt_reason = reason
        self.event("SAFE_HOLD", reason)
        self.record()
        raise _Halt(reason)

    def wait_for(self, cond, timeout_s: float) -> bool:
        waited = 0.0
        while not cond():
            if waited >= timeout_s:
                return False
            self.tick(0.0)
            waited += self.dt
        return True

    def dwell(self, seconds: float):
        for _ in range(int(round(seconds / self.dt))):
            self.tick(0.0)

    def _need_command_link(self, what: str):
        """Without autonomy the rover only acts on live commands."""
        if self.cfg["autonomy"] or self.comm["local_link"]:
            if self.cfg["autonomy"] and not self.comm["local_link"] and not self.preloaded_announced:
                self.preloaded_announced = True
                self.counters["fallback_actions"] += 1
                self.event("PRELOADED_COMMANDS_ACTIVE", "no live link; executing preloaded commands under autonomy")
                self.event("AUTONOMOUS_FALLBACK", "continue on planned route with preloaded commands; store data onboard",
                           action="continue_on_preloaded_commands")
            if self.comm["local_link"]:
                self.preloaded_announced = False
            return
        self.safety = "PAUSED"
        self.counters["safety_pauses"] += 1
        self.event("SAFETY_PAUSE", f"command link lost before {what}; autonomy disabled, waiting for link",
                   timeout_s=self.a["command_timeout_s"])
        ok = self.wait_for(lambda: self.comm["local_link"], self.a["command_timeout_s"])
        if not ok:
            self.safe_hold(f"no command link for {self.a['command_timeout_s']:.0f} s and autonomy disabled")
        self.safety = "NOMINAL"

    def _check_uncertainty(self):
        thr = self.a["uncertainty_threshold_m"]
        if self.nav.sigma_m <= thr:
            return
        self.event("NAV_THRESHOLD_EXCEEDED", f"uncertainty {self.nav.sigma_m:.1f} m exceeds {thr:.0f} m safety limit",
                   sigma_m=round(self.nav.sigma_m, 2), threshold_m=thr)
        self.safety = "PAUSED"
        self.counters["safety_pauses"] += 1
        if self.cfg["autonomy"]:
            self.counters["fallback_actions"] += 1
            self.event("AUTONOMOUS_FALLBACK", "pause and search for a landmark or beacon fix", action="pause_and_localise")
            if self.nav.mode != "LOCAL_NAVIGATION":
                self.nav.mode = "LOCAL_NAVIGATION"
                self.event("LOCAL_NAVIGATION_ENABLED", "switched to local navigation")
            p = self.nav.params
            saved = (p.landmark_range_m, p.beacon_range_m)
            p.landmark_range_m, p.beacon_range_m = 300.0, 400.0  # stationary extended search
            self.used_landmarks.clear()
            ok = self.wait_for(lambda: self.nav.sigma_m <= thr, 120.0)
            p.landmark_range_m, p.beacon_range_m = saved
            if not ok:
                self.safe_hold("uncertainty above limit and no landmark or beacon fix available")
        else:
            self.event("SAFETY_PAUSE", "awaiting ground-assisted localisation (requires Earth path)")
            ok = self.wait_for(lambda: self.comm["earth_path"], self.a["command_timeout_s"])
            if not ok:
                self.safe_hold("uncertainty above limit, autonomy disabled and no Earth path")
            self.dwell(round_trip_estimate_s(self.a["earth_moon_distance_m"]) + self.a["operator_response_s"])
            before = self.nav.correct(5.0)
            self.counters["nav_corrections"] += 1
            self.event("GROUND_POSITION_UPDATE", "ground-assisted position update (assumed 5 m)",
                       sigma_before_m=round(before, 2), sigma_after_m=5.0)
        self.safety = "NOMINAL"

    def drive_to(self, s_goal: float, purpose: str):
        while abs(self.s - s_goal) > 1e-6:
            self._need_command_link(purpose)
            self._check_uncertainty()
            step = min(self.speed * self.dt, abs(s_goal - self.s))
            self.s += step if s_goal > self.s else -step
            self.tick(step)
            for w in self.waypoints:
                ws = self.cum[min(w["path_index"], len(self.cum) - 1)]
                if w["id"] not in self.wp_reached and abs(self.s - ws) < self.speed * self.dt / 2 + 1e-6 \
                        and purpose == "traverse" and w["id"] != "START":
                    self.wp_reached.add(w["id"])
                    self.event("WAYPOINT_REACHED", w["id"], waypoint=w["id"], comm_visible_planned=w["comm_visible"])

    def find_comm_point(self):
        """Nearest point back along the route with a geometrically available local link."""
        n = len(self.path)
        i_now = int(np.searchsorted(self.cum, self.s))
        for i in range(min(i_now, n - 1), -1, -1):
            c = self.evaluate_comm(self.path[i])
            if c["local_link"]:
                return self.cum[i]
        return None

    # ---------- mission
    def run(self) -> dict:
        try:
            self._mission()
        except _Halt:
            pass
        return self.result()

    def _mission(self):
        a = self.a
        self.comm = self.evaluate_comm()
        self.prev_local = self.comm["local_link"]
        self.prev_rover_base_status = self.comm["segments"]["rover_base"]["geometry"]
        self.record()
        self.start_phase(1)
        self.event("SYSTEM_CHECK", "rover subsystems nominal (simulated check)")
        self.dwell(120)
        self.event("COMM_CHECK", "local link available" if self.comm["local_link"] else "local link NOT available",
                   active_path=self.comm["active_path"], earth_path=self.comm["earth_path"],
                   one_way_earth_delay_s=round(self.earth_one_way_s, 3))
        self.dwell(120)
        init_mode = "DEGRADED" if self.cfg["nav_mode"] == "DEGRADED" and self.cfg["nav_event_time_s"] <= 0 else "NOMINAL"
        self.nav.initialise(init_mode)
        self.event("NAV_INITIALISED", f"initial position estimate set ({init_mode})", sigma_m=self.nav.sigma_m)
        self.dwell(60)

        self.start_phase(2)
        self._need_command_link("route upload")
        self.event("ROUTE_UPLOADED", "recommended route and preloaded command sequence uploaded",
                   route_length_m=round(self.length, 1), waypoints=len(self.waypoints))
        self.dwell(60)

        self.start_phase(3)
        self.drive_to(self.length, "traverse")

        self.start_phase(4)
        self._need_command_link("terrain survey")
        self.dwell(600)
        self.queue_mb += a["survey_data_mb"]
        self.max_queue_mb = max(self.max_queue_mb, self.queue_mb)
        self.event("SURVEY_COMPLETE", "terrain survey complete; data queued", data_mb=a["survey_data_mb"])
        self.event("DATA_QUEUED", f"{self.queue_mb:.0f} MB waiting to be transmitted", queue_mb=round(self.queue_mb, 1))

        self.start_phase(5)
        cand = self._select_candidate()
        self.event("CANDIDATE_SELECTED", "lowest-slope traversable cell within 40 m of target", **cand)
        if math.dist(self.xy, (cand["x"], cand["y"])) > 1:
            self.path.append((cand["x"], cand["y"]))
            self._build_arclength()
            self.drive_to(self.length, "candidate approach")

        self.start_phase(6)
        self._need_command_link("science operation")
        self._check_uncertainty()
        if self.nav.sigma_m > a["science_uncertainty_m"]:
            self._corrections(force=True)
        if self.nav.sigma_m > a["science_uncertainty_m"]:
            self.science = "FAILED"
            self.event("SCIENCE_FAILED", f"sample location uncertainty {self.nav.sigma_m:.1f} m exceeds "
                       f"{a['science_uncertainty_m']:.0f} m requirement", sigma_m=round(self.nav.sigma_m, 2))
        else:
            self.dwell(900)
            self.science = "COMPLETED"
            self.queue_mb += a["science_data_mb"]
            self.max_queue_mb = max(self.max_queue_mb, self.queue_mb)
            self.event("SCIENCE_COMPLETE", "simulated sampling complete; data stored onboard",
                       data_mb=a["science_data_mb"], sigma_m=round(self.nav.sigma_m, 2))

        self.start_phase(7)
        if self.queue_mb > 0 and not self.comm["earth_path"]:
            if self.cfg["autonomy"]:
                s_rec = self.find_comm_point()
                if s_rec is None:
                    self.safe_hold("no point on the route restores the local link; data stored onboard")
                self.counters["reroutes"] += 1
                self.counters["fallback_actions"] += 1
                self.deviations.append(f"comm recovery move back {self.s - s_rec:.0f} m along route")
                self.event("REROUTE", "autonomous move back along route to nearest communication-visible point",
                           back_m=round(self.s - s_rec, 1), action="comm_recovery_move")
                self.drive_to(s_rec, "comm recovery")
            else:
                self.event("SAFETY_PAUSE", "no Earth path for data; autonomy disabled, waiting")
                self.counters["safety_pauses"] += 1
        if self.queue_mb > 0:
            ok = self.wait_for(lambda: self.queue_mb <= 0, a["command_timeout_s"] * 2)
            if not ok:
                self.safe_hold("data could not be transmitted; stored onboard")

        self.start_phase(8)
        self.drive_to(0.0, "return")
        self.event("RETURNED_TO_SAFE_POINT", "rover at staging point (safe point)")
        self.phase_log[8].update(end_s=round(self.time, 1), status="completed")
        self.status = "COMPLETED_WITH_DEVIATIONS" if (self.deviations or self.counters["fallback_actions"]) else "COMPLETED"
        if self.science != "COMPLETED":
            self.status = "PARTIAL"
        self.event("MISSION_COMPLETE", self.status)

    def _select_candidate(self) -> dict:
        t, a = self.t, self.a
        tx, ty = self.path[-1]
        best, best_s = (tx, ty), float(t.slope_deg[t.cell_of(tx, ty)])
        rr = int(40 // t.cell)
        r0, c0 = t.cell_of(tx, ty)
        for r in range(max(0, r0 - rr), min(t.n, r0 + rr + 1)):
            for c in range(max(0, c0 - rr), min(t.n, c0 + rr + 1)):
                x, y = t.centre(r, c)
                if math.hypot(x - tx, y - ty) > 40 or t.nogo[r, c] or t.slope_deg[r, c] > a["max_slope_deg"]:
                    continue
                if t.slope_deg[r, c] < best_s - 1e-9:
                    best, best_s = (x, y), float(t.slope_deg[r, c])
        return {"x": round(best[0], 1), "y": round(best[1], 1), "slope_deg": round(best_s, 2),
                "roughness_m": round(float(t.roughness_m[t.cell_of(*best)]), 3)}

    def result(self) -> dict:
        if self.phase in self.phase_log and "end_s" not in self.phase_log[self.phase]:
            self.phase_log[self.phase].update(end_s=round(self.time, 1),
                                              status="halted" if self.halt_reason else "completed")
        if self.status is None:
            self.status = "SAFE_HOLD"
            self.event("MISSION_ENDED", f"safe hold: {self.halt_reason}")
        phases = []
        for n, name in PHASES:
            p = self.phase_log.get(n)
            phases.append(p if p else {"phase": n, "name": name, "status": "not_reached"})
        summary = {
            "status": self.status,
            "halt_reason": self.halt_reason,
            "science_result": self.science,
            "planned_route_m": round(self.cum[-1], 1),
            "distance_driven_m": round(self.driven_m, 1),
            "mission_duration_s": round(self.time, 1),
            "earth_path_unavailable_s": round(self.outage_s, 1),
            "max_data_queued_mb": round(self.max_queue_mb, 1),
            "data_left_onboard_mb": round(self.queue_mb, 1),
            "data_transmitted_mb": round(self.transmitted_mb, 1),
            "max_position_uncertainty_m": round(self.max_sigma, 2),
            "final_position_uncertainty_m": round(self.nav.sigma_m, 2),
            **self.counters,
            "deviations": self.deviations,
            "phases_completed": sum(1 for p in phases if p.get("status") == "completed"),
            "one_way_earth_delay_s": round(self.earth_one_way_s, 3),
            "round_trip_propagation_estimate_s": round(2 * self.earth_one_way_s, 3),
        }
        return {"simulation_version": SIMULATION_MODEL_VERSION, "summary": summary, "phases": phases,
                "events": self.events, "frames": self.frames,
                "relay_xy": self.relay_xy, "beacons": [list(b) for b in self.beacons]}
