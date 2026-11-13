"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { messages as t } from "@/i18n/en";
import { eventsUpTo, formatSimTime, frameIndexAt, interpolatedPose, phaseStates } from "@/lib/mission/playback";
import type { Catalog, LosResult, MissionConfig, Run, Scenario, TerrainData, TrainingSite, XY } from "@/lib/mission/types";
import { MapPanel } from "./MapPanel";
import { Badge, LosProfile, PhaseTracker, RouteAnalysis, statusTone, Telemetry, Timeline } from "./Panels";
import type { Layers, Viewer3DHandle } from "./Viewer3D";

const Viewer3D = dynamic(() => import("./Viewer3D").then((m) => m.Viewer3D), { ssr: false });

const API = "/api/v1/mission";
type Pick = "start" | "target" | "relay" | "beacon" | "losA" | "losB" | null;
type Tab = "timeline" | "route" | "sandbox" | "compare" | "report";
type SiteResp = { selected: TrainingSite; curated_record_counts: Record<string, unknown> };
type CompareResp = { group: string; runs: Run[]; run_ids: number[] };
type ReportRec = { id: number; run_id: number; url: string; snapshot_sha256: string; generated_at: string; has_viewer_snapshot: boolean };

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${API}${path}`, { cache: "no-store", headers: { "Content-Type": "application/json" }, ...init });
  const body = await r.json();
  if (!r.ok) throw new Error(`${body.message ?? r.statusText}${body.details ? `: ${JSON.stringify(body.details)}` : ""}`);
  return body as T;
}

const Card = ({ title, children, testId }: { title: string; children: React.ReactNode; testId?: string }) => (
  <section className="space-y-2 rounded-lg border border-line bg-surface p-3" data-testid={testId}>
    <h2 className="text-sm font-bold uppercase tracking-wider text-olive">{title}</h2>
    {children}
  </section>
);

const xyText = (p: XY | null | undefined) => (p ? `${p[0].toFixed(0)} E, ${p[1].toFixed(0)} N` : "—");

export function MissionLab() {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [site, setSite] = useState<SiteResp | null>(null);
  const [cfg, setCfg] = useState<MissionConfig | null>(null);
  const [terrain, setTerrain] = useState<TerrainData | null>(null);
  const [region, setRegion] = useState("MOON-SOUTH-POLAR-6DEG");
  const [pick, setPick] = useState<Pick>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [scenario, setScenario] = useState<Scenario | null>(null);
  const [run, setRun] = useState<Run | null>(null);
  const [simT, setSimT] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(600);
  const [layers, setLayers] = useState<Layers>({ routes: true, hazards: true, comm: true, uncertainty: true, markers: true });
  const [mapLayer, setMapLayer] = useState<"hillshade" | "slope" | "visibility">("hillshade");
  const [follow, setFollow] = useState(false);
  const [tab, setTab] = useState<Tab>("timeline");
  const [compare, setCompare] = useState<CompareResp | null>(null);
  const [report, setReport] = useState<ReportRec | null>(null);
  const [losA, setLosA] = useState<XY | null>(null);
  const [losB, setLosB] = useState<XY | null>(null);
  const [los, setLos] = useState<LosResult | null>(null);
  const [losBHeight, setLosBHeight] = useState<number | null>(null);
  const [outage, setOutage] = useState({ segment: "rover_base", start_s: 3000, duration_s: 1200 });
  const viewer = useRef<Viewer3DHandle>(null);

  useEffect(() => {
    Promise.all([api<Catalog & { default_config: MissionConfig }>("/catalog"), api<SiteResp>("/training-sites?objective=LUNAR-RECON-NAV")])
      .then(([c, s]) => {
        setCatalog(c);
        setCfg(c.default_config);
        setSite(s);
      })
      .catch((e) => setError(String(e)));
  }, []);

  const seed = cfg?.terrain_seed;
  const blockage = cfg?.terrain_blockage;
  useEffect(() => {
    if (seed === undefined) return;
    api<TerrainData>(`/terrain?seed=${seed}&blockage=${blockage}&step=2`).then(setTerrain).catch((e) => setError(String(e)));
  }, [seed, blockage]);

  const set = <K extends keyof MissionConfig>(k: K, v: MissionConfig[K]) => setCfg((c) => (c ? { ...c, [k]: v } : c));
  const setAdv = (k: string, v: number) => setCfg((c) => (c ? { ...c, advanced: { ...c.advanced, [k]: v } } : c));

  const imageUrl = useCallback((layer: string, c: MissionConfig | null) => {
    if (!c) return "";
    const q = new URLSearchParams({ seed: String(c.terrain_seed), blockage: String(c.terrain_blockage), layer,
      comm_mode: c.comm_mode, max_slope_deg: String(c.advanced.max_slope_deg) });
    if (c.comm_mode === "relay" && c.relay_xy) {
      q.set("relay_x", String(c.relay_xy[0]));
      q.set("relay_y", String(c.relay_xy[1]));
    }
    return `${API}/terrain.png?${q}`;
  }, []);

  // ---- scenario generation / re-run (all calculations on the server)
  const generate = async () => {
    if (!cfg) return;
    setBusy(true);
    setError(null);
    setPlaying(false);
    try {
      const same = scenario && scenario.config.terrain_seed === cfg.terrain_seed &&
        JSON.stringify(scenario.config.start_xy) === JSON.stringify(cfg.start_xy) &&
        JSON.stringify(scenario.config.target_xy) === JSON.stringify(cfg.target_xy);
      if (same && scenario) {
        const r = await api<Run>(`/scenarios/${scenario.id}/runs`, { method: "POST", body: JSON.stringify({ case: "custom", config: cfg }) });
        setRun(r);
      } else {
        const r = await api<{ scenario: Scenario; run: Run }>("/scenarios", {
          method: "POST", body: JSON.stringify({ body: "moon", region, objective: "LUNAR-RECON-NAV", config: cfg }),
        });
        setScenario(r.scenario);
        setRun(r.run);
        setCompare(null);
      }
      setReport(null);
      setSimT(0);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const loadRun = async (id: number) => {
    setBusy(true);
    try {
      const r = await api<Run>(`/runs/${id}`);
      setRun(r);
      setSimT(0);
      setPlaying(false);
      setReport(null);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const runComparison = async () => {
    if (!scenario) return;
    setBusy(true);
    try {
      setCompare(await api<CompareResp>(`/scenarios/${scenario.id}/comparison`, { method: "POST" }));
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const exportReport = async () => {
    if (!run) return;
    setBusy(true);
    try {
      const snap = viewer.current?.snapshot() ?? null;
      setReport(await api<ReportRec>(`/runs/${run.id}/report`, { method: "POST", body: JSON.stringify({ viewer_snapshot_png: snap }) }));
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const useSuggestions = async () => {
    if (!cfg) return;
    try {
      const s = await api<{ relay_xy: XY | null; beacons: XY[] }>("/suggestions", { method: "POST", body: JSON.stringify({ config: cfg }) });
      setCfg((c) => (c ? { ...c, relay_xy: s.relay_xy, beacons: s.beacons } : c));
    } catch (e) {
      setError(String(e));
    }
  };

  // ---- line-of-sight sandbox (server calculation)
  useEffect(() => {
    if (!losA || !losB || !cfg) return;
    api<LosResult>(`/los?seed=${cfg.terrain_seed}&blockage=${cfg.terrain_blockage}`, {
      method: "POST",
      body: JSON.stringify({ a: losA, b: losB, a_height_m: cfg.advanced.rover_antenna_m, b_height_m: losBHeight ?? cfg.advanced.relay_antenna_m,
        max_range_m: cfg.advanced.max_link_range_m }),
    }).then(setLos).catch((e) => setError(String(e)));
  }, [losA, losB, losBHeight, cfg]);

  const onPick = (xy: XY) => {
    if (!pick) return;
    if (pick === "start") set("start_xy", xy);
    if (pick === "target") set("target_xy", xy);
    if (pick === "relay") set("relay_xy", xy);
    if (pick === "beacon") set("beacons", [...(cfg?.beacons ?? []), xy].slice(0, 8));
    if (pick === "losA") { setLosA(xy); setPick("losB"); return; }
    if (pick === "losB") { setLosB(xy); setPick(null); return; }
    setPick(null);
  };

  // ---- playback (looks up saved frames only)
  const frames = useMemo(() => run?.frames ?? [], [run]);
  const tEnd = frames.length ? frames[frames.length - 1].t : 0;
  useEffect(() => {
    if (!playing) return;
    let raf = 0;
    let last = performance.now();
    const step = (now: number) => {
      const dt = (now - last) / 1000;
      last = now;
      setSimT((v) => {
        const nv = Math.min(tEnd, v + dt * speed);
        if (nv >= tEnd) setPlaying(false);
        return nv;
      });
      raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [playing, speed, tEnd]);

  const fi = frameIndexAt(frames, simT);
  const frame = fi >= 0 ? frames[fi] : null;
  const pose = useMemo(() => interpolatedPose(frames, simT), [frames, simT]);
  const states = run ? phaseStates(run.phases, simT) : [];
  const seen = run ? eventsUpTo(run.events, simT) : [];
  const nextAction = (() => {
    if (!run || !frame) return "—";
    if (frame.safety === "SAFE_HOLD") return `Safe hold — ${run.summary.halt_reason ?? ""}`;
    if (frame.safety === "PAUSED") return "Paused by the safety policy — see the latest timeline event.";
    const cur = run.phases.findIndex((_, i) => states[i] === "current");
    const nxt = run.phases[cur + 1];
    return cur >= 0 ? `${run.phases[cur].name} (waypoint ${frame.wp ?? "—"})${nxt ? ` → then: ${nxt.name}` : ""}` : "—";
  })();

  if (error && !catalog) return <p role="alert" className="text-terracotta">{error}</p>;
  if (!catalog || !cfg || !site) return <p>Loading Mission Lab…</p>;
  const reg = catalog.regions.find((r) => r.code === region)!;
  const obj = catalog.objectives[0];
  const s = site.selected;
  const markers = [
    { xy: terrain?.base_xy ?? ([0, 0] as XY), label: "BASE", kind: "base" as const },
    { xy: cfg.start_xy, label: "START", kind: "start" as const },
    { xy: cfg.target_xy, label: "TARGET", kind: "target" as const },
    ...(cfg.comm_mode === "relay" && cfg.relay_xy ? [{ xy: cfg.relay_xy, label: "RELAY", kind: "relay" as const }] : []),
    ...cfg.beacons.map((b, i) => ({ xy: b, label: `B${i + 1}`, kind: "beacon" as const })),
  ];

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-serif text-3xl font-bold">{t.missionLab.title}</h1>
          <p>{t.missionLab.subtitle}</p>
        </div>
        <p className="max-w-xl rounded border-2 border-terracotta bg-surface p-2 text-xs" data-testid="synthetic-banner">
          <b>{t.missionLab.synthetic}.</b> {t.missionLab.syntheticNote}
        </p>
      </header>
      {error && <p role="alert" className="rounded border border-terracotta bg-surface p-2 text-sm text-terracotta" data-testid="error">{error}</p>}

      <div className="grid gap-4 xl:grid-cols-[320px_minmax(0,1fr)]">
        {/* ---------------- setup */}
        <aside className="space-y-3" aria-label="Mission setup">
          <Card title={t.missionLab.step1} testId="step-body">
            {catalog.bodies.map((b) => (
              <label key={b.code} className={`flex items-center gap-2 text-sm ${b.available ? "" : "opacity-50"}`}>
                <input type="radio" name="body" checked={b.code === "moon"} disabled={!b.available} readOnly /> {b.name}
                <span className="text-xs">({b.note})</span>
              </label>
            ))}
          </Card>
          <Card title={t.missionLab.step2} testId="step-region">
            <select className="w-full rounded border border-olive bg-bg-deep p-1 text-sm" value={region} onChange={(e) => setRegion(e.target.value)} aria-label="Lunar region">
              {catalog.regions.map((r) => <option key={r.code} value={r.code}>{r.name}</option>)}
            </select>
            <ul className="list-disc space-y-1 pl-4 text-xs">
              {reg.relevance.map((r, i) => <li key={i}>{r.text} <Badge tone="info">{r.basis}{r.source ? ` · ${r.source}` : ""}</Badge></li>)}
            </ul>
            <p className="text-[11px]">Bounds: {String(reg.bounds.min_latitude_deg)}° to {String(reg.bounds.max_latitude_deg)}° latitude ({String(reg.bounds.basis)}). {String(reg.bounds.note)}</p>
          </Card>
          <Card title={t.missionLab.step3} testId="step-objective">
            <p className="text-sm font-semibold">{obj.name}</p>
            <p className="text-xs">{obj.primary}</p>
            <details className="text-xs"><summary>Success criteria and abort conditions</summary>
              <ul className="list-disc pl-4">{obj.success_criteria.map((x) => <li key={x}>{x}</li>)}</ul>
              <ul className="list-disc pl-4 text-terracotta">{obj.abort_conditions.map((x) => <li key={x}>{x}</li>)}</ul>
            </details>
          </Card>
          <Card title={t.missionLab.step4} testId="step-site">
            <p className="text-sm font-semibold" data-testid="site-name">{s.name} <Badge tone="warn">{s.label}</Badge></p>
            <p className="text-xs">{s.why_selected}</p>
            <p className="text-xs font-semibold text-terracotta" data-testid="site-not-analog">Validated lunar analog: {s.is_validated_lunar_analog ? "yes" : "no"}. {s.note}</p>
            <details className="text-xs"><summary>Tasks supported, differences, what it cannot reproduce</summary>
              <p className="mt-1 font-semibold">Supports</p><ul className="list-disc pl-4">{s.tasks_supported.map((x) => <li key={x}>{x}</li>)}</ul>
              <p className="mt-1 font-semibold">Relevant properties</p><ul className="list-disc pl-4">{s.relevant_properties.map((x) => <li key={x}>{x}</li>)}</ul>
              <p className="mt-1 font-semibold">Differences from the Moon</p><ul className="list-disc pl-4">{s.differences_from_moon.map((x) => <li key={x}>{x}</li>)}</ul>
              <p className="mt-1 font-semibold">Cannot reproduce</p><ul className="list-disc pl-4">{s.cannot_reproduce.map((x) => <li key={x}>{x}</li>)}</ul>
              <p className="mt-1">Curated records checked: {JSON.stringify(site.curated_record_counts)}</p>
            </details>
            <p className="text-xs">Data: <b>{s.data_status}</b> · terrain seed {cfg.terrain_seed}</p>
          </Card>
          <Card title={t.missionLab.step5} testId="step-config">
            {terrain && (
              <MapPanel terrain={terrain} imageUrl={imageUrl("hillshade", cfg)} size={360} markers={markers}
                        routes={run?.routes} onPick={pick && pick !== "losA" && pick !== "losB" ? onPick : undefined} testId="setup-map"
                        pickHint={pick && pick !== "losA" && pick !== "losB" ? `Click the map to place: ${pick}` : "Use the buttons below, then click the map."} />
            )}
            <div className="grid grid-cols-2 gap-1 text-xs">
              <button type="button" className="rounded border border-olive px-2 py-1" onClick={() => setPick("start")} data-testid="pick-start">Start: {xyText(cfg.start_xy)}</button>
              <button type="button" className="rounded border border-olive px-2 py-1" onClick={() => setPick("target")} data-testid="pick-target">Target: {xyText(cfg.target_xy)}</button>
            </div>
            <label className="block text-xs">Rover speed profile
              <select className="mt-0.5 w-full rounded border border-olive bg-bg-deep p-1" value={cfg.speed_profile} onChange={(e) => set("speed_profile", e.target.value)} data-testid="speed">
                {Object.entries((catalog as Catalog & { speed_profiles_mps: Record<string, number> }).speed_profiles_mps).map(([k, v]) => <option key={k} value={k}>{k} ({v} m/s, assumed)</option>)}
              </select>
            </label>
            <fieldset className="text-xs"><legend className="font-semibold">Communication</legend>
              {(["direct", "relay"] as const).map((m) => (
                <label key={m} className="mr-3"><input type="radio" name="comm" checked={cfg.comm_mode === m} onChange={() => set("comm_mode", m)} data-testid={`comm-${m}`} /> {m === "direct" ? "Direct to base" : "Relay-assisted"}</label>
              ))}
              {cfg.comm_mode === "relay" && (
                <div className="mt-1 flex flex-wrap items-center gap-1">
                  <span>Relay: {xyText(cfg.relay_xy)}</span>
                  <button type="button" className="rounded border border-olive px-1" onClick={() => setPick("relay")}>Place on map</button>
                </div>
              )}
            </fieldset>
            <fieldset className="text-xs"><legend className="font-semibold">Positioning (injected event)</legend>
              <select className="w-full rounded border border-olive bg-bg-deep p-1" value={cfg.nav_mode} onChange={(e) => set("nav_mode", e.target.value)} data-testid="nav-mode">
                <option value="NOMINAL">NOMINAL — external fixes throughout</option>
                <option value="DEGRADED">DEGRADED — sparse, less precise fixes</option>
                <option value="GNSS_UNAVAILABLE">GNSS_UNAVAILABLE — external positioning lost</option>
                <option value="LOCAL_NAVIGATION">LOCAL_NAVIGATION — lost, use local references</option>
              </select>
              <label className="mt-1 block">starts at (s) <input type="number" min={0} className="w-24 rounded border border-olive px-1" value={cfg.nav_event_time_s} onChange={(e) => set("nav_event_time_s", Number(e.target.value))} /></label>
            </fieldset>
            <label className="block text-xs"><input type="checkbox" checked={cfg.autonomy} onChange={(e) => set("autonomy", e.target.checked)} data-testid="autonomy" /> Autonomous fallback enabled</label>
            <fieldset className="space-y-1 text-xs"><legend className="font-semibold">Failure injection</legend>
              <label className="block"><input type="checkbox" checked={cfg.terrain_blockage} onChange={(e) => set("terrain_blockage", e.target.checked)} data-testid="blockage" /> Inject terrain blockage (synthetic mound)</label>
              <div className="flex flex-wrap items-center gap-1">
                <select className="rounded border border-olive bg-bg-deep" value={outage.segment} onChange={(e) => setOutage({ ...outage, segment: e.target.value })} aria-label="Outage segment">
                  <option value="rover_base">rover–base link</option><option value="base_earth">base–Earth link</option>
                </select>
                <input aria-label="Outage start (s)" type="number" className="w-16 rounded border border-olive px-1" value={outage.start_s} onChange={(e) => setOutage({ ...outage, start_s: Number(e.target.value) })} />
                <input aria-label="Outage duration (s)" type="number" className="w-16 rounded border border-olive px-1" value={outage.duration_s} onChange={(e) => setOutage({ ...outage, duration_s: Number(e.target.value) })} />
                <button type="button" className="rounded border border-olive px-1" onClick={() => set("outages", [...cfg.outages, outage])} data-testid="add-outage">Add timed outage</button>
              </div>
              {cfg.outages.map((o, i) => (
                <p key={i}>{o.segment} at {o.start_s}s for {o.duration_s}s <button type="button" className="underline" onClick={() => set("outages", cfg.outages.filter((_, j) => j !== i))}>remove</button></p>
              ))}
            </fieldset>
            <fieldset className="space-y-1 text-xs"><legend className="font-semibold">Relay and local beacons</legend>
              <p>Beacons: {cfg.beacons.length ? cfg.beacons.map((b, i) => `B${i + 1} ${xyText(b)}`).join("; ") : "none"}</p>
              <div className="flex flex-wrap gap-1">
                <button type="button" className="rounded border border-olive px-1" onClick={() => setPick("beacon")}>Add beacon on map</button>
                <button type="button" className="rounded border border-olive px-1" onClick={() => set("beacons", [])}>Clear beacons</button>
                <button type="button" className="rounded border border-olive px-1" onClick={useSuggestions} data-testid="use-suggestions">Use derived relay + beacon sites</button>
              </div>
            </fieldset>
            <details className="text-xs" data-testid="advanced"><summary className="font-semibold">{t.missionLab.advanced}</summary>
              <div className="mt-1 grid grid-cols-2 gap-1">
                {([["max_slope_deg", "Max slope (deg)"], ["uncertainty_threshold_m", "Safety limit (m)"], ["science_uncertainty_m", "Science limit (m)"],
                  ["max_link_range_m", "Max link range (m)"], ["rover_antenna_m", "Rover mast (m)"], ["relay_antenna_m", "Relay mast (m)"],
                  ["drift_fraction", "DR drift (fraction)"], ["downlink_mb_per_s", "Downlink (MB/s)"]] as const).map(([k, label]) => (
                  <label key={k}>{label}<input type="number" step="any" className="w-full rounded border border-olive px-1" value={Number(cfg.advanced[k])} onChange={(e) => setAdv(k, Number(e.target.value))} data-testid={`adv-${k}`} /></label>
                ))}
                {Object.entries(cfg.advanced.weights).map(([k, v]) => (
                  <label key={k}>w_{k}<input type="number" step="0.1" min={0} className="w-full rounded border border-olive px-1" value={v} onChange={(e) => setCfg((c) => c ? { ...c, advanced: { ...c.advanced, weights: { ...c.advanced.weights, [k]: Number(e.target.value) } } } : c)} /></label>
                ))}
                <label>Simulation seed<input type="number" className="w-full rounded border border-olive px-1" value={cfg.seed} onChange={(e) => set("seed", Number(e.target.value))} /></label>
                <label>Terrain seed<input type="number" className="w-full rounded border border-olive px-1" value={cfg.terrain_seed} onChange={(e) => set("terrain_seed", Number(e.target.value))} /></label>
              </div>
            </details>
            <button type="button" disabled={busy} onClick={generate} data-testid="generate"
                    className="w-full rounded bg-olive px-3 py-2 font-semibold text-on-accent disabled:opacity-60">
              {busy ? t.missionLab.working : run ? t.missionLab.rerun : t.missionLab.generate}
            </button>
          </Card>
        </aside>

        {/* ---------------- workspace */}
        <main className="min-w-0 space-y-3" aria-label="Mission workspace">
          {!run && <p className="rounded border border-dashed border-olive p-6 text-center">Configure the mission and press <b>{t.missionLab.generate}</b>.</p>}
          {run && run.status === "NO_ROUTE" && (
            <p role="alert" data-testid="no-route-state" className="rounded border-2 border-terracotta bg-surface p-3">
              <b>No route.</b> {(run.summary.reasons ?? []).join("; ")} — change the start, target or constraints and generate again.
            </p>
          )}
          {run && run.status !== "NO_ROUTE" && terrain && (
            <>
              <div className="flex flex-wrap items-center gap-2 text-sm" data-testid="run-header">
                <b>Scenario #{run.scenario_id}</b> · <span data-testid="run-id">Run #{run.id}</span> · case {run.case_label} ·
                <Badge tone={statusTone(run.status)} testId="run-status">{run.status}</Badge>
                <span>science: <b data-testid="science-result">{run.summary.science_result}</b></span>
                <Badge tone="warn">{t.missionLab.synthetic}</Badge>
              </div>
              <div className="h-[480px] overflow-hidden rounded-lg border-2 border-olive bg-black">
                <Viewer3D ref={viewer} terrain={terrain} textureUrl={imageUrl(mapLayer, run.config)} run={run} pose={pose} frame={frame} layers={layers} follow={follow} />
              </div>
              <div className="flex flex-wrap items-center gap-2 text-sm" data-testid="playback">
                <button type="button" className="rounded bg-raised px-3 py-1 text-fg" onClick={() => { if (simT >= tEnd) setSimT(0); setPlaying(!playing); }} data-testid="play">
                  {playing ? "Pause" : simT > 0 && simT < tEnd ? "Resume" : "Play"}
                </button>
                <button type="button" className="rounded border border-line-strong px-3 py-1" onClick={() => { setSimT(0); setPlaying(false); }} data-testid="restart">Restart</button>
                <label>Speed <select value={speed} onChange={(e) => setSpeed(Number(e.target.value))} className="rounded border border-olive bg-bg-deep" data-testid="speed-select">
                  {[60, 300, 600, 1800, 3600].map((v) => <option key={v} value={v}>{v}×</option>)}
                </select></label>
                <input type="range" min={0} max={tEnd} step={1} value={simT} onChange={(e) => setSimT(Number(e.target.value))} className="min-w-40 flex-1" aria-label="Simulation time" data-testid="scrubber" />
                <span className="font-mono" data-testid="sim-clock">{formatSimTime(simT)} / {formatSimTime(tEnd)}</span>
              </div>
              <div className="flex flex-wrap gap-3 text-xs" aria-label="Layers">
                {(Object.keys(layers) as (keyof Layers)[]).map((k) => (
                  <label key={k}><input type="checkbox" checked={layers[k]} onChange={(e) => setLayers({ ...layers, [k]: e.target.checked })} data-testid={`layer-${k}`} /> {k}</label>
                ))}
                <label>Terrain colour <select value={mapLayer} onChange={(e) => setMapLayer(e.target.value as typeof mapLayer)} className="rounded border border-olive bg-bg-deep" data-testid="map-layer">
                  <option value="hillshade">hillshade</option><option value="slope">slope</option><option value="visibility">comm visibility heatmap</option>
                </select></label>
                <label><input type="checkbox" checked={follow} onChange={(e) => setFollow(e.target.checked)} data-testid="follow" /> follow rover</label>
              </div>
              <PhaseTracker phases={run.phases} states={states} nextAction={nextAction} />
              <div className="grid gap-3 2xl:grid-cols-[minmax(0,1fr)_280px]">
                <div className="min-w-0 space-y-3">

              <div role="tablist" className="flex flex-wrap gap-1 border-b border-olive">
                {(Object.keys(t.missionLab.tabs) as Tab[]).map((k) => (
                  <button key={k} role="tab" aria-selected={tab === k} type="button" onClick={() => setTab(k)} data-testid={`tab-${k}`}
                          className={`rounded-t px-3 py-1 text-sm ${tab === k ? "bg-olive text-on-accent" : "bg-surface"}`}>{t.missionLab.tabs[k]}</button>
                ))}
              </div>
              <div className="rounded-b border border-t-0 border-line bg-surface p-3">
                {tab === "timeline" && <Timeline events={run.events} t={simT} onSeek={(v) => { setSimT(v); setPlaying(false); }} />}
                {tab === "route" && <RouteAnalysis rec={run.routes.recommended} alt={run.routes.alternate} note={run.routes.recommended?.meta?.alternate_note} />}
                {tab === "sandbox" && (
                  <div className="grid gap-3 md:grid-cols-2" data-testid="sandbox">
                    <div className="space-y-1 text-xs">
                      <MapPanel terrain={terrain} imageUrl={imageUrl("visibility", cfg)} size={380} testId="sandbox-map"
                                markers={[...(losA ? [{ xy: losA, label: "ROVER", kind: "rover" as const }] : []), ...(losB ? [{ xy: losB, label: "RELAY/BASE", kind: "relay" as const }] : [])]}
                                line={losA && losB && los ? { a: losA, b: losB, ok: los.status === "LINE_OF_SIGHT" } : null}
                                obstructions={(los?.obstructions ?? []).map((o) => [o.x, o.y] as XY)}
                                onPick={pick === "losA" || pick === "losB" ? onPick : undefined}
                                pickHint={pick === "losA" ? "Click the rover position" : pick === "losB" ? "Click the relay/base position" : "Heatmap: visibility from the base (and relay) at rover mast height."} />
                      <div className="flex gap-1">
                        <button type="button" className="rounded border border-olive px-2" onClick={() => { setPick("losA"); setLos(null); setLosBHeight(null); }} data-testid="los-pick">Pick rover then relay</button>
                        <button type="button" className="rounded border border-olive px-2" onClick={() => { if (frame) { setLosBHeight(cfg.advanced.base_antenna_m); setLosA([frame.x, frame.y]); setLosB(terrain.base_xy); } }} data-testid="los-current">Current rover → base</button>
                      </div>
                    </div>
                    <div className="space-y-2 text-sm">
                      <p>Result: <Badge tone={los?.status === "LINE_OF_SIGHT" ? "ok" : los ? "bad" : "info"} testId="los-status">{los?.status ?? "pick two points"}</Badge></p>
                      {los && <p className="text-xs">{los.reason}; distance {los.distance_m} m; minimum clearance {los.min_clearance_m} m.</p>}
                      <LosProfile los={los} />
                      <p className="text-[11px]">Communication Visibility = geometric line of sight between antenna tips ({cfg.advanced.rover_antenna_m} m / {losBHeight ?? cfg.advanced.relay_antenna_m} m), including lunar curvature. It is not an RF link budget; no dBm or RSSI is shown.</p>
                    </div>
                  </div>
                )}
                {tab === "compare" && (
                  <div className="space-y-2 text-sm" data-testid="compare">
                    <p className="text-xs">Same mission, start, target and seeds. Baseline: nominal positioning, direct link, no outage. Stress: injected terrain blockage, GNSS unavailable from {cfg.nav_event_time_s} s, autonomy disabled. Mitigated: same stresses plus derived relay, derived beacons and autonomy enabled.</p>
                    <button type="button" disabled={busy || !scenario} onClick={runComparison} className="rounded bg-olive px-3 py-1 font-semibold text-on-accent disabled:opacity-60" data-testid="run-compare">
                      {busy ? t.missionLab.working : "Run baseline / stress / mitigated"}
                    </button>
                    {compare && (
                      <table className="w-full text-xs" data-testid="compare-table">
                        <thead><tr className="text-left text-olive"><th>Metric</th>{compare.runs.map((r) => <th key={r.id}>{r.case_label} (#{r.id})</th>)}</tr></thead>
                        <tbody>
                          {([["status", "Completion"], ["planned_route_m", "Route (m)"], ["mission_duration_s", "Duration"], ["earth_path_unavailable_s", "Earth path unavailable"],
                            ["max_data_queued_mb", "Max data queued (MB)"], ["max_position_uncertainty_m", "Max uncertainty (m)"], ["safety_pauses", "Safety pauses"],
                            ["fallback_actions", "Fallback actions"], ["science_result", "Sampling"]] as const).map(([k, label]) => (
                            <tr key={k} className="border-b border-line">
                              <td>{label}</td>
                              {compare.runs.map((r) => {
                                const v = r.summary[k];
                                return <td key={r.id} data-testid={`cmp-${r.case_label}-${k}`}>{k.endsWith("_s") ? formatSimTime(Number(v)) : String(v)}</td>;
                              })}
                            </tr>
                          ))}
                          <tr><td />{compare.runs.map((r) => <td key={r.id}><button type="button" className="underline" onClick={() => loadRun(r.id)} data-testid={`load-${r.case_label}`}>Load in viewer</button></td>)}</tr>
                        </tbody>
                      </table>
                    )}
                  </div>
                )}
                {tab === "report" && (
                  <div className="space-y-2 text-sm" data-testid="report-panel">
                    <p>The report is generated on the server from the exact saved Mission Run #{run.id} (configuration, routes, events, frames and summary) and embeds a snapshot hash. The current 3D view is attached as a snapshot. Runs from the latest comparison of this scenario are included in the results section.</p>
                    <button type="button" disabled={busy} onClick={exportReport} className="rounded bg-terracotta px-3 py-1 font-semibold text-on-accent disabled:opacity-60" data-testid="export-report">
                      {busy ? t.missionLab.working : report ? "Regenerate report" : `Export report for run #${run.id}`}
                    </button>
                    {report && (
                      <p data-testid="report-ready">
                        Report #{report.id} for run #{report.run_id} ({report.generated_at}, snapshot {report.snapshot_sha256.slice(0, 12)}…, 3D snapshot {report.has_viewer_snapshot ? "attached" : "not available"}) ·{" "}
                        <a className="underline" href={report.url} target="_blank" rel="noreferrer" data-testid="report-open">Open report</a> ·{" "}
                        <a className="underline" href={`${report.url}?download=true`} data-testid="report-download">Download HTML</a> — use “Print / save as PDF” in the report for a PDF.
                      </p>
                    )}
                  </div>
                )}
              </div>
                </div>
                <aside className="space-y-3" aria-label="Telemetry and events">
          {run && run.status !== "NO_ROUTE" && <Telemetry frame={frame} run={run} t={simT} />}
          {run && run.status !== "NO_ROUTE" && (
            <section className="rounded-lg border border-line bg-surface p-3 text-xs" aria-label="Latest events">
              <h3 className="mb-1 font-bold uppercase tracking-wider text-olive">Latest events</h3>
              <ol className="space-y-0.5" data-testid="latest-events">
                {seen.slice(-6).reverse().map((e) => <li key={e.seq}><span className="font-mono">{formatSimTime(e.t)}</span> <b>{e.type}</b></li>)}
              </ol>
            </section>
          )}
                </aside>
              </div>
            </>
          )}
        </main>

      </div>
    </div>
  );
}
