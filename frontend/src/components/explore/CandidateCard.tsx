"use client";

import { useState } from "react";
import type { Candidate, Dimension, EvidenceQuality, SourceRef } from "@/lib/api";
import { formatCoord } from "@/lib/api";
import { messages as t } from "@/i18n/en";
import { Meter } from "./Meter";

function SourceLink({ s, locator }: { s: SourceRef | null; locator: string | null }) {
  if (!s) return <span>—</span>;
  const href = s.url ?? (s.doi ? `https://doi.org/${s.doi}` : null);
  return (
    <span>
      {href ? <a className="underline" href={href} target="_blank" rel="noreferrer">{s.title}</a> : s.title}
      {locator && <span className="text-muted"> · {locator}</span>}
      <span className="ml-1 rounded bg-bg px-1 text-[10px] uppercase tracking-wide text-fg-2">{t.access[s.source_access] ?? s.source_access}</span>
    </span>
  );
}

/** Groups backend rubric levels for reading; it never recomputes or reweights anything. */
function groupDimensions(dims: Dimension[]) {
  const by = (levels: string[]) => dims.filter((d) => d.rubric_level && levels.includes(d.rubric_level));
  return {
    similar: by(["strong", "close"]),
    partial: by(["partial"]),
    different: by(["weak", "mismatch"]),
    missing: dims.filter((d) => d.weight > 0 && !d.rubric_level).sort((a, b) => b.weight - a.weight),
  };
}

function StatusPill({ c }: { c: Candidate }) {
  if (c.status === "ranked" && c.rank !== null)
    return <span className="rounded-full bg-olive px-3 py-1 text-sm font-semibold text-on-accent" data-testid="rank-badge">{t.compare.statusRanked(c.rank)}</span>;
  const text = c.status === "excluded" ? t.compare.statusExcluded : c.status === "not_available" ? t.compare.statusNotAvailable : t.compare.statusInsufficient;
  return <span className="rounded-full border border-dashed border-warn px-3 py-1 text-xs font-semibold text-warn" data-testid="status-pill">{text}</span>;
}

function EvidenceTile({ eq }: { eq: EvidenceQuality | undefined }) {
  const access = eq ? Object.entries(eq.source_access) : [];
  return (
    <div className="space-y-1.5" data-testid="evidence-quality">
      <p className="text-xs font-medium text-fg-2">{t.compare.evidenceHeading}</p>
      {!eq ? (
        <p className="text-xs italic text-muted">{t.compare.evidenceNotReported}</p>
      ) : (
        <>
          <p className="text-xs font-semibold text-fg" data-testid="evidence-class">
            {eq.claim_class ? `Class ${eq.claim_class.code} — ${eq.claim_class.label}` : t.compare.evidenceNone}
          </p>
          <p className="text-[11px] text-fg-2">
            {access.length === 0 ? "No assessed sources" : access.map(([k, n]) => `${n} ${(t.access[k] ?? k).toLowerCase()}`).join(" · ")}
          </p>
        </>
      )}
    </div>
  );
}

