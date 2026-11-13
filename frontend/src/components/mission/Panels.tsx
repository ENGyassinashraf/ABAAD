"use client";

import { formatSimTime, type PhaseState } from "@/lib/mission/playback";
import type { Frame, LosResult, MissionEvent, Phase, Route, Run } from "@/lib/mission/types";

const LINK_LABEL: Record<string, string> = {
  LINE_OF_SIGHT: "LINE_OF_SIGHT", BLOCKED_BY_TERRAIN: "BLOCKED_BY_TERRAIN", OUT_OF_RANGE: "OUT_OF_RANGE", UNKNOWN: "UNKNOWN",
};

export function Badge({ tone, children, testId }: { tone: "ok" | "warn" | "bad" | "info"; children: React.ReactNode; testId?: string }) {
  const c = { ok: "bg-olive text-ivory", warn: "bg-ochre text-earth", bad: "bg-terracotta text-ivory", info: "bg-earth text-ivory" }[tone];
  return <span data-testid={testId} className={`inline-block rounded px-2 py-0.5 text-xs font-semibold ${c}`}>{children}</span>;
}

export function statusTone(s: string): "ok" | "warn" | "bad" {
  if (s === "COMPLETED") return "ok";
  if (s === "COMPLETED_WITH_DEVIATIONS" || s === "PARTIAL") return "warn";
  return "bad";
}

function Row({ k, v, testId }: { k: string; v: React.ReactNode; testId?: string }) {
  return (
    <div className="flex justify-between gap-3 border-b border-border-soft py-1 text-sm">
      <dt className="text-earth/80">{k}</dt>
      <dd className="text-right font-medium" data-testid={testId}>{v}</dd>
    </div>
  );
}

export function Telemetry({ frame, run, t }: { frame: Frame | null; run: Run; t: number }) {
  if (!frame) return null;
  const s = run.summary;
  const losTone = frame.los === "LINE_OF_SIGHT" ? "ok" : frame.los === "BLOCKED_BY_TERRAIN" ? "bad" : "warn";
  return (
    <section aria-labelledby="tel-h" className="rounded-lg border-2 border-olive bg-ivory p-3">
      <h3 id="tel-h" className="mb-2 text-sm font-bold uppercase tracking-wider text-olive">Telemetry (simulated)</h3>
      <dl>
        <Row k="Sim time" v={formatSimTime(t)} testId="tel-time" />
        <Row k="Direct link geometry" v={<Badge tone={losTone} testId="tel-los">{LINK_LABEL[frame.los] ?? frame.los}</Badge>} />
        <Row k="Local link / path" v={<span data-testid="tel-local">{frame.local ? `available (${frame.path})` : "unavailable"}</span>} />
        <Row k="Earth path" v={frame.earth ? "available" : "unavailable"} testId="tel-earth" />
        <Row k="One-way Earth–Moon delay" v={`${s.one_way_earth_delay_s ?? "—"} s`} />
        <Row k="Round-trip (theoretical)" v={`${s.round_trip_propagation_estimate_s ?? "—"} s`} />
        <Row k="Since last Earth contact" v={frame.since_contact == null ? "no contact yet" : formatSimTime(frame.since_contact)} testId="tel-since" />
        <Row k="Data waiting" v={`${frame.queue.toFixed(1)} MB`} testId="tel-queue" />
        <Row k="Navigation mode" v={frame.nav} testId="tel-nav" />
        <Row k="Position uncertainty (1σ)" v={`${frame.sigma.toFixed(1)} m`} testId="tel-sigma" />
        <Row k="Speed (assumed)" v={`${run.routes.recommended?.assumed_speed_mps ?? "—"} m/s`} />
        <Row k="Distance driven" v={`${frame.dist.toFixed(0)} m`} testId="tel-dist" />
        <Row k="Safety state" v={frame.safety} testId="tel-safety" />
        <Row k="Energy" v="not modelled" />
      </dl>
      <p className="mt-2 text-[11px]">Geometric visibility only — not measured RSSI; no signal strength is computed.</p>
    </section>
  );
}

