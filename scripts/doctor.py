"""Environment verification report (Phase 1 deliverable 3).

Records the real platform and tool versions and performs clean import and
smoke tests of the GIS stack. Run on the target Mac with `make doctor`; the
report is printed and written to var/doctor-report.md.
"""

from __future__ import annotations

import importlib.metadata as md
import platform
import shutil
import sqlite3
import subprocess
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "var" / "doctor-report.md"
results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str) -> None:
    results.append((name, ok, detail))


def cmd(*args: str) -> str:
    exe = shutil.which(args[0])
    if not exe:
        return "NOT FOUND"
    try:
        return subprocess.run([exe, *args[1:]], capture_output=True, text=True, timeout=20).stdout.strip() or "?"
    except (OSError, subprocess.SubprocessError) as e:
        return f"error: {e}"


def wheel_tag(dist: str) -> str:
    try:
        files = md.distribution(dist).files or []
        wheel = next((f for f in files if f.name == "WHEEL"), None)
        if wheel is None:
            return "?"
        tags = [l.split(":", 1)[1].strip() for l in wheel.read_text().splitlines() if l.startswith("Tag:")]
        return ", ".join(tags) or "?"
    except md.PackageNotFoundError:
        return "not installed"


def platform_section() -> list[str]:
    mac = platform.mac_ver()[0]
    sw_vers = cmd("sw_vers") if sys.platform == "darwin" else "n/a (not macOS)"
    sqlite_v = sqlite3.sqlite_version
    strict = tuple(int(p) for p in sqlite_v.split(".")[:3]) >= (3, 37, 0)
    check("SQLite >= 3.37.0 (STRICT)", strict, sqlite_v)
    check("Python 3.12.x", sys.version_info[:2] == (3, 12), platform.python_version())
    node = cmd("node", "--version")
    check("Node.js present", node.startswith("v"), node)
    pnpm = cmd("pnpm", "--version")
    check("pnpm present", pnpm[:1].isdigit(), pnpm)
    return [
        f"| OS | {platform.system()} {platform.release()} |",
        f"| macOS version | {mac or 'n/a'} |",
        f"| sw_vers | {sw_vers.replace(chr(10), '; ')} |",
        f"| CPU architecture | {platform.machine()} |",
        f"| Python | {platform.python_version()} ({sys.executable}) |",
        f"| SQLite runtime | {sqlite_v} |",
        f"| Node.js | {node} |",
        f"| pnpm | {pnpm} |",
        f"| uv | {cmd('uv', '--version')} |",
        f"| Google Chrome | {chrome_version()} |",
    ]


def chrome_version() -> str:
    mac_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if Path(mac_path).exists():
        try:
            return subprocess.run([mac_path, "--version"], capture_output=True, text=True, timeout=20).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return "installed (version unknown)"
    return cmd("google-chrome", "--version")


def gis_section() -> list[str]:
    rows = []
    for dist in ("numpy", "rasterio", "shapely", "pyproj"):
        try:
            version = md.version(dist)
        except md.PackageNotFoundError:
            version = "NOT INSTALLED"
        rows.append(f"| {dist} | {version} | {wheel_tag(dist)} |")
    warnings.filterwarnings("ignore")

    try:
        import numpy as np
        a = np.arange(6, dtype="float64").reshape(2, 3)
        check("numpy import + array maths", float(a.sum()) == 15.0, np.__version__)
    except Exception as e:  # noqa: BLE001
        check("numpy import + array maths", False, repr(e))

    try:
        from pyproj import CRS, Transformer
        mars = CRS("IAU_2015:49900")
        t = Transformer.from_crs("IAU_2015:49900", "IAU_2015:49910", always_xy=True)
        x, _ = t.transform(45, 30)
        check("pyproj IAU_2015 Mars CRS + transform", "Mars" in mars.name and abs(x - 2667361.3885) < 0.01,
              f"{mars.name}; x(45°E)={x:.4f} m")
    except Exception as e:  # noqa: BLE001
        check("pyproj IAU_2015 Mars CRS + transform", False, repr(e))

    try:
        from shapely import wkt
        g = wkt.loads("POLYGON ((40 25, 50 25, 50 35, 40 35, 40 25))")
        check("shapely WKT parse + validity", g.is_valid and g.area == 100.0, f"area={g.area}")
    except Exception as e:  # noqa: BLE001
        check("shapely WKT parse + validity", False, repr(e))

    try:
        import numpy as np
        import rasterio
        from pyproj import CRS
        from rasterio.io import MemoryFile
        from rasterio.transform import from_origin
        crs = rasterio.crs.CRS.from_wkt(CRS("IAU_2015:49910").to_wkt())
        with MemoryFile() as mem:
            with mem.open(driver="GTiff", width=4, height=4, count=1, dtype="uint8", crs=crs,
                          transform=from_origin(0, 0, 1000, 1000)) as ds:
                ds.write(np.full((1, 4, 4), 7, dtype="uint8"))
            with mem.open() as ds:
                ok = ds.read(1)[0, 0] == 7 and "Mars" in ds.crs.to_wkt()
        check("rasterio GeoTIFF write/read in a Mars CRS", bool(ok), f"rasterio {rasterio.__version__}, GDAL {rasterio.__gdal_version__}")
    except Exception as e:  # noqa: BLE001
        check("rasterio GeoTIFF write/read in a Mars CRS", False, repr(e))
    return rows


def main() -> int:
    plat = platform_section()
    gis = gis_section()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# ABAAD environment report — {now}",
        "",
        "| Item | Value |", "| --- | --- |", *plat,
        "",
        "## GIS packages (installed wheel tags)",
        "",
        "| Package | Version | Wheel tag |", "| --- | --- | --- |", *gis,
        "",
        "## Checks",
        "",
        "| Check | Result | Detail |", "| --- | --- | --- |",
        *[f"| {n} | {'PASS' if ok else 'FAIL'} | {d} |" for n, ok, d in results],
        "",
    ]
    text = "\n".join(lines)
    print(text)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(text)
    failed = [n for n, ok, _ in results if not ok]
    print(f"Report written to {REPORT.relative_to(ROOT)}")
    print("doctor: ALL CHECKS PASSED" if not failed else f"doctor: {len(failed)} CHECK(S) FAILED: {', '.join(failed)}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
