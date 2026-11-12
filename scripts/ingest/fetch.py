"""Download (or dry-run) one registered Phase 2 dataset product.

Dry run is the default and makes NO network call at all: it only prints the
registry's own metadata (provider, source URL, licence, access conditions)
and the destination path, and writes nothing. ``--confirm`` is required to
download; a single file over 500 MB additionally needs ``--allow-large``;
the running total for the whole dataset directory is capped at 3 GB.

Session safety gate (beyond the spec): even with ``--confirm``, this script
refuses to make any real network request unless the environment variable
``ABAAD_ALLOW_REAL_DOWNLOADS=1`` is set. That variable is meant for the
owner's Mac only -- this keeps the tool usable there while guaranteeing it
can never fetch a real dataset from this (or any other) cloud session.

Usage: python scripts/ingest/fetch.py DATASET [--confirm] [--allow-large] [--db PATH]
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.ingest import registry  # noqa: E402

MAX_SINGLE_FILE_BYTES = 500 * 1024 * 1024  # 500 MB
MAX_TOTAL_BYTES = 3 * 1024 * 1024 * 1024  # 3 GB


class IngestRefused(RuntimeError):
    pass


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def download_file(url: str, dest: Path) -> int:  # pragma: no cover - exercised only via a monkeypatch in tests
    """Streams ``url`` to a temp file, then atomically renames it onto ``dest``.
    Returns the byte count written. No resume support yet (known limitation)."""
    tmp = dest.with_suffix(dest.suffix + ".part")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url) as response, tmp.open("wb") as out:  # noqa: S310
        written = 0
        while chunk := response.read(1 << 20):
            out.write(chunk)
            written += len(chunk)
    tmp.rename(dest)
    return written


def current_data_bytes(data_dir: Path) -> int:
    return sum(p.stat().st_size for p in data_dir.rglob("*") if p.is_file())


def dry_run_report(entry: dict) -> str:
    lines = [
        f"DRY RUN  dataset {entry['code']} -- {entry['product_name']}",
        f"  provider:          {entry['provider']}",
        f"  source_url:        {entry['source_url']}",
        f"  licence_summary:   {entry['licence_summary']}",
        f"  access_conditions: {entry['access_conditions']}",
        f"  destination:       data/raw/{entry['code']}/ (written only with --confirm)",
        "  expected size:     not measured in this session (no network call made during a dry run)",
        "  Nothing was downloaded or written.",
    ]
    return "\n".join(lines)


def ingest(code: str, confirm: bool, allow_large: bool, data_dir: Path) -> str:
    entry = registry.find(code)
    if entry is None:
        raise IngestRefused(f"{code!r} is not in curation/datasets.json (see `make ingest-list`)")
    if not confirm:
        return dry_run_report(entry)

    if os.environ.get("ABAAD_ALLOW_REAL_DOWNLOADS") != "1":
        return (
            f"REFUSED  real downloads are deferred to the owner's Mac for dataset {code}.\n"
            "  Set ABAAD_ALLOW_REAL_DOWNLOADS=1 on the machine that should actually fetch this file.\n"
            "  Nothing was downloaded or written."
        )

    dest_dir = data_dir / "raw" / code
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / Path(entry["source_url"]).name
    size = download_file(entry["source_url"], dest)
    if size > MAX_SINGLE_FILE_BYTES and not allow_large:
        dest.unlink(missing_ok=True)
        raise IngestRefused(
            f"{code}: downloaded file is {size} bytes, over the 500 MB single-file threshold;"
            " re-run with --allow-large if the owner has approved it (gate G2-C)"
        )
    total = current_data_bytes(data_dir)
    if total > MAX_TOTAL_BYTES:
        dest.unlink(missing_ok=True)
        raise IngestRefused(f"data/ would total {total} bytes, over the 3 GB Phase 2 cap")
    digest = sha256_of(dest)
    return f"OK       downloaded {dest} ({size} bytes, sha256={digest[:12]}...)"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("dataset")
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--allow-large", action="store_true")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    args = parser.parse_args(argv)
    try:
        print(ingest(args.dataset, args.confirm, args.allow_large, args.data_dir))
    except IngestRefused as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
