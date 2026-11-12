"""Runtime configuration.

Defaults work out of the box; every value can be overridden with an
environment variable (documented in the README). No secrets are used.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

#: Repository root: backend/src/abaad_api/config.py -> parents[3]
REPO_ROOT = Path(__file__).resolve().parents[3]

#: Minimum SQLite runtime required for STRICT tables (sqlite.org/stricttables.html).
MIN_SQLITE_VERSION = (3, 37, 0)

API_VERSION = "0.1.0"


@dataclass(frozen=True)
class Settings:
    db_path: Path
    backup_dir: Path
    cors_origins: tuple[str, ...]

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.db_path}"


def get_settings() -> Settings:
    db_path = Path(os.environ.get("ABAAD_DB_PATH", REPO_ROOT / "var" / "abaad.sqlite"))
    backup_dir = Path(os.environ.get("ABAAD_BACKUP_DIR", REPO_ROOT / "var" / "backups"))
    origins = os.environ.get(
        "ABAAD_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    )
    return Settings(
        db_path=db_path.resolve(),
        backup_dir=backup_dir.resolve(),
        cors_origins=tuple(o.strip() for o in origins.split(",") if o.strip()),
    )
