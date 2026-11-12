/**
 * Minimal WKT reader for the map spike (POINT and single-ring POLYGON only).
 * The output is an in-memory geometry for MapLibre in the CRS declared next to
 * the WKT; it is never served or labelled as RFC 7946 GeoJSON.
 */

export type WktGeometry =
  | { type: "Point"; coordinates: [number, number] }
  | { type: "Polygon"; coordinates: [number, number][][] };

function parsePairs(body: string): [number, number][] {
  return body.split(",").map((pair) => {
    const nums = pair.trim().split(/\s+/).map(Number);
    if (nums.length !== 2 || nums.some((n) => !Number.isFinite(n))) {
      throw new Error(`Invalid WKT coordinate pair: "${pair.trim()}"`);
    }
    return [nums[0], nums[1]];
  });
}

export function parseWkt(wkt: string): WktGeometry {
  const text = wkt.trim();
  const point = /^POINT\s*\(\s*([^()]+)\s*\)$/i.exec(text);
  if (point) {
    const [c] = parsePairs(point[1]);
    return { type: "Point", coordinates: c };
  }
  const poly = /^POLYGON\s*\(\s*\(\s*([^()]+)\s*\)\s*\)$/i.exec(text);
  if (poly) {
    const ring = parsePairs(poly[1]);
    const [first, last] = [ring[0], ring[ring.length - 1]];
    if (ring.length < 4 || first[0] !== last[0] || first[1] !== last[1]) {
      throw new Error("WKT polygon ring must be closed and have at least 4 positions");
    }
    return { type: "Polygon", coordinates: [ring] };
  }
  throw new Error(`Unsupported WKT (spike supports POINT and single-ring POLYGON): ${text.slice(0, 40)}`);
}
