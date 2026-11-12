/**
 * Coordinate reference systems used by the Phase 1 map feasibility spike.
 *
 * Rules (Revision 1, Document 1):
 *  - Earth geometry may be RFC 7946 GeoJSON (WGS 84 lon/lat).
 *  - Mars/Moon geometry is never RFC 7946; it carries its own CRS.
 *  - A map never mixes sources from different CRSs (MapLibre does not
 *    reproject tile content), so every source added through this module
 *    declares its CRS and a mismatch is refused (test T4).
 */

export type Body = "earth" | "mars" | "moon";

export interface PlanarCrs {
  /** CRS identifier, also used as the MapLibre projection name (must contain a colon). */
  id: string;
  body: Body;
  name: string;
  /** Sphere radius in metres from the IAU 2015 definition. */
  radiusM: number;
  /** PROJ string; also the MapLibre `definition` handed to the worker handler. */
  definition: string;
  forward(lonLat: number[]): number[];
  inverse(xy: number[]): number[];
  tileMatrix: { id: string; origin: [number, number]; extentAtZoom0: number; tileSize: number };
}

const DEG = Math.PI / 180;

/** IAU_2015:49910 — Mars (2015) Sphere / Ocentric / Equirectangular, clon = 0. */
export const MARS_RADIUS_M = 3396190;
export const MARS_EQC: PlanarCrs = {
  id: "IAU_2015:49910",
  body: "mars",
  name: "Mars (2015) - Sphere / Ocentric / Equirectangular, clon = 0",
  radiusM: MARS_RADIUS_M,
  definition: "+proj=eqc +lat_ts=0 +lat_0=0 +lon_0=0 +x_0=0 +y_0=0 +R=3396190 +units=m",
  forward: ([lon, lat]) => [MARS_RADIUS_M * lon * DEG, MARS_RADIUS_M * lat * DEG],
  inverse: ([x, y]) => [x / (MARS_RADIUS_M * DEG), y / (MARS_RADIUS_M * DEG)],
  tileMatrix: {
    id: "ABAAD-MarsEqcQuad",
    origin: [-Math.PI * MARS_RADIUS_M, Math.PI * MARS_RADIUS_M],
    extentAtZoom0: 2 * Math.PI * MARS_RADIUS_M,
    tileSize: 512,
  },
};

/** Identifiers of non-planar-CRS sources that may appear on an Earth map. */
export const EARTH_WEB_MERCATOR = "EPSG:3857";
export const EARTH_CRS84 = "OGC:CRS84";

export class CrsMismatchError extends Error {
  constructor(
    public readonly mapCrs: string,
    public readonly sourceCrs: string,
    public readonly sourceId: string,
  ) {
    super(
      `Refused source "${sourceId}": its CRS ${sourceCrs} does not match the map CRS ${mapCrs}. ` +
        "MapLibre does not reproject tiles, so mixing CRSs would draw in the wrong place.",
    );
    this.name = "CrsMismatchError";
  }
}

/** Throws unless a source declared in `sourceCrs` may be drawn on a map in `mapCrs`. */
export function assertCompatibleCrs(mapCrs: string, sourceCrs: string, sourceId: string): void {
  if (mapCrs === sourceCrs) return;
  // RFC 7946 (CRS84) vector data is reprojected by MapLibre itself on a Web Mercator map.
  if (mapCrs === EARTH_WEB_MERCATOR && sourceCrs === EARTH_CRS84) return;
  // Planetary lon/lat geometry is projected by the registered CRS's own converter.
  if (mapCrs === MARS_EQC.id && sourceCrs === "IAU_2015:49900") return;
  throw new CrsMismatchError(mapCrs, sourceCrs, sourceId);
}

/** Metres represented by one CSS pixel at `zoom` on a map in this planar CRS. */
export function metresPerPixel(crs: PlanarCrs, zoom: number): number {
  return crs.tileMatrix.extentAtZoom0 / (crs.tileMatrix.tileSize * 2 ** zoom);
}
