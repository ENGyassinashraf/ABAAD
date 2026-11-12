"use client";

import { useEffect } from "react";
import reference from "../../../public/spike-fixtures/moon_reference.json";
import { formatDistance, forwardSouthPolar, MOON_RADIUS_M, niceLength, polarRadius, scaleFactor } from "@/lib/lunar";
import type { Status, TestId } from "./useResults";

const SIZE = 440;
const C = SIZE / 2;
const EDGE_LAT = -80;
const RINGS = [-80, -82, -84, -86, -88];
const MERIDIANS = Array.from({ length: 12 }, (_, i) => i * 30);
/** Round to 0.001 px so server and browser trigonometry render identical SVG (no hydration mismatch). */
const r3 = (v: number) => Math.round(v * 1000) / 1000;

/** Static south-polar panel (T5). No lunar imagery in Phase 1: the fill is a synthetic placeholder. */
export function MoonPanel({ report }: { report: (id: TestId, s: Status, actual: string) => void }) {
  const rhoMax = polarRadius(EDGE_LAT);
  const s = (C - 24) / rhoMax; // px per metre at the pole (scale factor 1)
  const toPx = (lon: number, lat: number) => {
    const [x, y] = forwardSouthPolar(lon, lat);
    return [r3(C + x * s), r3(C - y * s)] as const;
  };
  const barM = niceLength(rhoMax * 0.4);

  useEffect(() => {
    const worst = Math.max(
      ...reference.reference_points.map((p) => {
        const [x, y] = forwardSouthPolar(p.lon, p.lat);
        return Math.hypot(x - p.x_m, y - p.y_m);
      }),
    );
    const radiusOk = reference.radius_m === MOON_RADIUS_M;
    report("T5", worst < 1e-3 && radiusOk ? "pass" : "fail",
      `static SVG panel in ${reference.crs} (${reference.crs_name}); max deviation from pyproj: ${worst.toExponential(2)} m; ` +
      `radius ${MOON_RADIUS_M} m; scale bar ${formatDistance(barM)} = ${(barM * s).toFixed(1)} px (true at pole; ` +
      `scale factor ${scaleFactor(EDGE_LAT).toFixed(4)} at ${EDGE_LAT}°)`);
  }, [report, barM, s]);

  return (
    <figure className="space-y-2">
      <svg viewBox={`0 0 ${SIZE} ${SIZE}`} className="w-full max-w-md rounded border-2 border-olive bg-ivory" role="img"
        aria-label="Synthetic lunar south-polar test panel with graticule and scale bar" data-testid="moon-panel">
        <defs>
          <pattern id="hatch" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <line x1="0" y1="0" x2="0" y2="8" stroke="#d8cbb8" strokeWidth="2" />
          </pattern>
        </defs>
        <circle cx={C} cy={C} r={r3(rhoMax * s)} fill="url(#hatch)" />
        {RINGS.map((lat) => (
          <g key={lat}>
            <circle cx={C} cy={C} r={r3(polarRadius(lat) * s)} fill="none" stroke="#5e6c4b" strokeWidth={lat === EDGE_LAT ? 2 : 1} />
            <text x={C + 3} y={r3(C - polarRadius(lat) * s - 3)} fontSize="10" fill="#3d352d">{`${-lat}°S`}</text>
          </g>
        ))}
        {MERIDIANS.map((lon) => {
          const [x, y] = toPx(lon, EDGE_LAT);
          return (
            <g key={lon}>
              <line x1={C} y1={C} x2={x} y2={y} stroke="#5e6c4b" strokeWidth="1" />
              <text x={r3(C + (x - C) * 1.06)} y={r3(C + (y - C) * 1.06 + 3)} fontSize="9" textAnchor="middle" fill="#3d352d">
                {lon === 0 ? "0°" : lon <= 180 ? `${lon}°E` : `${360 - lon}°W`}
              </text>
            </g>
          );
        })}
        <g transform={`translate(16 ${SIZE - 20})`} data-testid="moon-scale">
          <line x1="0" y1="0" x2={r3(barM * s)} y2="0" stroke="#3d352d" strokeWidth="3" />
          <text x="0" y="-6" fontSize="11" fill="#3d352d">{`${formatDistance(barM)} (true at pole)`}</text>
        </g>
        <text x={SIZE - 8} y={SIZE - 8} fontSize="10" textAnchor="end" fill="#a95e40">SYNTHETIC PLACEHOLDER — no lunar imagery</text>
      </svg>
      <figcaption className="text-xs">
        Moon south pole, {reference.crs} ({reference.crs_name}), radius {MOON_RADIUS_M.toLocaleString("en")} m, to
        {" "}{-EDGE_LAT}°S. Static panel: no interactive polar map in Phase 1. The hatched fill is a placeholder, not data.
      </figcaption>
    </figure>
  );
}
