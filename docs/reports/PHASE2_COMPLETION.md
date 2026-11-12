# Phase 2 completion report

| | |
|---|---|
| **Date** | 2026-11-12 |
| **Branch** | `phase2/scientific-data-layer` (base `main`; never committed to directly) |
| **PR** | [#1 — Phase2/scientific data layer](https://github.com/ENGyassinashraf/ABAAD/pull/1), open, unmerged |
| **Environment this session ran in** | macOS (Darwin, arm64), confirmed with `uname -a`/`sw_vers` |

This report covers two passes: the initial Phase 2 implementation, and a
subsequent pre-merge hardening pass driven by `ABAAD_Phase_2_PreMerge_
Hardening_Spec.md` (findings F-01…F-15). Both are reflected here as the
final state of the branch.

## 0. Current status — comparison app (supersedes the figures further down where they conflict)

**Scope:** at the owner's request the comparison app described in the
*ABAAD Project & Scientific Guide* (formerly "Phase 3") was built on top of
Phase 2: target → reference region → task → ranked results with map and
evidence → traceable report. See `docs/DECISIONS.md` P2-08…P2-14.

**What changed since the hardening pass**
- **Map fixed:** the eight map-spike e2e failures were a path bug in
  `frontend/scripts/copy-maplibre-worker.mjs` (no URL-decoding, so a path with
  a space wrote the worker to a bogus `%20` directory), not a network problem.
- **Scoring engine** (`science/…/scoring.py`): Guide §06 score and coverage,
  unknown ≠ zero, < 50 % coverage = insufficient evidence (not ranked).
- **Migration 0006:** comparison dimensions, per-task weights with rationale,
  rubric-constrained dimension assessments citing an Earth-side and a
  planetary-side source; `rover_mobility` task for Mars and Moon.
- **Curated data:** references Gale Crater, Bagnold Dunes, Jezero Crater, Lunar
  South Pole, Shackleton (USGS gazetteer centers where they exist; recorded
  gaps for Bagnold Dunes and the South Pole). 12 new sources (S14–S25), all
  opened on 2026-11-12 with exact statements in `access_note`. Claims C10–C12;
  C3 moved C→B after S02's abstract was verified via Crossref. 18 assessments,
  28 task weights. Totals: 23 sources, 17 regions, 11 claims (all class B,
  all published by owner decision), 4 datasets.
- **API:** `GET /api/v1/compare/options`, `GET /api/v1/compare`.
- **Frontend:** `/` (featured Egyptian candidates), `/explore`, `/report`
  (print/PDF + JSON download), `/sites`.
- `make dev` and the e2e backend now load the curated data automatically.

**Headline results on the curated data**

| Reference × task | Result |
|---|---|
| Bagnold Dunes × aeolian | Western Desert ranked #1, score 64.3, coverage 70 % |
| Jezero × fluvial | Dakhla ranked #1, score 41.7, coverage 60 % |
| Jezero × GPR/subsurface | Gilf Kebir ranked #1, score 45.0, coverage 50 % |
| Gale × GPR/subsurface | nobody ranked — Gilf Kebir 10 % coverage (no Gale subsurface source) |
| Elysium Planitia × basaltic volcanology | Holuhraun ranked #1, score 75.0, coverage 60 % |
| Lunar South Pole × rover mobility | nobody ranked — documented environment mismatches only |

**Tests (this Mac, macOS arm64, exact exit codes)**

| Command | Result | Exit |
|---|---|---|
| `uv run pytest` (backend + science + scripts) | 140 passed, 0 failed, 0 skipped | 0 |
| `pnpm run typecheck` | clean | 0 |
| `pnpm run test:unit` | 14 passed | 0 |
| `pnpm run build` | success; routes `/`, `/explore`, `/report`, `/sites`, `/dev/map-spike` | 0 |
| `pnpm exec playwright test` (real Chrome, real OpenFreeMap tiles) | **17 passed, 0 failed, 0 skipped** (3 home, 8 map spike incl. T1, 6 full-journey) | 0 |
| Migrations | base → 0006 upgrade, downgrade to 0005, re-upgrade: OK; FK check empty | 0 |

**Still open (honest list)**
1. All 11 claims are published (owner decision, 2026-11-12); each still carries its limitations and open gates.
2. Most sources are abstract- or page-level reads; no claim is class A.
3. Dimension coverage is thin by design: only dimensions with evidence on both
   sides are assessed. More sources → more coverage.
4. Bagnold Dunes, Lunar South Pole, Western Desert, Yungay, University Valley,
   Holuhraun, McMurdo, Atacama: no verified location (gaps recorded).
5. Gates V-1…V-11 unchanged; no real dataset downloaded (`download_url` null).
6. Migration 0005 cannot be downgraded once datasets with a pending (NULL) CRS
   are loaded (inherent to F-02).
7. CI workflow not pushed (token lacks `workflow` scope).

## 1. What is implemented

**Migrations** `0003`, `0004`, `0005` (`backend/migrations/versions/`):
- `0003`/`0004`: the Phase 2 provenance schema (9 new tables: `region_alias`,
  `research_task`, `site_task_claim`, `site_task_claim_source`, `dataset`,
  `data_asset`, `processing_record`, `processing_input`, `coverage_gap`),
  extensions to `publication`/`region`/`region_geometry`/`measurement_source`,
  and the seed data (3 planetary bodies, 7 research tasks).
- `0005` (hardening): `site_task_claim.reference_body_id` (always explicit,
  enforced against `research_task.applies_to` and the reference region's
  body, on INSERT and UPDATE); `region.body_id`/`region_role` and
  `research_task.applies_to` become immutable once a claim references them;
  removed the triggers that forced every Mars/Moon dataset's CRS into an
  `IAU_2015` family; `dataset.horizontal_crs` is now nullable with an
  explicit `horizontal_crs_status`; an asset can never be marked validated
  while its dataset's CRS is unverified; `dataset.collection_id` (stable
  identity) and `download_url` (separate from the catalogue `source_url`);
  UPDATE-side triggers for `processing_input`/`data_asset` body and
  CRS/vertical/unit consistency that previously existed only on INSERT;
  `processing_record` output metadata checked against its actual output
  asset; `publication.source_access` gained `partial_full_text` with an
  `access_note`.

