# Mission Lab (MVP)

Mission Lab turns one lunar mission objective into an explainable rover **training scenario**:
a route, a 3D playback, communication and navigation events, a comparison of three cases, and a
printable Mission Operations Report. Everything runs on a reproducible simulation.

> **Synthetic / Demonstration.** The terrain is procedurally generated from a seed. It is not
> real lunar or Earth elevation data, and no Earth site is presented as a validated lunar analog.

## The one scenario

| Item | Value | Basis |
|---|---|---|
| Destination | Moon | MVP scope |
| Reference region | Lunar south polar region, poleward of 84°S | Project-curated latitude cap. NASA's Artemis III candidate regions are reported to lie within 6° of the South Pole; region selection criteria included terrain slope, ease of communications with Earth and lighting (NASA, 2022). |
| Objective | Lunar Surface Reconnaissance & Navigation (8 phases) | Mission template |
| Training environment | Synthetic lunar-operations training range | ABAAD has no curated Earth record with evidence for a lunar task (`GET /api/v1/mission/training-sites` shows the counts). Phase 2 owner decision D-P2-02 forbids adding an unsupported Earth lunar analog. |

## How the three features share one state

```text
MissionScenario (mission_scenario) ──< MissionRun (mission_run: config snapshot, seed, summary, phases, frames)
                                             ├──< MissionRoute (mission_route: recommended / alternate)
                                             ├──< MissionEvent (mission_event: ordered timeline)
                                             └──< MissionReport (mission_report: snapshot SHA-256, HTML artifact)
```

- The **server** does every calculation: terrain, line of sight, routes, propagation delay,
  navigation uncertainty, state transitions and events (`backend/src/abaad_api/mission/`).
- The **3D viewer, telemetry, timeline and link sandbox** display the saved frames and events of
  one `MissionRun`. The rover position comes from the frame at the current playback time.
- The **report** is rendered from the saved run (`POST /api/v1/mission/runs/{id}/report`). It
  embeds the SHA-256 of the run snapshot, so a regenerated report can be matched to its run.

## Models (all simplified; training use only)

| Model | What it does | What it is not |
|---|---|---|
| Terrain | Spectral noise, tilt, craters, a template ridge with a saddle, an optional injected mound, and boulder-field no-go zones. 160 × 160 cells of 8 m. | Not real data; not geo-referenced. |
| Communication Visibility | Straight ray between antenna tips against bilinear terrain, plus lunar curvature (d₁d₂/2R, R = 1 737 400 m). States: `LINE_OF_SIGHT`, `BLOCKED_BY_TERRAIN`, `OUT_OF_RANGE`, `UNKNOWN`. | Not an RF link budget. No RSSI or dBm values. |
| Link segments | rover–base, rover–relay, relay–base and base–Earth are evaluated separately. A relay only helps if both of its segments are up. Nothing restores the Earth path while base–Earth is down. | — |
| Delay | One way = distance / c (384 400 km reference → 1.282 s). Round trip is reported only as a theoretical 2× value, before system and processing overhead. | No Mars conjunction scenario. |
| Data queue | Survey and sample data are queued and drained at an assumed throughput only while the full path to Earth is available. | Not a protocol model. |
| Navigation | NOMINAL / DEGRADED / GNSS_UNAVAILABLE / LOCAL_NAVIGATION / UNKNOWN. Dead-reckoning 1σ grows by a fraction of distance travelled. Landmark and beacon fixes require range and line of sight. GNSS loss is an injected event; LuGRE obtained a lunar-surface fix in March 2025. | Not a flight-qualified filter or SLAM. |
| Route planner | 8-connected grid A*. Hard constraints: max slope (cell and move grade), no-go zones, must reach the target. Soft costs: distance, slope, roughness, hazard proximity, no communication visibility. The alternate route uses a diversity penalty. | Not a global optimum; demonstration route. No energy model. |
| Safety policy | With autonomy: continue on preloaded commands; switch to local navigation; pause and seek a fix above the threshold; comm-recovery move for data; safe hold if no fix is available. Without autonomy: stop when the command link is lost, wait for the timeout, then safe hold. | — |

## Launch and demonstrate

```bash
make migrate   # applies revisions up to 0007 (Mission Lab tables)
make dev       # backend :8000, frontend :3000
open http://localhost:3000/mission-lab
```

Demo sequence (about 5 minutes):

1. Review steps 1–4 (Moon, region with sources, objective, synthetic training range and its limits).
2. Press **Generate scenario**. The recommended and alternate routes appear on the map and in 3D.
3. Press **Play** at 3600×. Watch phases 1→3. Behind the ridge, telemetry switches to
   `BLOCKED_BY_TERRAIN`, autonomy activates preloaded commands, and data starts queuing.
4. Open **Link sandbox** and pick two points to see the cross-section and the visibility heatmap.
5. Open **Compare cases** and run baseline / stress / mitigated. Stress ends in `SAFE_HOLD`;
   mitigated (relay + derived beacons + autonomy) completes the sampling.
6. Load the stress run and scrub to the end (phases 4–8 not reached).
7. Open **Report**, export, and open the report. Use "Print / save as PDF" for a PDF.

## API (all under `/api/v1/mission`)

`GET /catalog` · `GET /training-sites` · `GET /terrain` · `GET /terrain.png` · `POST /los` ·
`POST /suggestions` · `POST /scenarios` · `GET /scenarios/{id}` · `POST /scenarios/{id}/runs` ·
`POST /scenarios/{id}/comparison` · `GET /runs/{id}` · `POST /runs/{id}/report` · `GET /reports/{id}`

## Known limitations

- Synthetic terrain only. The Mission Lab does not yet use any ingested LOLA or Earth DEM.
- The report is print-ready HTML (decision D4). A PDF is produced with the browser's print dialog.
- The 3D view needs WebGL. Without it the viewer says so; the map, telemetry and timeline still work.
- Migration numbering: Mission Lab is revision 0007, after the Phase 2 migrations 0003–0006.