export function PhaseTracker({ phases, states, nextAction }: { phases: Phase[]; states: PhaseState[]; nextAction: string }) {
  const tone: Record<PhaseState, string> = {
    done: "bg-olive text-ivory", current: "bg-terracotta text-ivory ring-2 ring-earth", next: "bg-sand border border-olive",
    pending: "bg-sand", halted: "bg-earth text-ivory", not_reached: "bg-sand opacity-50 line-through",
  };
  return (
    <section aria-label="Mission phases" className="space-y-1">
      <ol className="grid grid-cols-4 gap-1 lg:grid-cols-8" data-testid="phase-tracker">
        {phases.map((p, i) => (
          <li key={p.phase} data-state={states[i]} data-testid={`phase-${p.phase}`}
              className={`rounded px-1.5 py-1 text-[11px] leading-tight ${tone[states[i]]}`} title={p.name}>
            <b>{p.phase}</b> {p.name}
          </li>
        ))}
      </ol>
      <p className="text-xs" data-testid="next-action"><b>Next action:</b> {nextAction}</p>
    </section>
  );
}

export function Timeline({ events, t, onSeek }: { events: MissionEvent[]; t: number; onSeek: (t: number) => void }) {
  const important = new Set(["LOS_LOST", "COMM_BLOCKED", "COMM_RECOVERED", "POSITIONING_UNAVAILABLE", "POSITIONING_DEGRADED",
    "NAV_UNCERTAINTY_INCREASING", "NAV_CORRECTION", "AUTONOMOUS_FALLBACK", "SAFETY_PAUSE", "SAFE_HOLD", "REROUTE",
    "DATA_TRANSMITTED", "SCIENCE_COMPLETE", "SCIENCE_FAILED", "MISSION_COMPLETE", "NAV_THRESHOLD_EXCEEDED", "OUTAGE_START", "OUTAGE_END"]);
  return (
    <ol className="max-h-80 space-y-1 overflow-auto pr-1 text-xs" data-testid="timeline">
      {events.map((e) => (
        <li key={e.seq} data-type={e.type}>
          <button type="button" onClick={() => onSeek(e.t)}
                  className={`w-full rounded px-2 py-1 text-left ${e.t <= t ? "bg-ivory" : "bg-sand opacity-60"} ${important.has(e.type) ? "border-l-4 border-terracotta" : "border-l-4 border-border-soft"}`}>
            <span className="font-mono">{formatSimTime(e.t)}</span> · P{e.phase} · <b>{e.type}</b> — {e.result}
          </button>
        </li>
      ))}
    </ol>
  );
}

