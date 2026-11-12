# Environment verification report (deliverable 3)

Two environments are kept strictly apart. Nothing below claims a result on the owner's Mac unless it was produced there.

## A. Cloud workspace (tested by Claude, 2026-11-12)

Full output: [evidence/doctor-cloud-linux.md](evidence/doctor-cloud-linux.md)

| Item | Value |
| --- | --- |
| OS / CPU | Linux 6.18 (x86_64) — **not macOS, not Apple Silicon** |
| Python | 3.12.3 |
| SQLite runtime (Python `sqlite3.sqlite_version`) | 3.45.1 (≥ 3.37.0, STRICT supported) |
| Node.js / pnpm | v22.23.4 / 10.28.0 |
| uv | 0.11.32 |
| Chrome | Google Chrome for Testing 153.0.8010.12 |
| numpy / rasterio / shapely / pyproj | 2.5.4 / 1.5.2 (GDAL 3.12.2) / 2.2.0 / 3.8.0, manylinux wheels |
| GIS smoke checks | numpy arrays PASS · pyproj IAU_2015:49900→49910 transform PASS · shapely WKT PASS · rasterio GeoTIFF write/read in a Mars CRS PASS |

## B. Owner's Mac (macOS 27.2, M3 Pro, 18 GB) — **NOT YET RUN**

Wheel metadata checked on PyPI (not installed): cp312 macOS arm64 wheels exist for numpy 2.5.4 (macosx_11_0 / 14_0), rasterio 1.5.2 (**macosx_15_0**), shapely 2.2.0 (macosx_11_0) and pyproj 3.8.0 (macosx_14_0). All minimums are below 27.2, but installation is unverified until you run:

```bash
make install && make doctor
```

Paste `var/doctor-report.md` into this file under a heading "B. Owner's Mac — results". Expected: macOS 27.2, `arm64`, Python 3.12.x, SQLite ≥ 3.37.0, and all checks PASS.
