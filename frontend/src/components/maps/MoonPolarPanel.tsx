"use client";

import { useState } from "react";
import type { Region } from "@/lib/api";
import { formatCoord } from "@/lib/api";
import { formatDistance, MOON_RADIUS_M, niceLength, polarRadius } from "@/lib/lunar";
import { moonPanelXY, precisionOf } from "@/lib/mapView";
import { messages as t } from "@/i18n/en";
import { PrecisionBadge } from "./PrecisionBadge";

const SIZE = 440;
const C = SIZE / 2;
const R = C - 30;
const r3 = (v: number) => Math.round(v * 1000) / 1000;

/** Two fixed extents of the same static panel; the projection never changes. */
const EXTENTS = {
  wide: { edge: -80, rings: [-80, -82, -84, -86, -88] },
  pole: { edge: -88, rings: [-88, -88.5, -89, -89.5] },
} as const;
type Extent = keyof typeof EXTENTS;

/**
 * Static south-polar panel in IAU_2015:30135 (Moon 2015 sphere, south polar
 * stereographic, R = 1,737,400 m) — the approved Moon decision. It is not an
 * interactive polar map: the only interaction is choosing one of two fixed
 * extents and selecting a stored point. No lunar imagery is used; the disc is
 * a neutral, labelled context fill.
 */
export function MoonPolarPanel({ regions, selected, onSelect }: { regions: Region[]; selected: string | null; onSelect: (code: string) => void }) {
  const [extent, setExtent] = useState<Extent>("pole");
  const { edge, rings } = EXTENTS[extent];
  const s = R / polarRadius(edge);
  const barM = niceLength(polarRadius(edge) * 0.45);
  const sel = regions.find((r) => r.code === selected) ?? null;
  const placed = regions
    .filter((r) => r.geometry)
    .map((r) => ({ r, xy: moonPanelXY(r.geometry!.lon, r.geometry!.lat, edge, R) }))
    .filter((p): p is { r: Region; xy: [number, number] } => p.xy !== null);

  return (
    <figure className="space-y-2" aria-labelledby="moon-caption">
      <div className="relative rounded-xl border border-line-strong bg-map-moon p-2">
        <div className="absolute right-2 top-2 z-10 flex overflow-hidden rounded-md border border-line-strong text-xs" role="group" aria-label={t.maps.moonExtent}>
          {(Object.keys(EXTENTS) as Extent[]).map((k) => (
            <button key={k} type="button" aria-pressed={extent === k} data-testid={`moon-extent-${k}`} onClick={() => setExtent(k)}
              className={`px-2.5 py-1 font-semibold ${extent === k ? "bg-ochre text-on-accent" : "bg-bg/80 hover:bg-hover"}`}>
              {t.maps.moonExtentLabel(-EXTENTS[k].edge)}
            </button>
          ))}
        </div>
        <svg viewBox={`0 0 ${SIZE} ${SIZE}`} className="mx-auto block w-full max-w-[26rem]" role="group"
          aria-label={t.maps.moonAria(-edge)} data-testid="moon-polar-panel" data-extent={extent}>
          <defs>
            <radialGradient id="moon-disc" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#3a3830" />
              <stop offset="100%" stopColor="#2b2a24" />
            </radialGradient>
          </defs>
          <circle cx={C} cy={C} r={R} fill="url(#moon-disc)" stroke="#665a45" strokeWidth={1.5} />
          {rings.map((lat) => (
            <g key={lat}>
              <circle cx={C} cy={C} r={r3(polarRadius(lat) * s)} fill="none" stroke="rgba(243,235,221,0.16)" strokeWidth={1} />
              <text x={C + 4} y={r3(C - polarRadius(lat) * s - 3)} fontSize="10" fill="#c9beaa">{`${-lat}°S`}</text>
            </g>
          ))}
          {Array.from({ length: 12 }, (_, i) => i * 30).map((lon) => {
            const [x, y] = moonPanelXY(lon, edge, edge, R)!;
            return (
              <g key={lon}>
                <line x1={C} y1={C} x2={r3(C + x)} y2={r3(C + y)} stroke="rgba(243,235,221,0.12)" strokeWidth={1} />
                <text x={r3(C + x * 1.08)} y={r3(C + y * 1.08 + 3)} fontSize="9" textAnchor="middle" fill="#9a907f">
                  {lon === 0 ? "0°" : lon <= 180 ? `${lon}°E` : `${360 - lon}°W`}
                </text>
              </g>
            );
          })}
          <g aria-hidden="true">
            <line x1={C - 5} x2={C + 5} y1={C} y2={C} stroke="#c9beaa" />
            <line y1={C - 5} y2={C + 5} x1={C} x2={C} stroke="#c9beaa" />
          </g>
          {placed.map(({ r, xy }) => {
            const active = r.code === selected;
            const x = r3(C + xy[0]);
            const y = r3(C + xy[1]);
            const approx = precisionOf(r) === "approximate_point";
            return (
              <g key={r.code} role="button" tabIndex={0} aria-pressed={active} data-testid={`moon-marker-${r.code}`} data-selected={active}
                aria-label={`${r.name}, ${formatCoord(r.geometry!)}, ${t.precision[precisionOf(r)]}`}
                onClick={() => onSelect(r.code)} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(r.code); } }}
                className="cursor-pointer outline-none [&:focus-visible>circle:first-child]:stroke-[#fcf9f2]">
                <circle cx={x} cy={y} r={active ? 9 : 7} fill={active ? "#d2ae70" : "rgba(132,145,108,0.55)"}
                  stroke={active ? "#d2ae70" : "#84916c"} strokeWidth={2} strokeDasharray={approx ? "3 2" : undefined} />
                {active && <circle cx={x} cy={y} r={14} fill="none" stroke="rgba(210,174,112,0.45)" strokeWidth={3} />}
                <rect x={x + 12} y={y - 9} width={r.name.length * 6.4 + 10} height={18} rx={4} fill={active ? "#d2ae70" : "rgba(27,26,22,0.8)"} />
                <text x={x + 17} y={y + 4} fontSize="11" fontWeight={active ? 700 : 400} fill={active ? "#1b1a16" : "#c9beaa"}>{r.name}</text>
              </g>
            );
          })}
          <g transform={`translate(18 ${SIZE - 18})`} data-testid="moon-scale">
            <line x1="0" y1="0" x2={r3(barM * s)} y2="0" stroke="#c9beaa" strokeWidth="3" />
            <text x="0" y="-6" fontSize="11" fill="#c9beaa">{`${formatDistance(barM)} (true at pole)`}</text>
          </g>
          <text x={SIZE - 10} y={SIZE - 10} fontSize="10" textAnchor="end" fill="#9a907f">{t.maps.moonNoImagery}</text>
        </svg>
        {sel && precisionOf(sel) === "none" && (
          <p className="mx-2 mb-2 rounded-md border border-warn/60 bg-bg/90 p-2 text-xs" role="status" data-testid="moon-no-geometry">
            <span className="font-semibold text-warn">{sel.name}: {t.maps.noGeometry}.</span> {t.maps.moonBodyLevel} {sel.geometry_gap}
          </p>
        )}
      </div>
      <figcaption id="moon-caption" className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-fg-2">
        <span>IAU_2015:30135 · {t.maps.moonCrsNote(MOON_RADIUS_M.toLocaleString("en"))}</span>
        {sel && <PrecisionBadge precision={precisionOf(sel)} />}
      </figcaption>
    </figure>
  );
}
