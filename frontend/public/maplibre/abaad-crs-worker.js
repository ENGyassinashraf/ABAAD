/*
 * MapLibre worker-side projection handler (map feasibility spike, Phase 1).
 * GeoJSON sources are tiled inside web workers, where the main-thread
 * converter cannot be passed, so the workers rebuild it from the CRS
 * `definition` string. Only the definitions below are accepted; any other
 * string throws so that a wrong CRS can never be used silently.
 */
/* global self */
(function () {
  var DEFINITIONS = {
    // IAU_2015:49910 Mars (2015) Sphere / Ocentric / Equirectangular, clon = 0
    "+proj=eqc +lat_ts=0 +lat_0=0 +lon_0=0 +x_0=0 +y_0=0 +R=3396190 +units=m": 3396190,
  };
  self.setProjectionHandler(function (definition) {
    var R = DEFINITIONS[definition];
    if (!R) throw new Error("ABAAD: unknown CRS definition in worker: " + definition);
    var k = Math.PI / 180;
    return {
      forward: function (p) { return [R * p[0] * k, R * p[1] * k]; },
      inverse: function (p) { return [p[0] / (R * k), p[1] / (R * k)]; },
    };
  });
})();
