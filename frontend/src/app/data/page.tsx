import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = { title: "Open data — ABAAD | أبعاد" };

type Status = "in use" | "registered" | "planned";
type Res = { name: string; agency: string; url: string; what: string; use: string; status: Status; where?: [string, string] };

// Resources listed by the NASA Space Apps 2026 challenge "Identify Earth Locations that
// Analog the Permanent Moon Base Locations and Mars", and how ABAAD uses each today.
const GROUPS: { title: string; items: Res[] }[] = [
  {
    title: "Earth",
    items: [
      { name: "NASA Worldview / GIBS", agency: "NASA", url: "https://worldview.earthdata.nasa.gov/", status: "in use",
        what: "Global satellite imagery served as map tiles.", where: ["/explore", "Explore map"],
        use: "Basemaps behind the Earth candidate map: Blue Marble shaded relief and recent MODIS Terra true colour. Context only — not used for scoring." },
      { name: "NASA Earthdata Search", agency: "NASA", url: "https://search.earthdata.nasa.gov/", status: "planned",
        what: "Discovery and download of NASA Earth-science observations.",
        use: "Next source for Earth-side measurements (surface temperature, elevation, aerosols) to fill criteria that are still unassessed." },
      { name: "Copernicus Data Space Ecosystem", agency: "ESA", url: "https://dataspace.copernicus.eu/", status: "registered",
        what: "Sentinel data and the Copernicus DEM.", where: ["/sites", "Dataset DS-01"],
        use: "Copernicus DEM GLO-30 is registered as dataset DS-01 (EPSG:4326, EGM2008). Tiles are downloaded with `make ingest` on the owner's machine." },
      { name: "ESA Open Science Catalog", agency: "ESA", url: "https://opensciencedata.esa.int/", status: "planned",
        what: "Catalogue of open geoscience datasets and workflows.", use: "Discovery of additional Earth datasets for new analog dimensions." },
      { name: "RADARSAT-1 and RADARSAT Constellation Mission", agency: "CSA", url: "https://donnees-data.asc-csa.gc.ca/en/dataset/radarsat1", status: "planned",
        what: "C-band synthetic aperture radar, day/night, all weather (RADARSAT-1 archive under an open licence).",
        use: "Radar roughness and sand-penetration context for the Egyptian sites (shallow-subsurface / GPR task)." },
      { name: "SAR Python tutorial", agency: "CSA", url: "https://github.com/asc-csa/Synthetic_Aperture_Radar_Tutorial", status: "planned",
        what: "Worked examples for reading and visualising SAR imagery.", use: "Reference for the RADARSAT processing step." },
      { name: "JAXA G-Portal", agency: "JAXA", url: "https://gportal.jaxa.jp/gpr/index/index", status: "planned",
        what: "Earth-observation products from JAXA missions.", use: "Candidate source for additional Earth variables (snow, vegetation, precipitation) when a task needs them." },
    ],
  },
  {
    title: "Moon and Mars",
    items: [
      { name: "NASA Planetary Data System (PDS)", agency: "NASA", url: "https://pds.nasa.gov/", status: "registered",
        what: "NASA's archive of planetary mission data.", where: ["/sites", "Datasets DS-03, DS-04, DS-05"],
        use: "MOLA MEGDR (Mars topography) and LOLA GDR (lunar south-polar elevation) are registered with provenance; their CRS stays pending until the product labels are read." },
      { name: "Lunar Reconnaissance Orbiter — LOLA", agency: "NASA", url: "https://pds-geosciences.wustl.edu/missions/lro/", status: "registered",
        what: "Laser-altimeter elevation of the Moon, including polar products.", where: ["/mission-lab", "Mission Lab"],
        use: "LDEM_80S_80M (south of 80°S) is registered as DS-05. Next: replace the Mission Lab's synthetic training terrain with a real LOLA clip near the South Pole." },
      { name: "LRO Diviner lunar radiometer", agency: "NASA", url: "https://pds-geosciences.wustl.edu/missions/lro/diviner.htm", status: "planned",
        what: "Lunar surface temperatures, with polar and resource products.",
        use: "Temperature dimension for lunar-base analogs: compare polar cold traps with cold, ice-bearing Earth environments." },
    ],
  },
];

const TONE: Record<Status, string> = {
  "in use": "border-ok text-ok",
  registered: "border-ochre text-ochre",
  planned: "border-line-strong text-muted",
};

export default function OpenDataPage() {
  return (
    <div className="space-y-10">
      <header className="space-y-3">
        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-ochre">ABAAD · Open data</p>
        <h1 className="font-serif text-4xl font-semibold">Data behind ABAAD</h1>
        <p className="max-w-3xl text-fg-2">
          The open Earth, Moon and Mars resources named by the NASA Space Apps 2026 challenge{" "}
          <a className="text-ochre underline" href="https://www.spaceappschallenge.org/2026/challenges/permanent-moon-base-locations-and-mars/" target="_blank" rel="noreferrer">
            “Identify Earth Locations that Analog the Permanent Moon Base Locations and Mars”
          </a>
          , and exactly how far ABAAD uses each one today.
        </p>
        <ul className="flex flex-wrap gap-3 text-xs">
          {(Object.keys(TONE) as Status[]).map((s) => (
            <li key={s} className={`rounded-full border px-2.5 py-0.5 font-semibold uppercase tracking-wider ${TONE[s]}`}>{s}</li>
          ))}
          <li className="text-muted">in use = live in the app · registered = provenance stored, files downloaded on demand · planned = not used yet</li>
        </ul>
      </header>
      {GROUPS.map((g) => (
        <section key={g.title} className="space-y-4" aria-labelledby={`g-${g.title}`}>
          <h2 id={`g-${g.title}`} className="font-serif text-2xl font-semibold">{g.title}</h2>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {g.items.map((r) => (
              <article key={r.name} data-testid="data-resource" data-status={r.status}
                className="flex flex-col gap-3 rounded-xl border border-line bg-surface p-5 transition-colors hover:border-line-strong hover:bg-raised">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-wider text-muted">{r.agency}</p>
                    <h3 className="text-lg font-semibold leading-snug">
                      <a href={r.url} target="_blank" rel="noreferrer" className="text-fg no-underline hover:text-ochre">{r.name} ↗</a>
                    </h3>
                  </div>
                  <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${TONE[r.status]}`}>{r.status}</span>
                </div>
                <p className="text-sm text-fg-2">{r.what}</p>
                <p className="text-sm"><span className="font-semibold text-fg">In ABAAD: </span><span className="text-fg-2">{r.use}</span></p>
                {r.where && <Link href={r.where[0]} className="mt-auto text-xs text-ochre underline">{r.where[1]} →</Link>}
              </article>
            ))}
          </div>
        </section>
      ))}
      <p className="text-xs text-muted">NASA does not endorse ABAAD. Each provider&apos;s own data-use terms apply.</p>
    </div>
  );
}