export function RouteAnalysis({ rec, alt, note }: { rec?: Route; alt?: Route; note?: string | null }) {
  if (!rec) return <p data-testid="no-route">No route.</p>;
  const keys = ["distance_cost", "slope_penalty", "roughness_penalty", "hazard_penalty", "communication_penalty"];
  const max = Math.max(...keys.map((k) => Math.max(rec.cost_breakdown[k] ?? 0, alt?.cost_breakdown[k] ?? 0)), 1);
  const row = (label: string, a: React.ReactNode, b: React.ReactNode) => (
    <tr><td className="py-0.5 pr-2">{label}</td><td className="pr-2 font-medium">{a}</td><td>{b}</td></tr>
  );
  const pct = (v: number) => `${Math.round(v * 100)}%`;
  return (
    <div className="space-y-3 text-sm" data-testid="route-analysis">
      <table className="w-full">
        <thead><tr className="text-left text-xs uppercase text-olive"><th>Metric</th><th>Recommended</th><th>Alternate</th></tr></thead>
        <tbody>
          {row("Distance", <span data-testid="route-distance">{rec.distance_m} m</span>, alt ? `${alt.distance_m} m` : "—")}
          {row("Max / mean slope", `${rec.max_slope_deg}° / ${rec.mean_slope_deg}°`, alt ? `${alt.max_slope_deg}° / ${alt.mean_slope_deg}°` : "—")}
          {row("Est. duration (assumed speed)", `${(rec.estimated_duration_s / 3600).toFixed(1)} h`, alt ? `${(alt.estimated_duration_s / 3600).toFixed(1)} h` : "—")}
          {row("Comm-visible length", pct(rec.comm_visible_fraction), alt ? pct(alt.comm_visible_fraction) : "—")}
          {row("Hazard exposure", `${rec.hazard_exposure_m} m`, alt ? `${alt.hazard_exposure_m} m` : "—")}
          {row("Total weighted cost", <b>{rec.total_cost}</b>, alt ? alt.total_cost : "—")}
        </tbody>
      </table>
      <div>
        <p className="text-xs font-semibold uppercase text-olive">Cost breakdown (recommended vs alternate)</p>
        {keys.map((k) => (
          <div key={k} className="grid grid-cols-[9rem_1fr] items-center gap-2 text-xs">
            <span>{k.replace(/_/g, " ")}</span>
            <span className="space-y-0.5">
              <span className="block h-2 rounded bg-terracotta" style={{ width: `${(100 * (rec.cost_breakdown[k] ?? 0)) / max}%` }} />
              {alt && <span className="block h-2 rounded bg-olive/60" style={{ width: `${(100 * (alt.cost_breakdown[k] ?? 0)) / max}%` }} />}
            </span>
          </div>
        ))}
      </div>
      <p><b>Why recommended:</b> {rec.explanation}</p>
      {!alt && note && <p className="text-xs">Alternate: {note}</p>}
      <p className="text-xs">
        {rec.planner_version} · hard constraints: max slope {String(rec.hard_constraints.max_slope_deg)}°, no-go zones avoided, target must be reached.
        {" "}<b>Demonstration route</b> — {rec.meta?.demonstration_reason}. Not a global optimum.
      </p>
    </div>
  );
}

export function LosProfile({ los }: { los: LosResult | null }) {
  if (!los || los.profile.length === 0) return <p className="text-xs">Pick two points on the map to see the terrain cross-section.</p>;
  const w = 420, h = 150, L = 34, B = 18;
  const ds = los.profile.map((p) => p.d);
  const ys = los.profile.flatMap((p) => [p.ground, p.ray]);
  const dmax = Math.max(...ds, 1), ymin = Math.min(...ys), ymax = Math.max(...ys);
  const X = (d: number) => L + ((w - L - 6) * d) / dmax;
  const Y = (v: number) => h - B - ((h - B - 8) * (v - ymin)) / (ymax - ymin || 1);
  const ground = los.profile.map((p) => `${X(p.d)},${Y(p.ground)}`).join(" ");
  return (
    <figure data-testid="los-profile">
      <svg viewBox={`0 0 ${w} ${h}`} width="100%" className="rounded border border-border-soft bg-white">
        <polygon points={`${X(0)},${h - B} ${ground} ${X(dmax)},${h - B}`} fill="#d8cbb8" />
        <polyline points={ground} fill="none" stroke="#3d352d" />
        <line x1={X(los.profile[0].d)} y1={Y(los.profile[0].ray)} x2={X(dmax)} y2={Y(los.profile[los.profile.length - 1].ray)}
              stroke={los.status === "LINE_OF_SIGHT" ? "#5e9a66" : "#d0402f"} strokeWidth={2} />
        {los.obstructions.map((o, i) => <circle key={i} cx={X(o.distance_m)} cy={Y(los.profile.reduce((a, p) => (Math.abs(p.d - o.distance_m) < Math.abs(a.d - o.distance_m) ? p : a)).ground)} r={4} fill="#ff3b2f" />)}
        <text x={L} y={h - 4} fontSize={9}>0 m</text>
        <text x={w - 6} y={h - 4} fontSize={9} textAnchor="end">{dmax.toFixed(0)} m</text>
        <text x={2} y={12} fontSize={9}>{ymax.toFixed(0)} m</text>
      </svg>
      <figcaption className="text-xs">Terrain cross-section (with lunar curvature) and the antenna-to-antenna ray.</figcaption>
    </figure>
  );
}
