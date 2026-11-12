# ABAAD UI/UX Visual Upgrade Completion Report

Implements `ABAAD_UI_UX_Visual_Maps_and_Comparison_Spec.md` (rev. 1.0, 12 Nov 2026).
All tests below were run on the target Mac (macOS, Apple Silicon, installed Google Chrome).

## Git

- **Base branch and SHA:** `phase2/scientific-data-layer` @ `c978e63` (PR #1, open, unmerged). `main` does not contain the comparison app, so the UI work is based on the Phase 2 branch, not on `main`.
- **Working branch:** `phase-ui/visual-maps-comparison`
- **Commits:** `9a33006` compare API contract · `228daeb` theme/brand/maps/comparison · the tests/docs/screenshots commit that adds this report (see the PR for the head SHA).
- **PR URL:** see the PR opened from this branch into `phase2/scientific-data-layer` (stacked on PR #1).
- **Pushed:** yes. **Merged: no.** `main` untouched; no history rewritten; no historical migration edited; no dependency added or upgraded (`package.json` and both lockfiles unchanged).

## Audit

- **Routes/components inspected:** `/` (`app/page.tsx`), `/explore` (`ExploreClient`, `CandidateCard`, `CandidateMap`, `Meter`, `ReferenceLocator`), `/report` (`ReportClient`), `/sites` (`SitesClient`), `/dev/map-spike` (`SpikeLab`, `EarthSpike`, `MarsSpike`, `MoonPanel`), `layout.tsx`, `Wordmark`, `ApiStatus`, `lib/{api,crs,lunar,maplibre,wkt}.ts`, `globals.css`, `routes/compare.py`.
- **Theme before:** light sand/ivory page, Tailwind 4 `@theme` with six brand colours used directly as utilities; no dark tokens, no motion.
- **Mars map root cause (MAP-01):** not a projection or tile bug. The comparison app **had no Mars map at all**: the only Mars view was `ReferenceLocator`, a 240 × 120 px schematic rectangle with one dot. The approved `IAU_2015:49910` MapLibre registration existed only on the developer spike page with synthetic tiles. In addition, the API never sent stored outlines (`_geometry` selected only `point_locator` rows), so Arabia Terra's approximate polygon could not be drawn; Bagnold Dunes, Elysium Planitia and the North Polar Sand Sea have no geometry (recorded gaps) and simply showed nothing, with no explanation. Of the spec's diagnosis list this is (3) region geometry missing + (8) selection state not connected to any map + an absent product map; (1) basemap imagery missing is also true but is a data limitation, not a bug.
- **Moon root cause:** Shackleton (129.78° E, 89.67° S) was plotted by the same equirectangular schematic, where y = (90 − lat)/180 · H = 119.6 of 120 px, then clamped to the bottom edge — i.e. effectively invisible and in the wrong projection. The approved static stereographic panel (`IAU_2015:30135`) was only used on the spike page.
- **Comparison contract inspected:** `GET /api/v1/compare` returned `status` (`ranked | insufficient_evidence`), `score`, `coverage`, `rank`, per-dimension rubric/sources, claims, method, limitations. Gaps: no evidence-quality field, no outline geometry, ranking threshold only as prose.

## Visual system

- **Design tokens (`frontend/src/app/globals.css`):** `bg #1B1A16`, `bg-deep #161611`, `surface #24221C`, `raised #2D2A22`, `hover #383329`, `line #494235`, `line-strong #665A45`, `fg #F3EBDD` (Sand), `fg-2 #C9BEAA`, `muted #9A907F`, `olive #84916C` (accessible), `olive-deep #5E6C4B` (original), `terracotta #C47A58`, `ochre #D2AE70`, `ivory`, `sand`, `earth`, `on-accent #1B1A16`, status `ok #93B07A`, `warn #D9A441`, `err #D97A68`, map grounds `map-mars`, `map-moon`.
- **Contrast (WCAG 2 formula, computed, on `surface`):** fg 13.4, fg-2 8.7, muted 5.1, olive 4.7, terracotta 4.8, ochre 7.6, err 5.3, ok 6.6, warn 7.1. Text on accent fills uses `on-accent` (5.2:1 on olive); Ivory on the accessible olive would be 3.2:1, so it is not used. Olive/terracotta are not used for small text on `raised` (4.3:1).
- **Brand:** `ABAAD | أبعاد` lockup (Latin wordmark dominant, Arabic in its own `lang="ar" dir="rtl"` span, ochre divider); hero shows the slogan at display size and the descriptor; the rail shows the compact lockup + descriptor and the slogan at the foot; footer has name, slogan, descriptor and the existing temporary-wordmark notice. Browser title unchanged (`ABAAD | أبعاد — Earth Analog Discovery Platform`). No logo invented.
- **Typography:** system serif for wordmark/headings, system sans for UI, Arabic font stack (`Geeza Pro`, `Noto Naskh Arabic`…). No web fonts loaded.
- **Shell:** left rail (≥ lg) with active-section bar and `aria-current`; compact sticky top bar with horizontally scrollable nav below lg. Destinations limited to real routes: Home, Explore & compare, Analog sites (developer spike link de-emphasised in the rail).
- **Motion:** CSS only (no animation library): two star layers (twinkle 9–13 s, drift 160–240 s), planet surface bands (90 s), two orbit dots (48 s / 80 s), hero reveal 320 ms, hovers 150–200 ms, map `easeTo` 600 ms. Continuous motion lives only in the hero; the planet is hidden below `md` so it never sits behind body text. Markers do not animate geometry.
- **Reduced motion:** `prefers-reduced-motion: reduce` sets `animation: none` on stars/planet/orbits and collapses other animations/transitions; verified by `ui.spec.ts › reduced motion stops the decorative hero animation` (computed `animation-name` is `none`, and not `none` without the preference).
- **Responsive checks:** 1440 × 900 (desktop), 1280 × 900 (Playwright default), 375 × 812 (mobile). No horizontal page overflow at 375 px on `/`, `/explore?…` with results, `/sites` (tested). Tablet width was not separately screenshotted.

## Maps

- **Mars projection:** `IAU_2015:49910` (Mars 2015 sphere, equirectangular, R = 3,396,190 m), tile matrix `ABAAD-MarsEqcQuad` unchanged; registration moved verbatim into `src/lib/marsProjection.ts` and shared by the spike and the product map. Verified in `ui.spec.ts`: `map.getProjection().type === "IAU_2015:49910"`, and the projected pixel offset between Jezero and Gale equals (Δlon, Δlat) × 512 · 2^zoom / 360 within 1 px; each marker's dot centre is within 1.5 px of `map.project()` of its stored coordinate.
- **Mars basemap source/coverage:** **none.** No validated Mars imagery exists in ABAAD (MOLA DS-03 CRS pending). The map shows a labelled neutral context (planet extent fill + 30° graticule with HTML labels). This is stated under the map on every view.
- **Mars region geometry behaviour:** stored points (Gale, Jezero) → keyboard-focusable marker buttons with name, coordinates and precision in their accessible name; stored approximate outline (Arabia Terra) → dashed outline + faint fill; regions without geometry (Bagnold Dunes, Elysium Planitia, North Polar Sand Sea) → no marker, no zoom box, a "no verified geometry" notice with the recorded gap reason, and for Bagnold an explicit note that the parent (Gale) point is context only. Selection is one state shared by URL, list, map and details panel; map clicks select the clicked region only (child never replaced by parent). Fit-to-selected, Reset view, Focus selected, zoom buttons, coordinate readout (planetocentric, from the registered inverse), Mars scale bar. Scroll-wheel zoom requires Ctrl/⌘ (`cooperativeGestures`) so page scrolling never zooms the map.
- **Moon static SVG behaviour:** `IAU_2015:30135` south polar stereographic, R = 1,737,400 m, rendered with the existing tested `lunar.ts` forward. Two fixed extents (to 88° S default, to 80° S); Shackleton placed by the stereographic forward and verified in `ui.spec.ts` against an independent formula (cx, cy within 0.01 SVG units); points outside the extent return `null` rather than being clamped. Lunar South Pole region: notice "shown at body level only: no boundary is drawn".
- **Geometry precision states:** `source_traced_outline`, `approximate_outline`, `source_traced_point`, `approximate_point`, `none` — always shown as a text badge (not colour alone) in the list, details panel and caption. "Geometry rejected/invalid" has no stored records, so no UI state was added for it.
- **Loading/error/fallback states:** Mars `loading` (status text), `ready`, `error` (message + Retry; list and coordinates keep working); Earth candidate map keeps its existing `offline` state, now announced via `role="status"`. Compare loading/error states retained (`compare-error` testid).
- **Attribution:** Mars caption: point coordinates from the USGS Gazetteer of Planetary Nomenclature, outlines from the paper cited per region, no surface imagery; the selected region's source is linked in the details panel. Earth map keeps OpenFreeMap/OpenMapTiles/OSM attribution.

## Comparison

- **Research task/profile flow:** body → reference region (map + list) → task → results. A "Research question" bar is always visible ("Which Earth sites could support “<task>” research for <region> (<body>)?"); until both are chosen it prompts instead of showing any score.
- **Match score display:** only for `ranked` candidates; otherwise "Not computed". Labelled "Task-specific match score" with an explanation that it is not a percentage similarity.
- **Data coverage display:** separate meter + "n of m weighted criteria assessed".
- **Evidence quality display:** separate tile from `evidence_quality`: best visible claim class with its label, and counts of cited sources by access level. If an API build lacks the field the tile says "Not reported by this API version" (never fabricated).
- **Insufficient evidence behaviour:** dashed card, "Not ranked — insufficient evidence" pill, no rank, plain-language reason with the engine's threshold ("Only 10 % … (threshold 50 %)"). `excluded`/`not_available` have distinct pill text in the UI type, but the current engine produces neither.
- **Dimension/evidence details:** table (≥ md) / stacked rows (< md) with criterion, weight, rubric level and s, value & unit, rationale, Earth-side and reference-side sources with locator and access level, evidence basis. Value & unit honestly reads "none stored · unitless s" with a caption: ABAAD stores no measured parameter values yet.
- **Similarities/differences:** grouped from backend rubric levels (strong/close · partial · weak/mismatch · unassessed weighted), each with its task weight.
- **Recommendation limitations:** "Potential use" = the published claim's text, tagged *evidence-supported interpretation* with its class; "Reason" = the claim's similarities; differences and limitations always shown; "Suggested next measurement" names the highest-weight unassessed criteria and is tagged *research suggestion — unverified until curated*. No generic or mission-readiness language.

## Tests

| Command (cwd) | Exit | Result | Notes |
| --- | --- | --- | --- |
| `uv run pytest -q` (repo root) | 0 | 144 passed | +3 new compare tests (evidence quality, claim-class absence, outline exposure) |
| `pnpm typecheck` (`frontend/`) | 0 | clean | |
| `pnpm test:unit` (`frontend/`) | 0 | 21 passed (2 files) | +7 in `src/lib/mapView.test.ts` |
| `pnpm exec playwright test` (`frontend/`) — final run | 0 | 24 passed, 0 failed, 15 skipped | the 15 skipped are `screenshots.spec.ts`, which runs only with `ABAAD_SCREENSHOTS=1` |
| `ABAAD_SCREENSHOTS=1 pnpm exec playwright test e2e/screenshots.spec.ts` | 0 | 15 passed | writes `docs/reports/ui-screenshots/*.png` |

**Failure classification, intermediate runs (not hidden):**
1. First full run: `ui.spec.ts` Mars test timed out clicking the Gale marker. Cause: test ordering — after fitting to Jezero, Gale is ~420 px outside the map viewport. **Test bug**, fixed by resetting the view before clicking. Not an application failure.
2. One later full run: `map-spike.spec.ts › T1 Earth map with OpenFreeMap` failed and `ui.spec.ts › no horizontal overflow at mobile width` timed out. T1 is the documented external-provider smoke test; the mobile test waited for `networkidle` while the Earth map streamed OpenFreeMap tiles. `curl` to `tiles.openfreemap.org` returned 200 in 0.3–1.4 s immediately afterwards, and both passed in the previous and following full runs. Classified as **external provider latency**; the mobile test was changed to wait for application content instead of `networkidle` so layout checks no longer depend on the provider. T1 itself remains a provider-dependent smoke test.

## Screenshots

All in `docs/reports/ui-screenshots/` (captured by `e2e/screenshots.spec.ts` against the production build):

- Home desktop/mobile: `01-home-desktop.png`, `02-home-mobile.png`; reduced motion: `15-home-reduced-motion.png`
- Mars full view/selected region: `03-mars-full-view.png`, `04-mars-selected-jezero.png`, `05-mars-approx-outline-arabia.png`, `06-mars-no-geometry-bagnold.png`
- Moon: `07-moon-shackleton.png`
- Comparison sufficient evidence: `08-compare-sufficient-evidence.png`, `09-compare-evidence-details.png`
- Comparison insufficient evidence: `10-compare-insufficient-evidence.png`; Moon mismatch: `11-compare-moon-mismatch.png`; error state: `13-compare-error-state.png`
- Responsive: `02-home-mobile.png`, `12-compare-mobile.png`; sites: `14-sites-desktop.png`

## Acceptance criteria

| ID | Status | Evidence |
| --- | --- | --- |
| UX-01 | PASS | Tokens in `globals.css` `@theme`; components use token utilities. Exceptions: MapLibre paint and SVG attributes cannot read CSS variables, so `MarsMap.tsx` (constant `C`) and `MoonPolarPanel.tsx` repeat token hex values; the body-selector globe gradients are literal. |
| UX-02 | PASS | `bg #1B1A16`; screenshots 01, 03. |
| UX-03 | PASS | Sand text, olive/terracotta/ochre accents from the brand palette; screenshots. |
| UX-04 | PASS | Hero, rail, footer, title; `ui.spec.ts` asserts the h1 contains `أبعاد` and the slogan. |
| UX-05 | PASS | 01-home-desktop: lockup, slogan, purpose statement, both actions above the fold. |
| UX-06 | PASS | One shell for all routes; `aria-current` on the active section. |
| UX-07 | PASS (desktop, mobile) / not separately checked (tablet) | No overflow at 375 px (tested); screenshots 02, 12. |
| UX-08 | PASS (manual review) | Continuous motion only in the hero; planet hidden below md. No CPU/GPU measurement was taken. |
| UX-09 | PASS | Automated test (reduced motion). |
| MAP-01 | PASS | Diagnosis above. |
| MAP-02 | PASS | Same registration module; projection asserted in e2e. |
| MAP-03 | PASS | Selected marker ochre with ring + label pill (04); selected outline ochre (05). |
| MAP-04 | PASS | e2e: centre equals Jezero after selection; Reset returns to (0, 0). |
| MAP-05 | PASS (no basemap to fail) | There is no Mars basemap; e2e aborts every non-localhost request and the markers still render. |
| MAP-06 | PASS | Static SVG, same CRS and maths; only fixed-extent switching added (UI-02). |
| MAP-07 | PASS | Precision badge + dashed style for approximate; Shackleton shown as a point, never a disc (07). |
| MAP-08 | PASS | Only stored geometry is drawn; Bagnold/Elysium/NPSS/South Pole draw nothing (e2e asserts 2 Mars markers and no Bagnold marker). |
| MAP-09 | PASS | Legend, graticule labels, scale bars, CRS line, attribution in the caption. |
| CMP-01 | PASS | Research-question bar; e2e asserts it names task and region. |
| CMP-02 | PASS | e2e: score "Not computed", coverage "10.0 / 100", evidence tile present, for an unranked candidate. |
| CMP-03 | PASS | e2e: no rank badge; dashed card; separate section. |
| CMP-04 | PASS (with stated limitation) | Status, rubric, sources, locator, access level shown; units: none are stored, which the table states explicitly. |
| CMP-05 | PASS | Grouping of backend rubric levels only (UI-04). |
| CMP-06 | PASS | Potential use / reason / differences / limitations / next measurement, each tagged. |
| CMP-07 | PASS | No new numbers are computed in the browser; the only arithmetic is display formatting and camera framing. |
| TECH-01 | PASS | Existing e2e (home, explore, map spike) pass unchanged except the backend contract additions; `test_compare.py` key-set assertion updated for the new `evidence_quality` field. |
| TECH-02 | PASS | No dependency added (`git diff phase2/scientific-data-layer -- frontend/package.json frontend/pnpm-lock.yaml uv.lock` is empty). |
| TECH-03 | PASS for console errors (the explore and Mars e2e tests assert no console errors) / not measured for memory | Map instances, markers and listeners are removed on unmount; no heap profiling was done. |
| TECH-04 | PASS | Table above. |
| TECH-05 | PASS | Dedicated branch and PR; not merged. |

## Known limitations

- **Scientific/data:** no Mars or Moon surface imagery; only three Mars and one Moon region have stored geometry (and Arabia Terra's is approximate); no measured parameter values exist, so dimension rows show rubric levels without units; evidence quality reflects mostly abstract/page-level reads (no class-A claim).
- **Technical:** the Earth candidate map still uses the light OpenFreeMap "liberty" style (a dark style was not verified and was not switched blindly); T1 depends on an external provider; tablet layout not screenshotted; no performance profiling; the sticky research-question bar can cover the top of content while scrolling on desktop (by design, it is ~70 px).
- **Follow-ups:** verify MOLA/CTX mosaics (CRS, rights) before any Mars raster basemap; curate measured parameters with units to fill "Value & unit"; resolve geometry gates (V-2, V-3, V-4, V-6) so more regions can be placed; the CI workflow is still not pushed (token lacks `workflow` scope).
