# ABAAD | أبعاد

**Different Dimensions. One Connection.** — Earth Analog Discovery Platform

ABAAD will compare Earth locations with Mars and Moon reference regions **for one research mission at a time**, showing what matches, what differs and how strong the evidence is. Planning is in the Phase 0 Revision 1 package (see [docs/DECISIONS.md](docs/DECISIONS.md)).

> **Status: Phase 1, project foundation.** The application has a landing page, a health-checked API, a migrated SQLite schema and a developer-only map feasibility spike. It contains **no scientific data, comparisons or scores**. Everything on the spike page is a labelled synthetic test fixture.

## Prerequisites (macOS on Apple Silicon)

| Tool | Version | Install |
| --- | --- | --- |
| Xcode Command Line Tools (git, make, curl) | any current | `xcode-select --install` |
| uv | 0.11 or later | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Python | 3.12 (installed automatically by uv) | — |
| Node.js | 24 LTS recommended (22.12+ works) | https://nodejs.org or `brew install node@24` |
| pnpm | 10.28.0 | `npm install -g pnpm@10.28.0` |
| Google Chrome | current | used by the end-to-end tests |

No Docker, database server, Conda or Parallels is needed. SQLite comes with Python; it must be 3.37.0 or later, which `make doctor` checks.

## Install

```bash
git clone https://github.com/ENGyassinashraf/ABAAD.git
cd ABAAD
make install        # uv sync --frozen  +  pnpm install --frozen-lockfile
make doctor         # environment report -> var/doctor-report.md
```

## Run

```bash
make dev            # migrates the DB, starts both servers in the background
```

| What | URL |
| --- | --- |
| App (open in Chrome) | http://localhost:3000 |
| Map feasibility spike (dev) | http://localhost:3000/dev/map-spike |
| API health | http://localhost:8000/api/v1/health |
| API docs (OpenAPI) | http://localhost:8000/api/v1/docs |

```bash
make status         # are the servers running?
make stop           # stops only the processes started by make dev
```

Logs are written to `.run/backend.log` and `.run/frontend.log`.

## Test

```bash
make test           # everything below
make test-backend   # pytest: API, migrations, constraints, science package, scripts
make test-frontend  # TypeScript type check + Vitest unit tests
make test-e2e       # Playwright in Google Chrome on ports 3100/8100 (own DB)
```

The end-to-end tests build the frontend and start their own servers on ports 3100 and 8100 with a fresh database, so they can run while `make dev` is running. Test **T1** needs internet access to `tiles.openfreemap.org`.

## Data, backup and restore

```bash
make migrate                                   # create/upgrade var/abaad.sqlite
make backup                                    # var/backups/abaad-<UTC time>.sqlite (online backup + integrity check)
make stop && make restore FILE=var/backups/abaad-<time>.sqlite   # asks you to type 'restore'
make verify-data                               # data/manifest.json vs files in data/
```

Restore checks the backup's integrity first and keeps a `pre-restore-*.sqlite` safety copy. It refuses to run while the backend is running.

## Configuration (optional)

Defaults need no setup. Override with environment variables only if needed:

| Variable | Default | Purpose |
| --- | --- | --- |
| `ABAAD_DB_PATH` | `var/abaad.sqlite` | SQLite database file |
| `ABAAD_BACKUP_DIR` | `var/backups` | Backup folder |
| `ABAAD_CORS_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Origins allowed to call the API directly |
| `ABAAD_API_ORIGIN` | `http://127.0.0.1:8000` | Where Next.js proxies `/api/v1/*` |

## Repository layout

```
backend/     FastAPI app (src/abaad_api), Alembic migrations, tests
science/     abaad_science — plain-Python science engine (placeholder in Phase 1)
frontend/    Next.js app, Playwright e2e tests, MapLibre spike
scripts/     dev/stop, backup/restore, verify-data, doctor, port check
spike/       generator for the synthetic map-spike fixtures
data/        scientific files (ignored by Git) + manifest.json
docs/        DECISIONS.md and Phase 1 reports
var/         local database, backups, reports (ignored by Git)
```

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `ERROR: port 8000 (or 3000) is already in use` | The message shows the owning process. If it is an old ABAAD run, use `make stop`; otherwise stop that program. |
| `ABAAD is already running` | `make stop`, then `make dev`. |
| `dependencies missing` | `make install` |
| Frontend did not start within 180 s | Read `.run/frontend.log`; delete `frontend/.next` and retry. |
| Home page says "API unreachable" | `make status`; read `.run/backend.log`. |
| Health shows `degraded` | Run `make migrate`. |
| `SQLite … is too old; STRICT tables need >= 3.37.0` | Run `uv python install 3.12` and `uv sync --frozen`. uv's Python ships a recent SQLite. |
| Rasterio fails to install | Current wheels need macOS 15+ on Apple Silicon. Report the `make doctor` output. |
| Playwright cannot find Chrome | Install Google Chrome, or run `pnpm --dir frontend exec playwright install chrome`. |
| Map spike T1 FAIL "Failed to fetch" | Check internet access to `https://tiles.openfreemap.org`. |
