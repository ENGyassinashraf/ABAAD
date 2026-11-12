import { describe, expect, it } from "vitest";
import type { Region } from "./api";
import { MARS_EQC } from "./crs";
import { forwardSouthPolar, polarRadius } from "./lunar";
import { boundsOf, marsCamera, marsFullZoom, moonPanelXY, precisionOf } from "./mapView";

const point = (lon: number, lat: number, status = "source_traced") =>
  ({ geometry: { lon, lat, geometry_status: status } as Region["geometry"], outline: null }) as Pick<Region, "geometry" | "outline">;

describe("precisionOf", () => {
  it("states what the stored geometry supports, never more", () => {
    expect(precisionOf(point(137.7, -5.44))).toBe("source_traced_point");
    expect(precisionOf(point(25.9, 23.7, "approximate"))).toBe("approximate_point");
    expect(precisionOf({ geometry: null, outline: null })).toBe("none");
    expect(precisionOf({ geometry: null, outline: { rings: [[[0, 0]]], crs_code: "x", geometry_status: "approximate", uncertainty_note: null, source: null } })).toBe("approximate_outline");
  });
});

describe("marsCamera (ABAAD-MarsEqcQuad)", () => {
  it("frames a point at the requested zoom without inventing an extent", () => {
    const b = boundsOf(point(77.69, 18.41))!;
    expect(b.west).toBe(b.east);
    expect(marsCamera(b, 800, 400, { pointZoom: 2.3 })).toEqual({ center: [77.69, 18.41], zoom: 2.3 });
  });

  it("fits an outline using the tile matrix: 360° = tileSize px at zoom 0", () => {
    const b = { west: -12, south: 0, east: 70, north: 35 }; // stored Arabia Terra outline box
    const { center, zoom } = marsCamera(b, 1024, 1024, { fill: 0.5 });
    expect(center).toEqual([29, 17.5]);
    const widthPx = (MARS_EQC.tileMatrix.tileSize * 2 ** zoom * 82) / 360;
    expect(widthPx).toBeCloseTo(512, 6); // 50 % of 1024
  });

  it("full-planet zoom fits 360° × 180° in the viewport", () => {
    expect(marsFullZoom(1024, 512)).toBeCloseTo(1, 10);
    expect(marsFullZoom(512, 512)).toBeCloseTo(0, 10);
  });
});

describe("moonPanelXY (IAU_2015:30135)", () => {
  it("scales the projected metres so the panel edge latitude sits on the panel radius", () => {
    const [x, y] = moonPanelXY(90, -88, -88, 200)!;
    expect(x).toBeCloseTo(200, 9);
    expect(y).toBeCloseTo(0, 9);
  });

  it("places Shackleton (129.78° E, 89.67° S) from the stereographic forward, with SVG y down", () => {
    const [px, py] = moonPanelXY(129.78, -89.67, -88, 200)!;
    const [mx, my] = forwardSouthPolar(129.78, -89.67);
    const s = 200 / polarRadius(-88);
    expect(px).toBeCloseTo(mx * s, 9);
    expect(py).toBeCloseTo(-my * s, 9);
    expect(Math.hypot(mx, my)).toBeGreaterThan(9_000); // ~10 km from the pole
    expect(Math.hypot(mx, my)).toBeLessThan(11_000);
  });

  it("returns null outside the panel instead of clamping to the edge", () => {
    expect(moonPanelXY(0, -70, -80, 200)).toBeNull();
  });
});
