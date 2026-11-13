import { expect, test, type Locator, type Page } from "@playwright/test";

// Full Mission Lab workflow against the real backend (fresh e2e database).
// No external map tiles are used: all imagery comes from the ABAAD API.

async function clickMapAt(page: Page, map: Locator, xy: [number, number], extent = 1280) {
  await map.scrollIntoViewIfNeeded();
  const box = await map.boundingBox();
  if (!box) throw new Error("map not visible");
  await page.mouse.click(box.x + (xy[0] / extent) * box.width, box.y + ((extent - xy[1]) / extent) * box.height);
}

test("Moon → region → objective → site → generate → play → link sandbox → compare → report", async ({ page, request }) => {
  test.setTimeout(240_000);
  const errors: string[] = [];
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  page.on("pageerror", (e) => errors.push(e.message));

  await page.goto("/mission-lab");
  await expect(page.getByTestId("synthetic-banner")).toContainText("Synthetic / Demonstration");
  await expect(page.getByTestId("step-body")).toContainText("Moon");
  await expect(page.getByTestId("step-region")).toContainText("Lunar south polar region");
  await expect(page.getByTestId("step-objective")).toContainText("Lunar Surface Reconnaissance & Navigation");
  await expect(page.getByTestId("site-name")).toContainText("Synthetic lunar-operations training range");
  await expect(page.getByTestId("site-not-analog")).toContainText("Validated lunar analog: no");

  // Generate the scenario (server: validation, routes, simulation, save)
  await page.getByTestId("generate").click();
  await expect(page.getByTestId("run-status")).toHaveText("COMPLETED_WITH_DEVIATIONS", { timeout: 60_000 });
  await expect(page.getByTestId("viewer3d")).toHaveAttribute("data-state", /ready|unavailable/);
  const runId = (await page.getByTestId("run-id").textContent())!.replace(/\D/g, "");

  // Route analysis
  await page.getByTestId("tab-route").click();
  await expect(page.getByTestId("route-distance")).toContainText(" m");
  await expect(page.getByTestId("route-analysis")).toContainText("Demonstration route");

  // Playback drives the telemetry from saved frames
  await expect(page.getByTestId("phase-1")).toHaveAttribute("data-state", "current");
  await page.getByTestId("speed-select").selectOption("3600");
  await page.getByTestId("play").click();
  await expect(page.getByTestId("phase-3")).toHaveAttribute("data-state", /current|done/, { timeout: 20_000 });
  await page.getByTestId("play").click(); // pause
  await expect(page.getByTestId("tel-time")).not.toHaveText("0:00:00");
  await page.getByTestId("layer-routes").uncheck();
  await page.getByTestId("layer-routes").check();

  // Scrub behind the ridge: link geometry must change state
  await page.getByTestId("scrubber").fill("9000");
  await expect(page.getByTestId("tel-los")).toHaveText("BLOCKED_BY_TERRAIN");
  await page.getByTestId("scrubber").fill("100000");
  await expect(page.getByTestId("phase-8")).toHaveAttribute("data-state", "done");
  await page.getByTestId("tab-timeline").click();
  await expect(page.getByTestId("timeline").locator('[data-type="LOS_LOST"]').first()).toBeVisible();
  await expect(page.getByTestId("timeline").locator('[data-type="REROUTE"]')).toHaveCount(1);

  // Link sandbox: base area → target area is blocked; moving the relay end changes the result
  await page.getByTestId("tab-sandbox").click();
  const map = page.getByTestId("sandbox-map");
  await page.getByTestId("los-pick").click();
  await clickMapAt(page, map, [1060, 1040]);
  await clickMapAt(page, map, [150, 170]);
  await expect(page.getByTestId("los-status")).toHaveText("BLOCKED_BY_TERRAIN");
  await expect(page.getByTestId("los-profile")).toBeVisible();
  await page.getByTestId("los-pick").click();
  await clickMapAt(page, map, [200, 230]);
  await clickMapAt(page, map, [150, 170]);
  await expect(page.getByTestId("los-status")).toHaveText("LINE_OF_SIGHT");

  // Comparison of the same mission
  await page.getByTestId("tab-compare").click();
  await page.getByTestId("run-compare").click();
  await expect(page.getByTestId("compare-table")).toBeVisible({ timeout: 90_000 });
  await expect(page.getByTestId("cmp-stress-status")).toHaveText("SAFE_HOLD");
  await expect(page.getByTestId("cmp-mitigated-science_result")).toHaveText("COMPLETED");
  await expect(page.getByTestId("cmp-baseline-science_result")).toHaveText("COMPLETED");
  await page.getByTestId("load-stress").click();
  await expect(page.getByTestId("run-status")).toHaveText("SAFE_HOLD");
  await page.getByTestId("scrubber").fill("100000");
  await expect(page.getByTestId("tel-safety")).toHaveText("SAFE_HOLD");
  await expect(page.getByTestId("phase-6")).toHaveAttribute("data-state", "not_reached");

  // Report for the exact saved run currently loaded
  await page.getByTestId("tab-report").click();
  const loadedRun = (await page.getByTestId("run-id").textContent())!.replace(/\D/g, "");
  await page.getByTestId("export-report").click();
  await expect(page.getByTestId("report-ready")).toContainText(`run #${loadedRun}`, { timeout: 60_000 });
  const href = await page.getByTestId("report-open").getAttribute("href");
  const html = await (await request.get(href!)).text();
  expect(html).toContain(`Run #${loadedRun}`);
  expect(html).toContain("7. Step-by-Step Field Operations Runbook");
  expect(html).toContain("SYNTHETIC / DEMONSTRATION");
  expect(html).toContain("baseline / stress / mitigated comparison".replace(/^b/, "B"));
  expect(loadedRun).not.toBe(runId);

  expect(errors).toEqual([]);
});

test("controls change the result, and an impossible target gives a clear no-route state", async ({ page, request }) => {
  test.setTimeout(180_000);
  await page.goto("/mission-lab");
  await page.getByTestId("generate").click();
  await expect(page.getByTestId("run-status")).toHaveText("COMPLETED_WITH_DEVIATIONS", { timeout: 60_000 });

  // Same scenario, new run: autonomy off + injected blockage -> safe hold
  await page.getByTestId("autonomy").uncheck();
  await page.getByTestId("blockage").check();
  await page.getByTestId("generate").click();
  await expect(page.getByTestId("run-status")).toHaveText("SAFE_HOLD", { timeout: 60_000 });

  // Target inside a no-go boulder field
  const terrain = await (await request.get("/api/v1/mission/terrain?blockage=true")).json();
  const hz = terrain.hazards[0];
  await page.getByTestId("pick-target").click();
  await clickMapAt(page, page.getByTestId("setup-map"), [hz.x, hz.y]);
  await page.getByTestId("generate").click();
  await expect(page.getByTestId("no-route-state")).toContainText("no-go", { timeout: 60_000 });
});
