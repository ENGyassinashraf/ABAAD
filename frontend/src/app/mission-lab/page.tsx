import type { Metadata } from "next";
import { MissionLab } from "@/components/mission/MissionLab";

export const metadata: Metadata = { title: "Mission Lab — ABAAD | أبعاد" };

export default function MissionLabPage() {
  // Break out of the 5xl layout column: the mission workspace needs the full width.
  return (
    <div className="relative left-1/2 w-[min(1600px,calc(100vw-2rem))] -translate-x-1/2">
      <MissionLab />
    </div>
  );
}
