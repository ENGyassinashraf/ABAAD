"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import "maplibre-gl/dist/maplibre-gl.css";
import type { GeoJSONSource, Map as MlMap, Marker, StyleSpecification } from "maplibre-gl";
import type { Candidate } from "@/lib/api";
import { loadMapLibre } from "@/lib/maplibre";
import { messages as t } from "@/i18n/en";

/**
 * Basemaps from NASA GIBS (the imagery service behind NASA Worldview), one of the
 * open-data resources of the Space Apps 2026 analog challenge. Raster tiles only,
 * so the map needs no vector-tile or font host.
 */
const GIBS = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best";
const recentDate = () => new Date(Date.now() - 3 * 86_400_000).toISOString().slice(0, 10);
export const BASEMAPS = {
  bluemarble: { label: "NASA Blue Marble (shaded relief)", url: () => `${GIBS}/BlueMarble_ShadedRelief_Bathymetry/default/default/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpg`, maxzoom: 8 },
  modis: { label: "MODIS Terra true colour", url: () => `${GIBS}/MODIS_Terra_CorrectedReflectance_TrueColor/default/${recentDate()}/GoogleMapsCompatible_Level9/{z}/{y}/{x}.jpg`, maxzoom: 9 },
} as const;
type BasemapKey = keyof typeof BASEMAPS;

function gibsStyle(key: BasemapKey): StyleSpecification {
  const b = BASEMAPS[key];
  return {
    version: 8,
    sources: {
      gibs: { type: "raster", tiles: [b.url()], tileSize: 256, maxzoom: b.maxzoom,
        attribution: "Imagery: NASA GIBS / Worldview" + (key === "modis" ? ` · ${recentDate()}` : "") },
    },
    layers: [{ id: "background", type: "background", paint: { "background-color": "#161611" } }, { id: "gibs", type: "raster", source: "gibs" }],
  };
}

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
  const [basemap, setBasemap] = useState<BasemapKey>("bluemarble");
  const labels = useRef<Marker[]>([]);

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
      map = new ml.Map({ container: ref.current, style: gibsStyle("bluemarble"), center: [10, 15], zoom: 1.6, attributionControl: { compact: true } });
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
    // Labels as HTML markers (no font server needed)
    labels.current.forEach((m) => m.remove());
    void loadMapLibre().then((ml) => {
      labels.current = features.features.map((f) => {
        const el = document.createElement("div");
        el.textContent = f.properties.label;
        el.className = "pointer-events-none mt-5 whitespace-nowrap rounded bg-bg/80 px-1.5 py-0.5 text-[11px] font-semibold text-fg shadow";
        return new ml.Marker({ element: el, anchor: "top" }).setLngLat(f.geometry.coordinates as [number, number]).addTo(map);
      });
    });
    const pts = features.features.map((f) => f.geometry.coordinates);
    if (pts.length === 1) map.easeTo({ center: pts[0] as [number, number], zoom: 4 });
    else if (pts.length > 1) {
      const lons = pts.map((p) => p[0]);
      const lats = pts.map((p) => p[1]);
      map.fitBounds([[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]], { padding: 60, maxZoom: 5, duration: 600 });
    }
  }, [features, state]);

  // Switch the NASA GIBS basemap without rebuilding the map.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || state !== "ready") return;
    const src = map.getSource("gibs") as unknown as { setTiles?: (t: string[]) => void } | undefined;
    src?.setTiles?.([BASEMAPS[basemap].url()]);
  }, [basemap, state]);

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
      <div className="flex flex-wrap items-center gap-2 text-xs text-fg-2">
        <label htmlFor="basemap">Basemap</label>
        <select id="basemap" data-testid="basemap" value={basemap} onChange={(e) => setBasemap(e.target.value as BasemapKey)}
          className="rounded border border-line-strong bg-bg-deep px-1.5 py-0.5 text-fg">
          {(Object.keys(BASEMAPS) as BasemapKey[]).map((k) => <option key={k} value={k}>{BASEMAPS[k].label}</option>)}
        </select>
        <span className="text-muted">NASA GIBS (Worldview) · context imagery, not analysis data</span>
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
