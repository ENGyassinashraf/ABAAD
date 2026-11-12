// Copies MapLibre's web-worker bundle into public/ so the browser can load it.
// MapLibre 6 ships the worker as a separate module; bundlers do not serve it.
// Runs automatically before `dev`, `build` and after `pnpm install`.
import { copyFileSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";

const require = createRequire(import.meta.url);
const pkgDir = path.dirname(require.resolve("maplibre-gl/package.json"));
const outDir = path.join(path.dirname(new URL(import.meta.url).pathname), "..", "public", "maplibre");
mkdirSync(outDir, { recursive: true });
copyFileSync(path.join(pkgDir, "dist", "maplibre-gl-worker.mjs"), path.join(outDir, "maplibre-gl-worker.mjs"));
console.log("Copied maplibre-gl-worker.mjs to public/maplibre/");
