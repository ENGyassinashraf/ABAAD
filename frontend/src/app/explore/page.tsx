import type { Metadata } from "next";
import { Suspense } from "react";
import { ExploreClient } from "@/components/explore/ExploreClient";
import { messages as t } from "@/i18n/en";

export const metadata: Metadata = { title: `${t.explore.title} | ${t.brand.nameLatin}` };

export default function ExplorePage() {
  return (
    <Suspense fallback={<p>{t.explore.loading}</p>}>
      <ExploreClient />
    </Suspense>
  );
}
