import { expect, type Page, test } from "@playwright/test";

// UI/UX upgrade acceptance checks (docs/reports/UI_UX_VISUAL_UPGRADE_COMPLETION.md).
// Map positions are checked numerically against the approved projections,
// not just by looking at screenshots.

type MapProbe = { proj: string; zoom: number; center: { lng: number; lat: number }; jz: { x: number; y: number }; gale: { x: number; y: number } };

async function marsProbe(page: Page): Promise<MapProbe> {
  return page.evaluate(() => {
    const m = (window as unknown as { __abaadMarsProductMap: import("maplibre-gl").Map }).__abaadMarsProductMap;
    return { proj: m.getProjection()!.type as string, zoom: m.getZoom(), center: m.getCenter(), jz: m.project([77.69, 18.41]), gale: m.project([137.7, -5.44]) };
  });
}

async function settled(page: Page) {
  await page.waitForFunction(() => {
    const m = (window as unknown as { __abaadMarsProductMap?: import("maplibre-gl").Map }).__abaadMarsProductMap;
    return !!m && !m.isMoving();
  });
}

test("Mars map uses IAU_2015:49910 and places stored points where the projection says", async ({ page }) => {
  const errors: string[] = [];
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  await page.goto("/explore");
  await page.getByTestId("body-mars").click();
  await expect(page.getByTestId("mars-map")).toHaveAttribute("data-state", "ready");
  await page.getByTestId("ref-MARS-JEZERO-CRATER").click();
  await expect(page.getByTestId("mars-map")).toHaveAttribute("data-selected", "MARS-JEZERO-CRATER");
  await settled(page);

  const p = await marsProbe(page);
  expect(p.proj).toBe("IAU_2015:49910");
  expect(p.center.lng).toBeCloseTo(77.69, 4); // fit-to-selected
  expect(p.center.lat).toBeCloseTo(18.41, 4);
  // ABAAD-MarsEqcQuad: 360° of longitude = 512 · 2^zoom CSS px; 180° of latitude = 256 · 2^zoom.
  const pxPerDeg = (512 * 2 ** p.zoom) / 360;
  expect(Math.abs((p.gale.x - p.jz.x) - (137.7 - 77.69) * pxPerDeg)).toBeLessThan(1);
  expect(Math.abs((p.gale.y - p.jz.y) - (18.41 - -5.44) * pxPerDeg)).toBeLessThan(1);

  // The selected marker's dot is drawn on the projected point (anchor = dot, not label).
  const jz = page.getByTestId("mars-marker-MARS-JEZERO-CRATER");
  await expect(jz).toHaveAttribute("data-selected", "true");
  const box = (await page.getByTestId("mars-map").boundingBox())!;
  const dot = (await jz.locator(".abaad-marker__dot").boundingBox())!;
  expect(Math.abs(dot.x + dot.width / 2 - box.x - p.jz.x)).toBeLessThan(1.5);
  expect(Math.abs(dot.y + dot.height / 2 - box.y - p.jz.y)).toBeLessThan(1.5);

  // Reset view returns to the whole planet.
  await page.getByTestId("mars-reset").click();
  await settled(page);
  const r = await marsProbe(page);
  expect(r.center.lng).toBeCloseTo(0, 4);
  expect(r.center.lat).toBeCloseTo(0, 4);
  // Map → list: clicking a marker selects that region everywhere.
  await page.getByTestId("mars-marker-MARS-GALE-CRATER").click();
  await expect(page).toHaveURL(/reference=MARS-GALE-CRATER/);
  await expect(page.getByTestId("ref-MARS-GALE-CRATER")).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("reference-details")).toContainText("Gale Crater");
  await expect(page.getByTestId("reference-details").getByTestId("precision-badge")).toHaveAttribute("data-precision", "source_traced_point");

  expect(errors).toEqual([]);
});

test("a Mars region without geometry is listed and explained, never placed", async ({ page }) => {
  await page.goto("/explore?reference=MARS-BAGNOLD-DUNES");
  await expect(page.getByTestId("mars-map")).toHaveAttribute("data-state", "ready");
  await expect(page.getByTestId("mars-no-geometry")).toContainText("no verified geometry");
  await expect(page.getByTestId("mars-no-geometry")).toContainText("not this feature's location");
  await expect(page.getByTestId("mars-marker-MARS-BAGNOLD-DUNES")).toHaveCount(0);
  await expect(page.locator(".abaad-marker")).toHaveCount(2); // only Gale and Jezero have stored points
  await expect(page.getByTestId("mars-focus")).toHaveCount(0); // no invented zoom box

  await page.getByTestId("ref-MARS-ARABIA-TERRA").click();
  await expect(page.getByTestId("reference-details").getByTestId("precision-badge")).toHaveAttribute("data-precision", "approximate_outline");
});

test("Mars vector geometry does not depend on any external tile provider", async ({ page }) => {
  await page.route(/^https?:\/\/(?!localhost|127\.0\.0\.1)/, (route) => route.abort());
  await page.goto("/explore?reference=MARS-JEZERO-CRATER");
  await expect(page.getByTestId("mars-map")).toHaveAttribute("data-state", "ready");
  await expect(page.getByTestId("mars-marker-MARS-JEZERO-CRATER")).toBeVisible();
  await expect(page.getByTestId("mars-basemap-note")).toContainText("no validated Mars surface imagery");
});

