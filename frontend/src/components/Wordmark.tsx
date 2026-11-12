import { messages as t } from "@/i18n/en";

/** Clearly temporary text wordmark (decision D5). The official logo is not recreated. */
export function Wordmark({ large = false }: { large?: boolean }) {
  return (
    <span className="inline-flex items-baseline gap-2 font-serif" aria-label={`${t.brand.nameLatin} ${t.brand.nameArabic}`}>
      <span className={large ? "text-5xl font-semibold tracking-wide" : "text-xl font-semibold tracking-wide"}>
        {t.brand.nameLatin}
      </span>
      <span aria-hidden="true" className="text-olive">|</span>
      <span lang="ar" dir="rtl" className={large ? "text-5xl" : "text-xl"}>
        {t.brand.nameArabic}
      </span>
    </span>
  );
}
