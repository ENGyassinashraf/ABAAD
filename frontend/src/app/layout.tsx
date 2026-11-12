import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import { Wordmark } from "@/components/Wordmark";
import { messages as t } from "@/i18n/en";

export const metadata: Metadata = {
  title: `${t.brand.nameLatin} | ${t.brand.nameArabic} — ${t.brand.descriptor}`,
  description: t.brand.slogan,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" dir="ltr">
      <body className="flex min-h-screen flex-col font-sans">
        <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:m-2 focus:rounded focus:bg-ivory focus:p-2">
          Skip to content
        </a>
        <header className="border-b-2 border-olive bg-ivory print:hidden">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-4 py-3">
            <Link href="/" className="no-underline">
              <Wordmark />
            </Link>
            <nav aria-label={t.nav.label}>
              <ul className="flex gap-4 text-sm font-medium">
                <li><Link className="underline-offset-4 hover:underline" href="/">{t.nav.home}</Link></li>
                <li><Link className="underline-offset-4 hover:underline" href="/explore">{t.nav.explore}</Link></li>
                <li><Link className="underline-offset-4 hover:underline" href="/sites">{t.nav.sites}</Link></li>
                <li><Link className="underline-offset-4 hover:underline" href="/dev/map-spike">{t.nav.mapSpike}</Link></li>
              </ul>
            </nav>
          </div>
        </header>
        <main id="main" className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">{children}</main>
        <footer className="border-t border-border-soft bg-ivory print:hidden">
          <div className="mx-auto flex max-w-6xl flex-wrap justify-between gap-2 px-4 py-3 text-xs">
            <span>{t.footer.phase}</span>
            <span>{t.brand.temporaryWordmark}</span>
          </div>
        </footer>
      </body>
    </html>
  );
}
