"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { messages as t } from "@/i18n/en";

type Stats = {
  earth: number; earthLocated: number; references: number; sources: number; datasets: number; tasks: number;
  revision: string | null; healthy: boolean; checkedAt: Date; missions: number;
};

async function get<T>(path: string): Promise<T> {
  const r = await fetch(path, { cache: "no-store" });
  if (!r.ok && r.status !== 503) throw new Error(String(r.status));
  return r.json() as Promise<T>;
}

type Region = { validation_status: string };

/** Live counts read from the ABAAD API every 30 s. Nothing here is estimated or hard-coded. */
export function LiveDashboard() {
  const [s, setS] = useState<Stats | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const [earth, refs, sources, datasets, tasks, health] = await Promise.all([
          get<{ total: number; items: Region[] }>("/api/v1/regions?limit=200&body=earth&role=analog"),
          get<{ total: number }>("/api/v1/regions?limit=1&role=reference"),
          get<{ total: number }>("/api/v1/sources?limit=1"),
          get<unknown[]>("/api/v1/datasets"),
          get<{ items: unknown[] }>("/api/v1/tasks"),
          get<{ status: string; database: { schema_revision: string | null } }>("/api/v1/health"),
        ]);
        const missions = await get<{ objectives: unknown[] }>("/api/v1/mission/catalog").then((c) => c.objectives.length).catch(() => 0);
        const located = earth.items.filter((r) => r.validation_status === "site_confirmed").length;
        if (alive) {
          setS({ earth: earth.total, earthLocated: located, references: refs.total, sources: sources.total,
            datasets: datasets.length, tasks: tasks.items.length, revision: health.database.schema_revision,
            healthy: health.status === "ok", checkedAt: new Date(), missions });
          setFailed(false);
        }
      } catch {
        if (alive) setFailed(true);
      }
    };
    load();
    const id = setInterval(load, 30_000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  const tiles: [string, string | number, string, string][] = s
    ? [
        [t.dashboard.earth, s.earth, t.dashboard.earthNote(s.earthLocated), "/sites"],
        [t.dashboard.references, s.references, t.dashboard.referencesNote, "/sites"],
        [t.dashboard.tasks, s.tasks, t.dashboard.tasksNote, "/explore"],
        [t.dashboard.sources, s.sources, t.dashboard.sourcesNote, "/sites"],
        [t.dashboard.datasets, s.datasets, t.dashboard.datasetsNote, "/sites"],
        [t.dashboard.missionLab, s.missions, t.dashboard.missionLabNote, "/mission-lab"],
      ]
    : [];

  return (
    <section aria-labelledby="dash-heading" className="space-y-4" data-testid="live-dashboard">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-ochre">{t.dashboard.kicker}</p>
          <h2 id="dash-heading" className="font-serif text-2xl font-semibold">{t.dashboard.heading}</h2>
        </div>
        <p className="flex items-center gap-2 text-xs text-muted" aria-live="polite">
          <span className={`relative inline-flex h-2.5 w-2.5 rounded-full ${failed ? "bg-err" : s?.healthy ? "bg-ok" : "bg-warn"}`}>
            {!failed && s?.healthy && <span className="absolute inset-0 animate-ping rounded-full bg-ok/60 motion-reduce:hidden" />}
          </span>
          {failed ? t.dashboard.offline : s ? t.dashboard.updated(s.checkedAt.toLocaleTimeString(), s.revision ?? "—") : t.dashboard.loading}
        </p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-6">
        {(s ? tiles : Array.from({ length: 6 }, () => ["", "", "", ""] as [string, string, string, string])).map(([label, value, note, href], i) => (
          <Link key={label || i} href={href || "#"} data-testid={label ? `stat-${i}` : undefined}
            className="group relative overflow-hidden rounded-xl border border-line bg-surface p-4 no-underline transition duration-200 hover:-translate-y-0.5 hover:border-ochre/60 hover:bg-raised">
            <span aria-hidden="true" className="absolute inset-y-0 left-0 w-0.5 bg-gradient-to-b from-ochre via-terracotta to-olive opacity-70" />
            {s ? (
              <>
                <p className="text-[11px] font-semibold uppercase tracking-wider text-muted">{label}</p>
                <p className="mt-1 font-serif text-4xl leading-none text-fg tabular-nums">{value}</p>
                <p className="mt-2 text-xs text-fg-2">{note}</p>
              </>
            ) : (
              <div className="space-y-2 motion-safe:animate-pulse">
                <div className="h-3 w-24 rounded bg-raised" />
                <div className="h-8 w-12 rounded bg-raised" />
                <div className="h-3 w-32 rounded bg-raised" />
              </div>
            )}
          </Link>
        ))}
      </div>
    </section>
  );
}
