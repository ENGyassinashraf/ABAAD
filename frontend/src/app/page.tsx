import { ApiStatus } from "@/components/ApiStatus";
import { Wordmark } from "@/components/Wordmark";
import { messages as t } from "@/i18n/en";

export default function HomePage() {
  return (
    <div className="space-y-8">
      <section className="space-y-3">
        <h1>
          <Wordmark large />
        </h1>
        <p className="text-xl font-serif">{t.brand.slogan}</p>
        <p className="text-sm font-semibold uppercase tracking-wider text-olive">{t.brand.descriptor}</p>
        <p className="max-w-prose">{t.home.intro}</p>
      </section>
      <p className="rounded-lg border-2 border-terracotta bg-ivory p-4 text-sm" data-testid="phase-notice">
        {t.home.phaseNotice}
      </p>
      <section aria-labelledby="status-heading" className="space-y-3">
        <h2 id="status-heading" className="text-lg font-semibold">{t.home.statusHeading}</h2>
        <ApiStatus />
      </section>
    </div>
  );
}
