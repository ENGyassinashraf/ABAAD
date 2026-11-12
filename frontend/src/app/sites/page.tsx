import type { Metadata } from "next";
import { SitesClient } from "@/components/sites/SitesClient";
import { messages as t } from "@/i18n/en";

export const metadata: Metadata = { title: `${t.sites.title} | ${t.brand.nameLatin}` };

export default function SitesPage() {
  return <SitesClient />;
}
