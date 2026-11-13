import { messages as t } from "@/i18n/en";

/**
 * Decorative hero art: CSS-only starfield, a stylised planet and two orbit
 * rings. No imagery, no data, no ephemeris — the slow rotation is decoration
 * and stops under prefers-reduced-motion (globals.css).
 */
export function HeroArt() {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true" data-testid="hero-art">
      <div className="abaad-stars abaad-stars--a" />
      <div className="abaad-stars abaad-stars--b" />
      <div className="absolute right-0 top-1/2 hidden h-[30rem] w-[30rem] -translate-y-1/2 md:block lg:h-[34rem] lg:w-[34rem]">
        <div className="abaad-orbit absolute inset-0 rounded-full border border-fg/10">
          <span className="absolute left-1/2 top-0 h-2 w-2 -translate-x-1/2 -translate-y-1/2 rounded-full bg-ochre shadow-[0_0_10px_rgb(210_174_112/0.7)]" />
        </div>
        <div className="abaad-orbit abaad-orbit--slow absolute inset-10 rounded-full border border-dashed border-fg/10">
          <span className="absolute bottom-0 left-1/2 h-1.5 w-1.5 -translate-x-1/2 translate-y-1/2 rounded-full bg-fg/70" />
        </div>
        <div className="abaad-planet absolute inset-24 overflow-hidden rounded-full">
          <div className="abaad-planet__bands absolute inset-0 rounded-full" />
        </div>
      </div>
      <p className="sr-only">{t.home.heroArtNote}</p>
    </div>
  );
}
