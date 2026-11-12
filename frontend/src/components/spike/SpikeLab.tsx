"use client";

import "maplibre-gl/dist/maplibre-gl.css";
import { EarthSpike } from "./EarthSpike";
import { MarsSpike } from "./MarsSpike";
import { MoonPanel } from "./MoonPanel";
import { type TestId, useResults } from "./useResults";

const LABEL: Record<string, string> = { pending: "RUNNING", pass: "PASS", fail: "FAIL" };

export function SpikeLab() {
  const { results, report } = useResults();
  return (
    <div className="space-y-8">
      <section aria-labelledby="results-heading">
        <h2 id="results-heading" className="mb-2 text-lg font-semibold">Results in this browser</h2>
        <table className="w-full border-collapse bg-ivory text-left text-xs" data-testid="spike-results">
          <thead>
            <tr className="border-b-2 border-olive">
              <th className="p-2">Test</th><th className="p-2">Result</th><th className="p-2">Expected</th><th className="p-2">Actual</th>
            </tr>
          </thead>
          <tbody>
            {(Object.keys(results) as TestId[]).map((id) => (
              <tr key={id} className="border-b border-border-soft align-top" data-testid={`result-${id}`} data-status={results[id].status}>
                <td className="p-2 font-semibold">{id}</td>
                <td className={`p-2 font-semibold ${results[id].status === "fail" ? "text-terracotta" : "text-olive"}`}>
                  {LABEL[results[id].status]}
                </td>
                <td className="p-2">{results[id].expected}</td>
                <td className="p-2 font-mono" data-testid={`actual-${id}`}>{results[id].actual}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      <section aria-labelledby="t1"><h2 id="t1" className="mb-2 font-semibold">T1 — Earth (interactive)</h2><EarthSpike report={report} /></section>
      <section aria-labelledby="t2"><h2 id="t2" className="mb-2 font-semibold">T2, T3, T4, T6 — Mars in a declared planetary CRS</h2><MarsSpike report={report} /></section>
      <section aria-labelledby="t5"><h2 id="t5" className="mb-2 font-semibold">T5 — Moon south pole (static panel)</h2><MoonPanel report={report} /></section>
    </div>
  );
}
