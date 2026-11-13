"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { fetchOptions, fetchRegions, formatCoord, type Geometry, type OptionsResponse, type RegionSummary } from "@/lib/api";
import { messages as t } from "@/i18n/en";

type GeoRow = {
  geometry_status: string;
  geometry_text: string;
  encoding: string;
  crs_code: string;
  latitude_type: string;
  longitude_domain: string;
  geometry_method: string | null;
  uncertainty_note: string | null;
};

function toGeometry(g: GeoRow): Geometry | null {
  let lon: number;
  let lat: number;
  if (g.encoding === "rfc7946_geojson") {
    const p = JSON.parse(g.geometry_text);
    if (p.type !== "Point") return null;
    [lon, lat] = p.coordinates;
  } else {
    const m = /POINT\s*\(([-\d.]+)\s+([-\d.]+)\)/.exec(g.geometry_text);
    if (!m) return null;
    lon = Number(m[1]);
    lat = Number(m[2]);
  }
  return { lon, lat, crs_code: g.crs_code, latitude_type: g.latitude_type, longitude_domain: g.longitude_domain,
    geometry_status: g.geometry_status, geometry_method: g.geometry_method, uncertainty_note: g.uncertainty_note, source: null, source_locator: null };
}

function SiteCard({ r, geom, featured }: { r: RegionSummary; geom: Geometry | null | undefined; featured?: { title: string; blurb: string; reference: string } }) {
  return (
    <article className={`space-y-2 rounded-lg border-2 bg-surface p-4 ${featured ? "border-olive" : "border-line"}`} data-testid={`site-${r.code}`}>
      <p className="text-xs font-semibold uppercase tracking-wider text-olive">
        {r.country_code ?? r.body} · {r.region_level}{r.parent_code ? ` · in ${r.parent_code}` : ""}
      </p>
      <h3 className="text-lg font-semibold leading-snug">{featured?.title ?? r.name}</h3>
      {featured && <p className="text-sm">{featured.blurb}</p>}
      {r.origin_status === "disputed" && <p className="text-xs font-semibold text-terracotta">Origin disputed — never presented as confirmed impact craters.</p>}
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-xs">
        <dt className="font-semibold">{t.sites.status}</dt><dd>{r.validation_status.replaceAll("_", " ")}</dd>
        <dt className="font-semibold">{t.sites.location}</dt>
        <dd>{geom === undefined ? "…" : geom ? `${formatCoord(geom)} (${geom.geometry_status === "approximate" ? "approximate context point" : "source-traced"})` : "no verified location (recorded gap)"}</dd>
        {featured && <><dt className="font-semibold">Compare with</dt><dd>{featured.reference}</dd></>}
      </dl>
      {geom?.geometry_status === "approximate" && geom.uncertainty_note && <p className="text-xs text-muted">{geom.uncertainty_note}</p>}
    </article>
  );
}

export function SitesClient() {
  const [earth, setEarth] = useState<RegionSummary[] | null>(null);
  const [geoms, setGeoms] = useState<Record<string, Geometry | null>>({});
  const [options, setOptions] = useState<OptionsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const ac = new AbortController();
    Promise.all([fetchRegions({ body: "earth", role: "analog" }, ac.signal), fetchOptions(ac.signal)])
      .then(async ([regions, opts]) => {
        setEarth(regions.items);
        setOptions(opts);
        const entries = await Promise.all(regions.items.map(async (r) => {
          const res = await fetch(`/api/v1/regions/${encodeURIComponent(r.code)}/geometries`, { signal: ac.signal });
          const rows = (await res.json()) as GeoRow[];
          return [r.code, rows.length ? toGeometry(rows[0]) : null] as const;
        }));
        setGeoms(Object.fromEntries(entries));
      })
      .catch((e) => (e as Error).name !== "AbortError" && setError((e as Error).message));
    return () => ac.abort();
  }, []);

  if (error) return <p role="alert" className="rounded-lg border-2 border-terracotta bg-surface p-4">{error}</p>;
  if (!earth || !options) return <p>{t.explore.loading}</p>;

  const featuredCodes = ["EG-WD-GILF-KEBIR", "EG-WD", "EG-WD-DAKHLA"];
  const egyptian = featuredCodes.map((c) => earth.find((r) => r.code === c)).filter((r): r is RegionSummary => !!r);
  const global = earth.filter((r) => !featuredCodes.includes(r.code));

  return (
    <div className="space-y-10">
      <header className="space-y-2">
        <h1 className="font-serif text-3xl font-semibold">{t.sites.title}</h1>
        <p className="max-w-prose">{t.sites.lead}</p>
      </header>

      <section className="space-y-3" aria-labelledby="eg">
        <h2 id="eg" className="text-xl font-semibold">{t.home.egyptHeading}</h2>
        <div className="grid gap-4 md:grid-cols-3">
          {egyptian.map((r) => <SiteCard key={r.code} r={r} geom={geoms[r.code]} featured={t.featured[r.code]} />)}
        </div>
      </section>

      <section className="space-y-3" aria-labelledby="gl">
        <h2 id="gl" className="text-xl font-semibold">{t.home.globalHeading}</h2>
        <div className="grid gap-4 md:grid-cols-3">
          {global.map((r) => <SiteCard key={r.code} r={r} geom={geoms[r.code]} />)}
        </div>
      </section>

      <section className="space-y-3" aria-labelledby="ref">
        <h2 id="ref" className="text-xl font-semibold">{t.sites.references}</h2>
        <div className="grid gap-4 md:grid-cols-3">
          {options.references.map(({ region, tasks }) => (
            <article key={region.code} className="space-y-2 rounded-lg border-2 border-line bg-surface p-4" data-testid={`site-${region.code}`}>
              <p className="text-xs font-semibold uppercase tracking-wider text-olive">{region.body} · {region.region_level}</p>
              <h3 className="text-lg font-semibold leading-snug">{region.name}</h3>
              <p className="text-xs">{region.geometry ? `${formatCoord(region.geometry)} (gazetteer center)` : `No verified coordinates. ${region.geometry_gap ?? ""}`}</p>
              <p className="text-xs">{tasks.length} task{tasks.length === 1 ? "" : "s"} available ·{" "}
                <Link className="underline" href={`/explore?reference=${encodeURIComponent(region.code)}`}>{t.home.cta}</Link>
              </p>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
