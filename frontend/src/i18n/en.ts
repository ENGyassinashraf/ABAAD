/**
 * English UI strings. All user-facing text lives here so an Arabic (RTL)
 * catalogue can be added later without touching components (decision D6).
 */
export const en = {
  brand: {
    nameLatin: "ABAAD",
    nameArabic: "أبعاد",
    slogan: "Different Dimensions. One Connection.",
    descriptor: "Earth Analog Discovery Platform",
    temporaryWordmark: "Temporary text wordmark — the approved ABAAD logo has not been uploaded yet.",
  },
  nav: {
    label: "Main navigation",
    home: "Home",
    mapSpike: "Map spike (dev)",
  },
  home: {
    intro:
      "ABAAD will help researchers find Earth locations that are useful analogs for specific Mars and Moon research tasks — explaining what matches, what differs, and how strong the evidence is.",
    phaseNotice:
      "Phase 1 foundation. No comparisons, scores or scientific results exist in this application yet.",
    statusHeading: "System status",
  },
  status: {
    checking: "Checking API…",
    ok: "API and database OK",
    degraded: "API reachable, but the database is not ready",
    unreachable: "API unreachable — is the backend running? (make dev)",
    schema: "Schema revision",
    sqlite: "SQLite",
  },
  footer: {
    phase: "Phase 1 — project foundation",
  },
} as const;

export type Messages = typeof en;
export const messages: Messages = en;
