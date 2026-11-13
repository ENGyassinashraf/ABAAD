"""Simplified, explainable navigation-uncertainty model (training only).

This is NOT a flight-qualified navigation filter or SLAM system.

* NOMINAL: an external position fix every step; 1-sigma = sigma_fix_m.
* DEGRADED: external fixes only every ``degraded_fix_interval_s`` with
  1-sigma = sigma_degraded_m; dead reckoning in between.
* GNSS_UNAVAILABLE: no external fix; dead reckoning only. 1-sigma grows
  linearly with distance travelled: sigma += drift_fraction * distance.
* LOCAL_NAVIGATION: dead reckoning plus corrections from mapped landmarks or a
  local beacon when one is within range AND in geometric line of sight.
* UNKNOWN: before navigation is initialised.

The estimate error is a seeded random walk whose magnitude follows sigma, so
true and estimated positions can be drawn separately. GNSS is not assumed
impossible at the Moon (NASA's LuGRE obtained a navigation fix on the lunar
surface in March 2025); loss of external positioning is an injected training
event.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

MODES = ("NOMINAL", "DEGRADED", "GNSS_UNAVAILABLE", "LOCAL_NAVIGATION", "UNKNOWN")


@dataclass
class NavParams:
    sigma_fix_m: float = 1.0
    sigma_degraded_m: float = 6.0
    degraded_fix_interval_s: float = 300.0
    drift_fraction: float = 0.03
    sigma_landmark_m: float = 3.0
    landmark_range_m: float = 150.0
    sigma_beacon_m: float = 1.5
    beacon_range_m: float = 250.0


@dataclass
class NavState:
    params: NavParams
    rng: np.random.Generator
    mode: str = "UNKNOWN"
    sigma_m: float = 0.0
    err: list = field(default_factory=lambda: [0.0, 0.0])
    _drift_dir: float = 0.0
    _since_fix_s: float = 0.0

    def initialise(self, mode: str) -> None:
        self.mode = mode
        self.sigma_m = self.params.sigma_degraded_m if mode == "DEGRADED" else self.params.sigma_fix_m
        self._drift_dir = float(self.rng.uniform(0, 2 * math.pi))
        self._set_error(self.sigma_m * 0.7)

    def _set_error(self, magnitude: float) -> None:
        a = float(self.rng.uniform(0, 2 * math.pi))
        self.err = [magnitude * math.cos(a), magnitude * math.sin(a)]

    def step(self, moved_m: float, dt: float) -> None:
        p = self.params
        if self.mode == "UNKNOWN":
            return
        if self.mode == "NOMINAL":
            self.sigma_m = p.sigma_fix_m
            self._set_error(abs(float(self.rng.normal(0, p.sigma_fix_m * 0.5))))
            return
        self._since_fix_s += dt
        if self.mode == "DEGRADED" and self._since_fix_s >= p.degraded_fix_interval_s:
            self._since_fix_s = 0.0
            self.sigma_m = p.sigma_degraded_m
            self._set_error(abs(float(self.rng.normal(0, p.sigma_degraded_m * 0.5))))
            return
        if moved_m > 0:  # dead reckoning drift
            self.sigma_m += p.drift_fraction * moved_m
            self._drift_dir += float(self.rng.normal(0, 0.05))
            step = p.drift_fraction * moved_m
            self.err[0] += step * math.cos(self._drift_dir) + float(self.rng.normal(0, step * 0.2))
            self.err[1] += step * math.sin(self._drift_dir) + float(self.rng.normal(0, step * 0.2))
            mag = math.hypot(*self.err)
            if mag > self.sigma_m * 1.2:  # keep the drawn error consistent with the modelled sigma
                self.err = [e * self.sigma_m * 1.2 / mag for e in self.err]

    def correct(self, sigma_after: float) -> float:
        before = self.sigma_m
        self.sigma_m = min(self.sigma_m, sigma_after)
        self._set_error(abs(float(self.rng.normal(0, self.sigma_m * 0.5))))
        self._since_fix_s = 0.0
        return before
