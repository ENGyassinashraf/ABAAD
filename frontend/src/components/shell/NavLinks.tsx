"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { messages as t } from "@/i18n/en";

const LINKS = [
  { href: "/", label: t.nav.home, icon: "M3 11.5 12 4l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z" },
  { href: "/explore", label: t.nav.explore, icon: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Zm4 5-2.5 5.5L8 16l2.5-5.5z" },
  { href: "/mission-lab", label: t.nav.missionLab, icon: "M12 2 4 7v10l8 5 8-5V7zm0 4.3 4.5 2.8v5.8L12 17.7l-4.5-2.8V9.1z" },
  { href: "/data", label: "Open data", icon: "M12 3c4.4 0 8 1.3 8 3s-3.6 3-8 3-8-1.3-8-3 3.6-3 8-3Zm-8 3v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3" },
  { href: "/sites", label: t.nav.sites, icon: "M12 21s-6-5.3-6-10a6 6 0 1 1 12 0c0 4.7-6 10-6 10Zm0-8a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z" },
];

/** Primary navigation; the active section is marked with aria-current and a visible bar. */
export function NavLinks({ orientation }: { orientation: "vertical" | "horizontal" }) {
  const path = usePathname();
  const vertical = orientation === "vertical";
  return (
    <ul className={vertical ? "space-y-1" : "flex gap-1 overflow-x-auto"}>
      {LINKS.map((l) => {
        const active = l.href === "/" ? path === "/" : path.startsWith(l.href) || (l.href === "/explore" && path.startsWith("/report"));
        return (
          <li key={l.href}>
            <Link href={l.href} aria-current={active ? "page" : undefined}
              className={`group flex items-center rounded-lg py-2 ${vertical ? "gap-3 px-3" : "gap-2 px-2.5"} text-sm font-medium no-underline transition-colors duration-150 ${
                active ? "bg-raised text-fg" : "text-fg-2 hover:bg-raised hover:text-fg"} ${vertical ? "border-l-2" : "border-b-2 whitespace-nowrap"} ${
                active ? "border-ochre" : "border-transparent"}`}>
              <svg aria-hidden="true" viewBox="0 0 24 24" className={`h-4 w-4 shrink-0 ${active ? "text-ochre" : "text-muted group-hover:text-fg-2"}`}
                fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round"><path d={l.icon} /></svg>
              {l.label}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
