"""Generate SYNTHETIC map-spike fixtures (Phase 1, test T2/T3/T5 only).

Nothing produced here is scientific data. The Mars raster is an invented
pattern (graticule, three control-point markers and a rectangle) used only to
check that MapLibre places tiles and overlays in a declared planetary CRS
without hidden reprojection. Outputs go to frontend/public/spike-fixtures/.

CRS decisions (all verified with pyproj's IAU_2015 definitions):
* Geometry CRS  IAU_2015:49900 — Mars (2015) Sphere / Ocentric, lon east,
  domain -180..180, degrees, axis order lon/lat.
* Display CRS   IAU_2015:49910 — Mars (2015) Sphere / Ocentric /
  Equirectangular, clon = 0 (+proj=eqc +R=3396190), metres.
* Tile matrix   "ABAAD-MarsEqcQuad": square power-of-two quad grid,
  origin (-pi*R, +pi*R), extent at zoom 0 = 2*pi*R, 512-px tiles, zoom 0-3.
  Rows outside +-90 deg latitude are transparent.
* Moon panel    IAU_2015:30135 — Moon (2015) Sphere / Ocentric / South Polar
  (+proj=stere +lat_0=-90 +k=1 +R=1737400); reference values for the TS tests.

Run:  uv run python spike/generate_fixtures.py
"""

from __future__ import annotations

import json
import math
import struct
import warnings
import zlib
from pathlib import Path

import numpy as np
from pyproj import CRS, Transformer

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "public" / "spike-fixtures"

GEOM_CRS = "IAU_2015:49900"
DISPLAY_CRS = "IAU_2015:49910"
MOON_GEOG = "IAU_2015:30100"
MOON_POLAR = "IAU_2015:30135"
TILE = 512
MAX_ZOOM = 3

LABEL = "SYNTHETIC TEST FIXTURE — map feasibility spike only; not scientific data"

# Invented control points (not real features).
CONTROL_POINTS = [
    {"id": "CP-A", "lon": 0.0, "lat": 0.0},
    {"id": "CP-B", "lon": 45.0, "lat": 30.0},
    {"id": "CP-C", "lon": -120.0, "lat": -60.0},
]
TEST_POLYGON_WKT = "POLYGON ((40 25, 50 25, 50 35, 40 35, 40 25))"
POLY_LON = (40.0, 50.0)
POLY_LAT = (25.0, 35.0)

COLORS = {
    "background": (232, 217, 189, 255),
    "graticule": (110, 96, 70, 255),
    "polygon": (255, 214, 0, 255),
    "marker": (255, 0, 255, 255),
}


def png_bytes(rgba: np.ndarray) -> bytes:
    """Minimal PNG encoder (RGBA8), so no imaging dependency is needed."""
    h, w, _ = rgba.shape
    raw = b"".join(b"\x00" + rgba[row].tobytes() for row in range(h))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def render_tile(z: int, tx: int, ty: int, radius: float, origin: tuple[float, float], extent0: float) -> np.ndarray:
    res = extent0 / (TILE * 2**z)  # metres per pixel
    i = np.arange(TILE) + 0.5
    x = origin[0] + (tx * TILE + i) * res  # pixel-centre CRS x
    y = origin[1] - (ty * TILE + i) * res  # pixel-centre CRS y
    X, Y = np.meshgrid(x, y)
    lon = np.degrees(X / radius)
    lat = np.degrees(Y / radius)
    px_deg = math.degrees(res / radius)  # one pixel in degrees

    img = np.zeros((TILE, TILE, 4), dtype=np.uint8)
    inside = np.abs(lat) <= 90.0
    img[inside] = COLORS["background"]

    def near_multiple(a: np.ndarray, step: float) -> np.ndarray:
        return np.abs(a - step * np.round(a / step)) < 0.6 * px_deg

    grat = inside & (near_multiple(lon, 30.0) | near_multiple(lat, 30.0))
    img[grat] = COLORS["graticule"]

    in_lon = (lon >= POLY_LON[0] - 0.6 * px_deg) & (lon <= POLY_LON[1] + 0.6 * px_deg)
    in_lat = (lat >= POLY_LAT[0] - 0.6 * px_deg) & (lat <= POLY_LAT[1] + 0.6 * px_deg)
    edge = (
        (in_lat & ((np.abs(lon - POLY_LON[0]) < 0.6 * px_deg) | (np.abs(lon - POLY_LON[1]) < 0.6 * px_deg)))
        | (in_lon & ((np.abs(lat - POLY_LAT[0]) < 0.6 * px_deg) | (np.abs(lat - POLY_LAT[1]) < 0.6 * px_deg)))
    )
    img[edge & inside] = COLORS["polygon"]

    # 3x3-pixel markers centred on each control point (radius = 1 source pixel).
    for cp in CONTROL_POINTS:
        cx, cy = math.radians(cp["lon"]) * radius, math.radians(cp["lat"]) * radius
        hit = (np.abs(X - cx) <= 1.0 * res) & (np.abs(Y - cy) <= 1.0 * res)
        img[hit] = COLORS["marker"]
    return img


