import { describe, expect, it } from "vitest";
import mars from "../../public/spike-fixtures/mars_fixture.json";
import moon from "../../public/spike-fixtures/moon_reference.json";
import { assertCompatibleCrs, CrsMismatchError, MARS_EQC, metresPerPixel } from "./crs";
import { forwardSouthPolar, MOON_RADIUS_M, niceLength, polarRadius, scaleFactor } from "./lunar";
import { parseWkt } from "./wkt";

describe("Mars equirectangular CRS (IAU_2015:49910)", () => {
  it("matches the fixture radius, tile matrix and PROJ definition", () => {
    expect(mars.synthetic).toBe(true);
    expect(MARS_EQC.radiusM).toBe(mars.display.radius_m);
    expect(MARS_EQC.tileMatrix.origin[0]).toBeCloseTo(mars.tile_matrix.origin[0], 6);
    expect(MARS_EQC.tileMatrix.origin[1]).toBeCloseTo(mars.tile_matrix.origin[1], 6);
    expect(MARS_EQC.tileMatrix.extentAtZoom0).toBeCloseTo(mars.tile_matrix.extentAtZoom0, 6);
    expect(MARS_EQC.tileMatrix.tileSize).toBe(mars.tile_matrix.tileSize);
    expect(MARS_EQC.definition).toBe(mars.display.proj);
  });

  it("forward() reproduces pyproj control-point coordinates to 1 mm", () => {
    for (const cp of mars.control_points) {
      const [x, y] = MARS_EQC.forward([cp.lon, cp.lat]);
      expect(Math.abs(x - cp.expected_x_m)).toBeLessThan(1e-3);
      expect(Math.abs(y - cp.expected_y_m)).toBeLessThan(1e-3);
    }
  });

  it("inverse() round-trips", () => {
    for (const cp of mars.control_points) {
      const [lon, lat] = MARS_EQC.inverse(MARS_EQC.forward([cp.lon, cp.lat]));
      expect(lon).toBeCloseTo(cp.lon, 9);
      expect(lat).toBeCloseTo(cp.lat, 9);
    }
  });

  it("metres per pixel follow the declared tile matrix", () => {
    expect(metresPerPixel(MARS_EQC, 0)).toBeCloseTo((2 * Math.PI * 3396190) / 512, 6);
    expect(metresPerPixel(MARS_EQC, 3)).toBeCloseTo(metresPerPixel(MARS_EQC, 0) / 8, 6);
  });
});

describe("CRS mismatch guard (T4)", () => {
  it("refuses Web Mercator tiles on a Mars map", () => {
    expect(() => assertCompatibleCrs(MARS_EQC.id, "EPSG:3857", "openfreemap")).toThrow(CrsMismatchError);
  });
  it("refuses Earth WGS 84 geometry on a Mars map", () => {
    expect(() => assertCompatibleCrs(MARS_EQC.id, "OGC:CRS84", "earth-outline")).toThrow(CrsMismatchError);
  });
  it("refuses Mars geometry on an Earth map", () => {
    expect(() => assertCompatibleCrs("EPSG:3857", "IAU_2015:49900", "mars-wkt")).toThrow(CrsMismatchError);
  });
  it("accepts matching CRSs", () => {
    expect(() => assertCompatibleCrs(MARS_EQC.id, MARS_EQC.id, "mars-tiles")).not.toThrow();
    expect(() => assertCompatibleCrs(MARS_EQC.id, "IAU_2015:49900", "mars-wkt")).not.toThrow();
    expect(() => assertCompatibleCrs("EPSG:3857", "OGC:CRS84", "earth-outline")).not.toThrow();
  });
});

describe("WKT reader", () => {
  it("reads the fixture polygon", () => {
    const g = parseWkt(mars.geometry.wkt);
    expect(g.type).toBe("Polygon");
    expect(g.coordinates).toEqual([[[40, 25], [50, 25], [50, 35], [40, 35], [40, 25]]]);
  });
  it("reads a point and rejects unsupported or open rings", () => {
    expect(parseWkt("POINT (45 30)")).toEqual({ type: "Point", coordinates: [45, 30] });
    expect(() => parseWkt("LINESTRING (0 0, 1 1)")).toThrow();
    expect(() => parseWkt("POLYGON ((0 0, 1 0, 1 1, 0 1))")).toThrow();
  });
});

describe("Lunar south polar stereographic (T5, IAU_2015:30135)", () => {
  it("uses the IAU 2015 lunar radius", () => {
    expect(MOON_RADIUS_M).toBe(moon.radius_m);
  });
  it("matches pyproj reference points to 1 mm", () => {
    for (const p of moon.reference_points) {
      const [x, y] = forwardSouthPolar(p.lon, p.lat);
      expect(Math.abs(x - p.x_m)).toBeLessThan(1e-3);
      expect(Math.abs(y - p.y_m)).toBeLessThan(1e-3);
    }
  });
  it("has true scale at the pole and known radii", () => {
    expect(scaleFactor(-90)).toBeCloseTo(1, 12);
    expect(polarRadius(-90)).toBeCloseTo(0, 6);
    expect(polarRadius(-80)).toBeCloseTo(304005.608, 2);
  });
  it("picks nice scale-bar lengths", () => {
    expect(niceLength(73000)).toBe(50000);
    expect(niceLength(19999)).toBe(10000);
    expect(niceLength(250)).toBe(200);
  });
});
