"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { ApiRequestError, type CompareResponse, fetchCompare, fetchOptions, type OptionsResponse } from "@/lib/api";
import { messages as t } from "@/i18n/en";
import { CandidateCard } from "./CandidateCard";
import { TargetPanel } from "./TargetPanel";

const CandidateMap = dynamic(() => import("./CandidateMap").then((m) => m.CandidateMap), {
  ssr: false,
  loading: () => <div className="h-80 w-full animate-pulse rounded-xl border border-line bg-surface" />,
});

const BODY_LABEL: Record<string, string> = { mars: "Mars", moon: "Moon" };
const BODY_NOTE: Record<string, string> = {
  mars: "Equirectangular map · IAU_2015:49910",
  moon: "Static south-polar panel · IAU_2015:30135",
};

function Step({ n, title, children, id }: { n: number; title: string; children: React.ReactNode; id: string }) {
  return (
    <section aria-labelledby={id} className="space-y-3">
      <h2 id={id} className="flex items-center gap-3 text-sm font-semibold uppercase tracking-[0.16em] text-fg-2">
        <span className="flex h-6 w-6 items-center justify-center rounded-full border border-ochre/70 font-serif text-xs text-ochre">{n}</span>
        {title}
      </h2>
      {children}
    </section>
  );
}

