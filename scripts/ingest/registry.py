"""Dataset registry: reads curation/datasets.json (never the network) and
reports what is planned, what is blocked, and rewrites data/manifest.json
from the database's data_asset table.

Usage:
  python scripts/ingest/registry.py list
  python scripts/ingest/registry.py manifest
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend" / "src"))
from abaad_api.config import get_settings  # noqa: E402

CURATION_DIR = ROOT / "curation"
DATA_DIR = ROOT / "data"

# Deferred per OD-3's default (skip all optional datasets) and D-P2-02 blocks on
# gates still open. Listed here only so `list` explains the full plan, not just
# what curation/datasets.json currently registers.
DEFERRED = {
    "DS-02": "REMA mosaic: blocked on gate V-6 (no University Valley position yet) and V-7 (CRS not stated on the page).",
    "DS-05b": "LDEM_80S_40M: optional sharper Moon test, skipped per OD-3's default.",
    "DS-06": "SRTM/ASTER cross-check at Dakhla: optional, skipped per OD-3's default.",
    "DS-07": "Landsat Collection 2 Level-2 SR: deferred, not needed for any Phase 2 acceptance criterion.",
}


def load_registry() -> list[dict]:
    return json.loads((CURATION_DIR / "datasets.json").read_text())["datasets"]


def find(code: str) -> dict | None:
    return next((d for d in load_registry() if d["code"] == code), None)


def cmd_list() -> int:
    print(f"{'code':<10} {'provider':<24} {'body':<6} {'status'}")
    for d in load_registry():
        print(f"{d['code']:<10} {d['provider']:<24} {d['body']:<6} planned (registered; dry run only until CONFIRM=1 on the Mac)")
    for code, reason in DEFERRED.items():
        print(f"{code:<10} {'-':<24} {'-':<6} deferred -- {reason}")
    return 0


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def cmd_manifest() -> int:
    """Rewrite data/manifest.json from data_asset rows (none ingested yet in
    this session; real entries are written here once the Mac ingests files)."""
    db_path = get_settings().db_path
    entries = []
    if db_path.exists():
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        for rel_path, sha, size in conn.execute("SELECT relative_path, sha256, size_bytes FROM data_asset"):
            entries.append({"path": rel_path, "sha256": sha, "bytes": size})
        conn.close()
    manifest_path = DATA_DIR / "manifest.json"
    manifest_path.write_text(json.dumps({"schema_version": 1, "files": entries}, indent=2) + "\n")
    print(f"Wrote {manifest_path} with {len(entries)} entries.")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv or argv[0] not in ("list", "manifest"):
        print(__doc__)
        return 1
    return cmd_list() if argv[0] == "list" else cmd_manifest()


if __name__ == "__main__":
    sys.exit(main())
