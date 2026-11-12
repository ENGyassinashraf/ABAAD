"use client";

import { useCallback, useState } from "react";

export type TestId = "T1" | "T2" | "T3" | "T4" | "T5" | "T6";
export type Status = "pending" | "pass" | "fail";
export interface Result {
  status: Status;
  expected: string;
  actual: string;
}

export const EXPECTED: Record<TestId, string> = {
  T1: "OpenFreeMap style loads in MapLibre; synthetic RFC 7946 outline drawn; OpenStreetMap attribution visible",
  T2: "Map runs in IAU_2015:49910 with tile matrix ABAAD-MarsEqcQuad; synthetic tiles drawn without reprojection",
  T3: "WKT polygon + 3 control points align with raster within 1 source pixel (main-thread and worker paths)",
  T4: "Adding Web Mercator tiles to the Mars map is refused by code and nothing is drawn",
  T5: "Static south-polar panel: graticule and scale bar computed from the lunar radius match pyproj",
  T6: "Mars map has no Earth scale control; its scale uses the Mars radius (measured within 0.5%)",
};

export function useResults() {
  const [results, setResults] = useState<Record<TestId, Result>>(() =>
    Object.fromEntries(
      (Object.keys(EXPECTED) as TestId[]).map((k) => [k, { status: "pending", expected: EXPECTED[k], actual: "running…" }]),
    ) as Record<TestId, Result>,
  );
  const report = useCallback((id: TestId, status: Status, actual: string) => {
    setResults((prev) => ({ ...prev, [id]: { ...prev[id], status, actual } }));
  }, []);
  return { results, report };
}
