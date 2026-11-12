import { messages as t } from "@/i18n/en";

/**
 * Bilingual text lockup (decision D5: temporary text wordmark — the approved
 * logo is not recreated). ABAAD dominates; أبعاد is its RTL counterpart in its
 * own span; the slogan and descriptor appear only where `size="hero"`.
 */
export function Wordmark({ size = "nav", large = false }: { size?: "nav" | "hero"; large?: boolean }) {
  const hero = size === "hero" || large;
  return (
    <span className="inline-flex flex-col gap-2" aria-label={`${t.brand.nameLatin} ${t.brand.nameArabic}`}>
      <span className="inline-flex items-center gap-3 font-serif leading-none">
        <span className={`font-semibold tracking-[0.14em] text-fg ${hero ? "text-[2.6rem] sm:text-7xl" : "text-xl"}`}>{t.brand.nameLatin}</span>
        <span aria-hidden="true" className={`block w-px self-stretch bg-ochre/70 ${hero ? "my-1" : ""}`} />
        <span lang="ar" dir="rtl" className={`font-arabic text-ochre ${hero ? "text-[2.6rem] sm:text-7xl" : "text-xl"}`}>{t.brand.nameArabic}</span>
      </span>
      {!hero && <span className="text-[10px] font-medium uppercase tracking-[0.18em] text-muted">{t.brand.descriptor}</span>}
    </span>
  );
}
