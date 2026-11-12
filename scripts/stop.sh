#!/usr/bin/env bash
# Stop only the processes started by scripts/dev.sh (recorded process groups).
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUN="$ROOT/.run"
stopped=0

stop_group() { # name pidfile expected-command-fragment
  local name="$1" file="$2" marker="$3" pid pgid cmdline i
  [ -f "$file" ] || return 0
  pid="$(cat "$file")"
  if ! kill -0 "$pid" 2>/dev/null; then
    echo "$name: not running (stale PID file removed)."
    rm -f "$file"; return 0
  fi
  pgid="$(ps -o pgid= -p "$pid" | tr -d ' ')"
  cmdline="$(ps -o command= -p "$pid")"
  # Safety: only signal a process group that dev.sh created (PGID == PID)
  # and whose leader is the expected command.
  if [ "$pgid" != "$pid" ] || [[ "$cmdline" != *"$marker"* ]]; then
    echo "$name: PID $pid is not an ABAAD process group ($cmdline); not touching it."
    rm -f "$file"; return 0
  fi
  kill -TERM -- "-$pgid" 2>/dev/null || true
  for i in 1 2 3 4 5 6 7 8 9 10; do
    kill -0 -- "-$pgid" 2>/dev/null || break
    sleep 1
  done
  if kill -0 -- "-$pgid" 2>/dev/null; then
    kill -KILL -- "-$pgid" 2>/dev/null || true
    echo "$name: forced to stop (process group $pgid)."
  else
    echo "$name: stopped (process group $pgid)."
  fi
  rm -f "$file"; stopped=1
}

stop_group "Frontend" "$RUN/frontend.pid" "pnpm"
stop_group "Backend" "$RUN/backend.pid" "uvicorn"
[ "$stopped" -eq 1 ] || echo "Nothing to stop: ABAAD is not running."
exit 0
