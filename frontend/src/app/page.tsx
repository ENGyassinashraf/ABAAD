import Link from "next/link";
import { ApiStatus } from "@/components/ApiStatus";
import { HeroArt } from "@/components/home/HeroArt";
import { Wordmark } from "@/components/Wordmark";
import { messages as t } from "@/i18n/en";

const FEATURED_LINKS: Record<string, string> = {
  "EG-WD-GILF-KEBIR": "/explore?reference=MARS-JEZERO-CRATER&task=shallow_subsurface_gpr",
  "EG-WD": "/explore?reference=MARS-BAGNOLD-DUNES&task=aeolian_geomorphology",
  "EG-WD-DAKHLA": "/explore?reference=MARS-JEZERO-CRATER&task=fluvial_paleohydrology",
};

const TASK_OF: Record<string, string> = {
  "EG-WD-GILF-KEBIR": "Shallow subsurface / GPR",
  "EG-WD": "Aeolian geomorphology",
  "EG-WD-DAKHLA": "Fluvial paleohydrology",
};

export default function HomePage() {
  return (
    <div className="space-y-16">
      <section className="relative overflow-hidden rounded-2xl border border-line bg-bg-deep px-5 py-12 sm:px-10 lg:py-16">
        <HeroArt />
        <div className="relative max-w-2xl space-y-6 animate-reveal">
          <h1 className="space-y-4">
            <Wordmark size="hero" />
            <span className="block font-serif text-2xl text-fg sm:text-3xl">{t.brand.slogan}</span>
          </h1>
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-ochre">{t.brand.descriptor}</p>
          <div className="space-y-3 pt-2">
            <p className="text-2xl font-semibold leading-snug text-fg sm:text-3xl">{t.home.heroTitle}</p>
            <p className="max-w-xl text-base text-fg-2 sm:text-lg">{t.home.heroLead}</p>
          </div>
          <div className="flex flex-wrap gap-3 pt-2">
            <Link href="/sites" data-testid="cta-sites"
              className="rounded-lg bg-ochre px-5 py-2.5 font-semibold text-on-accent no-underline transition-transform duration-150 hover:-translate-y-0.5">{t.home.ctaPrimary}</Link>
            <Link href="/explore" data-testid="cta-explore"
              className="rounded-lg border border-line-strong bg-surface/70 px-5 py-2.5 font-semibold text-fg no-underline transition-colors duration-150 hover:border-ochre hover:bg-hover">{t.home.ctaSecondary}</Link>
          </div>
          <p className="text-[11px] text-muted">{t.home.heroArtNote}</p>
        </div>
      </section>

      <p className="max-w-3xl rounded-xl border border-terracotta/60 bg-surface p-4 text-sm text-fg-2" data-testid="phase-notice">
        {t.home.phaseNotice}
      </p>

      <section aria-labelledby="eg-heading" className="space-y-5">
        <div className="flex flex-wrap items-end justify-between gap-2">
          <h2 id="eg-heading" className="font-serif text-2xl font-semibold">{t.home.egyptHeading}</h2>
          <Link className="text-sm text-ochre underline" href="/sites">{t.home.ctaSites}</Link>
        </div>
        <div className="grid gap-4 md:grid-cols-3">
          {Object.entries(t.featured).map(([code, f]) => (
            <Link key={code} href={FEATURED_LINKS[code]} data-testid={`featured-${code}`}
              className="group relative flex flex-col gap-3 overflow-hidden rounded-xl border border-line bg-surface p-5 no-underline transition duration-200 hover:-translate-y-0.5 hover:border-ochre/70 hover:bg-raised">
              <span aria-hidden="true" className="absolute inset-x-0 top-0 h-0.5 bg-gradient-to-r from-terracotta via-ochre to-olive opacity-70" />
              <p className="text-[11px] font-semibold uppercase tracking-wider text-ochre">Egypt · {TASK_OF[code]}</p>
              <h3 className="text-lg font-semibold leading-snug text-fg">{f.title}</h3>
              <p className="text-sm text-fg-2">{f.blurb}</p>
              <p className="mt-auto text-xs text-muted">vs {f.reference} <span aria-hidden="true" className="inline-block transition-transform group-hover:translate-x-1">→</span></p>
            </Link>
          ))}
        </div>
        <p className="text-sm text-fg-2">
          {t.home.globalHeading}: Atacama (Yungay, ARADS drilling site), McMurdo Dry Valleys (University Valley) and Holuhraun, Iceland.
        </p>
      </section>

      <section aria-labelledby="modules-heading" className="space-y-5">
        <h2 id="modules-heading" className="font-serif text-2xl font-semibold">{t.home.modulesHeading}</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {t.home.modules.map(([title, body, href]) => (
            <Link key={title} href={href} className="space-y-2 rounded-xl border border-line bg-surface p-4 no-underline transition-colors duration-150 hover:border-line-strong hover:bg-raised">
              <p className="font-semibold text-fg">{title}</p>
              <p className="text-sm text-fg-2">{body}</p>
            </Link>
          ))}
        </div>
      </section>

      <section aria-labelledby="journey-heading" className="space-y-5">
        <h2 id="journey-heading" className="font-serif text-2xl font-semibold">{t.home.journeyHeading}</h2>
        <ol className="grid gap-3 md:grid-cols-5">
          {t.home.journey.map(([title, body], i) => (
            <li key={title} className="relative space-y-1 rounded-xl border border-line bg-surface p-4">
              <span className="font-serif text-2xl text-terracotta">{String(i + 1).padStart(2, "0")}</span>
              <p className="font-semibold">{title}</p>
              <p className="text-xs text-fg-2">{body}</p>
            </li>
          ))}
        </ol>
      </section>

      <div className="grid gap-8 md:grid-cols-2">
        <section aria-labelledby="not-heading" className="space-y-3">
          <h2 id="not-heading" className="font-serif text-xl font-semibold">{t.home.notHeading}</h2>
          <ul className="list-disc space-y-1 pl-5 text-sm text-fg-2">{t.home.not.map((x) => <li key={x}>{x}</li>)}</ul>
        </section>
        <section aria-labelledby="status-heading" className="space-y-3">
          <h2 id="status-heading" className="font-serif text-xl font-semibold">{t.home.statusHeading}</h2>
          <ApiStatus />
        </section>
      </div>
    </div>
  );
}
