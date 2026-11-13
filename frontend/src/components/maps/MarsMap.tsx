"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import "maplibre-gl/dist/maplibre-gl.css";
import type { ExpressionSpecification, GeoJSONSource, Map as MlMap, Marker } from "maplibre-gl";
import type { Region } from "@/lib/api";
import { formatCoord } from "@/lib/api";
import { MARS_EQC, metresPerPixel } from "@/lib/crs";
import { formatDistance, niceLength } from "@/lib/lunar";
import { registerMarsProjection } from "@/lib/marsProjection";
import { boundsOf, marsCamera, marsFullZoom, precisionOf } from "@/lib/mapView";
import { messages as t } from "@/i18n/en";
import { PrecisionBadge } from "./PrecisionBadge";

/** Regional context around a point: ~60° of longitude across a typical panel. */
const POINT_ZOOM = 2.3;
/** Full-planet view leaves ~8 % margin so labels near ±180° are not clipped. */
const FULL_MARGIN = 0.92;

// Map paint colours mirror the theme tokens (MapLibre paint cannot read CSS variables).
const C = {
  bg: "#1f1a15",
  planet: "#2f2620",
  graticule: "rgba(243,235,221,0.10)",
  equator: "rgba(243,235,221,0.22)",
  olive: "#84916c",
  ochre: "#d2ae70",
};

type MapState = "loading" | "ready" | "error";

/** Graticule labels as inert HTML markers (the style has no glyph source, so no network fonts are needed). */
function gridLabel(ml: typeof import("maplibre-gl"), map: MlMap, lngLat: [number, number], text: string) {
  const el = document.createElement("span");
  el.className = "abaad-grid-label";
  el.setAttribute("aria-hidden", "true");
  el.textContent = text;
  new ml.Marker({ element: el, anchor: "top-left", offset: [3, 2] }).setLngLat(lngLat).addTo(map);
}

function graticule() {
  const features = [];
  for (let lon = -180; lon <= 180; lon += 30) {
    features.push({ type: "Feature" as const, properties: { major: lon === 0 ? 1 : 0 },
      geometry: { type: "LineString" as const, coordinates: [[lon, -90], [lon, 90]] } });
  }
  for (let lat = -60; lat <= 60; lat += 30) {
    features.push({ type: "Feature" as const, properties: { major: lat === 0 ? 1 : 0 },
      geometry: { type: "LineString" as const, coordinates: [[-180, lat], [180, lat]] } });
  }
  return { type: "FeatureCollection" as const, features };
}

/**
 * Mars reference regions on the approved IAU_2015:49910 equirectangular
 * projection (the same registration as the Phase 1 spike). There is no
 * validated Mars surface imagery in ABAAD yet, so the basemap is a labelled
 * neutral vector context (graticule only). Stored geometry is drawn as stored:
 * points stay points, the approximate Arabia Terra outline is dashed, and
 * regions without geometry are listed, never placed.
 */
