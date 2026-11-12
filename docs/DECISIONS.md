# Decision log

The planning baseline is **Phase 0 Revision 1** (Claude Doc "ABAAD — Phase 0: Technical Planning & Scientific Design", tabs "R1 · …"). Owner defaults for Phase 1: D1 both tracks; D2 Moon selectable, with no invented Egyptian lunar analogs; D3 deferred to Phase 2; D4 print-ready HTML report later, no PDF generator; D5 temporary text wordmark; D6 English-only UI that is localization-friendly. SQLite only.

| # | Date | Decision | Reason | Revision 1 reference |
| --- | --- | --- | --- | --- |
| P1-01 | 2026-11-12 | Python 3.12 via uv workspace (`backend`, `science`); root is not a package | Brief prefers 3.12; all pinned GIS wheels exist for cp312 on macOS arm64 | R1 · 1 Libraries |
| P1-02 | 2026-11-12 | Pins: FastAPI 0.162.5, uvicorn 0.54.0, SQLAlchemy 2.1.8, Alembic 1.20.1, Pydantic 2.14.3, pytest 9.2.0, httpx2 2.16.0; numpy 2.5.4, rasterio 1.5.2, shapely 2.2.0, pyproj 3.8.0 | Latest releases on PyPI on 2026-11-12. macOS arm64 cp312 wheel tags read from PyPI: numpy macosx_11_0/14_0, rasterio macosx_15_0, shapely macosx_11_0, pyproj macosx_14_0. All are below macOS 27.2. | R1 · 1 |
| P1-03 | 2026-11-12 | `httpx2` instead of `httpx` for the FastAPI TestClient | Starlette 1.10 deprecates `httpx` in its test client in favour of `httpx2` | — |
| P1-04 | 2026-11-12 | Node 24 LTS recommended; `engines` allows ≥ 22.12; pnpm 10.28.0 pinned via `packageManager` | Node 26, 24 and 22 are all LTS lines; 24 is mature and supported by Next 16 (≥ 20.9). The cloud workspace only has Node 22.23.4, so that is what was tested. | — |
| P1-05 | 2026-11-12 | Next.js 16.4.6, React 19.3.1, TypeScript **5.9.3** (not 7.x), Tailwind 4.3.5, MapLibre 6.18.0, Playwright 1.65.0, Vitest 5.1.0 | TypeScript 7 is the new native compiler; 5.9 is the conservative choice for Next.js tooling | — |
| P1-06 | 2026-11-12 | **shadcn/ui deferred to Phase 4** | The landing page and shell need no components; initialising shadcn pulls from an online registry. The brief allows shadcn "where useful". | R1 · 5 |
| P1-07 | 2026-11-12 | No `.env.example` | Every setting has a working default; optional overrides are documented in the README | Phase 1 brief §1 |
| P1-08 | 2026-11-12 | Browser calls FastAPI through a Next.js rewrite (`/api/v1/*` → `127.0.0.1:8000`) | Same origin, so no CORS setup for development. CORS is still configured for direct API use. | R1 · 1 |
| P1-09 | 2026-11-12 | All tables are SQLite **STRICT**, using only INTEGER/REAL/TEXT, every constraint named, booleans as INTEGER 0/1 with named CHECKs | STRICT requires SQLite ≥ 3.37.0 (checked at startup and in health). Named constraints survive Alembic batch rebuilds. | R1 · 4 |
| P1-10 | 2026-11-12 | Phase 1 schema = 8 core tables (planetary_body, publication, region, region_geometry, parameter, measurement, measurement_source, data_gap) and 10 triggers, empty | Enough to prove migrations, geometry rules, intervals, lineage and gap exclusivity without seeding any scientific facts | R1 · 4 (subset) |
| P1-11 | 2026-11-12 | Migration 0002 deliberately rebuilds `measurement` with `recreate="always"` and `table_kwargs={"sqlite_strict": True}` | Proves STRICT, CHECKs and triggers survive the risky SQLite path | R1 · 4; risk R16 |
| P1-12 | 2026-11-12 | **Finding:** when rebuilding table X, drop and re-create *every* trigger that references X, including triggers on other tables | Without it, Alembic's final `RENAME` failed: "error in trigger trg_gap_no_measurement_ins: no such table: main.measurement" | risk R16 |
| P1-13 | 2026-11-12 | **Finding:** Python's sqlite3 does not open a transaction before DDL, so a failed migration left half-applied changes. Fixed by SQLAlchemy's pysqlite recipe (`isolation_level=None` + explicit `BEGIN`) in both the app engine and `migrations/env.py`. | A test now runs a deliberately failing migration and asserts nothing changed | — |
| P1-14 | 2026-11-12 | Migrations run with `foreign_keys=OFF` on their own connection, then `PRAGMA foreign_key_check` must return no rows. App connections always use `foreign_keys=ON`, WAL and `busy_timeout=5000`. | sqlite.org's documented table-rebuild procedure | — |
| P1-15 | 2026-11-12 | No `abaad_demo.sqlite` in Phase 1. The production schema already rejects `is_synthetic = 1` rows by trigger. | The foundation does not need demo data (brief §4) | R1 · 4 |
| P1-16 | 2026-11-12 | No SpatiaLite. Planetary geometry is `ogc_wkt` with explicit CRS fields; RFC 7946 only for Earth (`OGC:CRS84`), enforced by CHECK and trigger | RFC 7946 is WGS 84 only | R1 · 1, R1 · 4 |
| P1-17 | 2026-11-12 | Map spike: Mars map in **IAU_2015:49910** (Mars 2015 sphere, equirectangular, R = 3,396,190 m) via MapLibre `addProjection`; tile matrix "ABAAD-MarsEqcQuad" (origin (−πR, +πR), extent 2πR, 512-px tiles); worker handler for GeoJSON | Verified with pyproj; MapLibre custom CRS is experimental, so the version is pinned | R1 · 1 spike |
| P1-18 | 2026-11-12 | Moon south pole = static SVG panel in IAU_2015:30135 (stereographic, R = 1,737,400 m); no interactive polar map | Fallback chosen in R1 · 1; correctness checked against pyproj | R1 · 1 T5 |
| P1-19 | 2026-11-12 | MapLibre 6 worker bundle copied to `public/maplibre/` (pre-dev, pre-build, post-install) and set with `setWorkerUrl` | Without it, MapLibre failed with "Worker failed to load" | — |
| P1-20 | 2026-11-12 | `make dev` runs each server in its own process group (bash job control) and records PIDs; `make stop` signals only those groups after checking PGID == PID and the expected command | Never kills unrelated processes; compatible with macOS bash 3.2 | Phase 1 brief §7 |
| P1-21 | 2026-11-12 | Playwright uses the installed Google Chrome (`channel: "chrome"`), a production build on port 3100 and FastAPI on port 8100 with a fresh DB | Matches the target browser; never touches `make dev` or the dev database | — |
| P1-22 | 2026-11-12 | Neutral favicon (a plain olive disc) | Removes a 404 console error; not a logo, and replaced when the approved logo is uploaded (D5) | D5 |
| P1-23 | 2026-11-12 | `agentRules: false` in `next.config.ts` | Next.js 16.4 otherwise writes an AGENTS.md into the project | — |

## Deviations from Revision 1

- **None in scope.** The schema is a documented *subset* of R1 · 4: dataset, dataset_file, derivation_run, run_input, distribution_bin, claim, comparison_* and profile tables arrive in Phases 2–3. `measurement_source` accepts only publication sources until datasets exist.
