import type { Metadata } from "next";
import { SpikeLab } from "@/components/spike/SpikeLab";

export const metadata: Metadata = { title: "Map feasibility spike (dev) — ABAAD" };

export default function MapSpikePage() {
  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold">Map feasibility spike (Phase 1, development only)</h1>
        <p className="rounded-lg border-2 border-terracotta bg-ivory p-3 text-sm" data-testid="synthetic-banner">
          <strong>Synthetic test fixtures only.</strong> Every outline, tile, control point and image on this page is
          invented to test map mechanics (tests T1–T6 in docs/reports/MAP_SPIKE.md). Nothing here is a study area,
          a scientific dataset or a result.
        </p>
      </header>
      <SpikeLab />
    </div>
  );
}
