import { loadMapLibre } from "@/lib/maplibre";
import { MARS_EQC } from "@/lib/crs";

let registered = false;

/**
 * Registers the approved Mars CRS (IAU_2015:49910, tile matrix
 * ABAAD-MarsEqcQuad) with MapLibre once per page and loads the worker-side
 * converter. Shared by the Phase 1 spike and the product Mars map so both use
 * exactly the same projection contract.
 */
export async function registerMarsProjection() {
  const ml = await loadMapLibre();
  if (!registered) {
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
    registered = true;
  }
  return ml;
}
