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

## Phase 2: curated science data (read-only)

Phase 2 adds a provenance layer on top of the Phase 1 schema: sources,
regions with hierarchy and geometry, site-task claims (Earth analog vs. a
Mars/Moon reference), and dataset/data-asset metadata. Nothing is invented —
a missing geometry or dataset is recorded as an explicit `coverage_gap`
reason, never silently rendered as zero. See `docs/DECISIONS.md` (P2-01…
P2-07) for what changed and why, and `docs/reports/PHASE2_COMPLETION.md`
for the full status.

```
make migrate         # apply migrations 0003-0006 (schema, seed bodies/tasks, comparison engine)
make load-curation    # load curation/*.json (sources, regions, geometries, claims, datasets)
make verify-data      # checks data/manifest.json AND the curated database
make ingest-list       # list planned dataset products (no network)
make ingest DATASET=DS-05            # dry run (default; prints metadata, writes nothing)
make ingest DATASET=DS-05 CONFIRM=1  # still refused unless ABAAD_ALLOW_REAL_DOWNLOADS=1 is set
```

Two claim_evidence_class corrections apply throughout: class `A` requires the
claim's supporting source to be `full_text_checked` and peer-reviewed —
never assigned from an abstract alone — and the Stoker et al. 2023
life-detection/drilling claim attaches only to the `CL-ATACAMA-ARADS-SITE`
feature, never to Yungay or to the Atacama region as a whole.

Read-only endpoints: `GET /api/v1/{bodies,regions,regions/{code}/geometries,tasks,claims,sources,datasets,assets,coverage}`.

## The comparison app

`make dev` now migrates **and loads the curated data**, then serves the app at
http://localhost:3000:

| Page | What it does |
| --- | --- |
| `/` | Overview, the three featured Egyptian candidates (one click to their comparison) |
| `/explore` | 1 target (Mars/Moon) → 2 reference region → 3 research task → 4 ranked results, map, evidence |
| `/report?reference=…&task=…` | Printable, traceable report (print → PDF) and JSON download |
| `/sites` | Every Earth analog site (3 Egyptian + global) and every planetary reference region |

**Sites.** Featured Egyptian candidates: Gilf Kebir crater-like structures,
Western Desert aeolian landforms, Dakhla Depression inverted channels.
Global sites: Atacama (Yungay, ARADS drilling site), McMurdo Dry Valleys
(University Valley), Holuhraun. Planetary references: Gale Crater, Bagnold
Dunes, Jezero Crater, Arabia Terra, Elysium Planitia, North Polar Sand Sea,
Lunar South Pole, Shackleton Crater.

**Method** (Project & Scientific Guide §06, implemented in `science/src/abaad_science/scoring.py`):
`Score = 100 × Σ(w·s) / Σ(w)` over assessed dimensions; `Coverage` is shown
separately; a missing assessment is *unknown*, never zero; below 50 % coverage
a candidate is "insufficient evidence" and is not ranked. Each similarity `s`
is a named rubric level (strong 1 · close 0.75 · partial 0.5 · weak 0.25 ·
mismatch 0) with a rationale and a source on **both** the Earth and planetary
side (`curation/comparison.json`). Weights per task carry a written rationale.

API: `GET /api/v1/compare/options`, `GET /api/v1/compare?reference=<code>&task=<code>`.

**Maps.** Mars is drawn on the approved `IAU_2015:49910` equirectangular
projection (same registration as the Phase 1 spike) with a neutral vector
context — ABAAD has no validated Mars imagery yet, and the map says so. The
Moon is the approved static south-polar stereographic panel (`IAU_2015:30135`).
Only stored geometry is drawn; every location shows its precision
(source-traced point, approximate outline, no verified geometry…). Each result
shows **match score, data coverage and evidence quality as three separate
outputs**. Screenshots and acceptance evidence:
`docs/reports/UI_UX_VISUAL_UPGRADE_COMPLETION.md`. Re-capture screenshots with
`ABAAD_SCREENSHOTS=1 pnpm exec playwright test e2e/screenshots.spec.ts` (from `frontend/`).

**Publishing claims** is an owner decision. All eleven curated claims are
published (owner decision, 2026-11-12); a claim left as `draft` would show only
its class and limitations. To change one, edit its `"publication_state"` in
`curation/claims.json` and run `make load-curation` (the database refuses publication unless the claim's
evidence class is supported). For a local demo of draft text only, start the
API with `ABAAD_ALLOW_UNPUBLISHED_API=1`.

## Repository layout

```
backend/     FastAPI app (src/abaad_api), Alembic migrations, tests
science/     abaad_science — plain-Python scoring engine (task-weighted score + coverage)
frontend/    Next.js app, Playwright e2e tests, MapLibre spike
scripts/     dev/stop, backup/restore, verify-data, doctor, port check, load_curation, ingest/
curation/    committed, reviewable Phase 2 source/region/geometry/claim/dataset JSON
spike/       generator for the synthetic map-spike fixtures
data/        scientific files (ignored by Git) + manifest.json
docs/        DECISIONS.md and Phase 1/2 reports
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
