#!/usr/bin/env bash
# Start the ABAAD backend (FastAPI :8000) and frontend (Next.js :3000) in the
# background, wait until both answer, then print their URLs.
# Compatible with the bash 3.2 that ships with macOS.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUN="$ROOT/.run"
API_PORT=8000
WEB_PORT=3000
mkdir -p "$RUN" "$ROOT/var"
cd "$ROOT"

alive() { [ -f "$1" ] && kill -0 "$(cat "$1")" 2>/dev/null; }

if alive "$RUN/backend.pid" || alive "$RUN/frontend.pid"; then
  echo "ABAAD is already running (PID files in .run/). Use 'make stop' first."
  exit 1
fi

for tool in uv pnpm curl; do
  command -v "$tool" >/dev/null 2>&1 || { echo "ERROR: '$tool' is not installed. See README > Prerequisites."; exit 1; }
done
[ -d "$ROOT/.venv" ] && [ -d "$ROOT/frontend/node_modules" ] || { echo "ERROR: dependencies missing. Run 'make install' first."; exit 1; }

uv run --frozen python scripts/portcheck.py "$API_PORT" "$WEB_PORT"

echo "Applying database migrations…"
uv run --frozen alembic -c backend/alembic.ini upgrade head

# Each background job gets its own process group (job control), so
# 'make stop' can stop exactly the processes started here and nothing else.
set -m
nohup uv run --frozen uvicorn abaad_api.main:app --host 127.0.0.1 --port "$API_PORT" \
  > "$RUN/backend.log" 2>&1 &
echo $! > "$RUN/backend.pid"
nohup pnpm --dir frontend run dev > "$RUN/frontend.log" 2>&1 &
echo $! > "$RUN/frontend.pid"
set +m

wait_for() { # url seconds name log
  local i=0
  until curl -sf -o /dev/null "$1"; do
    i=$((i + 1))
    if [ "$i" -gt "$2" ]; then
      echo "ERROR: $3 did not start within $2 s. Last log lines ($4):"
      tail -n 25 "$4" || true
      "$ROOT/scripts/stop.sh" >/dev/null 2>&1 || true
      exit 1
    fi
    sleep 1
  done
}

echo "Waiting for the backend…"
wait_for "http://127.0.0.1:$API_PORT/api/v1/health" 60 "Backend" "$RUN/backend.log"
echo "Waiting for the frontend (the first compile can take ~30 s)…"
wait_for "http://localhost:$WEB_PORT/" 180 "Frontend" "$RUN/frontend.log"

cat <<MSG

ABAAD is running.
  App (open in Chrome):  http://localhost:$WEB_PORT
  API health:            http://localhost:$API_PORT/api/v1/health
  API docs (OpenAPI):    http://localhost:$API_PORT/api/v1/docs
  Logs:                  .run/backend.log, .run/frontend.log
Stop with:               make stop
MSG