export function ExploreClient() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const reference = params.get("reference");
  const task = params.get("task");

  const [options, setOptions] = useState<OptionsResponse | null>(null);
  const [optionsError, setOptionsError] = useState<string | null>(null);
  const [body, setBody] = useState<string>("mars");
  const [result, setResult] = useState<CompareResponse | null>(null);
  const [resultError, setResultError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [highlighted, setHighlighted] = useState<string | null>(null);

  const setQuery = (next: { reference?: string | null; task?: string | null }) => {
    const q = new URLSearchParams(params.toString());
    for (const [k, v] of Object.entries(next)) {
      if (v) q.set(k, v);
      else q.delete(k);
    }
    router.replace(`${pathname}${q.toString() ? `?${q}` : ""}`, { scroll: false });
  };

  useEffect(() => {
    const ac = new AbortController();
    fetchOptions(ac.signal).then(setOptions).catch((e) => {
      if ((e as Error).name !== "AbortError") setOptionsError((e as Error).message);
    });
    return () => ac.abort();
  }, []);

  const selectedRef = useMemo(() => options?.references.find((r) => r.region.code === reference) ?? null, [options, reference]);

  useEffect(() => {
    if (selectedRef) setBody(selectedRef.region.body);
  }, [selectedRef]);

  useEffect(() => {
    setResult(null);
    setResultError(null);
    if (!reference || !task) return;
    const ac = new AbortController();
    setLoading(true);
    fetchCompare(reference, task, ac.signal)
      .then(setResult)
      .catch((e) => {
        if ((e as Error).name !== "AbortError") setResultError(e instanceof ApiRequestError ? e.message : String(e));
      })
      .finally(() => setLoading(false));
    return () => ac.abort();
  }, [reference, task]);

  const refsForBody = useMemo(() => options?.references.filter((r) => r.region.body === body).map((r) => r.region) ?? [], [options, body]);
  const ranked = result?.candidates.filter((c) => c.status === "ranked") ?? [];
  const unranked = result?.candidates.filter((c) => c.status !== "ranked") ?? [];
  const minCoverage = result?.method.min_coverage ?? 50;
  const taskObj = selectedRef?.tasks.find((x) => x.code === task) ?? null;

  const selectRegion = (code: string) => {
    if (!options) return;
    const keepTask = task && options.references.find((r) => r.region.code === code)?.tasks.some((x) => x.code === task);
    setQuery({ reference: code, task: keepTask ? task : null });
  };

  return (
    <div className="space-y-10">
      <header className="space-y-3">
        <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-ochre">{t.brand.nameLatin} · {t.nav.explore}</p>
        <h1 className="font-serif text-3xl font-semibold sm:text-4xl">{t.explore.title}</h1>
        <p className="max-w-prose text-fg-2">{t.explore.lead}</p>
      </header>

      {/* The research question is always visible, so no score appears without its task. */}
      <div className="z-20 rounded-xl lg:sticky border border-line-strong bg-bg/90 px-4 py-3 shadow-[0_8px_30px_rgb(0_0_0/0.25)] backdrop-blur lg:top-3" data-testid="research-question">
        <p className="text-[11px] font-semibold uppercase tracking-wider text-muted">Research question</p>
        <p className="text-sm font-semibold text-fg sm:text-base">
          {selectedRef && taskObj ? t.compare.question(taskObj.name, selectedRef.region.name, BODY_LABEL[selectedRef.region.body] ?? selectedRef.region.body) : t.compare.questionPending}
        </p>
      </div>

      {optionsError && <p role="alert" className="rounded-xl border border-err bg-surface p-4">{optionsError}</p>}
      {!options && !optionsError && <p role="status" className="text-fg-2">{t.explore.loading}</p>}

      {options && (
        <>
          <Step n={1} id="step1" title={t.explore.step1.replace(/^\d · /, "")}>
            <div className="flex flex-wrap gap-3" role="group" aria-label="Planetary body">
              {options.bodies.map((b) => {
                const active = body === b.code;
                return (
                  <button key={b.code} type="button" aria-pressed={active} data-testid={`body-${b.code}`}
                    onClick={() => { setBody(b.code); if (selectedRef?.region.body !== b.code) setQuery({ reference: null, task: null }); }}
                    className={`flex items-center gap-3 rounded-xl border px-4 py-3 text-left transition duration-150 ${
                      active ? "border-ochre bg-raised" : "border-line bg-surface hover:border-line-strong hover:bg-raised"}`}>
                    <span aria-hidden="true" className={`h-8 w-8 rounded-full ${b.code === "mars"
                      ? "bg-[radial-gradient(circle_at_35%_30%,#d29a74,#8e5139_60%,#3d2a20)]"
                      : "bg-[radial-gradient(circle_at_35%_30%,#d8d4c8,#8f8b80_60%,#3a3830)]"} ${active ? "ring-2 ring-ochre ring-offset-2 ring-offset-bg" : ""}`} />
                    <span>
                      <span className={`block font-semibold ${active ? "text-ochre" : "text-fg"}`}>{BODY_LABEL[b.code] ?? b.name}</span>
                      <span className="block text-[11px] text-muted">{BODY_NOTE[b.code]}</span>
                    </span>
                  </button>
                );
              })}
            </div>
          </Step>

          <Step n={2} id="step2" title={t.explore.step2.replace(/^\d · /, "")}>
            <TargetPanel body={body} regions={refsForBody} selected={reference} onSelect={selectRegion} />
            {!reference && <p className="text-sm text-fg-2">{t.explore.pickRegion}</p>}
          </Step>

          {selectedRef && (
            <Step n={3} id="step3" title={t.explore.step3.replace(/^\d · /, "")}>
              {selectedRef.tasks.length === 0 && <p>{t.explore.noTasks}</p>}
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4" role="group" aria-label="Research task">
                {selectedRef.tasks.map((tk) => {
                  const active = tk.code === task;
                  return (
                    <button key={tk.code} type="button" aria-pressed={active} data-testid={`task-${tk.code}`} onClick={() => setQuery({ task: tk.code })}
                      className={`rounded-lg border px-3 py-2.5 text-left text-sm font-semibold transition duration-150 ${
                        active ? "border-olive bg-olive text-on-accent" : "border-line bg-surface text-fg hover:border-line-strong hover:bg-raised"}`}>
                      {tk.name}
                    </button>
                  );
                })}
              </div>
              {taskObj && <p className="max-w-prose text-sm text-fg-2">{taskObj.description}</p>}
              {!task && <p className="text-sm text-fg-2">{t.explore.pickTask}</p>}
            </Step>
          )}
        </>
      )}

      {loading && <p aria-live="polite" role="status" className="text-fg-2">Comparing candidates…</p>}
      {resultError && <p role="alert" data-testid="compare-error" className="rounded-xl border border-err bg-surface p-4 text-sm">{resultError}</p>}

      {result && (
        <section aria-labelledby="results" className="space-y-6 animate-reveal" data-testid="results">
          <div className="flex flex-wrap items-end justify-between gap-3 border-b border-line-strong pb-3">
            <div className="space-y-1">
              <h2 id="results" className="flex items-center gap-3 text-sm font-semibold uppercase tracking-[0.16em] text-fg-2">
                <span className="flex h-6 w-6 items-center justify-center rounded-full border border-ochre/70 font-serif text-xs text-ochre">4</span>
                {t.explore.results.replace(/^\d · /, "")}: {result.task.name} · {result.reference.name}
              </h2>
              <p className="text-xs text-muted" data-testid="results-summary">
                {t.compare.summaryRanked(ranked.length)} · {t.compare.summaryInsufficient(unranked.length)} · {t.compare.threshold(minCoverage)}
              </p>
            </div>
            <Link data-testid="open-report" className="rounded-lg border border-terracotta px-3 py-1.5 text-sm font-semibold text-fg no-underline hover:bg-hover"
              href={`/report?reference=${encodeURIComponent(result.reference.code)}&task=${encodeURIComponent(result.task.code)}`}>
              {t.explore.openReport}
            </Link>
          </div>

          {result.reference.body === "moon" && (
            <p className="rounded-xl border border-terracotta/70 bg-surface p-4 text-sm text-fg-2" data-testid="moon-notice">{t.explore.notApplicableMoon}</p>
          )}

          <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_21rem]">
            <div className="min-w-0 space-y-8">
              <div className="space-y-3">
                <h3 className="font-serif text-xl font-semibold">{t.explore.ranked} ({ranked.length})</h3>
                {ranked.length === 0 && <p className="rounded-xl border border-line bg-surface p-4 text-sm text-fg-2" data-testid="none-ranked">{t.explore.noneRanked}</p>}
                {ranked.map((c) => (
                  <CandidateCard key={c.region.code} c={c} minCoverage={minCoverage} highlighted={highlighted === c.region.code} onFocus={() => setHighlighted(c.region.code)} />
                ))}
              </div>
              <div className="space-y-3">
                <h3 className="font-serif text-xl font-semibold">{t.explore.insufficient} ({unranked.length})</h3>
                <p className="text-sm text-fg-2">{t.explore.insufficientHelp}</p>
                {unranked.map((c) => (
                  <CandidateCard key={c.region.code} c={c} minCoverage={minCoverage} highlighted={highlighted === c.region.code} onFocus={() => setHighlighted(c.region.code)} />
                ))}
              </div>
            </div>

            <aside className="space-y-5 xl:sticky xl:top-28 xl:self-start">
              <section className="space-y-2">
                <h3 className="text-sm font-semibold text-fg">{t.explore.mapHeading}</h3>
                <CandidateMap candidates={result.candidates} highlighted={highlighted} onSelect={(code) => {
                  setHighlighted(code);
                  document.querySelector(`[data-testid="candidate-${code}"]`)?.scrollIntoView({ behavior: "smooth", block: "center" });
                }} />
              </section>
              <section className="space-y-2 rounded-xl border border-line bg-surface p-4 text-xs">
                <h3 className="text-sm font-semibold text-fg">{t.explore.weightsHeading}</h3>
                <ul className="space-y-1.5">
                  {result.weights.map((w) => (
                    <li key={w.dimension} className="space-y-0.5">
                      <span className="flex justify-between text-fg-2"><span>{w.name}</span><span className="tabular-nums">{w.weight}</span></span>
                      <span className="block h-1 rounded-full bg-bg"><span className="block h-1 rounded-full bg-olive" style={{ width: `${(w.weight / Math.max(...result.weights.map((x) => x.weight))) * 100}%` }} /></span>
                    </li>
                  ))}
                </ul>
                {result.weight_rationale && <p className="text-muted">{result.weight_rationale}</p>}
              </section>
              <section className="space-y-1.5 rounded-xl border border-line bg-surface p-4 text-xs text-fg-2">
                <h3 className="text-sm font-semibold text-fg">{t.explore.method}</h3>
                <p>{result.method.score_formula}</p>
                <p>{result.method.coverage_formula}</p>
                <p>{result.method.missing_data}</p>
                <p>{result.method.ranking}</p>
                <p className="font-semibold text-fg">{result.method.not_a_similarity_percentage}</p>
              </section>
              <section className="space-y-1.5 rounded-xl border border-line bg-surface p-4 text-xs text-fg-2">
                <h3 className="text-sm font-semibold text-fg">{t.report.limitationsHeading}</h3>
                <ul className="list-disc space-y-1 pl-4">{result.limitations.map((l) => <li key={l}>{l}</li>)}</ul>
              </section>
            </aside>
          </div>
        </section>
      )}
    </div>
  );
}
