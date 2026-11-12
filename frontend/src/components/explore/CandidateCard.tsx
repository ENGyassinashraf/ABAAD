"use client";

import { useState } from "react";
import type { Candidate, SourceRef } from "@/lib/api";
import { formatCoord } from "@/lib/api";
import { messages as t } from "@/i18n/en";
import { Meter } from "./Meter";

function SourceLink({ s, locator }: { s: SourceRef | null; locator: string | null }) {
  if (!s) return <span>—</span>;
  const href = s.url ?? (s.doi ? `https://doi.org/${s.doi}` : null);
  return (
    <span>
      {href ? <a className="underline" href={href} target="_blank" rel="noreferrer">{s.title}</a> : s.title}
      {locator && <span className="text-earth/70"> · {locator}</span>}
      <span className="ml-1 rounded bg-sand px-1 text-[10px] uppercase tracking-wide">{t.access[s.source_access] ?? s.source_access}</span>
    </span>
  );
}

export function CandidateCard({ c, highlighted, onFocus }: { c: Candidate; highlighted?: boolean; onFocus?: () => void }) {
  const [open, setOpen] = useState(false);
  const ranked = c.status === "ranked";
  const assessed = c.dimensions.filter((d) => d.similarity !== null);
  const g = c.region.geometry;

  return (
    <article
      data-testid={`candidate-${c.region.code}`}
      data-status={c.status}
      className={`rounded-lg border-2 bg-ivory p-4 transition-shadow ${highlighted ? "border-terracotta shadow-md" : ranked ? "border-olive" : "border-border-soft"}`}
      onMouseEnter={onFocus}
    >
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <p className="text-xs font-semibold uppercase tracking-wider text-olive">
            {c.region.group === "egyptian" ? t.explore.groupEgyptian : t.explore.groupGlobal}
            {c.region.country_code && ` · ${c.region.country_code}`} · {c.region.region_level}
          </p>
          <h3 className="text-lg font-semibold leading-snug">{c.region.name}</h3>
          {c.region.origin_status === "disputed" && (
            <p className="text-xs font-semibold text-terracotta">Origin disputed — not a confirmed impact crater field.</p>
          )}
        </div>
        {ranked ? (
          <span className="rounded-full bg-olive px-3 py-1 text-sm font-semibold text-ivory" data-testid="rank-badge">
            {t.explore.rank} {c.rank}
          </span>
        ) : (
          <span className="rounded-full border-2 border-ochre px-3 py-1 text-xs font-semibold">{t.explore.insufficient}</span>
        )}
      </header>

      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <Meter label={t.explore.score} value={c.score} tone={ranked ? "olive" : "ochre"} testId="score" />
        <Meter label={t.explore.coverage} value={c.coverage} tone="terracotta" testId="coverage" />
      </div>

      <p className="mt-2 text-xs text-earth/80">
        {assessed.length} of {c.dimensions.filter((d) => d.weight > 0).length} weighted dimensions assessed
        {g ? ` · ${g.geometry_status === "approximate" ? "approximate context point" : "source-traced point"} ${formatCoord(g)}` : " · no verified location"}
      </p>

      <button
        type="button"
        className="mt-3 text-sm font-semibold text-olive underline underline-offset-4"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        {open ? t.explore.hideDetails : t.explore.details}
      </button>

      {open && (
        <div className="mt-3 space-y-4" data-testid="candidate-details">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[36rem] border-collapse text-left text-xs">
              <thead>
                <tr className="border-b-2 border-olive">
                  <th className="py-1 pr-2">{t.explore.dimension}</th>
                  <th className="py-1 pr-2">{t.explore.weight}</th>
                  <th className="py-1 pr-2">{t.explore.rubric}</th>
                  <th className="py-1">{t.explore.sources}</th>
                </tr>
              </thead>
              <tbody>
                {c.dimensions.map((d) => (
                  <tr key={d.dimension} className="border-b border-border-soft align-top" data-testid={`dim-${d.dimension}`}>
                    <td className="py-2 pr-2 font-medium">{d.name}</td>
                    <td className="py-2 pr-2 tabular-nums">{d.weight > 0 ? d.weight : "not weighted"}</td>
                    <td className="py-2 pr-2">
                      {d.rubric_level ? (
                        <>
                          <span className="font-semibold">{t.rubric[d.rubric_level]}</span>
                          <span className="block text-earth/70">s = {d.similarity}</span>
                        </>
                      ) : (
                        <span className="italic text-earth/70">{t.explore.unknown}</span>
                      )}
                    </td>
                    <td className="py-2">
                      {d.rationale ? (
                        <div className="space-y-1">
                          <p>{d.rationale}</p>
                          <p><span className="font-semibold">{t.explore.earthSide}:</span> <SourceLink s={d.analog_source} locator={d.analog_locator} /></p>
                          <p><span className="font-semibold">{t.explore.planetSide}:</span> <SourceLink s={d.reference_source} locator={d.reference_locator} /></p>
                          {d.evidence_basis && <p className="text-earth/70">{t.basis[d.evidence_basis]}</p>}
                        </div>
                      ) : (
                        <span className="italic text-earth/70">No curated assessment — excluded from the score, not counted as zero.</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <section className="space-y-2">
            <h4 className="text-sm font-semibold">{t.explore.claims}</h4>
            {c.claims.length === 0 && <p className="text-xs">{t.explore.noClaims}</p>}
            {c.claims.map((cl) => (
              <div key={cl.id} className="rounded border border-border-soft bg-sand/50 p-3 text-xs" data-testid="claim">
                <p className="font-semibold">
                  Class {cl.claim_evidence_class.code} — {cl.claim_evidence_class.label} · {t.pairing[cl.reference_pairing_basis]}
                </p>
                {cl.supported_claim ? <p className="mt-1">{cl.supported_claim}</p> : <p className="mt-1 italic">{t.explore.draftNote}</p>}
                {cl.differences && <p className="mt-1"><span className="font-semibold">Differences:</span> {cl.differences}</p>}
                <p className="mt-1"><span className="font-semibold">Limitations:</span> {cl.limitations}</p>
              </div>
            ))}
          </section>

          {g?.uncertainty_note && (
            <p className="text-xs"><span className="font-semibold">Location note:</span> {g.uncertainty_note}</p>
          )}
          {!g && c.region.geometry_gap && (
            <p className="text-xs"><span className="font-semibold">Location gap:</span> {c.region.geometry_gap}</p>
          )}
        </div>
      )}
    </article>
  );
}
