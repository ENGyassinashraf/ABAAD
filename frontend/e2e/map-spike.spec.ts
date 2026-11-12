import { expect, test } from "@playwright/test";

// T1 needs internet access to tiles.openfreemap.org. Set ABAAD_E2E_OFFLINE=1
// ONLY where that host is unreachable (e.g. a sandbox); the report must then
// say T1 was not verified. On the owner's Mac it must run.
const offline = process.env.ABAAD_E2E_OFFLINE === "1";

test.describe("map feasibility spike (synthetic fixtures)", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/dev/map-spike");
    await expect(page.getByTestId("synthetic-banner")).toBeVisible();
    await expect
      .poll(async () => page.locator('[data-testid^="result-"][data-status="pending"]').count(), { timeout: 90_000 })
      .toBe(0);
  });

  for (const id of ["T2", "T3", "T4", "T5", "T6"]) {
    test(`${id} passes`, async ({ page }) => {
      const row = page.getByTestId(`result-${id}`);
      const actual = await page.getByTestId(`actual-${id}`).textContent();
      test.info().annotations.push({ type: "actual", description: actual ?? "" });
      await expect(row, actual ?? "").toHaveAttribute("data-status", "pass");
    });
  }

  test("T4 refusal is shown to the user", async ({ page }) => {
    await expect(page.getByTestId("crs-refusal")).toContainText("does not match the map CRS IAU_2015:49910");
  });

  test("T1 Earth map with OpenFreeMap passes", async ({ page }) => {
    test.skip(offline, "ABAAD_E2E_OFFLINE=1: tiles.openfreemap.org not reachable here; T1 NOT verified");
    const actual = await page.getByTestId("actual-T1").textContent();
    test.info().annotations.push({ type: "actual", description: actual ?? "" });
    await expect(page.getByTestId("result-T1"), actual ?? "").toHaveAttribute("data-status", "pass");
  });

  test("spike page screenshot (evidence)", async ({ page }) => {
    await page.screenshot({ path: "test-results/map-spike-evidence.png", fullPage: true });
  });
});