def main() -> None:
    warnings.filterwarnings("ignore", category=UserWarning)
    display = CRS(DISPLAY_CRS)
    radius = display.ellipsoid.semi_major_metre
    assert display.ellipsoid.semi_minor_metre == radius, "expected a sphere"
    extent0 = 2 * math.pi * radius
    origin = (-math.pi * radius, math.pi * radius)

    to_display = Transformer.from_crs(GEOM_CRS, DISPLAY_CRS, always_xy=True)
    cps = []
    for cp in CONTROL_POINTS:
        x, y = to_display.transform(cp["lon"], cp["lat"])
        cps.append({**cp, "expected_x_m": x, "expected_y_m": y})

    tiles_dir = OUT / "mars-eqc"
    count = 0
    for z in range(MAX_ZOOM + 1):
        for tx in range(2**z):
            for ty in range(2**z):
                path = tiles_dir / str(z) / str(tx) / f"{ty}.png"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(png_bytes(render_tile(z, tx, ty, radius, origin, extent0)))
                count += 1

    mars = {
        "label": LABEL,
        "synthetic": True,
        "body": "mars",
        "geometry": {
            "crs": GEOM_CRS,
            "crs_name": CRS(GEOM_CRS).name,
            "encoding": "ogc_wkt",
            "coordinate_units": "degree",
            "latitude_type": "planetocentric",
            "longitude_direction": "east",
            "longitude_domain": "-180..180",
            "axis_order": "lon_lat",
            "wkt": TEST_POLYGON_WKT,
        },
        "control_points": cps,
        "display": {
            "crs": DISPLAY_CRS,
            "crs_name": display.name,
            "proj": "+proj=eqc +lat_ts=0 +lat_0=0 +lon_0=0 +x_0=0 +y_0=0 +R=3396190 +units=m",
            "radius_m": radius,
        },
        "tile_matrix": {
            "id": "ABAAD-MarsEqcQuad",
            "origin": list(origin),
            "extentAtZoom0": extent0,
            "tileSize": TILE,
            "minzoom": 0,
            "maxzoom": MAX_ZOOM,
            "url": "/spike-fixtures/mars-eqc/{z}/{x}/{y}.png",
        },
        "colors": {k: list(v) for k, v in COLORS.items()},
        "alignment_tolerance_source_px": 1.0,
    }
    (OUT / "mars_fixture.json").write_text(json.dumps(mars, indent=2) + "\n")

    moon_crs = CRS(MOON_POLAR)
    to_polar = Transformer.from_crs(MOON_GEOG, MOON_POLAR, always_xy=True)
    samples = [(0, -90), (0, -80), (90, -85), (45, -88), (180, -82), (-60, -86)]
    moon = {
        "label": LABEL,
        "synthetic": True,
        "body": "moon",
        "crs": MOON_POLAR,
        "crs_name": moon_crs.name,
        "proj": "+proj=stere +lat_0=-90 +lon_0=0 +k=1 +R=1737400",
        "radius_m": moon_crs.ellipsoid.semi_major_metre,
        "reference_points": [
            {"lon": lon, "lat": lat, "x_m": to_polar.transform(lon, lat)[0], "y_m": to_polar.transform(lon, lat)[1]}
            for lon, lat in samples
        ],
    }
    (OUT / "moon_reference.json").write_text(json.dumps(moon, indent=2) + "\n")
    print(f"Wrote {count} synthetic Mars tiles and 2 fixture files to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
