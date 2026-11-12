import type { NextConfig } from "next";

// The browser only talks to the Next.js origin (http://localhost:3000).
// Requests to /api/v1/* are proxied to FastAPI, so no CORS setup is needed
// in development. ABAAD_API_ORIGIN lets the e2e tests use other ports.
const apiOrigin = process.env.ABAAD_API_ORIGIN ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  // A separate build directory lets the e2e tests build without touching
  // the directory used by `make dev`.
  distDir: process.env.ABAAD_NEXT_DIST_DIR ?? ".next",
  reactStrictMode: true,
  // Do not generate AGENTS.md / agent rule files in the project.
  agentRules: false,
  async rewrites() {
    return [{ source: "/api/v1/:path*", destination: `${apiOrigin}/api/v1/:path*` }];
  },
};

export default nextConfig;
