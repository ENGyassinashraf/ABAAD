"""Validate data/manifest.json against the files under data/.

* No entries and no files  -> "No data files yet" (success).
* Every manifest entry must exist with the recorded size and SHA-256.
* Files present under data/ but missing from the manifest are reported (failure).

Usage: python scripts/verify_data.py [--data-dir DIR]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IGNORED = {"README.md", "manifest.json", ".gitkeep", ".DS_Store"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def verify(data_dir: Path) -> tuple[bool, list[str]]:
    manifest_path = data_dir / "manifest.json"
    if not manifest_path.exists():
        return False, [f"ERROR: {manifest_path} not found"]
    manifest = json.loads(manifest_path.read_text())
    entries = manifest.get("files", [])
    on_disk = {
        p.relative_to(data_dir).as_posix()
        for p in data_dir.rglob("*")
        if p.is_file() and p.name not in IGNORED
    }
    messages: list[str] = []
    ok = True
    listed = set()
    for entry in entries:
        rel = entry["path"]
        listed.add(rel)
        path = data_dir / rel
        if not path.exists():
            ok = False
            messages.append(f"MISSING   {rel}")
            continue
        if "bytes" in entry and path.stat().st_size != entry["bytes"]:
            ok = False
            messages.append(f"SIZE      {rel}: expected {entry['bytes']}, found {path.stat().st_size}")
            continue
        digest = sha256(path)
        if digest != entry["sha256"]:
            ok = False
            messages.append(f"CHECKSUM  {rel}: expected {entry['sha256'][:12]}…, found {digest[:12]}…")
        else:
            messages.append(f"OK        {rel}")
    for rel in sorted(on_disk - listed):
        ok = False
        messages.append(f"UNLISTED  {rel} (present in data/ but not in manifest.json)")
    if not entries and not on_disk:
        messages.append("No data files yet: manifest has 0 entries and data/ holds no data files. OK.")
    return ok, messages


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    args = parser.parse_args()
    ok, messages = verify(args.data_dir)
    print("\n".join(messages))
    print("verify-data: PASSED" if ok else "verify-data: FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
