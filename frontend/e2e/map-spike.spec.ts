import { expect, test } from "@playwright/test";

// T1 needs internet access to tiles.openfreemap.org. Set ABAAD_E2E_OFFLINE=1
// ONLY where that host is unreachable (e.g. a sandbox); the report must then
// say T1 was not verified. On the owner's Mac it must run.
const offline = process.env.ABAAD_E2E_OFFLINE === "1";

// Hardening F-13: T1 depends on a real network fetch to tiles.openfreemap.org
// and must never block or fail the five deterministic, synthetic-fixture
// checks (T2-T6). beforeEach therefore waits only for T2-T6 to leave
// "pending" -- never for T1's own row -- so a tile-network outage can no
// longer cause all six tests to fail together. T1 is a separate network
// smoke test with its own wait and its own offline skip.
const DETERMINISTIC_IDS = ["T2", "T3", "T4", "T5", "T6"];
const deterministicPendingSelector = DETERMINISTIC_IDS.map((id) => `[data-testid="result-${id}"][data-status="pending"]`).join(", ");

test.describe("map feasibility spike (synthetic fixtures)", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/dev/map-spike");
    await expect(page.getByTestId("synthetic-banner")).toBeVisible();
    await expect
      .poll(async () => page.locator(deterministicPendingSelector).count(), { timeout: 90_000 })
      .toBe(0);
  });

  for (const id of DETERMINISTIC_IDS) {
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

  test("spike page screenshot (evidence, deterministic checks only)", async ({ page }) => {
    await page.screenshot({ path: "test-results/map-spike-evidence.png", fullPage: true });
  });
});

// Separate describe block: this is a network smoke test, not a logic test.
// It gets its own wait for result-T1 and never affects the block above.
test.describe("map feasibility spike (external tile network smoke test)", () => {
  test("T1 Earth map with OpenFreeMap passes", async ({ page }) => {
    test.skip(offline, "ABAAD_E2E_OFFLINE=1: tiles.openfreemap.org not reachable here; T1 NOT verified");
    await page.goto("/dev/map-spike");
    await expect
      .poll(async () => page.getByTestId("result-T1").getAttribute("data-status"), { timeout: 90_000 })
      .not.toBe("pending");
    const actual = await page.getByTestId("actual-T1").textContent();
    test.info().annotations.push({ type: "actual", description: actual ?? "" });
    await expect(page.getByTestId("result-T1"), actual ?? "").toHaveAttribute("data-status", "pass");
  });
});
