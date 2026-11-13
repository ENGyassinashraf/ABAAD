// Copies MapLibre's web-worker bundle into public/ so the browser can load it.
// MapLibre 6 ships the worker as a separate module; bundlers do not serve it.
// Runs automatically before `dev`, `build` and after `pnpm install`.
import { copyFileSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

// `new URL(import.meta.url).pathname` does NOT url-decode (e.g. a space
// becomes a literal "%20"), so any project path containing a space or other
// reserved character silently wrote this file to a bogus, never-served
// directory. fileURLToPath decodes correctly.
const require = createRequire(import.meta.url);
const pkgDir = path.dirname(require.resolve("maplibre-gl/package.json"));
const outDir = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "public", "maplibre");
mkdirSync(outDir, { recursive: true });
copyFileSync(path.join(pkgDir, "dist", "maplibre-gl-worker.mjs"), path.join(outDir, "maplibre-gl-worker.mjs"));
console.log("Copied maplibre-gl-worker.mjs to public/maplibre/");
