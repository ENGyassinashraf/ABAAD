# Test report (deliverable 6)

## Cloud workspace (Linux x86_64) — run by Claude on 2026-11-12

Command: `ABAAD_E2E_OFFLINE=1 make test`. Exit code 0. Full log: [evidence/make-test-cloud.log](evidence/make-test-cloud.log)

| Suite | Command | Result |
| --- | --- | --- |
| Backend + science + scripts (pytest) | `uv run --frozen pytest` | **41 passed**, 0 failed |
| TypeScript type check | `pnpm --dir frontend run typecheck` | passed (0 errors) |
| Unit tests (Vitest) | `pnpm --dir frontend run test:unit` | **14 passed**, 0 failed |
| End-to-end (Playwright, Google Chrome) | `pnpm --dir frontend run test:e2e` | **10 passed, 1 skipped**, 0 failed |

The skipped test is **T1 (Earth map)**, skipped only because `ABAAD_E2E_OFFLINE=1` was set: this workspace cannot reach `tiles.openfreemap.org`. Do **not** set that variable on your Mac; T1 must run and pass there.

Manual checks in the cloud workspace:

| Check | Result |
| --- | --- |
| `make dev` from a clean state | both servers up; URLs printed; health `ok` through the frontend proxy |
| Second `make dev` while running | refused: "ABAAD is already running" |
| `make dev` with port 8000 occupied | refused, with the owning process shown by `lsof` |
| `make stop` with unrelated `sleep` and `http.server` processes running | stopped only ABAAD's two process groups; unrelated processes survived |
| `make backup`, then `make restore FILE=…` | integrity ok, 9 tables, revision 0002; safety copy written |
| `make verify-data` on a clean checkout | "No data files yet … OK", exit 0 |
| `make doctor` | all checks PASS (Linux) |

### Python test inventory (41)
- Migrations (6): clean upgrade; STRICT-only types; downgrade then re-upgrade; downgrade to base; triggers fire after rebuild; failed migration is atomic
- Constraints (11): FK; named CHECK; STRICT typing; intervals without midpoint; RFC 7946 refused for Mars; RFC 7946 WGS 84 fields; planetary WKT accepted; body match; measurement ⟂ gap; one current measurement; synthetic refused
- DB and API (10): SQLite version; version gate; pragmas on every connection; health ok; health degraded when unmigrated; 404, 405, 422 and 500 error shapes; OpenAPI published
- Science package isolation (3)
- Scripts (11): verify-data clean / OK / 4 failure kinds; backup + restore round trip; restore refused while running; corrupt backup rejected; port busy / free; GIS stack smoke

## Owner's Mac — **NOT YET RUN**

```bash
make install
make doctor
make test            # do NOT set ABAAD_E2E_OFFLINE
make dev             # open http://localhost:3000 and /dev/map-spike in Chrome
make backup && make stop && make restore FILE=var/backups/<newest>.sqlite && make dev
make stop
```

Record the pass/fail counts here under "Owner's Mac — results".
