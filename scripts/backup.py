"""Back up or restore the ABAAD SQLite database with SQLite's online backup API.

  python scripts/backup.py backup             -> var/backups/abaad-<UTC timestamp>.sqlite
  python scripts/backup.py restore FILE [--yes] [--force]

A backup is verified with PRAGMA integrity_check before it is reported.
Restore verifies the backup first, keeps a safety copy of the current
database (pre-restore-<timestamp>.sqlite) and refuses while `make dev` is
running unless --force is given.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "src"))
from abaad_api.config import REPO_ROOT, get_settings  # noqa: E402

RUN_DIR = REPO_ROOT / ".run"


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _copy(src: Path, dst: Path) -> None:
    with sqlite3.connect(f"file:{src}?mode=ro", uri=True) as source, sqlite3.connect(dst) as target:
        source.backup(target)
    source.close()
    target.close()


def describe(db: Path) -> dict:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        tables = conn.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
        try:
            revision = conn.execute("SELECT version_num FROM alembic_version").fetchone()
            revision = revision[0] if revision else None
        except sqlite3.OperationalError:
            revision = None
        return {"integrity": integrity, "tables": tables, "revision": revision}
    finally:
        conn.close()


def backend_running() -> bool:
    pid_file = RUN_DIR / "backend.pid"
    if not pid_file.exists():
        return False
    try:
        os.kill(int(pid_file.read_text().strip()), 0)
        return True
    except (ValueError, ProcessLookupError, PermissionError):
        return False


def backup(db: Path, backup_dir: Path) -> Path:
    if not db.exists():
        raise SystemExit(f"ERROR: database {db} does not exist yet (run make dev or make migrate first).")
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / f"abaad-{_stamp()}.sqlite"
    _copy(db, target)
    info = describe(target)
    if info["integrity"] != "ok":
        raise SystemExit(f"ERROR: backup {target} failed integrity_check: {info['integrity']}")
    print(f"Backup written: {target}\n  integrity_check: ok, tables: {info['tables']}, schema revision: {info['revision']}")
    return target


def restore(db: Path, source: Path, backup_dir: Path, yes: bool, force: bool) -> None:
    if not source.exists():
        raise SystemExit(f"ERROR: backup file {source} not found.")
    info = describe(source)
    if info["integrity"] != "ok":
        raise SystemExit(f"ERROR: {source} failed integrity_check: {info['integrity']}")
    if backend_running() and not force:
        raise SystemExit("ERROR: the backend is running (make dev). Run make stop first, or pass --force.")
    if not yes:
        answer = input(f"Replace {db} with {source}? Type 'restore' to continue: ")
        if answer.strip() != "restore":
            raise SystemExit("Restore cancelled.")
    if db.exists():
        safety = backup_dir / f"pre-restore-{_stamp()}.sqlite"
        backup_dir.mkdir(parents=True, exist_ok=True)
        _copy(db, safety)
        print(f"Safety copy of the current database: {safety}")
    db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(f"file:{source}?mode=ro", uri=True) as src, sqlite3.connect(db) as dst:
        src.backup(dst)
    src.close()
    dst.close()
    after = describe(db)
    print(f"Restored {source} -> {db}\n  integrity_check: {after['integrity']}, tables: {after['tables']}, "
          f"schema revision: {after['revision']}")


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="ABAAD SQLite backup/restore")
    parser.add_argument("--db", type=Path, default=settings.db_path)
    parser.add_argument("--backup-dir", type=Path, default=settings.backup_dir)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("backup")
    r = sub.add_parser("restore")
    r.add_argument("file", type=Path)
    r.add_argument("--yes", action="store_true", help="do not ask for confirmation")
    r.add_argument("--force", action="store_true", help="restore even if the backend is running")
    args = parser.parse_args(argv)
    if args.cmd == "backup":
        backup(args.db, args.backup_dir)
    else:
        restore(args.db, args.file, args.backup_dir, args.yes, args.force)
    return 0


if __name__ == "__main__":
    sys.exit(main())
