"""Deterministic synthetic training terrain.

The terrain is procedurally generated from a seed: spectral noise, a gentle
regional tilt, bowl-shaped craters with raised rims, one template ridge with
a saddle (placed so that the target is hidden from the base station, which
creates a communication-occlusion training event), and boulder-field no-go
zones. It is NOT derived from any real lunar or Earth elevation data and is
labelled "Synthetic / Demonstration" everywhere it is shown.

Grid convention: ``z[row, col]``; row 0 is the southern edge, col 0 the
western edge. Cell centres are at ``((col + 0.5) * cell, (row + 0.5) * cell)``
in a local metric frame (x east, y north, metres). The frame is not
geo-referenced.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np

GENERATOR_NAME = "abaad-synthetic-training-terrain"
GENERATOR_VERSION = "1.0.0"
LOCAL_FRAME = "ABAAD-LOCAL-SYNTHETIC (metres, x east, y north, not geo-referenced)"

# Scenario template geometry (local metres). These are design parameters of
# the synthetic training range, not measurements of any real place.
BASE_XY = (150.0, 170.0)
DEFAULT_START_XY = (200.0, 230.0)
DEFAULT_TARGET_XY = (1060.0, 1040.0)
RIDGE = {"cx": 650.0, "cy": 640.0, "azimuth_deg": 135.0, "length_m": 760.0, "width_m": 55.0,
         "height_m": 38.0, "saddle_offset_m": 120.0, "saddle_depth": 0.55}
BLOCKAGE = {"cx": 400.0, "cy": 360.0, "height_m": 24.0, "sigma_m": 34.0}
KEEP_CLEAR = [BASE_XY, DEFAULT_START_XY, DEFAULT_TARGET_XY]


@dataclass(frozen=True)
class TerrainSpec:
    seed: int = 20261113
    n: int = 160
    cell_m: float = 8.0
    blockage: bool = False


@dataclass
class Terrain:
    spec: TerrainSpec
    z: np.ndarray
    slope_deg: np.ndarray
    roughness_m: np.ndarray
    nogo: np.ndarray
    craters: list[dict] = field(default_factory=list)
    hazards: list[dict] = field(default_factory=list)
    landmarks: list[dict] = field(default_factory=list)
    sha256: str = ""

    @property
    def n(self) -> int:
        return self.spec.n

    @property
    def cell(self) -> float:
        return self.spec.cell_m

    @property
    def extent_m(self) -> float:
        return self.spec.n * self.spec.cell_m

    def inside(self, x: float, y: float) -> bool:
        return 0.0 <= x <= self.extent_m and 0.0 <= y <= self.extent_m

    def cell_of(self, x: float, y: float) -> tuple[int, int]:
        """(row, col) of the cell containing (x, y), clipped to the grid."""
        c = min(self.n - 1, max(0, int(x // self.cell)))
        r = min(self.n - 1, max(0, int(y // self.cell)))
        return r, c

    def centre(self, r: int, c: int) -> tuple[float, float]:
        return ((c + 0.5) * self.cell, (r + 0.5) * self.cell)

    def elevation(self, x, y):
        """Bilinear elevation at metric coordinates (scalars or arrays)."""
        return bilinear(self.z, self.cell, x, y)

    def metadata(self) -> dict:
        return {
            "status": "synthetic",
            "label": "Synthetic / Demonstration",
            "generator": GENERATOR_NAME,
            "generator_version": GENERATOR_VERSION,
            "seed": self.spec.seed,
            "grid_cells": [self.n, self.n],
            "cell_size_m": self.cell,
            "extent_m": self.extent_m,
            "frame": LOCAL_FRAME,
            "injected_blockage": self.spec.blockage,
            "elevation_sha256": self.sha256,
            "elevation_range_m": [round(float(self.z.min()), 2), round(float(self.z.max()), 2)],
            "processing": [
                "spectral noise (power-law amplitude, exponent 1.2) scaled to 1.5 m standard deviation",
                "regional tilt 0.01 east, 0.005 north (dimensionless) and a 6 m low rise under the base station",
                "bowl craters with raised rims (template generator)",
                "template ridge with saddle (communication-occlusion training feature)",
                "boulder-field no-go zones (hard constraint)",
                "slope from central differences on the metric grid (numpy.gradient)",
                "roughness = RMS residual from the 3x3 mean elevation",
            ],
            "not_derived_from": "any real lunar or Earth elevation dataset",
        }


def bilinear(z: np.ndarray, cell: float, x, y):
    n = z.shape[0]
    fx = np.clip(np.asarray(x, dtype=float) / cell - 0.5, 0, n - 1.000001)
    fy = np.clip(np.asarray(y, dtype=float) / cell - 0.5, 0, n - 1.000001)
    c0 = np.floor(fx).astype(int)
    r0 = np.floor(fy).astype(int)
    tx = fx - c0
    ty = fy - r0
    z00 = z[r0, c0]
    z01 = z[r0, c0 + 1]
    z10 = z[r0 + 1, c0]
    z11 = z[r0 + 1, c0 + 1]
    return (z00 * (1 - tx) * (1 - ty) + z01 * tx * (1 - ty) + z10 * (1 - tx) * ty + z11 * tx * ty)


def _far_from(points, x, y, d) -> bool:
    return all(math.hypot(x - px, y - py) >= d for px, py in points)


def _generate(spec: TerrainSpec) -> Terrain:
    rng = np.random.default_rng(spec.seed)
    n, cell = spec.n, spec.cell_m
    coords = (np.arange(n) + 0.5) * cell
    X, Y = np.meshgrid(coords, coords)  # X[row, col], Y[row, col]

    # 1. Spectral noise
    kx = np.fft.fftfreq(n)
    K = np.sqrt(kx[None, :] ** 2 + kx[:, None] ** 2)
    K[0, 0] = np.inf
    amp = K ** -1.2
    phase = rng.uniform(0, 2 * np.pi, (n, n))
    noise = np.real(np.fft.ifft2(amp * np.exp(1j * phase)))
    noise = (noise - noise.mean()) / noise.std()
    z = 1.5 * noise
    # 2. Regional tilt and a low rise under the lander/base station (template)
    z += 0.01 * X + 0.005 * Y
    z += 6.0 * np.exp(-((X - BASE_XY[0]) ** 2 + (Y - BASE_XY[1]) ** 2) / (2 * 80.0 ** 2))

    # 3. Craters (kept away from base, start and target)
    craters = []
    tries = 0
    while len(craters) < 18 and tries < 500:
        tries += 1
        d = float(rng.uniform(30, 180))
        cx, cy = (float(v) for v in rng.uniform(0.05 * n * cell, 0.95 * n * cell, 2))
        if not _far_from(KEEP_CLEAR, cx, cy, d / 2 + 70):
            continue
        rad = d / 2
        r = np.hypot(X - cx, Y - cy) / rad
        depth, rim = 0.18 * d, 0.04 * d
        inside = rim - (depth + rim) * (1 - r ** 2)
        outside = rim * np.exp(-(((r - 1) / 0.3) ** 2))
        z += np.where(r < 1, inside, outside)
        craters.append({"x": round(cx, 1), "y": round(cy, 1), "diameter_m": round(d, 1)})

    # 4. Template ridge with a saddle
    az = math.radians(RIDGE["azimuth_deg"])
    ux, uy = math.sin(az), math.cos(az)  # along-axis unit vector (azimuth from north)
    dx, dy = X - RIDGE["cx"], Y - RIDGE["cy"]
    u = dx * ux + dy * uy
    v = -dx * uy + dy * ux
    half = RIDGE["length_m"] / 2
    taper = np.exp(-((u / half) ** 6))
    saddle = 1 - RIDGE["saddle_depth"] * np.exp(-(((u - RIDGE["saddle_offset_m"]) / 60.0) ** 2))
    z += RIDGE["height_m"] * np.exp(-((v / RIDGE["width_m"]) ** 2)) * taper * saddle

    # 5. Optional injected blockage (training control)
    if spec.blockage:
        z += BLOCKAGE["height_m"] * np.exp(
            -((X - BLOCKAGE["cx"]) ** 2 + (Y - BLOCKAGE["cy"]) ** 2) / (2 * BLOCKAGE["sigma_m"] ** 2))

    # 6. Boulder-field no-go zones
    hazards = []
    tries = 0
    nogo = np.zeros((n, n), dtype=bool)
    while len(hazards) < 4 and tries < 500:
        tries += 1
        hx, hy = (float(v) for v in rng.uniform(0.15 * n * cell, 0.85 * n * cell, 2))
        hr = float(rng.uniform(25, 45))
        if not _far_from(KEEP_CLEAR, hx, hy, hr + 110):
            continue
        hazards.append({"x": round(hx, 1), "y": round(hy, 1), "radius_m": round(hr, 1), "kind": "boulder_field"})
        nogo |= np.hypot(X - hx, Y - hy) <= hr

    # Derived layers on the metric grid
    gy, gx = np.gradient(z, cell)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    pad = np.pad(z, 1, mode="edge")
    mean3 = sum(pad[i:i + n, j:j + n] for i in range(3) for j in range(3)) / 9.0
    resid2 = sum((pad[i:i + n, j:j + n] - mean3) ** 2 for i in range(3) for j in range(3)) / 9.0
    rough = np.sqrt(resid2)

    # Landmarks: centres of craters >= 60 m across (mapped features in the training map)
    big = sorted((c for c in craters if c["diameter_m"] >= 60), key=lambda c: -c["diameter_m"])
    landmarks = [{"id": f"LM-{i + 1}", "x": c["x"], "y": c["y"], "kind": "mapped_crater",
                  "diameter_m": c["diameter_m"]} for i, c in enumerate(big)]

    sha = hashlib.sha256(z.astype(np.float32).tobytes()).hexdigest()
    return Terrain(spec=spec, z=z, slope_deg=slope, roughness_m=rough, nogo=nogo,
                   craters=craters, hazards=hazards, landmarks=landmarks, sha256=sha)


@lru_cache(maxsize=16)
def get_terrain(seed: int = 20261113, blockage: bool = False) -> Terrain:
    return _generate(TerrainSpec(seed=seed, blockage=blockage))


def hillshade(t: Terrain, azimuth_deg: float = 315.0, altitude_deg: float = 25.0) -> np.ndarray:
    gy, gx = np.gradient(t.z, t.cell)
    slope = np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gx, gy)
    az = math.radians(azimuth_deg)
    alt = math.radians(altitude_deg)
    shade = np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(az - aspect)
    return np.clip(shade, 0, 1)
