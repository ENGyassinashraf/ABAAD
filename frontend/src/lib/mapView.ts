/**
 * Pure helpers for the product planetary maps. No coordinate is invented
 * here: positions come from stored geometry and are projected only through
 * the approved CRS definitions in crs.ts (Mars) and lunar.ts (Moon).
 */
import type { Region } from "@/lib/api";
import { MARS_EQC } from "@/lib/crs";
import { forwardSouthPolar, polarRadius } from "@/lib/lunar";

/** What a region's stored geometry can honestly support on a map (UI spec §7.6). */
export type Precision =
  | "source_traced_outline"
  | "approximate_outline"
  | "source_traced_point"
  | "approximate_point"
  | "none";

export function precisionOf(r: Pick<Region, "geometry" | "outline">): Precision {
  if (r.outline) return r.outline.geometry_status === "source_traced" ? "source_traced_outline" : "approximate_outline";
  if (r.geometry) return r.geometry.geometry_status === "source_traced" ? "source_traced_point" : "approximate_point";
  return "none";
}

export type LonLatBounds = { west: number; south: number; east: number; north: number };

/** Bounds of the stored geometry (outline ring or single point); null when there is none. */
export function boundsOf(r: Pick<Region, "geometry" | "outline">): LonLatBounds | null {
  if (r.outline) {
    const pts = r.outline.rings.flat();
    const lons = pts.map((p) => p[0]);
    const lats = pts.map((p) => p[1]);
    return { west: Math.min(...lons), south: Math.min(...lats), east: Math.max(...lons), north: Math.max(...lats) };
  }
  if (r.geometry) return { west: r.geometry.lon, south: r.geometry.lat, east: r.geometry.lon, north: r.geometry.lat };
  return null;
}

/**
 * Camera for a lon/lat box on the Mars equirectangular map. In
 * ABAAD-MarsEqcQuad the whole planet (360° × 180°) is tileSize × tileSize/2
 * CSS px at zoom 0 and doubles per zoom level, so the zoom that makes a box
 * fill `fill` of the viewport follows directly from the tile matrix.
 * A point (zero-size box) gets `pointZoom`.
 */
export function marsCamera(
  b: LonLatBounds,
  widthPx: number,
  heightPx: number,
  { fill = 0.55, pointZoom = 3.5, maxZoom = 6 } = {},
): { center: [number, number]; zoom: number } {
  const center: [number, number] = [(b.west + b.east) / 2, (b.south + b.north) / 2];
  const dLon = b.east - b.west;
  const dLat = b.north - b.south;
  if (dLon === 0 && dLat === 0) return { center, zoom: pointZoom };
  const ts = MARS_EQC.tileMatrix.tileSize;
  const zx = dLon > 0 ? Math.log2((widthPx * fill) / ((ts * dLon) / 360)) : Infinity;
  const zy = dLat > 0 ? Math.log2((heightPx * fill) / ((ts / 2) * (dLat / 180))) : Infinity;
  return { center, zoom: Math.max(0, Math.min(maxZoom, zx, zy)) };
}

/** Zoom at which the whole of Mars fits the viewport (the "reset view"). */
export function marsFullZoom(widthPx: number, heightPx: number, margin = 1): number {
  const ts = MARS_EQC.tileMatrix.tileSize;
  return Math.max(0, Math.log2(margin * Math.min(widthPx / ts, heightPx / (ts / 2))));
}

/**
 * SVG placement on the static south-polar panel (IAU_2015:30135). The panel
 * spans the pole out to `edgeLat`; returns px from the panel centre, or null
 * if the point lies outside the panel.
 */
export function moonPanelXY(lon: number, lat: number, edgeLat: number, radiusPx: number): [number, number] | null {
  if (lat > edgeLat) return null;
  const s = radiusPx / polarRadius(edgeLat);
  const [x, y] = forwardSouthPolar(lon, lat);
  return [x * s, -y * s];
}
