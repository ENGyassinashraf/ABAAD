# Phase 1 completion report — mapped to G1

**Verdict: G1 is NOT yet complete.** Everything that can be demonstrated outside your Mac has been demonstrated in Claude's Linux cloud workspace. G1 requires the same evidence **on macOS 27.2 / Apple Silicon**, which only you can produce. Phase 2 has not started.

Legend: ✅ demonstrated in the cloud workspace · ⏳ requires your Mac · ❌ failed

| # | G1 criterion | Cloud workspace evidence | Mac |
| --- | --- | --- | --- |
| 1 | Clean setup works on macOS 27.2 / Apple Silicon, without Parallels or SQL Server | Clean `uv sync` + `pnpm install` on Linux. macOS arm64 cp312 wheels confirmed on PyPI for all four GIS packages (ENVIRONMENT.md). No Docker, SQL Server or Parallels dependency anywhere. | ⏳ `make install && make doctor` |
| 2 | `make dev` starts frontend and backend; UI opens in Chrome at localhost:3000 | ✅ Started from a clean state; headless Google Chrome loaded the page (evidence/home-cloud-chrome.png) | ⏳ |
| 3 | Frontend can call the FastAPI health endpoint | ✅ e2e `home.spec.ts`: status `ok`, schema revision 0002 shown | ⏳ |
| 4 | SQLite database created and migrated from a clean state | ✅ `make dev` on an empty `var/`; migration tests on fresh files | ⏳ |
| 5 | SQLite runtime ≥ 3.37.0 | ✅ 3.45.1 (checked at runtime and in `/health`) | ⏳ `make doctor` |
| 6 | STRICT, named CHECKs, FKs and triggers survive migration tests | ✅ DATABASE.md; 6 migration + 11 constraint tests | ⏳ `make test` |
| 7 | `make test` passes; backend smoke tests and a Playwright home/health test exist | ✅ 41 pytest + 14 Vitest + typecheck + 10 Playwright passed, T1 skipped (TESTS.md) | ⏳ including T1 |
| 8 | `make stop` stops project processes only | ✅ Unrelated processes survived (TESTS.md) | ⏳ |
| 9 | `make backup` produces a restorable backup; restore documented | ✅ Automated round-trip test + manual run; README § Data, backup and restore | ⏳ |
| 10 | GIS dependencies install/import, or an approved fallback | ✅ Linux wheels import and pass smoke tests | ⏳ macOS arm64 install not yet run |
| 11 | T1–T6 reported honestly; failed planetary tests use the static fallback | ✅ T2–T6 PASS; **T1 not verified** (network blocked here); Moon static panel by design (MAP_SPIKE.md) | ⏳ T1 |
| 12 | No fabricated scientific data, scores, boundaries or claims | ✅ Database empty; no regions, measurements or scores. Spike content labelled synthetic on screen and in code. Lunar/Mars radii come from the IAU 2015 definitions (via pyproj). | — |
| 13 | README matches the actual commands and tested environment | ✅ Every README command was run in the cloud workspace | ⏳ |

## Deliverables

| # | Deliverable | Location |
| --- | --- | --- |
| 1 | Repository with frontend, backend, science placeholder, migrations, tests, Makefile | this repository |
| 2 | README | [README.md](../../README.md) |
| 3 | Environment verification report | [ENVIRONMENT.md](ENVIRONMENT.md) (Mac section pending) |
| 4 | Database/migration verification report | [DATABASE.md](DATABASE.md) |
| 5 | Map feasibility spike report | [MAP_SPIKE.md](MAP_SPIKE.md) |
| 6 | Test report | [TESTS.md](TESTS.md) |
| 7 | Blockers and owner decisions | below |
| — | Decision log | [../DECISIONS.md](../DECISIONS.md) |

## Unresolved blockers and owner decisions

1. **Run the Mac checks** in TESTS.md and paste `var/doctor-report.md` and the test counts into the reports. Until then, G1 cannot be claimed.
2. **T1 (Earth basemap)** has not been verified anywhere yet. If OpenFreeMap is unreachable from your network too, decide on another free basemap; the Earth map is not otherwise blocked.
3. **Approve the Mars map approach:** interactive MapLibre custom CRS (works here, but the API is experimental and the version is pinned), with static panels as the fallback.
4. **Node version:** confirm Node 24 LTS on your Mac, or tell me which version you use. Node 22.12+ also works and is what was tested.
5. **shadcn/ui deferred** to Phase 4 (DECISIONS P1-06). Please confirm.
6. **Logo:** still to be uploaded (D5). A neutral favicon and the text wordmark are in place.
7. **D3** remains open for Phase 2, as agreed.
