"use client";

import { useEffect, useRef, useState } from "react";
import type { Map as MlMap, SourceSpecification } from "maplibre-gl";
import fixture from "../../../public/spike-fixtures/mars_fixture.json";
import { loadMapLibre } from "@/lib/maplibre";
import { assertCompatibleCrs, CrsMismatchError, MARS_EQC, metresPerPixel } from "@/lib/crs";
import { formatDistance, niceLength } from "@/lib/lunar";
import { parseWkt } from "@/lib/wkt";
import type { Status, TestId } from "./useResults";

type Rgb = [number, number, number];
const MARKER: Rgb = [255, 0, 255];
const POLYGON: Rgb = [255, 214, 0];
const OVERLAY: Rgb = [0, 200, 255];
const OVERLAY_HEX = "#00c8ff";

let projectionRegistered = false;

async function registerMarsProjection() {
  const ml = await loadMapLibre();
  if (!projectionRegistered) {
    try {
      ml.addProjection({
        name: MARS_EQC.id,
        projection: { forward: MARS_EQC.forward, inverse: MARS_EQC.inverse },
        tileMatrixSet: { origin: MARS_EQC.tileMatrix.origin, extentAtZoom0: MARS_EQC.tileMatrix.extentAtZoom0 },
        definition: MARS_EQC.definition,
      });
    } catch (e) {
      if (!/already (exists|registered)/.test(String(e))) throw e;
    }
    await ml.importScriptInWorkers(new URL("/maplibre/abaad-crs-worker.js", window.location.origin).href);
    projectionRegistered = true;
  }
  return ml;
}

/** Add a source only if its declared CRS is compatible with the map CRS (test T4). */
function addSourceChecked(map: MlMap, mapCrs: string, id: string, source: SourceSpecification, sourceCrs: string) {
  assertCompatibleCrs(mapCrs, sourceCrs, id);
  map.addSource(id, source);
}

const idle = (map: MlMap) => new Promise<void>((r) => map.once("idle", () => r()));

function close(a: Uint8Array, i: number, c: Rgb, tol = 40) {
  return Math.abs(a[i] - c[0]) <= tol && Math.abs(a[i + 1] - c[1]) <= tol && Math.abs(a[i + 2] - c[2]) <= tol;
}

/**
 * Centroid (CSS px, relative to the projected point) of pixels of colour `c`
 * in a square window around CSS point (px, py). Returns null if none found.
 */
function centroidNear(map: MlMap, px: number, py: number, c: Rgb, halfCss = 8) {
  const canvas = map.getCanvas();
  const gl = (canvas.getContext("webgl2") ?? canvas.getContext("webgl")) as WebGLRenderingContext;
  const dpr = canvas.width / canvas.clientWidth;
  const half = Math.round(halfCss * dpr);
  const cx = Math.round(px * dpr);
  const cy = Math.round(canvas.height - py * dpr);
  const size = 2 * half + 1;
  const buf = new Uint8Array(size * size * 4);
  gl.readPixels(cx - half, cy - half, size, size, gl.RGBA, gl.UNSIGNED_BYTE, buf);
  let sx = 0, sy = 0, n = 0;
  for (let row = 0; row < size; row++) {
    for (let col = 0; col < size; col++) {
      if (close(buf, (row * size + col) * 4, c)) {
        sx += col - half;
        sy += half - row; // GL rows go up; CSS y goes down
        n++;
      }
    }
  }
  if (!n) return null;
  return { dx: sx / n / dpr, dy: sy / n / dpr, count: n };
}

function hasColorNear(map: MlMap, px: number, py: number, c: Rgb, halfCss = 1.5) {
  return centroidNear(map, px, py, c, halfCss) !== null;
}

function setVisible(map: MlMap, ids: string[], on: boolean) {
  for (const id of ids) map.setLayoutProperty(id, "visibility", on ? "visible" : "none");
}

