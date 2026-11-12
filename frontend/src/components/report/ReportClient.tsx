"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { type CompareResponse, collectSources, fetchCompare, formatCoord } from "@/lib/api";
import { messages as t } from "@/i18n/en";

function downloadJson(data: CompareResponse) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `abaad-${data.reference.code}-${data.task.code}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

export function ReportClient() {
  const params = useSearchParams();
  const reference = params.get("reference");
  const task = params.get("task");
  const [data, setData] = useState<CompareResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!reference || !task) return;
    const ac = new AbortController();
    fetchCompare(reference, task, ac.signal).then(setData).catch((e) => {
      if ((e as Error).name !== "AbortError") setError((e as Error).message);
    });
    return () => ac.abort();
  }, [reference, task]);

  if (!reference || !task) return <p>{t.report.missing} <Link className="underline" href="/explore">{t.explore.title}</Link></p>;
  if (error) return <p role="alert" className="rounded-lg border-2 border-terracotta bg-ivory p-4">{error}</p>;
  if (!data) return <p>{t.explore.loading}</p>;

  const sources = collectSources(data);
  const sourceNo = new Map(sources.map((s, i) => [s.id, i + 1]));
  const cite = (id: number | undefined) => (id ? `[${sourceNo.get(id)}]` : "");

  return (
    <article className="report space-y-6 bg-ivory p-6 print:bg-white print:p-0" data-testid="report">
      <div className="flex flex-wrap gap-2 print:hidden">
        <button type="button" onClick={() => window.print()} className="rounded-lg border-2 border-olive bg-olive px-3 py-1.5 text-sm font-semibold text-ivory">{t.report.print}</button>
        <button type="button" onClick={() => downloadJson(data)} data-testid="download-json" className="rounded-lg border-2 border-olive bg-ivory px-3 py-1.5 text-sm font-semibold">{t.report.json}</button>
        <Link href={`/explore?reference=${encodeURIComponent(data.reference.code)}&task=${encodeURIComponent(data.task.code)}`}
          className="rounded-lg border-2 border-olive/50 px-3 py-1.5 text-sm font-semibold no-underline">{t.report.back}</Link>
      </div>

      <header className="space-y-1 border-b-2 border-olive pb-3">
        <p className="text-xs font-semibold uppercase tracking-wider text-olive">{t.brand.nameLatin} | {t.brand.nameArabic} · {t.brand.descriptor}</p>
        <h1 className="font-serif text-2xl font-semibold">{t.report.title}</h1>
        <p className="text-sm"><span className="font-semibold">{t.report.selection}:</span> {data.task.name} · {data.reference.name} ({data.reference.body})</p>
        <p className="text-xs">{t.report.generated} {data.generated_at}</p>
      </header>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">{t.explore.referenceHeading}</h2>
        <p className="text-sm">
          {data.reference.geometry
            ? <>{formatCoord(data.reference.geometry)} ({data.reference.geometry.latitude_type}, {data.reference.geometry.crs_code}) {cite(data.reference.geometry.source?.id)}. {data.reference.geometry.uncertainty_note}</>
            : <>{t.explore.locatorNone}. {data.reference.geometry_gap}</>}
        </p>
        <p className="text-sm">{data.task.description}</p>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">{t.explore.method}</h2>
        <ul className="list-disc space-y-1 pl-5 text-sm">
          <li>{data.method.score_formula}</li>
          <li>{data.method.coverage_formula}</li>
          <li>{data.method.missing_data}</li>
          <li>{data.method.ranking}</li>
          <li className="font-semibold">{data.method.not_a_similarity_percentage}</li>
        </ul>
        <table className="mt-2 w-full border-collapse text-left text-sm">
          <thead><tr className="border-b-2 border-olive"><th className="py-1">{t.explore.dimension}</th><th className="py-1">{t.explore.weight}</th></tr></thead>
          <tbody>{data.weights.map((w) => <tr key={w.dimension} className="border-b border-border-soft"><td className="py-1">{w.name}</td><td className="py-1 tabular-nums">{w.weight}</td></tr>)}</tbody>
        </table>
        {data.weight_rationale && <p className="text-xs">{data.weight_rationale}</p>}
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">{t.report.summary}</h2>
        <table className="w-full border-collapse text-left text-sm" data-testid="report-summary">
          <thead>
            <tr className="border-b-2 border-olive">
              <th className="py-1 pr-2">{t.explore.rank}</th><th className="py-1 pr-2">Site</th>
              <th className="py-1 pr-2">{t.explore.score}</th><th className="py-1">{t.explore.coverage}</th>
            </tr>
          </thead>
          <tbody>
            {data.candidates.map((c) => (
              <tr key={c.region.code} className="border-b border-border-soft">
                <td className="py-1 pr-2">{c.rank ?? "—"}</td>
                <td className="py-1 pr-2">{c.region.name}{c.region.group === "egyptian" ? " (Egypt)" : ""}</td>
                <td className="py-1 pr-2 tabular-nums">{c.score === null ? t.explore.insufficient : c.score.toFixed(1)}</td>
                <td className="py-1 tabular-nums">{c.coverage.toFixed(1)} %</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="space-y-4">
        <h2 className="text-lg font-semibold">{t.report.breakdown}</h2>
        {data.candidates.filter((c) => c.dimensions.some((d) => d.rationale) || c.claims.length).map((c) => (
          <div key={c.region.code} className="break-inside-avoid space-y-2 border-l-4 border-olive pl-3">
            <h3 className="font-semibold">{c.region.name} — {c.score === null ? t.explore.insufficient : `${c.score.toFixed(1)} / 100`} · {t.explore.coverage} {c.coverage.toFixed(1)} %</h3>
            <ul className="space-y-1 text-sm">
              {c.dimensions.map((d) => (
                <li key={d.dimension}>
                  <span className="font-semibold">{d.name}</span> (w {d.weight}):{" "}
                  {d.rubric_level
                    ? <>{t.rubric[d.rubric_level]} — {d.rationale} {cite(d.analog_source?.id)}{d.reference_source?.id !== d.analog_source?.id ? cite(d.reference_source?.id) : ""}</>
                    : <em>{t.explore.unknown} (excluded, not zero)</em>}
                </li>
              ))}
            </ul>
            {c.claims.map((cl) => (
              <p key={cl.id} className="text-xs">
                Claim class {cl.claim_evidence_class.code} ({cl.claim_evidence_class.label}), {t.pairing[cl.reference_pairing_basis]}, {cl.publication_state}. Limitations: {cl.limitations}
              </p>
            ))}
            {c.region.geometry?.uncertainty_note && <p className="text-xs">Location: {c.region.geometry.uncertainty_note} {cite(c.region.geometry.source?.id)}</p>}
          </div>
        ))}
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">{t.report.limitationsHeading}</h2>
        <ul className="list-disc space-y-1 pl-5 text-sm">{data.limitations.map((l) => <li key={l}>{l}</li>)}</ul>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">{t.report.sourcesHeading}</h2>
        <ol className="list-decimal space-y-1 pl-5 text-xs" data-testid="report-sources">
          {sources.map((s) => (
            <li key={s.id}>
              {s.citation ?? s.title}{" "}
              {(s.url || s.doi) && <a className="underline" href={s.url ?? `https://doi.org/${s.doi}`}>{s.doi ? `doi:${s.doi}` : s.url}</a>}
              {" "}— {t.access[s.source_access] ?? s.source_access}{s.accessed_on ? `, ${t.report.accessed} ${s.accessed_on}` : ""}.
            </li>
          ))}
        </ol>
      </section>
    </article>
  );
}
