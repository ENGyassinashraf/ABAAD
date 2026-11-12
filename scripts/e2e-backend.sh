#!/usr/bin/env bash
# Backend for the Playwright tests: a fresh, migrated database on port 8100,
# separate from the developer database and from `make dev` (port 8000).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export ABAAD_DB_PATH="$ROOT/var/e2e/abaad-e2e.sqlite"
rm -f "$ABAAD_DB_PATH" "$ABAAD_DB_PATH-wal" "$ABAAD_DB_PATH-shm"
mkdir -p "$(dirname "$ABAAD_DB_PATH")"
uv run --frozen alembic -c backend/alembic.ini upgrade head
exec uv run --frozen uvicorn abaad_api.main:app --host 127.0.0.1 --port 8100
