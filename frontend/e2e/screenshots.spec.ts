import { expect, test } from "@playwright/test";

// Captures the screenshots referenced by docs/reports/UI_UX_VISUAL_UPGRADE_COMPLETION.md.
// Runs only with ABAAD_SCREENSHOTS=1 so a normal test run never rewrites committed files.
const OUT = "../docs/reports/ui-screenshots";
test.skip(process.env.ABAAD_SCREENSHOTS !== "1", "screenshot capture runs only with ABAAD_SCREENSHOTS=1");

const shots: { name: string; path: string; w: number; h: number; ready?: string; scrollTo?: string; click?: string[]; motion?: "reduce" }[] = [
  { name: "01-home-desktop", path: "/", w: 1440, h: 900 },
  { name: "02-home-mobile", path: "/", w: 375, h: 812 },
  { name: "03-mars-full-view", path: "/explore", w: 1440, h: 900, ready: "mars-map", scrollTo: "step2" },
  { name: "04-mars-selected-jezero", path: "/explore?reference=MARS-JEZERO-CRATER", w: 1440, h: 900, ready: "mars-map", scrollTo: "step2" },
  { name: "05-mars-approx-outline-arabia", path: "/explore?reference=MARS-ARABIA-TERRA", w: 1440, h: 900, ready: "mars-map", scrollTo: "step2" },
  { name: "06-mars-no-geometry-bagnold", path: "/explore?reference=MARS-BAGNOLD-DUNES", w: 1440, h: 900, ready: "mars-map", scrollTo: "step2" },
  { name: "07-moon-shackleton", path: "/explore?reference=MOON-SHACKLETON-CRATER", w: 1440, h: 900, scrollTo: "step2" },
  { name: "08-compare-sufficient-evidence", path: "/explore?reference=MARS-BAGNOLD-DUNES&task=aeolian_geomorphology", w: 1440, h: 1100, scrollTo: "results" },
  { name: "09-compare-evidence-details", path: "/explore?reference=MARS-JEZERO-CRATER&task=shallow_subsurface_gpr", w: 1440, h: 1400, scrollTo: "candidate-EG-WD-GILF-KEBIR", click: ["candidate-EG-WD-GILF-KEBIR"] },
  { name: "10-compare-insufficient-evidence", path: "/explore?reference=MARS-GALE-CRATER&task=shallow_subsurface_gpr", w: 1440, h: 1000, scrollTo: "results" },
  { name: "11-compare-moon-mismatch", path: "/explore?reference=MOON-SOUTH-POLE&task=rover_mobility", w: 1440, h: 1000, scrollTo: "results" },
  { name: "12-compare-mobile", path: "/explore?reference=MARS-BAGNOLD-DUNES&task=aeolian_geomorphology", w: 375, h: 812, scrollTo: "candidate-EG-WD" },
  { name: "13-compare-error-state", path: "/explore?reference=MOON-SOUTH-POLE&task=aeolian_geomorphology", w: 1440, h: 900, scrollTo: "compare-error" },
  { name: "14-sites-desktop", path: "/sites", w: 1440, h: 900 },
  { name: "15-home-reduced-motion", path: "/", w: 1440, h: 900, motion: "reduce" },
];

for (const s of shots) {
  test(`screenshot ${s.name}`, async ({ browser }) => {
    const ctx = await browser.newContext({ viewport: { width: s.w, height: s.h }, reducedMotion: s.motion ?? "no-preference" });
    const page = await ctx.newPage();
    await page.goto(s.path);
    await page.waitForLoadState("networkidle");
    if (s.ready) await expect(page.getByTestId(s.ready)).toHaveAttribute("data-state", "ready");
    for (const id of s.click ?? []) await page.getByTestId(id).getByRole("button", { name: "Show evidence" }).click();
    if (s.scrollTo) {
      const el = (await page.getByTestId(s.scrollTo).count()) ? page.getByTestId(s.scrollTo) : page.locator(`#${s.scrollTo}`);
      await el.first().evaluate((n) => { n.scrollIntoView({ block: "start" }); window.scrollBy(0, -24); });
    }
    await page.waitForTimeout(900);
    await page.screenshot({ path: `${OUT}/${s.name}.png` });
    await ctx.close();
  });
}
