import { defineConfig, devices } from "@playwright/test";

// End-to-end tests run against their own servers on ports 3100 (Next.js
// production build) and 8100 (FastAPI with a fresh temporary database), so
// they never touch `make dev` (3000/8000) or the developer database.
// Browser: the installed Google Chrome (channel "chrome"), as on the target Mac.
export default defineConfig({
  testDir: "./e2e",
  timeout: 120_000,
  expect: { timeout: 30_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: "http://localhost:3100",
    ...devices["Desktop Chrome"],
    channel: "chrome",
    // Software WebGL for the Mission Lab 3D viewer in headless Chrome (the
    // tests do not depend on it: the viewer reports "unavailable" if absent).
    launchOptions: { args: ["--enable-unsafe-swiftshader"] },
    viewport: { width: 1280, height: 900 },
    deviceScaleFactor: 1,
    screenshot: "only-on-failure",
  },
  webServer: [
    {
      command: "bash ../scripts/e2e-backend.sh",
      url: "http://127.0.0.1:8100/api/v1/health",
      timeout: 120_000,
      reuseExistingServer: false,
    },
    {
      command: "pnpm run build && pnpm exec next start --port 3100 --hostname localhost",
      url: "http://localhost:3100/",
      timeout: 300_000,
      reuseExistingServer: false,
      env: { ABAAD_API_ORIGIN: "http://127.0.0.1:8100", ABAAD_NEXT_DIST_DIR: ".next-e2e" },
    },
  ],
});
