/** Loads MapLibre in the browser with its worker served from /public/maplibre/. */
export async function loadMapLibre() {
  const ml = await import("maplibre-gl");
  const workerUrl = new URL("/maplibre/maplibre-gl-worker.mjs", window.location.origin).href;
  if (ml.getWorkerUrl() !== workerUrl) ml.setWorkerUrl(workerUrl);
  return ml;
}