export function MarsSpike({ report }: { report: (id: TestId, s: Status, actual: string) => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const [zoom, setZoom] = useState(1);
  const [refusal, setRefusal] = useState<string | null>(null);

  useEffect(() => {
    let map: MlMap | undefined;
    let cancelled = false;

    (async () => {
      const ml = await registerMarsProjection();
      if (cancelled || !ref.current) return;
      const tm = fixture.tile_matrix;
      map = new ml.Map({
        container: ref.current,
        style: {
          version: 8,
          projection: { type: MARS_EQC.id },
          sources: {},
          layers: [{ id: "bg", type: "background", paint: { "background-color": "#ffffff" } }],
        },
        center: [0, 0],
        zoom: 1,
        maxZoom: 5,
        attributionControl: { compact: false, customAttribution: "Synthetic test tiles (ABAAD spike)" },
        canvasContextAttributes: { preserveDrawingBuffer: true, antialias: false },
      });
      (window as unknown as { __abaadMarsMap?: MlMap }).__abaadMarsMap = map;
      map.on("zoom", () => setZoom(map!.getZoom()));
      await new Promise<void>((r) => map!.once("load", () => r()));

      // --- T2: raster tiles in the declared tile matrix -----------------
      addSourceChecked(map, MARS_EQC.id, "mars-synthetic",
        { type: "raster", tiles: [new URL(tm.url, window.location.origin).href.replaceAll("%7B", "{").replaceAll("%7D", "}")],
          tileSize: tm.tileSize, minzoom: tm.minzoom, maxzoom: tm.maxzoom }, MARS_EQC.id);
      map.addLayer({ id: "mars-raster", type: "raster", source: "mars-synthetic", paint: { "raster-resampling": "nearest" } });

      // --- T3 overlays: WKT polygon + control points (geometry CRS 49900) --
      const poly = parseWkt(fixture.geometry.wkt);
      addSourceChecked(map, MARS_EQC.id, "test-polygon",
        { type: "geojson", data: { type: "Feature", properties: {}, geometry: poly } as never }, fixture.geometry.crs);
      addSourceChecked(map, MARS_EQC.id, "test-points", {
        type: "geojson",
        data: {
          type: "FeatureCollection",
          features: fixture.control_points.map((cp) => ({
            type: "Feature", properties: { id: cp.id }, geometry: { type: "Point", coordinates: [cp.lon, cp.lat] },
          })),
        } as never,
      }, fixture.geometry.crs);
      map.addLayer({ id: "overlay-polygon", type: "line", source: "test-polygon",
        paint: { "line-color": OVERLAY_HEX, "line-width": 2 } });
      map.addLayer({ id: "overlay-points", type: "circle", source: "test-points",
        paint: { "circle-radius": 7, "circle-color": "rgba(0,0,0,0)", "circle-stroke-color": OVERLAY_HEX, "circle-stroke-width": 2 } });
      await idle(map);

      const proj = map.getProjection()?.type;
      const bgProbe = map.project([15, 15]);
      const t2ok = proj === MARS_EQC.id && map.isSourceLoaded("mars-synthetic") &&
        hasColorNear(map, bgProbe.x, bgProbe.y, fixture.colors.background.slice(0, 3) as Rgb, 0.5);
      report("T2", t2ok ? "pass" : "fail",
        `projection=${proj}; tile matrix ${tm.id}, origin=(${tm.origin.map((v) => v.toFixed(1)).join(", ")}) m, ` +
        `extentAtZoom0=${tm.extentAtZoom0.toFixed(1)} m, ${tm.tileSize}-px tiles, zoom ${tm.minzoom}-${tm.maxzoom}; raster drawn: ${t2ok}`);

      // --- T3: alignment, measured in pixels -------------------------------
      let worstRaster = 0, worstOverlay = 0;
      const notes: string[] = [];
      let ok = true;
      for (const z of [1, 2, 3]) {
        for (const cp of fixture.control_points) {
          map.jumpTo({ center: [cp.lon, cp.lat], zoom: z });
          setVisible(map, ["overlay-polygon", "overlay-points"], false);
          await idle(map);
          const p = map.project([cp.lon, cp.lat]);
          const r = centroidNear(map, p.x, p.y, MARKER, 4);
          setVisible(map, ["overlay-polygon", "overlay-points"], true);
          setVisible(map, ["mars-raster"], false);
          await idle(map);
          const o = centroidNear(map, p.x, p.y, OVERLAY, 12);
          setVisible(map, ["mars-raster"], true);
          if (!r || !o) {
            ok = false;
            notes.push(`${cp.id}@z${z}: ${!r ? "raster marker" : "overlay circle"} not found`);
            continue;
          }
          // At integer zoom z with 512-px tiles, 1 CSS px = 1 source pixel of zoom-z tiles.
          worstRaster = Math.max(worstRaster, Math.hypot(r.dx, r.dy));
          worstOverlay = Math.max(worstOverlay, Math.hypot(o.dx, o.dy));
        }
      }
      // Polygon vertices: raster outline (yellow) and overlay line (cyan) at each projected vertex.
      map.jumpTo({ center: [45, 30], zoom: 3 });
      setVisible(map, ["overlay-polygon", "overlay-points"], false);
      await idle(map);
      const ring = (poly.type === "Polygon" ? poly.coordinates[0] : []).slice(0, 4);
      const rasterVerts = ring.map(([lon, lat]) => { const q = map!.project([lon, lat]); return hasColorNear(map!, q.x, q.y, POLYGON, 1.5); });
      setVisible(map, ["overlay-polygon"], true);
      setVisible(map, ["mars-raster"], false);
      await idle(map);
      const overlayVerts = ring.map(([lon, lat]) => { const q = map!.project([lon, lat]); return hasColorNear(map!, q.x, q.y, OVERLAY, 1.5); });
      setVisible(map, ["mars-raster", "overlay-points"], true);
      const tol = fixture.alignment_tolerance_source_px;
      ok = ok && worstRaster <= tol && worstOverlay <= tol && rasterVerts.every(Boolean) && overlayVerts.every(Boolean);
      report("T3", ok ? "pass" : "fail",
        `max offset raster marker vs projected CP: ${worstRaster.toFixed(2)} px; overlay (worker path) vs projected: ` +
        `${worstOverlay.toFixed(2)} px (tolerance ${tol} source px, zooms 1-3); polygon vertices on raster outline: ` +
        `${rasterVerts.filter(Boolean).length}/4, on overlay line: ${overlayVerts.filter(Boolean).length}/4` +
        (notes.length ? `; ${notes.join("; ")}` : ""));

      // --- T4: CRS mismatch must be refused ---------------------------------
      try {
        addSourceChecked(map, MARS_EQC.id, "openfreemap-earth",
          { type: "vector", url: "https://tiles.openfreemap.org/planet" }, "EPSG:3857");
        report("T4", "fail", "Web Mercator source was accepted on the Mars map");
      } catch (e) {
        const refused = e instanceof CrsMismatchError && !map.getSource("openfreemap-earth");
        setRefusal(e instanceof Error ? e.message : String(e));
        report("T4", refused ? "pass" : "fail", `${refused ? "Refused" : "Unexpected error"}: ${e instanceof Error ? e.message : e}`);
      }

      // --- T6: scale from the Mars radius -------------------------------------
      map.jumpTo({ center: [0, 0], zoom: 3 });
      await idle(map);
      const a = map.project([0, 0]);
      const b = map.project([0, 1]);
      const measured = (MARS_EQC.radiusM * Math.PI / 180) / Math.hypot(b.x - a.x, b.y - a.y);
      const computed = metresPerPixel(MARS_EQC, 3);
      const rel = Math.abs(measured - computed) / computed;
      const earthScale = ref.current?.querySelector(".maplibregl-ctrl-scale") !== null;
      report("T6", rel < 0.005 && !earthScale ? "pass" : "fail",
        `metres/px at zoom 3: computed from Mars radius ${computed.toFixed(1)}, measured ${measured.toFixed(1)} ` +
        `(${(rel * 100).toFixed(3)}% difference); MapLibre Earth scale control present: ${earthScale}`);
      map.jumpTo({ center: [45, 30], zoom: 2 });
    })().catch((e) => {
      for (const id of ["T2", "T3", "T4", "T6"] as TestId[]) report(id, "fail", `Exception: ${e}`);
    });

    return () => {
      cancelled = true;
      map?.remove();
    };
  }, [report]);

  // Scale bar from the Mars radius (equirectangular: true scale along meridians and the equator).
  const mpp = metresPerPixel(MARS_EQC, zoom);
  const barM = niceLength(mpp * 120);
  return (
    <figure className="space-y-2">
      <div className="relative">
        <div ref={ref} data-testid="mars-map" className="h-80 w-full rounded border-2 border-olive" />
        <div className="pointer-events-none absolute bottom-2 left-2 rounded bg-ivory/90 px-2 py-1 text-xs" data-testid="mars-scale">
          <div style={{ width: `${barM / mpp}px` }} className="h-1.5 border-x-2 border-b-2 border-earth" />
          {formatDistance(barM)} · Mars radius {MARS_EQC.radiusM.toLocaleString("en")} m
        </div>
      </div>
      {refusal && (
        <p role="alert" data-testid="crs-refusal" className="rounded border-2 border-terracotta bg-ivory p-2 text-xs">
          T4 refusal: {refusal}
        </p>
      )}
      <figcaption className="text-xs">
        Mars, {MARS_EQC.id} ({MARS_EQC.name}); tile matrix {fixture.tile_matrix.id}. <strong>All tiles, the yellow
        rectangle, the magenta control points and the cyan overlay are synthetic test fixtures</strong>, not Mars data.
      </figcaption>
    </figure>
  );
}
