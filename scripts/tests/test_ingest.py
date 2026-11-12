"""Tests for the Phase 2 ingestion tooling: dry run writes nothing, a plain
--confirm without the session-safety env var still writes nothing, the
500 MB/3 GB size gates are enforced with a mocked download, and no secret
looking strings are hard-coded in the tracked scripts."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.ingest import fetch, registry  # noqa: E402


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


def test_confirm_without_allow_env_var_is_refused_and_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.delenv("ABAAD_ALLOW_REAL_DOWNLOADS", raising=False)

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
    big = fetch.MAX_SINGLE_FILE_BYTES + 1

    def _fake_download(_url: str, dest: Path) -> int:
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
    big = fetch.MAX_SINGLE_FILE_BYTES + 1

    def _fake_download(_url: str, dest: Path) -> int:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"x" * 10)
        return big

    monkeypatch.setattr(fetch, "download_file", _fake_download)
    report = fetch.ingest("DS-01", confirm=True, allow_large=True, data_dir=tmp_path)
    assert report.startswith("OK")


def test_total_over_3gb_cap_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("ABAAD_ALLOW_REAL_DOWNLOADS", "1")

    def _fake_download(_url: str, dest: Path) -> int:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"x" * 10)
        return 1024  # small file, but the *existing* data/ dir is already huge

    # Simulate 3 GB already on disk under data/ before this download.
    pre_existing = tmp_path / "raw" / "already-huge.bin"
    pre_existing.parent.mkdir(parents=True, exist_ok=True)
    with pre_existing.open("wb") as f:
        f.seek(fetch.MAX_TOTAL_BYTES)
        f.write(b"\0")

    monkeypatch.setattr(fetch, "download_file", _fake_download)
    with pytest.raises(fetch.IngestRefused, match="3 GB"):
        fetch.ingest("DS-01", confirm=True, allow_large=True, data_dir=tmp_path)


def test_no_credential_shaped_strings_in_tracked_ingest_scripts():
    pattern = re.compile(r"(password|secret|api[_-]?key|token)\s*=\s*['\"][^'\"]+['\"]", re.IGNORECASE)
    for path in (ROOT / "scripts").rglob("*.py"):
        text = path.read_text()
        for match in pattern.finditer(text):
            assert False, f"{path}: looks like a hard-coded credential: {match.group(0)!r}"