function DimList({ title, dims, tone, empty }: { title: string; dims: Dimension[]; tone: string; empty: string }) {
  return (
    <div className="space-y-1.5">
      <p className={`text-[11px] font-semibold uppercase tracking-wider ${tone}`}>{title}</p>
      {dims.length === 0 ? <p className="text-xs text-muted">{empty}</p> : (
        <ul className="space-y-1 text-xs">
          {dims.map((d) => (
            <li key={d.dimension} className="text-fg-2">
              <span className="font-semibold text-fg">{d.name}</span>
              {d.rubric_level ? ` — ${t.rubric[d.rubric_level].split(" — ")[0].toLowerCase()}` : ` — ${t.explore.unknown}`}
              <span className="text-muted"> · {t.compare.whyMatters} {d.weight > 0 ? d.weight : "0 (not weighted)"}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function CandidateCard({ c, highlighted, onFocus, minCoverage }: { c: Candidate; highlighted?: boolean; onFocus?: () => void; minCoverage: number }) {
  const [open, setOpen] = useState(false);
  const ranked = c.status === "ranked";
  const weighted = c.dimensions.filter((d) => d.weight > 0);
  const assessedWeighted = weighted.filter((d) => d.similarity !== null);
  const g = c.region.geometry;
  const groups = groupDimensions(c.dimensions);
  const visibleClaims = c.claims.filter((cl) => cl.supported_claim);
  const nextDims = groups.missing.slice(0, 2).map((d) => d.name.toLowerCase());

  return (
    <article
      data-testid={`candidate-${c.region.code}`}
      data-status={c.status}
      className={`rounded-xl border p-4 transition duration-200 sm:p-5 ${
        highlighted ? "border-ochre bg-raised" : ranked ? "border-line-strong bg-surface" : "border-dashed border-line bg-surface/60"}`}
      onMouseEnter={onFocus}
      onFocus={onFocus}
    >
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-ochre">
            {c.region.group === "egyptian" ? t.explore.groupEgyptian : t.explore.groupGlobal}
            {c.region.country_code && ` · ${c.region.country_code}`} · {c.region.region_level}
          </p>
          <h3 className="text-lg font-semibold leading-snug text-fg">{c.region.name}</h3>
          {c.region.origin_status === "disputed" && (
            <p className="text-xs font-semibold text-terracotta">Origin disputed — not a confirmed impact crater field.</p>
          )}
        </div>
        <StatusPill c={c} />
      </header>

      <p className="mt-2 text-xs text-fg-2" data-testid="status-reason">
        {ranked ? t.compare.whyRanked(c.coverage) : c.status === "insufficient_evidence" ? t.compare.whyInsufficient(c.coverage, minCoverage) : ""}
      </p>

      {/* Three independent outputs: never combined into one number. */}
      <div className="mt-3 grid gap-4 rounded-lg border border-line bg-bg/40 p-3 sm:grid-cols-3">
        <div className="space-y-1">
          <Meter label={t.explore.score} value={ranked ? c.score : null} tone="olive" testId="score" nullText={t.compare.scoreNotComputed} />
          <p className="text-[11px] text-muted">{t.compare.scoreHelp}</p>
        </div>
        <div className="space-y-1">
          <Meter label={t.explore.coverage} value={c.coverage} tone="terracotta" testId="coverage" />
          <p className="text-[11px] text-muted">{t.compare.criteriaAssessed(assessedWeighted.length, weighted.length)}. {t.compare.coverageHelp}</p>
        </div>
        <div className="space-y-1">
          <EvidenceTile eq={c.evidence_quality} />
          <p className="text-[11px] text-muted">{t.compare.evidenceHelp}</p>
        </div>
      </div>

      <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4" data-testid="dimension-summary">
        <DimList title={t.compare.similarities} dims={groups.similar} tone="text-ok" empty={t.compare.noneListed} />
        <DimList title={t.compare.partial} dims={groups.partial} tone="text-ochre" empty={t.compare.noneListed} />
        <DimList title={t.compare.differences} dims={groups.different} tone="text-err" empty={t.compare.noneListed} />
        <DimList title={t.compare.missing} dims={groups.missing} tone="text-muted" empty={t.compare.noneListed} />
      </div>

      <p className="mt-3 text-xs text-muted">
        {g ? `${g.geometry_status === "approximate" ? "Approximate context point" : "Source-traced point"} ${formatCoord(g)}` : "No verified location"}
      </p>

      <button type="button" className="mt-3 text-sm font-semibold text-ochre underline underline-offset-4" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
        {open ? t.explore.hideDetails : t.explore.details}
      </button>

      {open && (
        <div className="mt-4 space-y-5 animate-reveal" data-testid="candidate-details">
          {/* Wide screens: table. Small screens: the same rows as stacked cards (no hover-only data). */}
          <div className="hidden md:block">
            <table className="w-full border-collapse text-left text-xs">
              <caption className="pb-2 text-left text-[11px] text-muted">{t.compare.unitCaption}</caption>
              <thead>
                <tr className="border-b border-line-strong text-fg-2">
                  <th className="py-1.5 pr-2 font-semibold">{t.explore.dimension}</th>
                  <th className="py-1.5 pr-2 font-semibold">{t.explore.weight}</th>
                  <th className="py-1.5 pr-2 font-semibold">{t.explore.rubric}</th>
                  <th className="py-1.5 pr-2 font-semibold">{t.compare.valueUnit}</th>
                  <th className="py-1.5 font-semibold">{t.explore.sources}</th>
                </tr>
              </thead>
              <tbody>
                {c.dimensions.map((d) => <DimRow key={d.dimension} d={d} />)}
              </tbody>
            </table>
          </div>
          <div className="space-y-2 md:hidden">
            {c.dimensions.map((d) => <DimStack key={d.dimension} d={d} />)}
          </div>

          <section className="space-y-2">
            <h4 className="text-sm font-semibold">{t.compare.relevance}</h4>
            {c.claims.length === 0 && <p className="text-xs text-fg-2">{t.explore.noClaims}</p>}
            {c.claims.map((cl) => (
              <div key={cl.id} className="space-y-1.5 rounded-lg border border-line bg-raised p-3 text-xs" data-testid="claim">
                <p className="font-semibold text-fg">
                  Class {cl.claim_evidence_class.code} — {cl.claim_evidence_class.label} · {t.pairing[cl.reference_pairing_basis]}
                </p>
                {cl.supported_claim ? (
                  <p><span className="font-semibold">{t.compare.potentialUse}</span> <span className="rounded bg-bg px-1 text-[10px] uppercase tracking-wide text-ok">{t.compare.potentialUseTag}</span>: {cl.supported_claim}</p>
                ) : <p className="italic">{t.explore.draftNote}</p>}
                {cl.similarities && <p><span className="font-semibold">{t.compare.reason}:</span> {cl.similarities}</p>}
                {cl.differences && <p><span className="font-semibold">Differences:</span> {cl.differences}</p>}
                <p><span className="font-semibold">Limitations:</span> {cl.limitations}</p>
              </div>
            ))}
            {nextDims.length > 0 && (
              <p className="rounded-lg border border-dashed border-line p-3 text-xs text-fg-2" data-testid="next-measurement">
                <span className="font-semibold text-fg">{t.compare.nextMeasurement}</span>{" "}
                <span className="rounded bg-bg px-1 text-[10px] uppercase tracking-wide text-warn">{t.compare.nextTag}</span>: {t.compare.nextText(nextDims.join(" and "))}
              </p>
            )}
            {visibleClaims.length === 0 && c.claims.length > 0 && <p className="text-xs text-muted">{t.explore.draftNote}</p>}
          </section>

          {g?.uncertainty_note && <p className="text-xs"><span className="font-semibold">Location note:</span> {g.uncertainty_note}</p>}
          {!g && c.region.geometry_gap && <p className="text-xs"><span className="font-semibold">Location gap:</span> {c.region.geometry_gap}</p>}
        </div>
      )}
    </article>
  );
}

function Rubric({ d }: { d: Dimension }) {
  return d.rubric_level ? (
    <>
      <span className="font-semibold text-fg">{t.rubric[d.rubric_level]}</span>
      <span className="block text-muted">s = {d.similarity}</span>
    </>
  ) : <span className="italic text-muted">{t.explore.unknown}</span>;
}

function Evidence({ d }: { d: Dimension }) {
  return d.rationale ? (
    <div className="space-y-1">
      <p>{d.rationale}</p>
      <p><span className="font-semibold">{t.explore.earthSide}:</span> <SourceLink s={d.analog_source} locator={d.analog_locator} /></p>
      <p><span className="font-semibold">{t.explore.planetSide}:</span> <SourceLink s={d.reference_source} locator={d.reference_locator} /></p>
      {d.evidence_basis && <p className="text-muted">{t.basis[d.evidence_basis]}</p>}
    </div>
  ) : <span className="italic text-muted">No curated assessment — excluded from the score, not counted as zero.</span>;
}

function DimRow({ d }: { d: Dimension }) {
  return (
    <tr className="border-b border-line align-top" data-testid={`dim-${d.dimension}`}>
      <td className="py-2 pr-2 font-medium text-fg">{d.name}</td>
      <td className="py-2 pr-2 tabular-nums">{d.weight > 0 ? d.weight : "not weighted"}</td>
      <td className="py-2 pr-2"><Rubric d={d} /></td>
      <td className="py-2 pr-2 text-muted">{t.compare.noValueShort}</td>
      <td className="py-2 text-fg-2"><Evidence d={d} /></td>
    </tr>
  );
}

function DimStack({ d }: { d: Dimension }) {
  return (
    <div className="space-y-1.5 rounded-lg border border-line p-3 text-xs" data-testid={`dim-m-${d.dimension}`}>
      <p className="flex justify-between gap-2"><span className="font-semibold text-fg">{d.name}</span><span className="tabular-nums text-muted">w {d.weight > 0 ? d.weight : "—"}</span></p>
      <Rubric d={d} />
      <p className="text-muted">{t.compare.noMeasuredValue}</p>
      <div className="text-fg-2"><Evidence d={d} /></div>
    </div>
  );
}
