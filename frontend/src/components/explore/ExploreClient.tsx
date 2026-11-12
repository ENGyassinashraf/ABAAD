"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { ApiRequestError, type CompareResponse, fetchCompare, fetchOptions, formatCoord, type OptionsResponse } from "@/lib/api";
import { messages as t } from "@/i18n/en";
import { CandidateCard } from "./CandidateCard";
import { CandidateMap } from "./CandidateMap";
import { ReferenceLocator } from "./ReferenceLocator";

const BODY_LABEL: Record<string, string> = { mars: "Mars", moon: "Moon" };

function Chip({ active, onClick, children, testId }: { active: boolean; onClick: () => void; children: React.ReactNode; testId?: string }) {
  return (
    <button type="button" onClick={onClick} aria-pressed={active} data-testid={testId}
      className={`rounded-lg border-2 px-4 py-2 text-left text-sm font-semibold transition-colors ${active ? "border-olive bg-olive text-ivory" : "border-olive/50 bg-ivory hover:border-olive"}`}>
      {children}
    </button>
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

  // Keep the body tab in sync with a reference chosen via the URL.
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

  const refsForBody = options?.references.filter((r) => r.region.body === body) ?? [];
  const ranked = result?.candidates.filter((c) => c.status === "ranked") ?? [];
  const insufficient = result?.candidates.filter((c) => c.status !== "ranked") ?? [];

  return (
    <div className="space-y-8">
      <header className="space-y-2">
        <h1 className="font-serif text-3xl font-semibold">{t.explore.title}</h1>
        <p className="max-w-prose">{t.explore.lead}</p>
      </header>

      {optionsError && <p role="alert" className="rounded-lg border-2 border-terracotta bg-ivory p-4">{optionsError}</p>}
      {!options && !optionsError && <p>{t.explore.loading}</p>}

      {options && (
        <>
          <section aria-labelledby="step1" className="space-y-3">
            <h2 id="step1" className="text-sm font-semibold uppercase tracking-wider text-olive">{t.explore.step1}</h2>
            <div className="flex flex-wrap gap-2">
              {options.bodies.map((b) => (
                <Chip key={b.code} active={body === b.code} testId={`body-${b.code}`}
                  onClick={() => { setBody(b.code); if (selectedRef?.region.body !== b.code) setQuery({ reference: null, task: null }); }}>
                  {BODY_LABEL[b.code] ?? b.name}
                </Chip>
              ))}
            </div>
          </section>

          <section aria-labelledby="step2" className="space-y-3">
            <h2 id="step2" className="text-sm font-semibold uppercase tracking-wider text-olive">{t.explore.step2}</h2>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {refsForBody.map(({ region }) => {
                const active = region.code === reference;
                return (
                  <button key={region.code} type="button" aria-pressed={active} data-testid={`ref-${region.code}`}
                    onClick={() => {
                      const keepTask = task && options.references.find((r) => r.region.code === region.code)?.tasks.some((x) => x.code === task);
                      setQuery({ reference: region.code, task: keepTask ? task : null });
                    }}
                    className={`rounded-lg border-2 p-3 text-left transition-colors ${active ? "border-olive bg-olive text-ivory" : "border-olive/40 bg-ivory hover:border-olive"}`}>
                    <span className="block font-semibold">{region.name}</span>
                    <span className="block text-xs opacity-80">
                      {region.region_level}{region.parent_code ? ` · in ${options.references.find((r) => r.region.code === region.parent_code)?.region.name ?? region.parent_code}` : ""}
                    </span>
                    <span className="mt-1 block text-xs opacity-80">{region.geometry ? formatCoord(region.geometry) : t.explore.locatorNone}</span>
                  </button>
                );
              })}
            </div>
            {!reference && <p className="text-sm">{t.explore.pickRegion}</p>}
          </section>

          {selectedRef && (
            <section aria-labelledby="step3" className="space-y-3">
              <h2 id="step3" className="text-sm font-semibold uppercase tracking-wider text-olive">{t.explore.step3}</h2>
              {selectedRef.tasks.length === 0 && <p>{t.explore.noTasks}</p>}
              <div className="flex flex-wrap gap-2">
                {selectedRef.tasks.map((tk) => (
                  <Chip key={tk.code} active={tk.code === task} testId={`task-${tk.code}`} onClick={() => setQuery({ task: tk.code })}>
                    {tk.name}
                  </Chip>
                ))}
              </div>
              {task && <p className="max-w-prose text-sm">{selectedRef.tasks.find((x) => x.code === task)?.description}</p>}
              {!task && <p className="text-sm">{t.explore.pickTask}</p>}
            </section>
          )}
        </>
      )}

      {loading && <p aria-live="polite">{t.explore.loading}</p>}
      {resultError && <p role="alert" data-testid="compare-error" className="rounded-lg border-2 border-terracotta bg-ivory p-4">{resultError}</p>}

      {result && (
        <section aria-labelledby="results" className="space-y-5" data-testid="results">
          <div className="flex flex-wrap items-end justify-between gap-3 border-b-2 border-olive pb-2">
            <h2 id="results" className="text-sm font-semibold uppercase tracking-wider text-olive">
              {t.explore.results}: {result.task.name} · {result.reference.name}
            </h2>
            <Link data-testid="open-report" className="rounded-lg border-2 border-terracotta bg-ivory px-3 py-1.5 text-sm font-semibold no-underline hover:bg-sand"
              href={`/report?reference=${encodeURIComponent(result.reference.code)}&task=${encodeURIComponent(result.task.code)}`}>
              {t.explore.openReport}
            </Link>
          </div>

          {result.reference.body === "moon" && (
            <p className="rounded-lg border-2 border-terracotta bg-ivory p-4 text-sm" data-testid="moon-notice">{t.explore.notApplicableMoon}</p>
          )}

          <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
            <div className="space-y-6">
              <div className="space-y-3">
                <h3 className="text-lg font-semibold">{t.explore.ranked} ({ranked.length})</h3>
                {ranked.length === 0 && <p className="rounded-lg border border-border-soft bg-ivory p-4 text-sm" data-testid="none-ranked">{t.explore.noneRanked}</p>}
                {ranked.map((c) => (
                  <CandidateCard key={c.region.code} c={c} highlighted={highlighted === c.region.code} onFocus={() => setHighlighted(c.region.code)} />
                ))}
              </div>
              <div className="space-y-3">
                <h3 className="text-lg font-semibold">{t.explore.insufficient} ({insufficient.length})</h3>
                <p className="text-sm">{t.explore.insufficientHelp}</p>
                {insufficient.map((c) => (
                  <CandidateCard key={c.region.code} c={c} highlighted={highlighted === c.region.code} onFocus={() => setHighlighted(c.region.code)} />
                ))}
              </div>
            </div>

            <aside className="space-y-6 lg:sticky lg:top-4 lg:self-start">
              <section className="space-y-2">
                <h3 className="text-sm font-semibold">{t.explore.mapHeading}</h3>
                <CandidateMap candidates={result.candidates} highlighted={highlighted} onSelect={(code) => {
                  setHighlighted(code);
                  document.querySelector(`[data-testid="candidate-${code}"]`)?.scrollIntoView({ behavior: "smooth", block: "center" });
                }} />
              </section>
              <section className="space-y-2">
                <h3 className="text-sm font-semibold">{t.explore.referenceHeading}: {result.reference.name}</h3>
                <ReferenceLocator region={result.reference} />
              </section>
              <section className="space-y-2 rounded-lg border border-border-soft bg-ivory p-3 text-xs">
                <h3 className="text-sm font-semibold">{t.explore.weightsHeading}</h3>
                <ul className="space-y-1">
                  {result.weights.map((w) => (
                    <li key={w.dimension} className="flex justify-between"><span>{w.name}</span><span className="tabular-nums">{w.weight}</span></li>
                  ))}
                </ul>
                {result.weight_rationale && <p className="text-earth/80">{result.weight_rationale}</p>}
              </section>
              <section className="space-y-1 rounded-lg border border-border-soft bg-ivory p-3 text-xs">
                <h3 className="text-sm font-semibold">{t.explore.method}</h3>
                <p>{result.method.score_formula}</p>
                <p>{result.method.coverage_formula}</p>
                <p>{result.method.missing_data}</p>
                <p>{result.method.ranking}</p>
                <p className="font-semibold">{result.method.not_a_similarity_percentage}</p>
              </section>
            </aside>
          </div>
        </section>
      )}
    </div>
  );
}
