import Link from "next/link";
import { ApiStatus } from "@/components/ApiStatus";
import { Wordmark } from "@/components/Wordmark";
import { messages as t } from "@/i18n/en";

const FEATURED_LINKS: Record<string, string> = {
  "EG-WD-GILF-KEBIR": "/explore?reference=MARS-JEZERO-CRATER&task=shallow_subsurface_gpr",
  "EG-WD": "/explore?reference=MARS-BAGNOLD-DUNES&task=aeolian_geomorphology",
  "EG-WD-DAKHLA": "/explore?reference=MARS-JEZERO-CRATER&task=fluvial_paleohydrology",
};

export default function HomePage() {
  return (
    <div className="space-y-12">
      <section className="space-y-4">
        <h1>
          <Wordmark large />
        </h1>
        <p className="font-serif text-2xl">{t.brand.slogan}</p>
        <p className="text-sm font-semibold uppercase tracking-wider text-olive">{t.brand.descriptor}</p>
        <p className="max-w-prose text-lg">{t.home.intro}</p>
        <div className="flex flex-wrap gap-3 pt-2">
          <Link href="/explore" data-testid="cta-explore"
            className="rounded-lg border-2 border-olive bg-olive px-5 py-2.5 font-semibold text-ivory no-underline hover:bg-earth">{t.home.cta}</Link>
          <Link href="/sites" className="rounded-lg border-2 border-olive bg-ivory px-5 py-2.5 font-semibold no-underline hover:bg-sand">{t.home.ctaSites}</Link>
        </div>
      </section>

      <p className="max-w-3xl rounded-lg border-2 border-terracotta bg-ivory p-4 text-sm" data-testid="phase-notice">
        {t.home.phaseNotice}
      </p>

      <section aria-labelledby="eg-heading" className="space-y-4">
        <h2 id="eg-heading" className="text-xl font-semibold">{t.home.egyptHeading}</h2>
        <div className="grid gap-4 md:grid-cols-3">
          {Object.entries(t.featured).map(([code, f]) => (
            <Link key={code} href={FEATURED_LINKS[code]} data-testid={`featured-${code}`}
              className="group space-y-2 rounded-lg border-2 border-olive/40 bg-ivory p-4 no-underline hover:border-olive">
              <p className="text-xs font-semibold uppercase tracking-wider text-olive">Egypt · vs {f.reference}</p>
              <h3 className="text-lg font-semibold leading-snug group-hover:underline">{f.title}</h3>
              <p className="text-sm">{f.blurb}</p>
            </Link>
          ))}
        </div>
        <p className="text-sm">
          {t.home.globalHeading}: Atacama (Yungay, ARADS drilling site), McMurdo Dry Valleys (University Valley) and Holuhraun, Iceland —{" "}
          <Link className="underline" href="/sites">{t.home.ctaSites}</Link>.
        </p>
      </section>

      <section aria-labelledby="journey-heading" className="space-y-4">
        <h2 id="journey-heading" className="text-xl font-semibold">{t.home.journeyHeading}</h2>
        <ol className="grid gap-3 md:grid-cols-5">
          {t.home.journey.map(([title, body], i) => (
            <li key={title} className="space-y-1 rounded-lg border border-border-soft bg-ivory p-3">
              <span className="text-xs font-semibold text-terracotta">{i + 1}</span>
              <p className="font-semibold">{title}</p>
              <p className="text-xs">{body}</p>
            </li>
          ))}
        </ol>
      </section>

      <section aria-labelledby="not-heading" className="space-y-2">
        <h2 id="not-heading" className="text-xl font-semibold">{t.home.notHeading}</h2>
        <ul className="list-disc space-y-1 pl-5 text-sm">{t.home.not.map((x) => <li key={x}>{x}</li>)}</ul>
      </section>

      <section aria-labelledby="status-heading" className="space-y-3">
        <h2 id="status-heading" className="text-lg font-semibold">{t.home.statusHeading}</h2>
        <ApiStatus />
      </section>
    </div>
  );
}
