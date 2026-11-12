# data/

Large scientific files live here and are **never committed** (see `.gitignore`).
Phase 1 contains no data files.

| Folder | Purpose |
| --- | --- |
| `raw/` | Files exactly as downloaded from the official source |
| `clipped/` | Study-area clips (Cloud Optimized GeoTIFF) |
| `derived/` | Products computed by the offline pipeline |
| `tiles/` | Pre-rendered map tiles |

Every file must be listed in `manifest.json` (path, SHA-256, size, source URL,
licence, date). `make verify-data` checks the files against the manifest.
