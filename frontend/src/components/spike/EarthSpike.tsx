"use client";

import { useEffect, useRef } from "react";
import type { Map as MlMap } from "maplibre-gl";
import { loadMapLibre } from "@/lib/maplibre";
import { assertCompatibleCrs, EARTH_CRS84, EARTH_WEB_MERCATOR } from "@/lib/crs";
import type { Status, TestId } from "./useResults";

export const OPENFREEMAP_STYLE = "https://tiles.openfreemap.org/styles/liberty";

// SYNTHETIC TEST OUTLINE at "Null Island" (0°, 0°) — a conventional test
// location in the open ocean, deliberately NOT an ABAAD study area.
const TEST_OUTLINE = {
  type: "FeatureCollection",
  features: [
    {
      type: "Feature",
      properties: { label: "SYNTHETIC TEST OUTLINE — not a study area" },
      geometry: { type: "Polygon", coordinates: [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]] },
    },
  ],
} as const;

export function EarthSpike({ report }: { report: (id: TestId, s: Status, actual: string) => void }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let map: MlMap | undefined;
    let done = false;
    const finish = (s: Status, msg: string) => {
      if (!done) {
        done = true;
        report("T1", s, msg);
      }
    };
    const timer = setTimeout(() => finish("fail", "Timed out after 20 s: style or tiles could not be loaded (network?)"), 20000);

    (async () => {
      const ml = await loadMapLibre();
      if (!ref.current) return;
      map = new ml.Map({
        container: ref.current,
        style: OPENFREEMAP_STYLE,
        center: [0.5, 0.5],
        zoom: 6,
        attributionControl: { compact: false },
      });
      map.addControl(new ml.ScaleControl({ unit: "metric" }), "bottom-left"); // Earth radius: correct here
      (window as unknown as { __abaadEarthMap?: MlMap }).__abaadEarthMap = map;
      map.on("error", (e) => {
        if (!map?.isStyleLoaded()) finish("fail", `Map error before style load: ${e.error?.message ?? "unknown"}`);
      });
      map.on("load", () => {
        if (!map) return;
        assertCompatibleCrs(EARTH_WEB_MERCATOR, EARTH_CRS84, "synthetic-test-outline");
        map.addSource("synthetic-test-outline", { type: "geojson", data: TEST_OUTLINE as never });
        map.addLayer({ id: "test-outline-fill", type: "fill", source: "synthetic-test-outline",
          paint: { "fill-color": "#a95e40", "fill-opacity": 0.15 } });
        map.addLayer({ id: "test-outline-line", type: "line", source: "synthetic-test-outline",
          paint: { "line-color": "#a95e40", "line-width": 3 } });
        map.once("idle", () => {
          const attrib = ref.current?.querySelector(".maplibregl-ctrl-attrib")?.textContent ?? "";
          const drawn = map!.queryRenderedFeatures({ layers: ["test-outline-line"] }).length > 0;
          const osm = attrib.includes("OpenStreetMap");
          clearTimeout(timer);
          finish(drawn && osm ? "pass" : "fail",
            `style loaded; outline rendered: ${drawn}; attribution: "${attrib.trim().slice(0, 120)}"`);
        });
      });
    })().catch((e) => finish("fail", `Exception: ${e}`));

    return () => {
      clearTimeout(timer);
      map?.remove();
    };
  }, [report]);

  return (
    <figure className="space-y-2">
      <div ref={ref} data-testid="earth-map" className="h-72 w-full rounded border-2 border-olive" />
      <figcaption className="text-xs">
        Earth, Web Mercator (EPSG:3857), OpenFreeMap &ldquo;liberty&rdquo; style. The terracotta square at 0°–1° E,
        0°–1° N is a <strong>synthetic test outline</strong> in RFC 7946 / WGS 84, not a study area.
      </figcaption>
    </figure>
  );
}
