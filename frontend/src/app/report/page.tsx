import type { Metadata } from "next";
import { Suspense } from "react";
import { ReportClient } from "@/components/report/ReportClient";
import { messages as t } from "@/i18n/en";

export const metadata: Metadata = { title: `${t.report.title} | ${t.brand.nameLatin}` };

export default function ReportPage() {
  return (
    <Suspense fallback={<p>{t.explore.loading}</p>}>
      <ReportClient />
    </Suspense>
  );
}
