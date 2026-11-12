"""Tests for the Phase 2 ingestion tooling: dry run writes nothing, a
download is refused without a verified download_url (F-08), a plain
--confirm without the session-safety env var still writes nothing, the
500 MB/3 GB size gates are enforced with a mocked download (F-09), unsafe
URLs are rejected (F-08/8.2), and no secret-looking strings are hard-coded
in the tracked scripts."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.ingest import fetch, registry  # noqa: E402

FAKE_ENTRY_WITH_DOWNLOAD_URL = {
    "code": "DS-01", "provider": "Copernicus Data Space", "product_name": "Copernicus DEM GLO-30",
    "source_url": "https://dataspace.copernicus.eu/explore-data/...",
    "download_url": "https://dataspace.copernicus.eu/files/test-product.tif",
    "licence_summary": "x", "access_conditions": "x",
}


def test_registry_lists_all_registered_datasets():
    codes = {d["code"] for d in registry.load_registry()}
    assert codes == {"DS-01", "DS-03", "DS-04", "DS-05"}


def test_dry_run_makes_no_network_call_and_writes_nothing(tmp_path, monkeypatch):
    def _boom(*_a, **_kw):
        raise AssertionError("dry run must never call download_file")

    monkeypatch.setattr(fetch, "download_file", _boom)
    report = fetch.ingest("DS-01", confirm=False, allow_large=False, data_dir=tmp_path)
    assert "DRY RUN" in report
    assert not any(tmp_path.rglob("*"))


def test_no_curated_dataset_has_a_download_url_yet():
    """Hardening F-08: none of the four registered products has a verified
    direct file URL yet, so a real download is refused for all of them."""
    for d in registry.load_registry():
        assert d.get("download_url") is None


def test_confirm_without_download_url_is_refused(tmp_path, monkeypatch):
    monkeypatch.setenv("ABAAD_ALLOW_REAL_DOWNLOADS", "1")

    def _boom(*_a, **_kw):
        raise AssertionError("must never download without a verified download_url")

    monkeypatch.setattr(fetch, "download_file", _boom)
    with pytest.raises(fetch.IngestRefused, match="no verified download_url"):
        fetch.ingest("DS-01", confirm=True, allow_large=False, data_dir=tmp_path)
    assert not any(tmp_path.rglob("*"))


def test_confirm_without_allow_env_var_is_refused_and_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.delenv("ABAAD_ALLOW_REAL_DOWNLOADS", raising=False)
    monkeypatch.setattr(registry, "find", lambda code: FAKE_ENTRY_WITH_DOWNLOAD_URL)

    def _boom(*_a, **_kw):
        raise AssertionError("must never download without ABAAD_ALLOW_REAL_DOWNLOADS=1")

    monkeypatch.setattr(fetch, "download_file", _boom)
    report = fetch.ingest("DS-01", confirm=True, allow_large=False, data_dir=tmp_path)
    assert "REFUSED" in report
    assert not any(tmp_path.rglob("*"))


def test_unknown_dataset_code_is_refused():
    with pytest.raises(fetch.IngestRefused, match="not in curation"):
        fetch.ingest("DS-99", confirm=False, allow_large=False, data_dir=Path("."))


def test_oversized_file_is_rejected_without_allow_large(tmp_path, monkeypatch):
    monkeypatch.setenv("ABAAD_ALLOW_REAL_DOWNLOADS", "1")
    monkeypatch.setattr(registry, "find", lambda code: FAKE_ENTRY_WITH_DOWNLOAD_URL)
    big = fetch.MAX_SINGLE_FILE_BYTES + 1

    def _fake_download(_url: str, dest: Path, max_bytes: int) -> int:
        assert max_bytes <= fetch.MAX_SINGLE_FILE_BYTES  # the cap was actually passed in
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"x")  # content doesn't matter; we fake the reported size
        return big

    monkeypatch.setattr(fetch, "download_file", _fake_download)
    with pytest.raises(fetch.IngestRefused, match="500 MB"):
        fetch.ingest("DS-01", confirm=True, allow_large=False, data_dir=tmp_path)
    # the oversized file must be removed, not left behind
    assert not any((tmp_path / "raw" / "DS-01").glob("*"))


def test_oversized_file_accepted_with_allow_large(tmp_path, monkeypatch):
    monkeypatch.setenv("ABAAD_ALLOW_REAL_DOWNLOADS", "1")
    monkeypatch.setattr(registry, "find", lambda code: FAKE_ENTRY_WITH_DOWNLOAD_URL)
    big = fetch.MAX_SINGLE_FILE_BYTES + 1

    def _fake_download(_url: str, dest: Path, max_bytes: int) -> int:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"x" * 10)
        return big

    monkeypatch.setattr(fetch, "download_file", _fake_download)
    report = fetch.ingest("DS-01", confirm=True, allow_large=True, data_dir=tmp_path)
    assert report.startswith("OK")


def test_total_over_3gb_cap_is_rejected_before_streaming(tmp_path, monkeypatch):
    """Hardening F-09: the cap is enforced from the running total already on
    disk BEFORE any streaming starts, not only after the fact."""
    monkeypatch.setenv("ABAAD_ALLOW_REAL_DOWNLOADS", "1")
    monkeypatch.setattr(registry, "find", lambda code: FAKE_ENTRY_WITH_DOWNLOAD_URL)

    def _boom(*_a, **_kw):
        raise AssertionError("must never start streaming once the 3 GB cap is already exceeded")

    # Simulate 3 GB already on disk under data/ before this download.
    pre_existing = tmp_path / "raw" / "already-huge.bin"
    pre_existing.parent.mkdir(parents=True, exist_ok=True)
    with pre_existing.open("wb") as f:
        f.seek(fetch.MAX_TOTAL_BYTES)
        f.write(b"\0")

    monkeypatch.setattr(fetch, "download_file", _boom)
    with pytest.raises(fetch.IngestRefused, match="3 GB"):
        fetch.ingest("DS-01", confirm=True, allow_large=True, data_dir=tmp_path)


def test_download_file_rejects_non_https(tmp_path):
    with pytest.raises(fetch.IngestRefused, match="non-https"):
        fetch.download_file("http://dataspace.copernicus.eu/x.tif", tmp_path / "x.tif", 1000)


def test_download_file_rejects_host_not_on_allowlist(tmp_path):
    with pytest.raises(fetch.IngestRefused, match="allowlist"):
        fetch.download_file("https://evil.example.com/x.tif", tmp_path / "x.tif", 1000)


def test_no_credential_shaped_strings_in_tracked_ingest_scripts():
    pattern = re.compile(r"(password|secret|api[_-]?key|token)\s*=\s*['\"][^'\"]+['\"]", re.IGNORECASE)
    for path in (ROOT / "scripts").rglob("*.py"):
        text = path.read_text()
        for match in pattern.finditer(text):
            assert False, f"{path}: looks like a hard-coded credential: {match.group(0)!r}"
