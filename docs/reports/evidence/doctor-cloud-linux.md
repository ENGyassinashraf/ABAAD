# ABAAD environment report — 2026-11-12 11:44 UTC

| Item | Value |
| --- | --- |
| OS | Linux 6.18.44-fc-v378 |
| macOS version | n/a |
| sw_vers | n/a (not macOS) |
| CPU architecture | x86_64 |
| Python | 3.12.3 (/home/claude/abaad/.venv/bin/python) |
| SQLite runtime | 3.45.1 |
| Node.js | v22.23.4 |
| pnpm | 10.28.0 |
| uv | uv 0.11.32 (x86_64-unknown-linux-gnu) |
| Google Chrome | Google Chrome for Testing 153.0.8010.12 |

## GIS packages (installed wheel tags)

| Package | Version | Wheel tag |
| --- | --- | --- |
| numpy | 2.5.4 | cp312-cp312-manylinux_2_27_x86_64, cp312-cp312-manylinux_2_28_x86_64 |
| rasterio | 1.5.2 | cp312-cp312-manylinux_2_28_x86_64 |
| shapely | 2.2.0 | cp312-cp312-manylinux_2_24_x86_64, cp312-cp312-manylinux_2_28_x86_64 |
| pyproj | 3.8.0 | cp312-cp312-manylinux_2_28_x86_64 |

## Checks

| Check | Result | Detail |
| --- | --- | --- |
| SQLite >= 3.37.0 (STRICT) | PASS | 3.45.1 |
| Python 3.12.x | PASS | 3.12.3 |
| Node.js present | PASS | v22.23.4 |
| pnpm present | PASS | 10.28.0 |
| numpy import + array maths | PASS | 2.5.4 |
| pyproj IAU_2015 Mars CRS + transform | PASS | Mars (2015) - Sphere / Ocentric; x(45°E)=2667361.3885 m |
| shapely WKT parse + validity | PASS | area=100.0 |
| rasterio GeoTIFF write/read in a Mars CRS | PASS | rasterio 1.5.2, GDAL 3.12.2 |