export function MarsMap({ regions, selected, onSelect }: { regions: Region[]; selected: string | null; onSelect: (code: string) => void }) {
  const box = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MlMap | null>(null);
  const markers = useRef<Map<string, { marker: Marker; el: HTMLButtonElement }>>(new Map());
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;
  const [state, setState] = useState<MapState>("loading");
  const [error, setError] = useState<string | null>(null);
  const [zoom, setZoom] = useState(0);
  const [cursor, setCursor] = useState<[number, number] | null>(null);
  const [attempt, setAttempt] = useState(0);

  const outlines = useMemo(() => ({
    type: "FeatureCollection" as const,
    features: regions.filter((r) => r.outline).map((r) => ({
      type: "Feature" as const,
      properties: { code: r.code, approx: r.outline!.geometry_status === "approximate" ? 1 : 0 },
      geometry: { type: "Polygon" as const, coordinates: r.outline!.rings },
    })),
  }), [regions]);

  // Create the map once per attempt.
  useEffect(() => {
    let map: MlMap | undefined;
    let cancelled = false;
    const markerStore = markers.current;
    setState("loading");
    (async () => {
      const ml = await registerMarsProjection();
      if (cancelled || !box.current) return;
      const { clientWidth: w, clientHeight: h } = box.current;
      map = new ml.Map({
        container: box.current,
        style: {
          version: 8,
          projection: { type: MARS_EQC.id },
          sources: {},
          layers: [{ id: "bg", type: "background", paint: { "background-color": C.bg } }],
        },
        center: [0, 0],
        zoom: marsFullZoom(w, h, FULL_MARGIN),
        minZoom: 0,
        maxZoom: 6,
        renderWorldCopies: false,
        cooperativeGestures: true, // page scroll never zooms the map by surprise
        attributionControl: false, // attribution is printed in the caption so it never covers controls
      });
      map.addControl(new ml.NavigationControl({ showCompass: false }), "top-right");
      map.on("error", (e) => {
        if (!map?.loaded()) { setError(String(e.error?.message ?? e.error ?? "map error")); setState("error"); }
      });
      map.on("zoom", () => setZoom(map!.getZoom()));
      map.on("mousemove", (e) => setCursor([e.lngLat.lng, e.lngLat.lat]));
      map.on("mouseout", () => setCursor(null));
      map.on("load", () => {
        if (!map || cancelled) return;
        // The planet's own extent (±180°, ±90°) so the off-planet canvas reads as "outside".
        map.addSource("planet", { type: "geojson", data: { type: "Feature", properties: {},
          geometry: { type: "Polygon", coordinates: [[[-180, -90], [180, -90], [180, 90], [-180, 90], [-180, -90]]] } } as never });
        map.addLayer({ id: "planet", type: "fill", source: "planet", paint: { "fill-color": C.planet } });
        map.addSource("graticule", { type: "geojson", data: graticule() as never });
        map.addLayer({ id: "graticule", type: "line", source: "graticule",
          paint: { "line-color": ["case", ["==", ["get", "major"], 1], C.equator, C.graticule], "line-width": 1 } });
        map.addSource("outlines", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
        map.addLayer({ id: "outline-fill", type: "fill", source: "outlines",
          paint: { "fill-color": C.olive, "fill-opacity": 0.08 } });
        map.addLayer({ id: "outline-line", type: "line", source: "outlines",
          paint: { "line-color": C.olive, "line-width": 1.5, "line-dasharray": [3, 2] } });
        map.on("click", "outline-fill", (e) => {
          const code = e.features?.[0]?.properties?.code;
          if (code) onSelectRef.current(String(code));
        });
        map.on("mouseenter", "outline-fill", () => (map!.getCanvas().style.cursor = "pointer"));
        map.on("mouseleave", "outline-fill", () => (map!.getCanvas().style.cursor = ""));
        for (const lon of [-150, -120, -90, -60, -30, 0, 30, 60, 90, 120, 150]) {
          gridLabel(ml, map, [lon, 0], lon === 0 ? "0°" : lon > 0 ? `${lon}°E` : `${360 + lon}°E`);
        }
        for (const lat of [-60, -30, 30, 60]) gridLabel(ml, map, [0, lat], lat > 0 ? `${lat}°N` : `${-lat}°S`);
        mapRef.current = map;
        (window as unknown as { __abaadMarsProductMap?: MlMap }).__abaadMarsProductMap = map;
        setZoom(map.getZoom());
        setState("ready");
      });
    })().catch((e) => { if (!cancelled) { setError(String(e)); setState("error"); } });
    return () => {
      cancelled = true;
      for (const { marker } of markerStore.values()) marker.remove();
      markerStore.clear();
      map?.remove();
      mapRef.current = null;
    };
  }, [attempt]);

  // Data: outlines + one accessible HTML marker per stored point.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || state !== "ready") return;
    (map.getSource("outlines") as GeoJSONSource | undefined)?.setData(outlines as never);
    let cancelled = false;
    (async () => {
      const ml = await registerMarsProjection();
      if (cancelled) return;
      for (const { marker } of markers.current.values()) marker.remove();
      markers.current.clear();
      for (const r of regions) {
        if (!r.geometry) continue;
        const el = document.createElement("button");
        el.type = "button";
        el.className = "abaad-marker";
        el.dataset.testid = `mars-marker-${r.code}`;
        el.dataset.precision = precisionOf(r);
        el.setAttribute("aria-label", `${r.name}, ${formatCoord(r.geometry)}, ${t.precision[precisionOf(r)]}`);
        const dot = document.createElement("span");
        dot.className = "abaad-marker__dot";
        dot.setAttribute("aria-hidden", "true");
        const label = document.createElement("span");
        label.className = "abaad-marker__label";
        label.textContent = r.name;
        el.append(dot, label);
        el.addEventListener("click", (ev) => { ev.stopPropagation(); onSelectRef.current(r.code); });
        const marker = new ml.Marker({ element: el, anchor: "center" }).setLngLat([r.geometry.lon, r.geometry.lat]).addTo(map);
        markers.current.set(r.code, { marker, el });
      }
      applySelection();
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [outlines, regions, state]);

  const applySelection = useCallback(() => {
    const map = mapRef.current;
    if (!map) return;
    for (const [code, { el }] of markers.current) {
      el.dataset.selected = String(code === selected);
      el.setAttribute("aria-pressed", String(code === selected));
    }
    if (map.getLayer("outline-line")) {
      const isSel: ExpressionSpecification = ["==", ["get", "code"], selected ?? ""];
      map.setPaintProperty("outline-line", "line-color", ["case", isSel, C.ochre, C.olive]);
      map.setPaintProperty("outline-line", "line-width", ["case", isSel, 2.5, 1.5]);
      map.setPaintProperty("outline-fill", "fill-color", ["case", isSel, C.ochre, C.olive]);
      map.setPaintProperty("outline-fill", "fill-opacity", ["case", isSel, 0.16, 0.06]);
    }
  }, [selected]);

  const frameSelected = useCallback(() => {
    const map = mapRef.current;
    const r = regions.find((x) => x.code === selected);
    const b = r ? boundsOf(r) : null;
    if (!map || !b || !box.current) return;
    map.easeTo({ ...marsCamera(b, box.current.clientWidth, box.current.clientHeight, { pointZoom: POINT_ZOOM }), duration: 600 });
  }, [regions, selected]);

  const resetView = useCallback(() => {
    const map = mapRef.current;
    if (!map || !box.current) return;
    map.easeTo({ center: [0, 0], zoom: marsFullZoom(box.current.clientWidth, box.current.clientHeight, FULL_MARGIN), duration: 600 });
  }, []);

  // Selection follows the list/URL; fit to the selected geometry when there is one.
  useEffect(() => {
    if (state !== "ready") return;
    applySelection();
    const r = regions.find((x) => x.code === selected);
    if (r && boundsOf(r)) frameSelected();
    else resetView();
  }, [selected, state, applySelection, frameSelected, resetView, regions]);

  const sel = regions.find((r) => r.code === selected) ?? null;
  const parent = sel?.parent_code ? regions.find((r) => r.code === sel.parent_code) ?? null : null;
  const mpp = metresPerPixel(MARS_EQC, zoom);
  const barM = niceLength(mpp * 110);

  return (
    <figure className="space-y-2" aria-labelledby="mars-map-caption">
      <div className="relative overflow-hidden rounded-xl border border-line-strong bg-map-mars">
        <div ref={box} data-testid="mars-map" data-state={state} data-selected={selected ?? ""}
          role="region" aria-label={t.maps.marsAria} className="h-[22rem] w-full sm:h-[26rem]" />


        {state === "loading" && (
          <p className="absolute inset-0 flex items-center justify-center text-sm text-fg-2" role="status">{t.maps.loading}</p>
        )}
        {state === "error" && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-bg/90 p-6 text-center text-sm" role="alert" data-testid="mars-map-error">
            <p>{t.maps.marsError}</p>
            {error && <p className="font-mono text-xs text-muted">{error}</p>}
            <button type="button" onClick={() => setAttempt((a) => a + 1)} className="rounded-md border border-ochre px-3 py-1.5 font-semibold text-ochre hover:bg-hover">{t.maps.retry}</button>
          </div>
        )}

        {state === "ready" && (
          <>
            <div className="absolute bottom-2 left-2 flex flex-wrap items-center gap-2">
              <button type="button" onClick={resetView} data-testid="mars-reset"
                className="rounded-md border border-line-strong bg-bg/85 px-2.5 py-1 text-xs font-semibold hover:bg-hover">{t.maps.reset}</button>
              {sel && boundsOf(sel) && (
                <button type="button" onClick={frameSelected} data-testid="mars-focus"
                  className="rounded-md border border-ochre/70 bg-bg/85 px-2.5 py-1 text-xs font-semibold text-ochre hover:bg-hover">{t.maps.focus}</button>
              )}
            </div>
            <div className="pointer-events-none absolute bottom-2 right-2 rounded-md bg-bg/85 px-2 py-1 text-right text-[11px] text-fg-2" data-testid="mars-scale">
              <div style={{ width: `${barM / mpp}px` }} className="ml-auto h-1.5 border-x-2 border-b-2 border-fg-2" />
              {formatDistance(barM)} {t.maps.scaleNote}
              <span className="block tabular-nums" data-testid="mars-cursor">
                {cursor ? `${Math.abs(cursor[1]).toFixed(2)}° ${cursor[1] >= 0 ? "N" : "S"}, ${cursor[0].toFixed(2)}° E` : t.maps.cursorHint}
              </span>
            </div>
          </>
        )}
      </div>
        {sel && precisionOf(sel) === "none" && (
          <div className="rounded-lg border border-warn/60 bg-surface p-3 text-xs" data-testid="mars-no-geometry" role="status">
            <span className="font-semibold text-warn">{sel.name}: {t.maps.noGeometry}.</span>{" "}
            {parent ? t.maps.parentContext(parent.name) : ""} {sel.geometry_gap}
          </div>
        )}

      <p className="text-[11px] leading-snug text-muted" data-testid="mars-basemap-note">{t.maps.marsNoImagery}</p>
      <figcaption id="mars-map-caption" className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-fg-2">
        <span className="inline-flex items-center gap-1.5"><span className="inline-block h-3 w-3 rounded-full border-2 border-ochre bg-ochre" />{t.maps.legendSelected}</span>
        <span className="inline-flex items-center gap-1.5"><span className="inline-block h-3 w-3 rounded-full border-2 border-olive bg-olive/60" />{t.maps.legendPoint}</span>
        <span className="inline-flex items-center gap-1.5"><span className="inline-block h-3 w-5 border-2 border-dashed border-olive" />{t.maps.legendApproxOutline}</span>
        <span className="text-muted">{MARS_EQC.id} · {t.maps.marsCrsNote}</span>
        <span className="text-muted" data-testid="mars-attribution">{t.maps.marsAttribution}</span>
        {sel && <PrecisionBadge precision={precisionOf(sel)} />}
      </figcaption>
    </figure>
  );
}
