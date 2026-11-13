import type { Metadata } from "next";
import { MissionLab } from "@/components/mission/MissionLab";

export const metadata: Metadata = { title: "Mission Lab — ABAAD | أبعاد" };

export default function MissionLabPage() {
  return <MissionLab />;
}
