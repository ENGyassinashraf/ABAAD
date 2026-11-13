import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import { Wordmark } from "@/components/Wordmark";
import { NavLinks } from "@/components/shell/NavLinks";
import { messages as t } from "@/i18n/en";

export const metadata: Metadata = {
  title: `${t.brand.nameLatin} | ${t.brand.nameArabic} — ${t.brand.descriptor}`,
  description: `${t.brand.slogan} ${t.brand.descriptor}.`,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" dir="ltr">
      <body className="min-h-screen font-sans text-fg antialiased">
        <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:m-2 focus:rounded focus:bg-raised focus:p-2">
          Skip to content
        </a>
        <div className="lg:grid lg:min-h-screen lg:grid-cols-[15rem_minmax(0,1fr)]">
          {/* Desktop rail */}
          <aside className="hidden border-r border-line bg-bg-deep/70 print:hidden lg:block">
            <div className="sticky top-0 flex h-screen flex-col gap-8 px-4 py-6">
              <Link href="/" className="px-2 no-underline"><Wordmark /></Link>
              <nav aria-label={t.nav.label}><NavLinks orientation="vertical" /></nav>
              <div className="mt-auto space-y-3 px-2 text-[11px] text-muted">
                <p className="font-serif text-xs italic text-fg-2">{t.brand.slogan}</p>
                <Link href="/dev/map-spike" className="block underline-offset-4 hover:text-fg-2 hover:underline">{t.nav.mapSpike}</Link>
              </div>
            </div>
          </aside>

          <div className="flex min-h-screen min-w-0 flex-col">
            {/* Compact top bar below lg */}
            <header className="sticky top-0 z-30 border-b border-line bg-bg/90 backdrop-blur print:hidden lg:hidden">
              <div className="flex items-center justify-between gap-3 px-4 pt-3">
                <Link href="/" className="no-underline"><Wordmark /></Link>
              </div>
              <nav aria-label={t.nav.label} className="px-2 pb-1 pt-2"><NavLinks orientation="horizontal" /></nav>
            </header>

            <main id="main" className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 sm:px-6 lg:px-10">{children}</main>

            <footer className="border-t border-line print:hidden">
              <div className="mx-auto flex max-w-6xl flex-wrap items-baseline justify-between gap-x-6 gap-y-2 px-4 py-4 text-xs text-muted sm:px-6 lg:px-10">
                <span>
                  <span className="font-semibold text-fg-2">{t.brand.nameLatin} | <span lang="ar" dir="rtl">{t.brand.nameArabic}</span></span>
                  {" · "}{t.brand.slogan}{" · "}{t.brand.descriptor}
                </span>
                <span>{t.footer.phase}</span>
                <span>{t.brand.temporaryWordmark}</span>
              </div>
            </footer>
          </div>
        </div>
      </body>
    </html>
  );
}
