"""Mission Operations Report: print-ready HTML generated from ONE saved run.

Every number in the report is read from the saved MissionRun (config
snapshot, routes, events, frames, summary) and its scenario; nothing is
hard-coded. The report embeds a SHA-256 of the canonical run snapshot so a
regenerated report can be checked against the same run.
"""

from __future__ import annotations

import base64
import hashlib
import html
import json
import math

from . import PLANNER_VERSION, REPORT_VERSION
from .catalog import EARTH_MOON_DIFFERENCES, OBJECTIVES, REGIONS, SOURCES
from .comms import SPEED_OF_LIGHT_MPS
from .config import SPEED_PROFILES
from .engine import PHASES
from .png import terrain_png
from .service import comm_visibility
from .terrain import BASE_XY, get_terrain

E = html.escape


def snapshot_sha256(run: dict) -> str:
    snap = {k: run[k] for k in ("id", "scenario_id", "scenario_version", "case_label", "seed", "config", "summary",
                                "phases", "routes", "events", "simulation_version", "started_at", "ended_at")}
    return hashlib.sha256(json.dumps(snap, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _fmt_t(s) -> str:
    if s is None:
        return "—"
    s = int(round(float(s)))
    return f"{s // 3600:d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def _dur(s) -> str:
    if s is None:
        return "—"
    s = float(s)
    return f"{s / 3600:.1f} h" if s >= 3600 else f"{s / 60:.0f} min"


def _xy(p) -> str:
    return "—" if not p else f"({p[0]:.0f} m E, {p[1]:.0f} m N)"


def _table(head, rows, cls="") -> str:
    th = "".join(f"<th>{E(str(h))}</th>" for h in head)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<table class="{cls}"><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>'


# ---------------------------------------------------------------- maps & charts
def _map_svg(t, run, layer, vis, title, size=640, show_events=True) -> str:
    cfg = run["config"]
    png = terrain_png(t, layer, vis, cfg["advanced"]["max_slope_deg"])
    b64 = base64.b64encode(png).decode()
    ext = t.extent_m
    k = size / ext

    def P(x, y):
        return x * k, (ext - y) * k

    parts = [f'<image href="data:image/png;base64,{b64}" x="0" y="0" width="{size}" height="{size}" '
             f'preserveAspectRatio="none"/>']
    for h in t.hazards:
        cx, cy = P(h["x"], h["y"])
        parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{h["radius_m"] * k:.1f}" class="nogo"/>')
    for lm in t.landmarks:
        cx, cy = P(lm["x"], lm["y"])
        parts.append(f'<g class="lm"><rect x="{cx - 4:.1f}" y="{cy - 4:.1f}" width="8" height="8"/>'
                     f'<text x="{cx + 6:.1f}" y="{cy - 6:.1f}">{lm["id"]}</text></g>')
    alt = run["routes"].get("alternate")
    if alt and alt.get("path"):
        pts = " ".join(f"{P(x, y)[0]:.1f},{P(x, y)[1]:.1f}" for x, y in alt["path"])
        parts.append(f'<polyline points="{pts}" class="alt"/>')
    rec = run["routes"].get("recommended")
    if rec and rec.get("path"):
        pts = " ".join(f"{P(x, y)[0]:.1f},{P(x, y)[1]:.1f}" for x, y in rec["path"])
        parts.append(f'<polyline points="{pts}" class="rec"/>')
        for w in rec["waypoints"]:
            cx, cy = P(w["x"], w["y"])
            cls = "wp" if w["comm_visible"] else "wp shadow"
            parts.append(f'<g class="{cls}"><circle cx="{cx:.1f}" cy="{cy:.1f}" r="5"/>'
                         f'<text x="{cx + 7:.1f}" y="{cy + 4:.1f}">{w["id"]}</text></g>')
    bx, by = P(*BASE_XY)
    parts.append(f'<g class="base"><path d="M{bx:.1f},{by - 9:.1f} L{bx + 8:.1f},{by + 6:.1f} L{bx - 8:.1f},{by + 6:.1f} Z"/>'
                 f'<text x="{bx + 10:.1f}" y="{by + 4:.1f}">BASE</text></g>')
    if cfg.get("comm_mode") == "relay" and cfg.get("relay_xy"):
        rx, ry = P(*cfg["relay_xy"])
        parts.append(f'<g class="relay"><path d="M{rx:.1f},{ry - 8:.1f} L{rx + 7:.1f},{ry + 5:.1f} L{rx - 7:.1f},{ry + 5:.1f} Z"/>'
                     f'<text x="{rx + 9:.1f}" y="{ry + 4:.1f}">RELAY</text></g>')
    for i, b in enumerate(cfg.get("beacons", [])):
        x, y = P(*b)
        parts.append(f'<g class="beacon"><circle cx="{x:.1f}" cy="{y:.1f}" r="6"/>'
                     f'<text x="{x + 8:.1f}" y="{y - 6:.1f}">B{i + 1}</text></g>')
    if show_events:
        marks = {"LOS_LOST": "!", "SAFE_HOLD": "H", "REROUTE": "R", "SCIENCE_COMPLETE": "S", "SCIENCE_FAILED": "X",
                 "NAV_THRESHOLD_EXCEEDED": "U"}
        for e in run["events"]:
            if e["type"] in marks:
                x, y = P(e["x"], e["y"])
                parts.append(f'<g class="ev"><circle cx="{x:.1f}" cy="{y:.1f}" r="8"/>'
                             f'<text x="{x:.1f}" y="{y + 4:.1f}" text-anchor="middle">{marks[e["type"]]}</text></g>')
    # scale bar 200 m
    parts.append(f'<g class="scale"><rect x="12" y="{size - 26}" width="{200 * k:.1f}" height="6"/>'
                 f'<text x="12" y="{size - 32}">200 m</text><text x="{size - 26}" y="22">N ↑</text></g>')
    return (f'<figure class="map"><svg viewBox="0 0 {size} {size}" width="{size}" height="{size}" '
            f'role="img" aria-label="{E(title)}">{"".join(parts)}</svg><figcaption>{E(title)}</figcaption></figure>')


def _line_chart(series, *, title, ylab, w=640, h=200, xmax=None, ymax=None, hline=None) -> str:
    xs = [x for s in series for x, _ in s["pts"]]
    ys = [y for s in series for _, y in s["pts"]]
    if not xs:
        return ""
    xmax = xmax or max(xs) or 1
    ymax = ymax or (max(ys) * 1.1 if max(ys) > 0 else 1)
    ymin = min(0.0, min(ys))
    L, B = 48, 28

    def X(v):
        return L + (w - L - 10) * v / xmax

    def Y(v):
        return h - B - (h - B - 10) * (v - ymin) / ((ymax - ymin) or 1)

    out = [f'<line x1="{L}" y1="{h - B}" x2="{w - 10}" y2="{h - B}" class="axis"/>',
           f'<line x1="{L}" y1="10" x2="{L}" y2="{h - B}" class="axis"/>',
           f'<text x="{L - 6}" y="14" text-anchor="end" class="tick">{ymax:.0f}</text>',
           f'<text x="{L - 6}" y="{h - B}" text-anchor="end" class="tick">{ymin:.0f}</text>',
           f'<text x="{w - 10}" y="{h - 8}" text-anchor="end" class="tick">{series[0].get("xlab", "")} '
           f'{xmax / 3600:.1f} h</text>' if series[0].get("time") else
           f'<text x="{w - 10}" y="{h - 8}" text-anchor="end" class="tick">{xmax:.0f} m</text>',
           f'<text x="4" y="{h / 2}" class="tick" transform="rotate(-90 10 {h / 2})">{E(ylab)}</text>']
    if hline is not None:
        out.append(f'<line x1="{L}" y1="{Y(hline[0]):.1f}" x2="{w - 10}" y2="{Y(hline[0]):.1f}" class="limit"/>'
                   f'<text x="{w - 12}" y="{Y(hline[0]) - 4:.1f}" text-anchor="end" class="tick">{E(hline[1])}</text>')
    for s in series:
        pts = " ".join(f"{X(x):.1f},{Y(y):.1f}" for x, y in s["pts"])
        out.append(f'<polyline points="{pts}" class="{s.get("cls", "s1")}"/>')
    return (f'<figure class="chart"><svg viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" '
            f'aria-label="{E(title)}">{"".join(out)}</svg><figcaption>{E(title)}</figcaption></figure>')


def _profile_chart(t, rec) -> str:
    pts, d = [], 0.0
    vis_runs = []
    path = rec["path"]
    for i, (x, y) in enumerate(path):
        if i:
            d += math.dist(path[i - 1], path[i])
        pts.append((d, float(t.elevation(x, y))))
    return _line_chart([{"pts": pts, "cls": "s1"}], title="Elevation profile along the recommended route "
                       "(synthetic terrain)", ylab="elevation m")


# ---------------------------------------------------------------- runbook
def _runbook(t, run, cfg) -> list[dict]:
    a = cfg["advanced"]
    ev = run["events"]
    rec = run["routes"].get("recommended") or {}
    wps = rec.get("waypoints", [])
    by = {}
    for e in ev:
        by.setdefault(e["type"], []).append(e)
    first = lambda k: by.get(k, [None])[0]  # noqa: E731
    phase_t = {p["phase"]: p for p in run["phases"]}
    speed = SPEED_PROFILES[cfg["speed_profile"]]
    steps: list[dict] = []

    def add(name, objective, action, start, observe, output, ok, fail, recovery, dur=None):
        steps.append({"name": name, "objective": objective, "action": action, "start": start, "observe": observe,
                      "output": output, "pass": ok, "fail": fail, "recovery": recovery, "duration": dur})

    start_wp = wps[0] if wps else None
    add("Establish the rover staging area",
        "Set up the staging point and base station exactly where the run assumed them.",
        f"Place the base station antenna mast ({a['base_antenna_m']:.1f} m) at {_xy(BASE_XY)} and the rover at the "
        f"staging point {_xy(cfg['start_xy'])}.",
        "Training range surveyed; rover and base station powered.",
        f"Staging-point slope {start_wp['slope_deg'] if start_wp else '—'} deg (synthetic terrain).",
        "Staging point marked; base mast erected.",
        f"Staging slope below the {a['max_slope_deg']:.0f} deg limit; base mast at planned height.",
        "Staging point inside a no-go zone or above the slope limit.",
        "Move the staging point to the nearest cell below the slope limit and regenerate the scenario.",
        _dur(120))
    e = first("SYSTEM_CHECK")
    add("Verify rover systems", "Confirm the rover is ready to drive.",
        "Run the rover system checklist (power, drive, mast, payload, data storage).",
        "Rover at staging point.", e["result"] if e else "—", "Signed system checklist.",
        "All subsystems report nominal.", "Any subsystem fault.", "Hold at staging; fix or swap the unit; repeat.",
        _dur(120))
    e = first("NAV_INITIALISED")
    add("Confirm the initial navigation estimate", "Start the traverse with a known position.",
        f"Initialise navigation in mode {cfg['nav_mode'] if cfg['nav_mode'] != 'LOCAL_NAVIGATION' else 'NOMINAL'} "
        "and compare the estimate with the surveyed staging point.",
        "Systems verified.", e["result"] if e else "—",
        f"Initial 1-sigma uncertainty {e['payload'].get('sigma_m', '—') if e else '—'} m.",
        f"Uncertainty at or below {a['science_uncertainty_m']:.0f} m.", "Estimate not available (mode UNKNOWN).",
        "Repeat initialisation; if still unavailable, start in LOCAL_NAVIGATION with a beacon at the staging point.",
        _dur(60))
    e = first("COMM_CHECK")
    add("Test the communication link", "Prove the command and data path before leaving the staging area.",
        f"Send a test command and telemetry frame over the {cfg['comm_mode']} path; confirm the base-to-Earth path.",
        "Navigation initialised.", e["result"] if e else "—",
        f"Path used: {e['payload'].get('active_path') if e else '—'}; Earth path "
        f"{'available' if e and e['payload'].get('earth_path') else 'NOT available'}; one-way Earth-Moon "
        f"propagation {run['summary'].get('one_way_earth_delay_s', '—')} s (imposed delay for training).",
        "Local link and Earth path both available.", "No local link at the staging point.",
        "Re-position the base mast or deploy the relay before starting; do not start without a tested link.",
        _dur(120))
    if cfg.get("comm_mode") == "relay" and cfg.get("relay_xy"):
        add("Deploy the relay", "Extend the local link behind the ridge.",
            f"Place the relay ({a['relay_antenna_m']:.1f} m mast) at {_xy(cfg['relay_xy'])} and verify relay-to-base "
            "line of sight.", "Base link tested.",
            "Relay powered; relay-to-base link reports line of sight.", "Relay position recorded.",
            "Relay-to-base geometric line of sight confirmed.", "Relay cannot see the base.",
            "Move the relay to higher ground with a view of the base; regenerate the scenario to re-check visibility.")
    if cfg.get("beacons"):
        bl = ", ".join(f"B{i + 1} {_xy(b)}" for i, b in enumerate(cfg["beacons"]))
        add("Deploy local navigation beacons", "Provide position corrections if external positioning is lost.",
            f"Place and survey beacons at {bl}.", "Route uploaded.", "Each beacon reports its surveyed position.",
            "Beacon positions recorded.", "All beacons surveyed and powered.", "Beacon missing or unsurveyed.",
            "Shorten the dead-reckoning legs: pause at the previous beacon and re-survey.")
    # traverse legs: group waypoints, flag notable ones
    shadow_start = next((i for i in range(1, len(wps)) if wps[i - 1]["comm_visible"] and not wps[i]["comm_visible"]), None)
    los = first("LOS_LOST")
    for i, w in enumerate(wps[1:], start=1):
        steep = w["slope_deg"] > 0.7 * a["max_slope_deg"]
        hazard = w["hazard_proximity"] > 0
        if not (steep or hazard or i == shadow_start or w["id"] == "TARGET"):
            continue
        prev = wps[i - 1]
        leg = math.dist((prev["x"], prev["y"]), (w["x"], w["y"]))
        if i == shadow_start:
            add(f"Verify communication visibility before {w['id']}",
                "Last planned point with communication visibility before the terrain shadow.",
                f"Stop at {prev['id']} {_xy((prev['x'], prev['y']))}; confirm the preloaded command sequence for the "
                "shadowed leg and downlink queued data.",
                f"Rover at {prev['id']}.",
                (f"Direct line of sight lost at {_fmt_t(los['t'])} near {_xy((los['x'], los['y']))}"
                 if los else "Planned loss of visibility after this point."),
                "Data queue empty; preloaded commands acknowledged.",
                "Commands acknowledged before entering the shadow.",
                "No acknowledgement received.",
                "Hold at this waypoint until acknowledged; if autonomy is disabled do not enter the shadow.",
                _dur(leg / speed))
        elif w["id"] != "TARGET":
            add(f"Terrain and hazard inspection at {w['id']}", "Check a demanding section before driving it.",
                f"Stop at {w['id']} {_xy((w['x'], w['y']))}; inspect slope ({w['slope_deg']} deg)"
                f"{' and the adjacent no-go boulder field' if hazard else ''}.",
                f"Rover approaching {w['id']}.", f"Slope {w['slope_deg']} deg; hazard proximity {w['hazard_proximity']}.",
                "Go/no-go decision logged.", f"Slope below {a['max_slope_deg']:.0f} deg and footing clear.",
                "Slope or obstacles worse than mapped.", "Take the alternate route if available, else return to the previous waypoint.",
                _dur(leg / speed))
    p3 = phase_t.get(3, {})
    add("Traverse to the target", "Follow the recommended route to the target area.",
        f"Drive the recommended route ({rec.get('distance_m', '—')} m, max slope {rec.get('max_slope_deg', '—')} deg) "
        f"at {speed} m/s ({cfg['speed_profile']}), waypoints " + ", ".join(w["id"] for w in wps[1:]) + ".",
        "Link and navigation verified.",
        "; ".join(sorted({e2["result"] for e2 in ev if e2["phase"] == 3 and e2["type"] in
                          ("COMM_BLOCKED", "POSITIONING_UNAVAILABLE", "POSITIONING_DEGRADED", "LOCAL_NAVIGATION_ENABLED",
                           "AUTONOMOUS_FALLBACK", "SAFETY_PAUSE", "SAFE_HOLD")})) or "No off-nominal events.",
        "Rover at the target area.", "Target reached without safe hold.",
        "Safe hold, uncertainty above limit, or command link lost without autonomy.",
        "Apply the fallback policy (Section 9).",
        _dur((p3.get("end_s") or 0) - (p3.get("start_s") or 0)) if p3.get("end_s") else None)
    for e in by.get("NAV_CORRECTION", [])[:6]:
        pass
    e = first("SURVEY_COMPLETE")
    add("Survey the target area", "Characterise the terrain before choosing the sampling spot.",
        "Perform the panoramic terrain survey at the target.", "Rover at target.",
        e["result"] if e else "Not reached in this run.", f"{e['payload']['data_mb'] if e else 0} MB survey data stored.",
        "Survey data stored and indexed.", "Survey not completed.", "Repeat survey; check storage capacity.", _dur(600))
    e = first("CANDIDATE_SELECTED")
    add("Select the sampling location", "Choose a safe, low-slope spot near the target.",
        "Select the lowest-slope traversable cell within 40 m of the target and approach it.", "Survey complete.",
        f"Selected {_xy((e['payload']['x'], e['payload']['y']))}, slope {e['payload']['slope_deg']} deg" if e else "Not reached.",
        "Sampling location recorded.", f"Slope below {a['max_slope_deg']:.0f} deg.", "No acceptable cell.",
        "Widen the search radius or abort the science operation.")
    sci = first("SCIENCE_COMPLETE") or first("SCIENCE_FAILED")
    add("Perform the simulated science operation", "Collect a sample whose location is known well enough.",
        "Run the sampling procedure (preloaded command if no live link and autonomy is enabled).",
        f"Position uncertainty at or below {a['science_uncertainty_m']:.0f} m.",
        sci["result"] if sci else "Not reached.", f"Result: {run['summary'].get('science_result')}.",
        "Sampling complete and sample location uncertainty within the limit.",
        "Uncertainty above the science limit, or no command authority.",
        "Request a beacon or landmark fix and retry; otherwise record the sample as location-uncertain.", _dur(900))
    add("Store and validate the science data", "Keep data safe until it reaches Earth.",
        "Verify checksums of stored data; queue it for downlink.", "Science operation finished.",
        f"Maximum queued: {run['summary'].get('max_data_queued_mb')} MB.", "Data queued with checksums.",
        "Queue matches the data produced.", "Missing or corrupted files.", "Re-read from instrument buffer; re-queue.")
    rr = first("REROUTE")
    tx = first("DATA_TRANSMITTED")
    if rr:
        recov = (f"Autonomous move back {rr['payload'].get('back_m')} m along the route to the nearest communication-"
                 f"visible point, then downlink.")
    elif cfg.get("comm_mode") == "relay":
        recov = "Downlink through the relay path."
    else:
        recov = "Downlink directly to the base."
    add("Recover communication / store-and-forward", "Deliver all queued data to Earth.", recov,
        "Data queued.", (f"Queue emptied at {_fmt_t(tx['t'])}" if tx else "Queue NOT emptied in this run."),
        f"{run['summary'].get('data_transmitted_mb')} MB transmitted.", "Queue empty.",
        "Earth path not restored within the timeout.",
        "Keep data onboard; continue to the safe point; downlink at the staging area.")
    p8 = phase_t.get(8, {})
    add("Return to the safe point or enter safe hold", "End the run in a safe state.",
        "Drive the route in reverse to the staging point (safe point).", "Data delivered or stored.",
        (first("RETURNED_TO_SAFE_POINT") or first("SAFE_HOLD") or {"result": "—"})["result"],
        f"Final status {run['summary']['status']}.", "Rover at staging point.", "Safe hold away from the staging point.",
        "Crew recovers the rover along the recorded track.",
        _dur((p8.get("end_s") or 0) - (p8.get("start_s") or 0)) if p8.get("end_s") else None)
    lessons = []
    s = run["summary"]
    if s.get("halt_reason"):
        lessons.append(f"Safe hold cause: {s['halt_reason']}.")
    if s.get("reroutes"):
        lessons.append("A communication-recovery move was needed: consider a relay for the shadowed target area.")
    if s.get("max_position_uncertainty_m", 0) > a["science_uncertainty_m"]:
        lessons.append("Uncertainty exceeded the science limit at some point: add beacons or landmarks.")
    add("Review the run and record lessons learned", "Capture what to change before the next run.",
        "Debrief using the event timeline (Section 11) and the case comparison.", "Run ended.",
        " ".join(lessons) or "No off-nominal outcome.", "Lessons-learned log.", "Debrief held.", "—", "—")
    return steps


# ---------------------------------------------------------------- main
def build_report(run: dict, scenario: dict, comparison: list[dict] | None, viewer_png_b64: str | None,
                 report_id: int | None = None) -> str:
    cfg = run["config"]
    a = cfg["advanced"]
    t = get_terrain(cfg["terrain_seed"], cfg["terrain_blockage"])
    vis = comm_visibility(cfg)
    s = run["summary"]
    rec = run["routes"].get("recommended") or {}
    alt = run["routes"].get("alternate") or None
    region = next(r for r in REGIONS if r["code"] == scenario["reference_region_code"])
    obj = next(o for o in OBJECTIVES if o["code"] == scenario["objective_code"])
    site = scenario["training_site"]
    terrain = scenario["terrain"]
    sha = snapshot_sha256(run)
    title = f"{obj['name']} — Mission Operations Report"
    synthetic_banner = ('<p class="banner">SYNTHETIC / DEMONSTRATION — training simulation on procedurally generated '
                        'terrain. Not a validated lunar analog, not a flight-qualified model, no measured RF data.</p>')

    def sec(n, name, body):
        return f'<section id="s{n}"><h2>{n}. {E(name)}</h2>{body}</section>'

    out = []
    # 1
    out.append(sec(1, "Executive Mission Brief", synthetic_banner + _table(["Item", "Value"], [
        ["Mission", E(obj["name"])],
        ["Destination / region", f"Moon — {E(region['name'])}"],
        ["Objective", E(obj["primary"])],
        ["Training environment", f"{E(site['name'])} <b>({E(site['label'])})</b>"],
        ["Case", E(run["case_label"])],
        ["Outcome", f"<b>{E(s['status'])}</b>" + (f" — {E(s['halt_reason'])}" if s.get("halt_reason") else "")],
        ["Science operation", E(s.get("science_result", "—"))],
        ["Simulated duration", _dur(s.get("mission_duration_s"))],
        ["Distance driven", f"{s.get('distance_driven_m', '—')} m (planned route {s.get('planned_route_m', '—')} m)"],
    ]) + f"<p>Summary: the rover ran the {len(PHASES)}-phase mission on the {E(cfg['comm_mode'])} communication "
        f"path with positioning mode {E(cfg['nav_mode'])} (from {cfg['nav_event_time_s']:.0f} s) and autonomy "
        f"{'enabled' if cfg['autonomy'] else 'disabled'}. {s.get('phases_completed', 0)} of 8 phases completed.</p>"))
    # 2
    rel = "".join(f"<li>{E(r['text'])} <span class='tag'>{E(r['basis'])}: {E(r.get('source', ''))}</span></li>"
                  for r in region["relevance"])
    out.append(sec(2, "Earth Analog Selection Rationale",
                   f"<p><b>Selected:</b> {E(site['name'])}. {E(site['why_selected'])}</p>"
                   f"<p class='warn'>{E(site['note'])}</p>"
                   f"<h3>Why this lunar region for this objective</h3><ul>{rel}</ul>"
                   "<h3>Tasks this environment supports</h3><ul>" + "".join(f"<li>{E(x)}</li>" for x in site["tasks_supported"]) + "</ul>"
                   "<h3>Relevant terrain / operational properties</h3><ul>" + "".join(f"<li>{E(x)}</li>" for x in site["relevant_properties"]) + "</ul>"
                   "<h3>Differences from the lunar environment</h3><p class='small'>General reference knowledge, not "
                   "source-verified in ABAAD.</p><ul>" + "".join(f"<li>{E(x)}</li>" for x in EARTH_MOON_DIFFERENCES) + "</ul>"
                   "<h3>What cannot be trained or reproduced</h3><ul>" + "".join(f"<li>{E(x)}</li>" for x in site["cannot_reproduce"]) + "</ul>"
                   f"<p>Curated-record check: {E(json.dumps(site.get('curated_record_counts', {})))} "
                   "(no Earth record with lunar-task evidence).</p>"))
    # 3
    out.append(sec(3, "Site and Terrain Data", _table(["Item", "Value"], [
        ["Geographic reference", "None — the training range is synthetic and not geo-referenced"],
        ["Terrain source", f"{E(terrain['generator'])} v{E(terrain['generator_version'])}, seed {terrain['seed']}"],
        ["Status", f"<b>{E(terrain['label'])}</b>"],
        ["Grid / resolution", f"{terrain['grid_cells'][0]} × {terrain['grid_cells'][1]} cells, {terrain['cell_size_m']} m"],
        ["Extent / frame", f"{terrain['extent_m']:.0f} m square; {E(terrain['frame'])}"],
        ["Reference-region CRS", E(region["bounds"]["crs"]) + " (region bounds only; not used by the terrain)"],
        ["Elevation range", f"{terrain['elevation_range_m'][0]} to {terrain['elevation_range_m'][1]} m (relative)"],
        ["Injected blockage", "yes" if terrain["injected_blockage"] else "no"],
        ["Elevation SHA-256", f"<code>{terrain['elevation_sha256']}</code>"],
        ["Coverage gaps", "none inside the synthetic grid; everything outside it is UNKNOWN"],
    ]) + "<h3>Processing steps</h3><ol>" + "".join(f"<li>{E(p)}</li>" for p in terrain["processing"]) + "</ol>"))
    # 4
    out.append(sec(4, "Mission Objectives",
                   f"<p><b>Primary:</b> {E(obj['primary'])}</p><h3>Secondary</h3><ul>"
                   + "".join(f"<li>{E(x)}</li>" for x in obj["secondary"]) + "</ul><h3>Expected observations</h3><ul>"
                   + "".join(f"<li>{E(x)}</li>" for x in obj["expected_observations"]) + "</ul><h3>Success criteria</h3><ul>"
                   + "".join(f"<li>{E(x)}</li>" for x in obj["success_criteria"]) + "</ul><h3>Abort conditions</h3><ul>"
                   + "".join(f"<li>{E(x)}</li>" for x in obj["abort_conditions"]) + "</ul>"))
    # 5
    out.append(sec(5, "Training Scenario Configuration", _table(["Setting", "Value", "Basis"], [
        ["Rover antenna / speed", f"{a['rover_antenna_m']} m mast; {cfg['speed_profile']} = {SPEED_PROFILES[cfg['speed_profile']]} m/s", "assumption"],
        ["Payload", f"survey {a['survey_data_mb']} MB, sample {a['science_data_mb']} MB (simulated)", "assumption"],
        ["Start / target", f"{_xy(cfg['start_xy'])} → {_xy(cfg['target_xy'])}", "user"],
        ["Waypoints", ", ".join(f"{w['id']} {_xy((w['x'], w['y']))}" for w in rec.get("waypoints", [])) or "—", "derived"],
        ["Communication mode", E(cfg["comm_mode"]) + (f"; relay {_xy(cfg['relay_xy'])}" if cfg.get("relay_xy") and cfg["comm_mode"] == "relay" else ""), "user / derived site"],
        ["Navigation mode", f"{E(cfg['nav_mode'])} from {cfg['nav_event_time_s']:.0f} s", "user (injected event)"],
        ["Beacons", ", ".join(f"B{i + 1} {_xy(b)}" for i, b in enumerate(cfg.get("beacons", []))) or "none", "user / derived"],
        ["Autonomous fallback", "enabled" if cfg["autonomy"] else "disabled", "user"],
        ["Injected outages", E(json.dumps(cfg.get("outages", []))) or "none", "user"],
        ["Safety limits", f"uncertainty {a['uncertainty_threshold_m']} m; science {a['science_uncertainty_m']} m; max slope {a['max_slope_deg']} deg", "assumption"],
        ["Seeds", f"simulation {cfg['seed']}; terrain {cfg['terrain_seed']}; step {a['dt_s']} s", "user"],
    ])))
    # 6
    rows = [["Distance", f"{rec.get('distance_m')} m", f"{alt['distance_m']} m" if alt else "—"],
            ["Max / mean slope", f"{rec.get('max_slope_deg')} / {rec.get('mean_slope_deg')} deg",
             f"{alt['max_slope_deg']} / {alt['mean_slope_deg']} deg" if alt else "—"],
            ["Estimated duration (assumed speed)", _dur(rec.get("estimated_duration_s")), _dur(alt["estimated_duration_s"]) if alt else "—"],
            ["Communication-visible length", f"{rec.get('comm_visible_fraction', 0):.0%}", f"{alt['comm_visible_fraction']:.0%}" if alt else "—"],
            ["Hazard exposure (within 40 m of no-go)", f"{rec.get('hazard_exposure_m')} m", f"{alt['hazard_exposure_m']} m" if alt else "—"]]
    for k in ("distance_cost", "slope_penalty", "roughness_penalty", "hazard_penalty", "communication_penalty"):
        rows.append([k.replace("_", " "), rec.get("cost_breakdown", {}).get(k), (alt or {}).get("cost_breakdown", {}).get(k, "—")])
    rows.append(["<b>total cost</b>", f"<b>{rec.get('total_cost')}</b>", f"<b>{alt['total_cost']}</b>" if alt else "—"])
    meta = rec.get("meta", {})
    out.append(sec(6, "Recommended Route",
                   _map_svg(t, run, "hillshade", vis, "Route map: recommended (solid) and alternate (dashed) routes, "
                            "waypoints (hollow = no planned comm visibility), no-go zones (red), base, relay, beacons, "
                            "landmarks (squares) and key events (! LOS lost, R reroute, S science, U uncertainty, H safe hold)")
                   + _map_svg(t, run, "visibility", vis, "Communication visibility from the active base/relay geometry "
                              "(green visible, red blocked by terrain, grey out of range) — geometric only", size=420, show_events=False)
                   + _table(["Metric", "Recommended", "Alternate"], rows)
                   + f"<p><b>Why recommended:</b> {E(rec.get('explanation', '—'))}</p>"
                   + (f"<p>Alternate: {E(meta.get('alternate_note') or '')}</p>" if not alt else
                      "<p><b>Trade-off:</b> the alternate is reported for contingency only; it is longer or crosses "
                      "more costly terrain under the same weights.</p>")
                   + f"<p class='small'>Planner {E(rec.get('planner_version', PLANNER_VERSION))}; weights "
                     f"{E(json.dumps(rec.get('weights', {})))}; hard constraints {E(json.dumps(rec.get('hard_constraints', {})))}. "
                     f"Demonstration route: {E(meta.get('demonstration_reason') or '')}. Not a global optimum.</p>"
                   + _profile_chart(t, rec)))
    # 7
    rb = _runbook(t, run, cfg)
    rb_html = ""
    for i, st in enumerate(rb, 1):
        rb_html += (f'<div class="step"><h3>Step {i}. {E(st["name"])}</h3>' + _table(["Field", "Detail"], [
            ["Objective", E(st["objective"])], ["Team / rover action", E(st["action"])],
            ["Starting conditions", E(st["start"])], ["Expected observation", E(st["observe"])],
            ["Expected output", E(st["output"])], ["Pass condition", E(st["pass"])],
            ["Failure condition", E(st["fail"])], ["Recovery action", E(st["recovery"])],
            ["Estimated duration", E(st["duration"] or "no valid estimate")]], "kv") + "</div>")
    out.append(sec(7, "Step-by-Step Field Operations Runbook",
                   "<p>Generated from this run's route and events. Durations are simulated values under the assumed "
                   "speed and fixed operation times.</p>" + rb_html))
    # 8
    comm_ev = [e for e in run["events"] if e["type"] in ("COMM_CHECK", "LOS_LOST", "COMM_BLOCKED", "COMM_RECOVERED",
                                                         "OUTAGE_START", "OUTAGE_END", "DATA_QUEUED", "DATA_TRANSMITTED",
                                                         "PRELOADED_COMMANDS_ACTIVE", "REROUTE")]
    d_em = a["earth_moon_distance_m"]
    out.append(sec(8, "Communication Plan", _table(["Item", "Value"], [
        ["Link endpoints", f"rover mast {a['rover_antenna_m']} m ↔ base {_xy(BASE_XY)} mast {a['base_antenna_m']} m"
         + (f" ↔ relay {_xy(cfg['relay_xy'])} mast {a['relay_antenna_m']} m" if cfg["comm_mode"] == "relay" and cfg.get("relay_xy") else "")
         + " ↔ Earth (from base)"],
        ["Mode", E(cfg["comm_mode"])],
        ["Earth–Moon one-way propagation", f"{d_em / SPEED_OF_LIGHT_MPS:.3f} s at {d_em / 1000:,.0f} km reference distance "
         "(distance / speed of light)"],
        ["Round-trip propagation (theoretical)", f"{2 * d_em / SPEED_OF_LIGHT_MPS:.3f} s, before system and processing overhead"],
        ["Local rover link", "evaluated separately: geometric line of sight per segment; propagation over ≤ 1.5 km is "
         "microseconds"],
        ["Maximum link range", f"{a['max_link_range_m']} m (assumption)"],
        ["Earth path unavailable", f"{_dur(s.get('earth_path_unavailable_s'))} in total"],
        ["Data queue", f"max {s.get('max_data_queued_mb')} MB; drained at an assumed {a['downlink_mb_per_s']} MB/s only "
         "while the full path to Earth is available"],
        ["Preloaded commands", "route drive sequence, survey, sampling and comm-recovery move"
         + (" (used)" if any(e["type"] == "PRELOADED_COMMANDS_ACTIVE" for e in run["events"]) else "")],
        ["Measurement status", "geometric visibility only — no RSSI, no link budget, no dBm values"],
    ]) + "<h3>Communication events</h3>" + _table(["Time", "Event", "Position", "Result"],
                                                  [[_fmt_t(e["t"]), E(e["type"]), _xy((e["x"], e["y"])), E(e["result"])] for e in comm_ev])
                   + _comm_strip(run)))
    # 9
    nav_ev = [e for e in run["events"] if e["type"] in ("NAV_INITIALISED", "POSITIONING_DEGRADED", "POSITIONING_UNAVAILABLE",
                                                        "LOCAL_NAVIGATION_ENABLED", "NAV_UNCERTAINTY_INCREASING", "NAV_CORRECTION",
                                                        "NAV_THRESHOLD_EXCEEDED", "GROUND_POSITION_UPDATE", "AUTONOMOUS_FALLBACK", "SAFE_HOLD")]
    frames = run.get("frames", [])
    sig = [(f["t"], f["sigma"]) for f in frames]
    out.append(sec(9, "Navigation and Autonomy Plan", _table(["Item", "Value"], [
        ["Primary positioning", "external fix (NOMINAL), injected change to " + E(cfg["nav_mode"]) + f" at {cfg['nav_event_time_s']:.0f} s"],
        ["Degradation model", f"dead reckoning: 1-sigma grows {a['drift_fraction'] * 100:.1f} % of distance travelled (assumption)"],
        ["Corrections", "landmark (150 m, line of sight) → 3 m; beacon (250 m, line of sight) → 1.5 m; requested above "
         f"{a.get('correction_request_m', 5)} m"],
        ["Safety threshold", f"{a['uncertainty_threshold_m']} m → pause; science limit {a['science_uncertainty_m']} m"],
        ["Fallback policy", ("autonomy ENABLED: continue on preloaded commands when the link is lost; switch to local "
                             "navigation; pause and search for a fix above the threshold; comm-recovery move for data; "
                             "safe hold if no fix") if cfg["autonomy"] else
         ("autonomy DISABLED: stop when the command link is lost; wait up to "
          f"{a['command_timeout_s']:.0f} s; ground-assisted position update needs the Earth path; otherwise safe hold")],
        ["Max / final uncertainty", f"{s.get('max_position_uncertainty_m')} / {s.get('final_position_uncertainty_m')} m"],
        ["Model status", "simplified training model — not a flight-qualified navigation filter or SLAM"],
    ]) + _line_chart([{"pts": sig, "cls": "s2", "time": True}], title="Position uncertainty (1-sigma) over simulated time",
                     ylab="uncertainty m", hline=(a["uncertainty_threshold_m"], "safety limit"))
        + "<h3>Navigation and autonomy events</h3>" + _table(["Time", "Event", "Position", "Result"],
                                                            [[_fmt_t(e["t"]), E(e["type"]), _xy((e["x"], e["y"])), E(e["result"])] for e in nav_ev])))
    # 10
    risks = [
        ["Steep / rough terrain", f"max route slope {rec.get('max_slope_deg')} deg vs {a['max_slope_deg']} deg limit",
         "Stop-and-inspect steps at flagged waypoints; alternate route held in reserve."],
        ["Unknown / low-resolution terrain", f"{terrain['cell_size_m']} m synthetic grid hides small obstacles",
         "Treat the route as a demonstration route; survey the real site at higher resolution before driving."],
        ["Communication blockage", f"{rec.get('comm_visible_fraction', 0):.0%} of the route has planned visibility",
         "Relay on high ground; verify link before the shadow; preloaded commands."],
        ["Navigation uncertainty", f"max {s.get('max_position_uncertainty_m')} m in this run",
         "Beacons spaced from the drift model; landmark checks; pause above the threshold."],
        ["Energy / duration", "no energy model implemented", "Not assessed; do not infer energy margins from this report."],
        ["Science operation failure", f"result {s.get('science_result')}", "Fix position before sampling; retry window."],
        ["Data transmission delay", f"max queue {s.get('max_data_queued_mb')} MB", "Store-and-forward; comm-recovery move."],
        ["Synthetic / missing data", "terrain and telemetry are synthetic", "Replace with surveyed site data before field use."],
    ]
    out.append(sec(10, "Risks and Mitigations", "<p class='small'>Qualitative; no risk probabilities are estimated.</p>"
                   + _table(["Risk", "Evidence from this run", "Mitigation"], [[E(c) for c in r] for r in risks])))
    # 11
    ph_rows = [[p["phase"], E(p["name"]), E(p.get("status", "not_reached")), _fmt_t(p.get("start_s")), _fmt_t(p.get("end_s"))]
               for p in run["phases"]]
    comp = ""
    if comparison:
        keys = [("status", "Completion status"), ("planned_route_m", "Route distance (m)"),
                ("mission_duration_s", "Mission duration"), ("earth_path_unavailable_s", "Earth path unavailable"),
                ("max_data_queued_mb", "Max data queued (MB)"), ("max_position_uncertainty_m", "Max uncertainty (m)"),
                ("safety_pauses", "Safety pauses"), ("fallback_actions", "Fallback actions"),
                ("science_result", "Sampling result")]
        crow = []
        for k, lab in keys:
            vals = []
            for c in comparison:
                v = c["summary"].get(k, "—")
                vals.append(_dur(v) if k in ("mission_duration_s", "earth_path_unavailable_s") else E(str(v)))
            crow.append([lab] + vals)
        comp = "<h3>Baseline / stress / mitigated comparison</h3>" + _table(
            ["Metric"] + [f"{E(c['case_label'])} (run #{c['id']})" for c in comparison], crow)
    out.append(sec(11, "Mission Results", _table(["Item", "Value"], [
        ["Final status", f"<b>{E(s['status'])}</b>"], ["Science result", E(s.get("science_result"))],
        ["Actual route", f"recommended route; {s.get('distance_driven_m')} m driven"],
        ["Route deviations", E("; ".join(s.get("deviations", [])) or "none")],
        ["Fallback actions / safety pauses / reroutes", f"{s.get('fallback_actions')} / {s.get('safety_pauses')} / {s.get('reroutes')}"],
        ["Navigation corrections", s.get("nav_corrections")],
    ]) + "<h3>Phase completion</h3>" + _table(["#", "Phase", "Status", "Start", "End"], ph_rows) + comp
        + _line_chart([{"pts": [(f["t"], f["queue"]) for f in frames], "cls": "s3", "time": True}],
                      title="Data waiting to be transmitted over simulated time", ylab="queue MB")
        + "<h3>Event timeline</h3>" + _table(["#", "Time", "Phase", "Event", "Result"],
                                            [[e["seq"], _fmt_t(e["t"]), e["phase"], E(e["type"]), E(e["result"])] for e in run["events"]], "small")))
    # 12
    shadow = [w for w in rec.get("waypoints", []) if not w["comm_visible"]]
    steep = [w for w in rec.get("waypoints", []) if w["slope_deg"] > 0.7 * a["max_slope_deg"]]
    last_vis = None
    for w in rec.get("waypoints", []):
        if w["comm_visible"]:
            last_vis = w
        else:
            break
    recs = [
        f"Follow the recommended route ({rec.get('distance_m')} m) through " + ", ".join(w["id"] for w in rec.get("waypoints", [])) + ".",
        "Give extra attention at " + (", ".join(f"{w['id']} ({w['slope_deg']} deg)" for w in steep) or "no waypoint above 70 % of the slope limit") + ".",
        f"Check communication at {last_vis['id'] if last_vis else 'START'} — the last waypoint with planned visibility before "
        f"{len(shadow)} shadowed waypoint(s).",
        (f"Deploy the relay at {_xy(cfg['relay_xy'])}" if cfg.get("relay_xy") and cfg["comm_mode"] == "relay"
         else "Consider a relay on high ground with a view of both the base and the target (see the mitigated case).")
        + (f"; beacons at {', '.join(_xy(b) for b in cfg['beacons'])}" if cfg.get("beacons") else "") + ".",
        f"Activate fallback when the local link is lost (preloaded commands) and when uncertainty exceeds "
        f"{a['uncertainty_threshold_m']} m (pause and localise).",
        f"Before sampling, verify position uncertainty ≤ {a['science_uncertainty_m']} m and slope below the limit.",
        "If communication is not recovered, keep data onboard, return along the recorded track and downlink at the staging point.",
        f"Stop or abort on: uncertainty above {a['uncertainty_threshold_m']} m with no fix in view; no command link for "
        f"{a['command_timeout_s']:.0f} s with autonomy disabled; any unmapped hazard.",
    ]
    out.append(sec(12, "Operational Recommendations", "<ol>" + "".join(f"<li>{E(r)}</li>" for r in recs) + "</ol>"))
    # 13
    out.append(sec(13, "Assumptions and Limitations", _table(["Category", "Items"], [
        ["Source-backed facts", "Artemis III region criteria and south-polar location (NASA, secondary report for the 6° figure); "
         "LuGRE lunar-surface GNSS fix (NASA)."],
        ["Project-curated records", "Reference region latitude cap; mission template; scenario template geometry (base, ridge, blockage)."],
        ["Derived calculations", "Slope, roughness, line of sight, visibility maps, routes and costs, relay/beacon suggestions, "
         "propagation delay, uncertainty history."],
        ["Synthetic inputs", "Terrain, landmarks, hazards, rover telemetry and every simulated event."],
        ["User-configured assumptions", "Speeds, antenna heights, link range, data volumes, throughput, drift rate, thresholds, timeouts."],
        ["Unknown / unavailable", "Real lunar or Earth DEM for this scenario; RF link budget; energy model; terramechanics; lighting."],
        ["Cannot establish", "That any Earth site is a lunar analog; real communication performance; real rover capability; "
         "mission success probabilities."],
    ])))
    # 14
    out.append(sec(14, "References and Provenance", _table(["Source", "Organization", "Date", "Link", "Supports", "Access status"],
                   [[E(r["title"]), E(r["organization"]), E(r["date"]), f'<a href="{E(r["url"])}">{E(r["url"])}</a>',
                     E(r["supports"]), E(r["access"])] for r in SOURCES], "small")
                   + "<p class='small'>No paper was reviewed in full for this report. Speed of light is the SI defined value; the "
                     "384,400 km Earth–Moon distance is a commonly used reference value, configurable per run.</p>"))
    # 15
    snap = (f'<figure class="snap"><img alt="3D viewer snapshot" src="data:image/png;base64,{viewer_png_b64}"/>'
            "<figcaption>3D viewer snapshot captured when the report was exported (synthetic terrain, "
            "vertical exaggeration as displayed).</figcaption></figure>") if viewer_png_b64 else \
        "<p>No 3D snapshot was attached to this export.</p>"
    out.append(sec(15, "Appendix", _table(["Item", "Value"], [
        ["Mission Run ID", f"#{run['id']} (scenario #{run['scenario_id']} v{run['scenario_version']}, case {E(run['case_label'])})"],
        ["Run timestamps", f"{E(run['started_at'])} → {E(run['ended_at'])} (wall clock)"],
        ["Run snapshot SHA-256", f"<code>{sha}</code>"],
        ["Report", f"#{report_id if report_id else '—'} · {E(REPORT_VERSION)}"],
        ["Data asset", f"synthetic terrain seed {terrain['seed']}, SHA-256 <code>{terrain['elevation_sha256']}</code>"],
        ["Planner", f"{E(rec.get('planner_version', PLANNER_VERSION))}; weights {E(json.dumps(rec.get('weights', {})))}"],
        ["Simulation model", E(run["simulation_version"])],
        ["Frames", f"{run.get('frame_count', len(frames))} state frames at {a['dt_s']} s"],
    ]) + snap + _map_svg(t, run, "slope", vis, f"Slope map (red = above {a['max_slope_deg']} deg)", size=420, show_events=False)
        + "<h3>Scenario configuration (snapshot)</h3><pre>" + E(json.dumps(cfg, indent=2)) + "</pre>"))

    toc = "".join(f'<li><a href="#s{i}">{E(n)}</a></li>' for i, n in enumerate([
        "Executive Mission Brief", "Earth Analog Selection Rationale", "Site and Terrain Data", "Mission Objectives",
        "Training Scenario Configuration", "Recommended Route", "Step-by-Step Field Operations Runbook",
        "Communication Plan", "Navigation and Autonomy Plan", "Risks and Mitigations", "Mission Results",
        "Operational Recommendations", "Assumptions and Limitations", "References and Provenance", "Appendix"], 1))
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>{E(title)} — Run #{run['id']}</title>
<style>{_CSS.replace('__RUN__', str(run['id']))}</style></head><body>
<header class="cover"><p class="brand">ABAAD | أبعاد · Mission Lab</p><h1>{E(title)}</h1>
<p>Moon · {E(region['name'])} · Run #{run['id']} · case {E(run['case_label'])}</p>{synthetic_banner}
<p class="small">Generated from saved Mission Run #{run['id']} · snapshot SHA-256 <code>{sha}</code></p>
<nav><h2>Contents</h2><ol>{toc}</ol></nav></header>
{''.join(out)}
<footer class="small">ABAAD Mission Lab · {E(REPORT_VERSION)} · Synthetic / Demonstration</footer>
<button class="noprint" onclick="window.print()">Print / save as PDF</button>
</body></html>"""


def _comm_strip(run) -> str:
    fr = run.get("frames", [])
    if not fr:
        return ""
    w, h = 640, 46
    tmax = fr[-1]["t"] or 1
    cells = []
    for f0, f1 in zip(fr, fr[1:]):
        x0 = 4 + (w - 8) * f0["t"] / tmax
        x1 = 4 + (w - 8) * f1["t"] / tmax
        cls = "ok" if f0["earth"] else ("loc" if f0["local"] else "no")
        cells.append(f'<rect x="{x0:.1f}" y="6" width="{max(0.5, x1 - x0):.1f}" height="22" class="{cls}"/>')
    return (f'<figure class="chart"><svg viewBox="0 0 {w} {h}" width="{w}" height="{h}">{"".join(cells)}'
            f'<text x="4" y="42" class="tick">0</text><text x="{w - 4}" y="42" text-anchor="end" class="tick">'
            f'{tmax / 3600:.1f} h</text></svg><figcaption>Link availability over time: green = Earth path, amber = '
            'local link only, red = no link</figcaption></figure>')


_CSS = """
@page { size: A4; margin: 18mm 14mm 18mm 14mm;
  @top-left { content: "ABAAD Mission Operations Report — Run #__RUN__"; font: 9pt sans-serif; color: #5e6c4b; }
  @top-right { content: "SYNTHETIC / DEMONSTRATION"; font: 9pt sans-serif; color: #a95e40; }
  @bottom-right { content: "Page " counter(page) " of " counter(pages); font: 9pt sans-serif; }
  @bottom-left { content: "Generated from the saved run snapshot"; font: 9pt sans-serif; color: #5e6c4b; } }
body { font: 11pt/1.45 ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif; color: #3d352d;
  background: #fcf9f2; max-width: 980px; margin: 0 auto; padding: 24px; }
h1 { font: 700 26pt ui-serif, Georgia, serif; margin: 6px 0; }
h2 { font: 700 16pt ui-serif, Georgia, serif; border-bottom: 2px solid #5e6c4b; padding-bottom: 4px; margin-top: 28px; }
h3 { font-size: 12pt; margin: 16px 0 6px; color: #5e6c4b; }
section { break-before: page; } section#s1 { break-before: auto; }
.cover { border-bottom: 3px solid #a95e40; padding-bottom: 12px; }
.brand { letter-spacing: .12em; text-transform: uppercase; color: #5e6c4b; font-weight: 600; }
.banner { border: 2px solid #a95e40; background: #f3ebdd; padding: 8px 10px; font-weight: 600; }
.warn { border-left: 4px solid #a95e40; padding-left: 8px; }
table { border-collapse: collapse; width: 100%; margin: 8px 0 14px; font-size: 10pt; }
th, td { border: 1px solid #d8cbb8; padding: 4px 6px; text-align: left; vertical-align: top; }
th { background: #f3ebdd; } table.kv td:first-child { width: 28%; font-weight: 600; }
table.small, .small { font-size: 9pt; }
.step { break-inside: avoid; } .tag { font-size: 8.5pt; color: #5e6c4b; }
figure { margin: 10px 0; break-inside: avoid; } figcaption { font-size: 9pt; color: #5e6c4b; }
.map svg, .chart svg, .snap img { max-width: 100%; height: auto; border: 1px solid #d8cbb8; background: #fff; }
.map text { font: 600 11px sans-serif; fill: #fff; paint-order: stroke; stroke: #000; stroke-width: 3px; }
.rec { fill: none; stroke: #e0703f; stroke-width: 3.5; } .alt { fill: none; stroke: #c9e0a8; stroke-width: 2.5; stroke-dasharray: 8 5; }
.wp circle { fill: #fff; stroke: #3d352d; stroke-width: 1.5; } .wp.shadow circle { fill: none; stroke: #fff; stroke-width: 2; }
.nogo { fill: rgba(170,30,30,.45); stroke: #a01e1e; } .lm rect { fill: #d9c27a; stroke: #3d352d; }
.base path { fill: #5e6c4b; stroke: #fff; stroke-width: 1.5; } .relay path { fill: #3b78b5; stroke: #fff; stroke-width: 1.5; }
.beacon circle { fill: #8e5ab5; stroke: #fff; stroke-width: 1.5; }
.ev circle { fill: #a95e40; stroke: #fff; stroke-width: 1.5; } .ev text { font-size: 10px; }
.scale rect { fill: #fff; stroke: #000; }
.axis { stroke: #3d352d; } .tick { font: 10px sans-serif; fill: #3d352d; } .limit { stroke: #a95e40; stroke-dasharray: 5 4; }
.s1 { fill: none; stroke: #5e6c4b; stroke-width: 2; } .s2 { fill: none; stroke: #8e5ab5; stroke-width: 2; }
.s3 { fill: none; stroke: #3b78b5; stroke-width: 2; }
rect.ok { fill: #5e9a66; } rect.loc { fill: #d6a93c; } rect.no { fill: #b4483a; }
pre { font-size: 8.5pt; background: #f3ebdd; padding: 8px; white-space: pre-wrap; }
button.noprint { position: fixed; right: 16px; bottom: 16px; padding: 8px 12px; background: #5e6c4b; color: #fff;
  border: 0; border-radius: 6px; font-weight: 600; cursor: pointer; }
@media print { .noprint { display: none; } body { max-width: none; padding: 0; background: #fff; } }
"""
