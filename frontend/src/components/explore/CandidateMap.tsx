"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import "maplibre-gl/dist/maplibre-gl.css";
import type { GeoJSONSource, Map as MlMap } from "maplibre-gl";
import type { Candidate } from "@/lib/api";
import { loadMapLibre } from "@/lib/maplibre";
import { messages as t } from "@/i18n/en";

const STYLE = "https://tiles.openfreemap.org/styles/liberty";

type Props = { candidates: Candidate[]; highlighted: string | null; onSelect: (code: string) => void };

/**
 * Earth candidates with a stored point. Source-traced points are solid;
 * approximate gazetteer context points are hollow and labelled as such.
 * Candidates with no verified location are simply absent (never guessed).
 */
export function CandidateMap({ candidates, highlighted, onSelect }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MlMap | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "offline">("loading");

  const features = useMemo(
    () => ({
      type: "FeatureCollection" as const,
      features: candidates
        .filter((c) => c.region.geometry && c.region.body === "earth")
        .map((c) => ({
          type: "Feature" as const,
          properties: {
            code: c.region.code,
            name: c.region.name,
            approx: c.region.geometry!.geometry_status === "approximate" ? 1 : 0,
            ranked: c.status === "ranked" ? 1 : 0,
            label: c.rank ? `#${c.rank} ${c.region.name}` : c.region.name,
          },
          geometry: { type: "Point" as const, coordinates: [c.region.geometry!.lon, c.region.geometry!.lat] },
        })),
    }),
    [candidates],
  );

  // Create the map once.
  useEffect(() => {
    let map: MlMap | undefined;
    let cancelled = false;
    const timer = setTimeout(() => !cancelled && mapRef.current === null && setState("offline"), 20000);
    (async () => {
      const ml = await loadMapLibre();
      if (!ref.current || cancelled) return;
      map = new ml.Map({ container: ref.current, style: STYLE, center: [10, 15], zoom: 1.6, attributionControl: { compact: true } });
      map.addControl(new ml.NavigationControl({ showCompass: false }), "top-right");
      map.on("error", () => {
        if (!map?.isStyleLoaded()) setState("offline");
      });
      map.on("load", () => {
        if (!map || cancelled) return;
        clearTimeout(timer);
        map.addSource("candidates", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
        map.addLayer({
          id: "cand-circle", type: "circle", source: "candidates",
          paint: {
            "circle-radius": ["case", ["==", ["get", "ranked"], 1], 9, 7],
            "circle-color": ["case", ["==", ["get", "approx"], 1], "rgba(0,0,0,0)", ["==", ["get", "ranked"], 1], "#5e6c4b", "#be985e"],
            "circle-stroke-color": ["case", ["==", ["get", "ranked"], 1], "#5e6c4b", "#a95e40"],
            "circle-stroke-width": 3,
          },
        });
        map.addLayer({
          id: "cand-label", type: "symbol", source: "candidates",
          layout: { "text-field": ["get", "label"], "text-size": 12, "text-offset": [0, 1.4], "text-anchor": "top", "text-font": ["Noto Sans Regular"] },
          paint: { "text-color": "#3d352d", "text-halo-color": "#fcf9f2", "text-halo-width": 1.5 },
        });
        map.on("click", "cand-circle", (e) => {
          const code = e.features?.[0]?.properties?.code;
          if (code) onSelect(String(code));
        });
        map.on("mouseenter", "cand-circle", () => (map!.getCanvas().style.cursor = "pointer"));
        map.on("mouseleave", "cand-circle", () => (map!.getCanvas().style.cursor = ""));
        mapRef.current = map;
        (window as unknown as { __abaadCandidateMap?: MlMap }).__abaadCandidateMap = map;
        setState("ready");
      });
    })().catch(() => setState("offline"));
    return () => {
      cancelled = true;
      clearTimeout(timer);
      map?.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Update data and frame the points whenever the candidate set changes.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || state !== "ready") return;
    (map.getSource("candidates") as GeoJSONSource | undefined)?.setData(features);
    const pts = features.features.map((f) => f.geometry.coordinates);
    if (pts.length === 1) map.easeTo({ center: pts[0] as [number, number], zoom: 4 });
    else if (pts.length > 1) {
      const lons = pts.map((p) => p[0]);
      const lats = pts.map((p) => p[1]);
      map.fitBounds([[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]], { padding: 60, maxZoom: 5, duration: 600 });
    }
  }, [features, state]);

  // Highlight follows hover/selection in the list.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || state !== "ready" || !map.getLayer("cand-circle")) return;
    map.setPaintProperty("cand-circle", "circle-stroke-width", ["case", ["==", ["get", "code"], highlighted ?? ""], 5, 3]);
  }, [highlighted, state]);

  return (
    <figure className="space-y-2">
      <div className="relative">
        <div ref={ref} data-testid="candidate-map" data-state={state} data-points={features.features.length}
          className="h-80 w-full overflow-hidden rounded-xl border border-line-strong bg-surface" />
        {state === "offline" && (
          <p role="status" data-testid="candidate-map-offline" className="absolute inset-0 flex items-center justify-center rounded-xl bg-bg/85 p-6 text-center text-sm text-fg-2">{t.explore.mapOffline}</p>
        )}
      </div>
      <figcaption className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-fg-2">
        <span className="inline-flex items-center gap-1.5"><span className="inline-block h-3 w-3 rounded-full border-[3px] border-olive-deep bg-olive-deep" />{t.explore.mapLegendTraced}, ranked</span>
        <span className="inline-flex items-center gap-1.5"><span className="inline-block h-3 w-3 rounded-full border-[3px] border-terracotta bg-ochre" />{t.explore.mapLegendTraced}, insufficient evidence</span>
        <span className="inline-flex items-center gap-1.5"><span className="inline-block h-3 w-3 rounded-full border-[3px] border-terracotta" />{t.explore.mapLegendApprox}</span>
        {features.features.length === 0 && <span>{t.explore.mapNoPoints}</span>}
      </figcaption>
    </figure>
  );
}