test("Moon static panel shows Shackleton at its stereographic position and the pole region honestly", async ({ page }) => {
  await page.goto("/explore?reference=MOON-SHACKLETON-CRATER");
  const panel = page.getByTestId("moon-polar-panel");
  await expect(panel).toHaveAttribute("data-extent", "pole");
  const marker = page.getByTestId("moon-marker-MOON-SHACKLETON-CRATER");
  await expect(marker).toHaveAttribute("data-selected", "true");
  // SVG units: centre 220, panel radius 190 to 88° S. Expected from +proj=stere +lat_0=-90 +R=1737400.
  const R = 1737400, rad = Math.PI / 180;
  const rho = (lat: number) => 2 * R * Math.tan(Math.PI / 4 + (lat * rad) / 2);
  const s = 190 / rho(-88);
  const ex = 220 + rho(-89.67) * Math.sin(129.78 * rad) * s;
  const ey = 220 - rho(-89.67) * Math.cos(129.78 * rad) * s;
  const c = marker.locator("circle").first();
  expect(Number(await c.getAttribute("cx"))).toBeCloseTo(ex, 2);
  expect(Number(await c.getAttribute("cy"))).toBeCloseTo(ey, 2);

  await page.getByTestId("moon-extent-wide").click();
  await expect(panel).toHaveAttribute("data-extent", "wide");
  await page.getByTestId("ref-MOON-SOUTH-POLE").click();
  await expect(page.getByTestId("moon-no-geometry")).toContainText("no boundary is drawn");
});

test("score, coverage and evidence quality are separate; unranked candidates have no score or rank", async ({ page }) => {
  await page.goto("/explore?reference=MARS-GALE-CRATER&task=shallow_subsurface_gpr");
  await expect(page.getByTestId("research-question")).toContainText("Shallow subsurface");
  await expect(page.getByTestId("research-question")).toContainText("Gale Crater");
  const gk = page.getByTestId("candidate-EG-WD-GILF-KEBIR");
  await expect(gk).toHaveAttribute("data-status", "insufficient_evidence");
  await expect(gk.getByTestId("rank-badge")).toHaveCount(0);
  await expect(gk.getByTestId("status-pill")).toHaveText("Not ranked — insufficient evidence");
  await expect(gk.getByTestId("score-value")).toHaveText("Not computed");
  await expect(gk.getByTestId("coverage-value")).toHaveText("10.0 / 100");
  await expect(gk.getByTestId("status-reason")).toContainText("threshold 50 %");
  await expect(gk.getByTestId("evidence-quality")).toBeVisible();

  await page.goto("/explore?reference=MARS-BAGNOLD-DUNES&task=aeolian_geomorphology");
  const wd = page.getByTestId("candidate-EG-WD");
  await expect(wd.getByTestId("score-value")).toHaveText("64.3 / 100");
  await expect(wd.getByTestId("coverage-value")).toHaveText("70.0 / 100");
  await expect(wd.getByTestId("evidence-class")).toContainText("Class B");
  const summary = wd.getByTestId("dimension-summary");
  await expect(summary).toContainText("Surface processes"); // close → similarity, from the backend rubric level
  await wd.getByRole("button", { name: "Show evidence" }).click();
  await expect(wd.getByTestId("next-measurement")).toContainText("Research suggestion");
  await expect(wd.locator("table caption")).toContainText("unitless similarity");
});

test("reduced motion stops the decorative hero animation", async ({ browser }) => {
  const ctx = await browser.newContext({ reducedMotion: "reduce" });
  const page = await ctx.newPage();
  await page.goto("/");
  const anim = await page.locator(".abaad-stars--a").evaluate((el) => getComputedStyle(el).animationName);
  expect(anim).toBe("none");
  const planet = await page.locator(".abaad-planet__bands").evaluate((el) => getComputedStyle(el).animationName);
  expect(planet).toBe("none");
  await ctx.close();

  const ctx2 = await browser.newContext({ reducedMotion: "no-preference" });
  const p2 = await ctx2.newPage();
  await p2.goto("/");
  expect(await p2.locator(".abaad-stars--a").evaluate((el) => getComputedStyle(el).animationName)).not.toBe("none");
  await ctx2.close();
});

test("brand lockup and no horizontal overflow at mobile width", async ({ browser }) => {
  const ctx = await browser.newContext({ viewport: { width: 375, height: 812 } });
  const page = await ctx.newPage();
  // Waits for app content, not "networkidle": the Earth basemap streams tiles from an
  // external provider, and layout overflow must not depend on that provider's speed.
  const ready: Record<string, string> = { "/": "api-status", "/explore?reference=MARS-BAGNOLD-DUNES&task=aeolian_geomorphology": "candidate-EG-WD", "/sites": "site-EG-WD" };
  for (const [path, id] of Object.entries(ready)) {
    await page.goto(path);
    await expect(page.getByTestId(id)).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow, path).toBeLessThanOrEqual(0);
  }
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("أبعاد");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Different Dimensions. One Connection.");
  await ctx.close();
});
