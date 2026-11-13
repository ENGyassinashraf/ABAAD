"use client";

import dynamic from "next/dynamic";
import type { Region } from "@/lib/api";
import { formatCoord } from "@/lib/api";
import { precisionOf } from "@/lib/mapView";
import { messages as t } from "@/i18n/en";
import { MoonPolarPanel } from "@/components/maps/MoonPolarPanel";
import { PrecisionBadge } from "@/components/maps/PrecisionBadge";

const MarsMap = dynamic(() => import("@/components/maps/MarsMap").then((m) => m.MarsMap), {
  ssr: false,
  loading: () => <div className="h-[22rem] w-full animate-pulse rounded-xl border border-line bg-map-mars sm:h-[26rem]" />,
});

/** Body map + region list + selected-region details, kept in one selection state. */
export function TargetPanel({ body, regions, selected, onSelect }: {
  body: string; regions: Region[]; selected: string | null; onSelect: (code: string) => void;
}) {
  const sel = regions.find((r) => r.code === selected) ?? null;
  const nameOf = (code: string | null) => regions.find((r) => r.code === code)?.name ?? code;

  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_19rem]">
      <div className="min-w-0">
        {body === "mars" && <MarsMap regions={regions} selected={selected} onSelect={onSelect} />}
        {body === "moon" && <MoonPolarPanel regions={regions} selected={selected} onSelect={onSelect} />}
      </div>

      <div className="space-y-4">
        <ul className="space-y-1.5" aria-label="Reference regions">
          {regions.map((region) => {
            const active = region.code === selected;
            return (
              <li key={region.code}>
                <button type="button" aria-pressed={active} data-testid={`ref-${region.code}`} onClick={() => onSelect(region.code)}
                  className={`w-full rounded-lg border px-3 py-2 text-left transition-colors duration-150 ${
                    active ? "border-ochre bg-raised" : "border-line bg-surface hover:border-line-strong hover:bg-raised"}`}>
                  <span className="flex items-center justify-between gap-2">
                    <span className={`font-semibold ${active ? "text-ochre" : "text-fg"}`}>{region.name}</span>
                    {active && <span className="text-[10px] font-semibold uppercase tracking-wider text-ochre">Selected</span>}
                  </span>
                  <span className="block text-xs text-muted">
                    {region.region_level}{region.parent_code ? ` · in ${nameOf(region.parent_code)}` : ""} · {t.precision[precisionOf(region)]}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>

        {sel && (
          <section className="space-y-2 rounded-xl border border-line bg-surface p-3 text-xs animate-reveal" data-testid="reference-details" aria-live="polite">
            <h3 className="text-sm font-semibold text-fg">{sel.name}</h3>
            <PrecisionBadge precision={precisionOf(sel)} />
            {sel.geometry && (
              <p><span className="font-semibold">{formatCoord(sel.geometry)}</span> · {sel.geometry.latitude_type}, {sel.geometry.crs_code}</p>
            )}
            {sel.outline && <p>{t.precision[precisionOf(sel)]} · {sel.outline.crs_code}{sel.outline.uncertainty_note ? ` — ${sel.outline.uncertainty_note}` : ""}</p>}
            {(sel.geometry?.source ?? sel.outline?.source) && (
              <p className="text-fg-2">Source:{" "}
                {(() => {
                  const s = (sel.geometry?.source ?? sel.outline?.source)!;
                  return s.url ? <a className="underline" href={s.url} target="_blank" rel="noreferrer">{s.title}</a> : s.title;
                })()}
              </p>
            )}
            {sel.geometry?.uncertainty_note && <p className="text-muted">{sel.geometry.uncertainty_note}</p>}
            {!sel.geometry && !sel.outline && <p className="text-fg-2">{sel.geometry_gap}</p>}
            {sel.parent_code && <p className="text-muted">Child feature of {nameOf(sel.parent_code)}; its own geometry is never replaced by the parent's.</p>}
          </section>
        )}
      </div>
    </div>
  );
}