**Curation data** (`curation/*.json`, loaded by `scripts/load_curation.py`):
11 sources, 12 regions, 2 source-traced/approximate geometries, 10 coverage
gaps, 8 site-task claims (**0 class A, 7 class B, 1 class C** — intentional:
no seeded claim's single supporting source has been read to completion),
4 dataset records. The loader is transactional, idempotent, validates every
claim (including drafts) against its supporting sources, and reconciles
stale rows out of `site_task_claim`/`region_geometry`/`coverage_gap`/
`dataset` on every run (the former Atacama-wide drilling claim is gone and
stays gone across reloads).

**Read-only API** (`backend/src/abaad_api/routes/{catalogue,regions,
evidence,data}.py`): `/bodies`, `/tasks`, `/regions`, `/regions/{code}/
geometries` (now includes `source_dataset_id`), `/claims` (now includes
`reference_body`; `include_unpublished=true` is refused with 403 unless
`ABAAD_ALLOW_UNPUBLISHED_API=1`), `/sources`, `/datasets` (now exposes
`horizontal_crs_status`, `collection_id`, `download_available`), `/assets`
(now exposes source item/label provenance and processing lineage),
`/coverage` (exactly four states: `present`/`gap`/`not_applicable`/
`not_yet_curated`, asset-aware, flags `inconsistent` when a gap and a
qualifying geometry/asset coexist).

**`make verify-data`**: extended with curation-database checks (provenance
completeness, geometry validity via `shapely`, gap/geometry exclusivity,
`validation_status` agreement, open verification gates listed, TEST-/
SYNTH- code rejection); `not_applicable` gaps are now counted and reported
separately from ordinary gaps, never conflated with them.

**Ingestion tooling** (`scripts/ingest/{registry,fetch}.py`): dry run makes
no network call at all. A real download is refused outright without a
verified `download_url` (none of the 4 registered products has one — only
`source_url`, the catalogue page). The 500 MB/3 GB caps are enforced from a
declared `Content-Length` before any body is read, and again on every
chunk while streaming (not only after the file finishes); requests are
restricted to `https` and a small provider-host allowlist, with a resolved
private/loopback/link-local address rejected and an HTML/XML response
rejected outright. `ABAAD_ALLOW_REAL_DOWNLOADS=1` remains a hard session
gate on top of all of this.

**CI (F-15): not added to this push.** A minimal PR workflow (backend
tests + frontend typecheck/unit/build) was written and briefly committed,
but pushing it needs a `workflow`-scoped GitHub token; the push was
blocked ("refusing an OAuth App to create or update workflow... without
`workflow` scope") and a re-auth device flow was started but not completed
in time, so the file was removed again to unblock the rest of this push.
It can be re-added once the token has that scope, or added directly via
the GitHub web UI.

## 2. Tests — exact results and exit codes

| Check | Result | Exit code |
|---|---|---|
| Backend + scripts tests (`uv run pytest`) | **99 passed, 0 failed, 0 skipped** | **0** |
| Frontend typecheck (`pnpm run typecheck`) | clean | **0** |
| Frontend unit tests (`pnpm run test:unit`) | **14 passed, 0 failed** | **0** |
| Full Playwright e2e suite (`pnpm run test:e2e`, real Google Chrome) | **3 passed, 8 failed, 0 skipped** (11 total) | **non-zero** (pnpm reported `8 failed`; the backgrounded shell wrapper itself returned 0, but Playwright's own run did not) |
| Migration upgrade base→head (schema only) | OK, final revision `0005` | 0 |
| Migration downgrade→base, re-upgrade→head (schema only, no curation data) | OK | 0 |
| Migration downgrade of `0005` **after real curation data is loaded** | **Fails**: `NOT NULL constraint failed: dataset.horizontal_crs` | 1 (new finding, see §4) |
| Secrets scan (pytest) | 1 passed | 0 |
| Secrets scan (broad repo grep) | 0 matches | n/a (grep exit 1 = no match = clean) |

**e2e breakdown — all 3 passes are `home.spec.ts`; all 8 failures are
`map-spike.spec.ts`:**
- `home.spec.ts` (3/3 passed): confirms the F-12 fix — the test now reads
  the expected schema revision from `/api/v1/health` itself instead of a
  hard-coded `"0002"`, so it no longer goes stale with each migration.
- `map-spike.spec.ts` (0/8 passed): T2, T3, T4, T5, T6, "T4 refusal", the
  evidence screenshot, and T1 all failed. T1's error changed from a 90s
  timeout to an explicit `Map error before style load: Worker failed to
  load. Check that the worker URL is correct.` T2-T6 (synthetic, no
  external network) are *also* stuck "pending" and time out — meaning the
  root cause is **not** (only) T1 blocking a shared wait condition, as I
  initially diagnosed. The F-13 test-isolation split (separate `describe`
  blocks, T1 no longer in the same pending-selector as T2-T6) was applied
  and is harmless, but it did not fix the real failure, because the real
  failure is page-wide: the MapLibre GL worker bundle (`frontend/public/
  maplibre/maplibre-gl-worker.mjs`, copied by a postinstall script per
  Phase 1 decision P1-19) is apparently not loading correctly in this
  production build/serve path, which breaks every map check on the page,
  not just the network-dependent one.
  - **This is confirmed pre-existing on unmodified `main`**, not a Phase 2
    regression: earlier in this session I ran the identical
    `map-spike.spec.ts` file against `main` (before any Phase 2 changes)
    in this same environment and got the same 8 failures.
  - I have not attempted to fix the worker-loading issue itself, per your
    instruction to stop making code changes.

## 3. Migrations — exact revisions and FK check
- Starting revision for this session: `0002` (Phase 1 head).
- Phase 2 adds `0003` → `0004` → `0005`. Final head: `0005`.
- `PRAGMA foreign_key_check` after a full base→head→(schema-only)downgrade→
  re-upgrade cycle: **0 rows** (clean).
- Database type used for all migration testing: disposable temp SQLite
  files (`/tmp/*.sqlite`), never the repository's own `var/abaad.sqlite`.

## 4. Remaining issues, deferred items, unverified assumptions
- **New, found during this final verification round, not fixed:**
  migration `0005`'s `downgrade()` cannot complete once real curation data
  with `horizontal_crs = NULL` exists (DS-03/DS-04/DS-05). This is an
  inherent tension between "support a clean downgrade" and "never invent a
  CRS to satisfy the old NOT NULL constraint" — the fix that makes F-02
  honest is exactly what makes a full data-preserving downgrade impossible.
  Alembic's transaction wrapper rolled the failed attempt back cleanly (no
  partial/corrupt state), so this is safe, just not reversible with data
  in place.
- **Still open, unverified, exactly as documented in `docs/DECISIONS.md`
  and the curation files' own notes:** V-1 through V-11 (Dakhla Figure 13
  coordinates, Yungay vs. ARADS coordinate mismatch, Holuhraun outline,
  North Polar Sand Sea/Elysium Planitia extents, Arabia Terra latitude
  convention, University Valley position, Copernicus/MOLA/LOLA access
  routes and real product labels, S01/S02/S05/S07 full-text reads).
- DS-02 (REMA) is still not registered (CRS not stated on its page).
  DS-05b, DS-06, DS-07 remain skipped per OD-3's default.
- No real dataset file has ever been opened or downloaded in this session.
  `download_url` is `null` for all 4 registered products, so a real
  download is structurally impossible right now — this is intentional
  (F-08), not an oversight.
- The CI workflow (F-15) was removed from this push (see §1); it needs a
  `workflow`-scoped token or the GitHub web UI to add.
- The map-spike e2e failures (§2) need investigation of the MapLibre
  worker bundle in the production build/serve path; this was not touched.

## 5. Security / safety
- No credential-shaped strings found by either the automated test or a
  broad repository grep (DOI/key/password/secret/private-key patterns).
- `.gitignore` now explicitly excludes `.env`/`.env.*`, `*.pem`, `*.key`,
  `credentials.json`, in addition to the pre-existing `data/**`, `var/`,
  `.run/` exclusions.
- Download safety: size caps enforced before and during streaming; https +
  host-allowlist; private/loopback/link-local address rejection; HTML/XML
  response rejection; `ABAAD_ALLOW_REAL_DOWNLOADS=1` session gate.
- No secrets, credentials, or binary data files were committed on this
  branch (verified via `git ls-files` + `du`).

## 6. Scientific status
Not scientifically complete, and not claimed to be. 12 curated regions (9
Earth analog + 3 Mars reference, no Moon analog region), 8 draft claims
(0 class A, 7 class B, 1 class C), 2 real geometries, 10 coverage gaps with
stated reasons, 4 registered dataset products with 0 real assets ingested.
Every unresolved item above has a named gate in `docs/DECISIONS.md` and the
curation JSON's own notes; nothing is silently marked resolved to pass a
check.

## 7. PR status
Branch pushed to `origin/phase2/scientific-data-layer`; PR #1 reflects the
latest commit. **Not merged.** `main` is untouched.

**Blockers for review, in order of severity:**
1. The map-spike e2e failures (§2/§4) — pre-existing on `main`, but still
   unresolved, and the MapLibre worker-loading symptom is new information
   worth the owner's attention.
2. Migration `0005`'s downgrade-with-real-data limitation (§3/§4).
3. The CI workflow (F-15) isn't in this push (token scope; see §1/§4).

No scientific-integrity or security blocker is open: every evidence-class,
CRS, coverage, and provenance finding from the hardening spec (F-01…F-11)
is fixed and tested; F-12 is fixed and tested; F-13 is partially addressed
(test isolation applied, underlying map failure not fixed); F-14 (this
report) is now committed; F-15 (CI) is written but not pushed (token
scope).
