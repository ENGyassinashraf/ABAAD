import { expect, test } from "@playwright/test";

// Full user journey (Project & Scientific Guide §03, §13, §14): select a
// target and reference region, select a task, compare, review, export.
// The e2e backend loads the committed curation data, so these numbers are
// the real curated results, not fixtures.

test("featured Western Desert card opens the Bagnold Dunes aeolian comparison", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("featured-EG-WD").click();
  await expect(page).toHaveURL(/reference=MARS-BAGNOLD-DUNES&task=aeolian_geomorphology/);
  const wd = page.getByTestId("candidate-EG-WD");
  await expect(wd).toHaveAttribute("data-status", "ranked");
  await expect(wd.getByTestId("rank-badge")).toHaveText("Rank 1");
  await expect(wd.getByTestId("score-value")).toHaveText("64.3 / 100");
  await expect(wd.getByTestId("coverage-value")).toHaveText("70.0 / 100");
});

test("click-through: Mars → Jezero → GPR ranks Gilf Kebir, evidence is traceable, report exports", async ({ page }) => {
  const errors: string[] = [];
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  await page.goto("/explore");
  await page.getByTestId("body-mars").click();
  await page.getByTestId("ref-MARS-JEZERO-CRATER").click();
  await page.getByTestId("task-shallow_subsurface_gpr").click();

  const gk = page.getByTestId("candidate-EG-WD-GILF-KEBIR");
  await expect(gk).toHaveAttribute("data-status", "ranked");
  await expect(gk.getByTestId("score-value")).toHaveText("45.0 / 100");
  await expect(gk).toContainText("Origin disputed");

  await gk.getByRole("button", { name: "Show evidence" }).click();
  const sub = gk.getByTestId("dim-subsurface");
  await expect(sub).toContainText("Partial");
  await expect(sub).toContainText("NASA's Perseverance Makes New Discoveries");
  await expect(gk.getByTestId("dim-geology_materials")).toContainText("unknown");

  // Map receives the candidates that have a stored point (data independent of tile loading).
  await expect(page.getByTestId("candidate-map")).toHaveAttribute("data-points", "3");

  await page.getByTestId("open-report").click();
  await expect(page).toHaveURL(/\/report\?reference=MARS-JEZERO-CRATER&task=shallow_subsurface_gpr/);
  await expect(page.getByTestId("report-summary")).toContainText("Gilf Kebir crater-like structures");
  await expect(page.getByTestId("report-sources")).toContainText("doi:10.1029/2005GL024263");
  const download = page.waitForEvent("download");
  await page.getByTestId("download-json").click();
  expect((await download).suggestedFilename()).toBe("abaad-MARS-JEZERO-CRATER-shallow_subsurface_gpr.json");
  expect(errors).toEqual([]);
});

test("Gale Crater has no subsurface source, so Gilf Kebir is insufficient evidence there", async ({ page }) => {
  await page.goto("/explore?reference=MARS-GALE-CRATER&task=shallow_subsurface_gpr");
  await expect(page.getByTestId("none-ranked")).toBeVisible();
  await expect(page.getByTestId("candidate-EG-WD-GILF-KEBIR")).toHaveAttribute("data-status", "insufficient_evidence");
});

test("Moon: only rover mobility is offered and nothing is ranked as a lunar analog", async ({ page }) => {
  await page.goto("/explore");
  await page.getByTestId("body-moon").click();
  await page.getByTestId("ref-MOON-SOUTH-POLE").click();
  await expect(page.getByTestId("task-aeolian_geomorphology")).toHaveCount(0);
  await page.getByTestId("task-rover_mobility").click();
  await expect(page.getByTestId("moon-notice")).toBeVisible();
  await expect(page.getByTestId("none-ranked")).toBeVisible();
  const gk = page.getByTestId("candidate-EG-WD-GILF-KEBIR");
  await gk.getByRole("button", { name: "Show evidence" }).click();
  await expect(gk.getByTestId("dim-environment")).toContainText("Mismatch");
});

test("invalid selection in the URL shows the API error instead of results", async ({ page }) => {
  await page.goto("/explore?reference=MOON-SOUTH-POLE&task=aeolian_geomorphology");
  await expect(page.getByTestId("compare-error")).toContainText("applies to 'mars'");
  await expect(page.getByTestId("results")).toHaveCount(0);
});

test("sites page lists the three Egyptian candidates, the global sites and the references", async ({ page }) => {
  await page.goto("/sites");
  for (const code of ["EG-WD-GILF-KEBIR", "EG-WD", "EG-WD-DAKHLA", "CL-ATACAMA-ARADS-SITE", "IS-HOLUHRAUN", "AQ-MDV-UNIVERSITY-VALLEY",
    "MARS-GALE-CRATER", "MARS-BAGNOLD-DUNES", "MARS-JEZERO-CRATER", "MOON-SHACKLETON-CRATER"]) {
    await expect(page.getByTestId(`site-${code}`)).toBeVisible();
  }
  await expect(page.getByTestId("site-EG-WD-GILF-KEBIR")).toContainText("approximate context point");
});
