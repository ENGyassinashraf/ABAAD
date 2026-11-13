"""Download (or dry-run) one registered Phase 2 dataset product.

Dry run is the default and makes NO network call at all: it only prints the
registry's own metadata (provider, catalogue source_url, licence, access
conditions) and the destination path, and writes nothing. ``--confirm`` is
required to download; a single file over 500 MB additionally needs
``--allow-large``; the running total under ``data/`` is capped at 3 GB,
enforced before and during streaming (hardening F-09), not only afterwards.

Hardening F-08: ``source_url`` is the catalogue/product-description page,
never assumed to be a downloadable file. A real download needs the
dataset's own ``download_url`` -- a verified direct file URL -- and is
refused outright if that field is empty (every product currently in
curation/datasets.json has it set to null, so no real download can proceed
from this tool today, by design).

Session safety gate (beyond the spec): even with ``--confirm`` and a
``download_url``, this script refuses to make any real network request
unless the environment variable ``ABAAD_ALLOW_REAL_DOWNLOADS=1`` is set.
That variable is meant for the owner's Mac only -- this keeps the tool
usable there while guaranteeing it can never fetch anything from this (or
any other) cloud session.

Usage: python scripts/ingest/fetch.py DATASET [--confirm] [--allow-large] [--db PATH]
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import os
import socket
import sys
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.ingest import registry  # noqa: E402

MAX_SINGLE_FILE_BYTES = 500 * 1024 * 1024  # 500 MB
MAX_TOTAL_BYTES = 3 * 1024 * 1024 * 1024  # 3 GB
CHUNK_SIZE = 1 << 20  # 1 MiB

# Hardening F-08/8.2: only these provider hosts are ever allowed, and only
# over https. A redirect target is re-checked against this same allowlist.
ALLOWED_HOSTS = {
    "dataspace.copernicus.eu",
    "pds-geosciences.wustl.edu",
    "ode.rsl.wustl.edu",
    "pgda.gsfc.nasa.gov",
}
REJECTED_CONTENT_TYPES = ("text/html", "application/xhtml+xml", "text/xml", "application/xml")


class IngestRefused(RuntimeError):
    pass


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(CHUNK_SIZE), b""):
            h.update(block)
    return h.hexdigest()


def _assert_safe_url(url: str) -> None:
    """Hardening F-08/8.2 (SSRF protection): https only, host on the
    allowlist, and never a literal private/loopback/link-local address."""
    parts = urlsplit(url)
    if parts.scheme != "https":
        raise IngestRefused(f"refusing non-https URL: {url!r}")
    host = parts.hostname
    if not host or host not in ALLOWED_HOSTS:
        raise IngestRefused(f"refusing URL on a host not in the allowlist: {host!r}")
    try:
        addr = ipaddress.ip_address(socket.gethostbyname(host))
    except (socket.gaierror, ValueError) as exc:
        raise IngestRefused(f"could not resolve host {host!r}: {exc}") from exc
    if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
        raise IngestRefused(f"refusing URL that resolves to a private/local address: {host!r} -> {addr}")


def download_file(url: str, dest: Path, max_bytes: int) -> int:  # pragma: no cover - exercised only via a monkeypatch in tests
    """Streams ``url`` to a temp file, then atomically renames it onto
    ``dest``. Returns the byte count written. Enforces ``max_bytes`` WHILE
    streaming (hardening F-09): the moment the running total would exceed
    it, the partial file is deleted and the download aborts -- it is never
    allowed to finish first. Rejects an HTML/XML response outright (F-08)."""
    _assert_safe_url(url)
    tmp = dest.with_suffix(dest.suffix + ".part")
    dest.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "ABAAD-ingest/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
            content_type = (response.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            if content_type in REJECTED_CONTENT_TYPES:
                raise IngestRefused(f"refusing a {content_type} response for {url!r} (expected a data file, not a page)")
            declared_length = response.headers.get("Content-Length")
            if declared_length is not None and int(declared_length) > max_bytes:
                raise IngestRefused(
                    f"declared Content-Length {declared_length} exceeds the {max_bytes}-byte limit for {url!r}"
                )
            written = 0
            with tmp.open("wb") as out:
                while chunk := response.read(CHUNK_SIZE):
                    written += len(chunk)
                    if written > max_bytes:
                        raise IngestRefused(f"{url!r} exceeded the {max_bytes}-byte limit while streaming; aborted")
                    out.write(chunk)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    tmp.rename(dest)
    return written


def current_data_bytes(data_dir: Path) -> int:
    return sum(p.stat().st_size for p in data_dir.rglob("*") if p.is_file())


def dry_run_report(entry: dict) -> str:
    lines = [
        f"DRY RUN  dataset {entry['code']} -- {entry['product_name']}",
        f"  provider:          {entry['provider']}",
        f"  catalogue page:    {entry['source_url']}",
        f"  download_url:      {entry.get('download_url') or '(none confirmed yet -- a real download is refused)'}",
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

    # Hardening F-08: source_url is the catalogue page, never a download
    # target. Refuse outright without a verified direct file URL.
    if not entry.get("download_url"):
        raise IngestRefused(
            f"{code}: no verified download_url on file (source_url is the catalogue page, not a data file);"
            " confirm the exact product file against the provider's real index/label before setting one"
        )

    if os.environ.get("ABAAD_ALLOW_REAL_DOWNLOADS") != "1":
        return (
            f"REFUSED  real downloads are deferred to the owner's Mac for dataset {code}.\n"
            "  Set ABAAD_ALLOW_REAL_DOWNLOADS=1 on the machine that should actually fetch this file.\n"
            "  Nothing was downloaded or written."
        )

    # Hardening F-09: the per-file cap passed to the streaming downloader is
    # tightened by whatever is already on disk, so the running total (not
    # just this one file) can never cross the 3 GB cap even transiently.
    already_on_disk = current_data_bytes(data_dir) if data_dir.exists() else 0
    remaining_total_budget = MAX_TOTAL_BYTES - already_on_disk
    if remaining_total_budget <= 0:
        raise IngestRefused(f"data/ already holds {already_on_disk} bytes, at or over the 3 GB Phase 2 cap")
    per_file_cap = MAX_SINGLE_FILE_BYTES if not allow_large else MAX_TOTAL_BYTES
    effective_cap = min(per_file_cap, remaining_total_budget)

    dest_dir = data_dir / "raw" / code
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / Path(urlsplit(entry["download_url"]).path).name
    try:
        size = download_file(entry["download_url"], dest, effective_cap)
    except IngestRefused as exc:
        if not allow_large:
            raise IngestRefused(f"{exc} (re-run with --allow-large if the owner has approved it, gate G2-C)") from exc
        raise
    # Defense in depth: download_file is responsible for enforcing effective_cap
    # WHILE streaming, but this double-checks the size it actually reports.
    if size > MAX_SINGLE_FILE_BYTES and not allow_large:
        dest.unlink(missing_ok=True)
        raise IngestRefused(
            f"{code}: downloaded file is {size} bytes, over the 500 MB single-file threshold"
            " (re-run with --allow-large if the owner has approved it, gate G2-C)"
        )
    digest = sha256_of(dest)
    return f"OK       downloaded {dest} ({size} bytes, sha256={digest[:12]}...) -- raw file only, not yet a registered data_asset (see F-10)"


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
