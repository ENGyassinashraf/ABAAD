/**
 * Lunar south polar stereographic maths for the static panel (test T5).
 * Matches IAU_2015:30135 — Moon (2015) Sphere / Ocentric / South Polar:
 *   +proj=stere +lat_0=-90 +lon_0=0 +k=1 +R=1737400
 * Unit tests compare these functions with pyproj reference values.
 */

export const MOON_RADIUS_M = 1737400;
const DEG = Math.PI / 180;

/** Distance from the south pole on the projection plane, metres. */
export function polarRadius(latDeg: number, radiusM = MOON_RADIUS_M): number {
  return 2 * radiusM * Math.tan(Math.PI / 4 + (latDeg * DEG) / 2);
}

/** Projected x, y in metres (y points towards longitude 0, as in PROJ). */
export function forwardSouthPolar(lonDeg: number, latDeg: number, radiusM = MOON_RADIUS_M): [number, number] {
  const rho = polarRadius(latDeg, radiusM);
  return [rho * Math.sin(lonDeg * DEG), rho * Math.cos(lonDeg * DEG)];
}

/** Point scale factor of the projection at a latitude (1 at the pole). */
export function scaleFactor(latDeg: number): number {
  return 2 / (1 - Math.sin(latDeg * DEG));
}

/** Pick a "nice" scale-bar length (1, 2 or 5 × 10^n metres) not wider than maxM. */
export function niceLength(maxM: number): number {
  const exp = 10 ** Math.floor(Math.log10(maxM));
  for (const m of [5, 2, 1]) if (m * exp <= maxM) return m * exp;
  return exp;
}

export function formatDistance(m: number): string {
  return m >= 1000 ? `${(m / 1000).toLocaleString("en")} km` : `${m.toLocaleString("en")} m`;
}
