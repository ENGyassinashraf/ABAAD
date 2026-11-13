"use client";

import type { ReactNode } from "react";
import { fromMapPx, toMapPx } from "@/lib/mission/playback";
import type { Route, TerrainData, XY } from "@/lib/mission/types";

type Marker = { xy: XY; label: string; kind: "start" | "target" | "base" | "relay" | "beacon" | "rover" | "estimate" | "point" };

type Props = {
  terrain: TerrainData;
  imageUrl: string;
  size?: number;
  routes?: { recommended?: Route; alternate?: Route };
  markers?: Marker[];
  sigma?: number | null;
  line?: { a: XY; b: XY; ok: boolean } | null;
  obstructions?: XY[];
  onPick?: (xy: XY) => void;
  pickHint?: string;
  testId?: string;
  children?: ReactNode;
};

const COLORS: Record<Marker["kind"], string> = {
  start: "#ffffff", target: "#e0703f", base: "#5e6c4b", relay: "#3b78b5", beacon: "#8e5ab5",
  rover: "#f3ebdd", estimate: "#d6a93c", point: "#ffd34d",
};

/** 2D top-down map (north up) used for placement, the link sandbox and the route overview. */
export function MapPanel({ terrain, imageUrl, size = 420, routes, markers = [], sigma, line, obstructions = [], onPick, pickHint, testId }: Props) {
  const ext = terrain.extent_m;
  const px = (p: XY) => toMapPx(p, ext, size);
  const k = size / ext;
  const pts = (path: XY[]) => path.map((p) => px(p).join(",")).join(" ");

  return (
    <figure className="space-y-1">
      <svg
        data-testid={testId}
        viewBox={`0 0 ${size} ${size}`}
        width="100%"
        className={`block rounded border border-olive bg-black ${onPick ? "cursor-crosshair" : ""}`}
        role="img"
        aria-label="Top-down map of the synthetic training terrain"
        onClick={(e) => {
          if (!onPick) return;
          const r = (e.currentTarget as SVGSVGElement).getBoundingClientRect();
          onPick(fromMapPx([((e.clientX - r.left) / r.width) * size, ((e.clientY - r.top) / r.height) * size], ext, size));
        }}
      >
        <image href={imageUrl} x="0" y="0" width={size} height={size} preserveAspectRatio="none" />
        {terrain.hazards.map((h, i) => {
          const [x, y] = px([h.x, h.y]);
          return <circle key={i} cx={x} cy={y} r={h.radius_m * k} fill="rgba(170,30,30,.45)" stroke="#a01e1e" />;
        })}
        {routes?.alternate?.path && <polyline points={pts(routes.alternate.path)} fill="none" stroke="#c9e0a8" strokeWidth={2} strokeDasharray="6 4" />}
        {routes?.recommended?.path && <polyline points={pts(routes.recommended.path)} fill="none" stroke="#ff7a3d" strokeWidth={3} />}
        {routes?.recommended?.waypoints?.map((w) => {
          const [x, y] = px([w.x, w.y]);
          return (
            <g key={w.id}>
              <circle cx={x} cy={y} r={3.5} fill={w.comm_visible ? "#fff" : "none"} stroke="#fff" strokeWidth={1.5} />
              <text x={x + 5} y={y - 4} fontSize={9} fill="#fff" stroke="#000" strokeWidth={2.5} paintOrder="stroke">{w.id}</text>
            </g>
          );
        })}
        {line && (() => {
          const [ax, ay] = px(line.a);
          const [bx, by] = px(line.b);
          return <line x1={ax} y1={ay} x2={bx} y2={by} stroke={line.ok ? "#5e9a66" : "#d0402f"} strokeWidth={2.5} strokeDasharray={line.ok ? undefined : "5 3"} />;
        })()}
        {obstructions.map((o, i) => {
          const [x, y] = px(o);
          return <circle key={`o${i}`} cx={x} cy={y} r={4} fill="#ff3b2f" stroke="#fff" />;
        })}
        {markers.map((m, i) => {
          const [x, y] = px(m.xy);
          if (m.kind === "estimate") {
            return <circle key={i} cx={x} cy={y} r={Math.max(3, (sigma ?? 1) * k)} fill="none" stroke={COLORS.estimate} strokeWidth={1.5} />;
          }
          return (
            <g key={i} data-marker={m.kind}>
              <circle cx={x} cy={y} r={m.kind === "rover" ? 5 : 4.5} fill={COLORS[m.kind]} stroke="#000" strokeWidth={1} />
              <text x={x + 6} y={y + 3} fontSize={9.5} fontWeight={600} fill="#fff" stroke="#000" strokeWidth={2.5} paintOrder="stroke">{m.label}</text>
            </g>
          );
        })}
        <rect x={8} y={size - 16} width={200 * k} height={4} fill="#fff" stroke="#000" />
        <text x={8} y={size - 20} fontSize={9} fill="#fff" stroke="#000" strokeWidth={2.5} paintOrder="stroke">200 m · N up</text>
      </svg>
      {pickHint && <figcaption className="text-xs">{pickHint}</figcaption>}
    </figure>
  );
}
