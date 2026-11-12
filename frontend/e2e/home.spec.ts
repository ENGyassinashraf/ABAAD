import { expect, test } from "@playwright/test";

test("home page shows the temporary wordmark, slogan and a live API/database status", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (m) => m.type() === "error" && consoleErrors.push(m.text()));

  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("ABAAD");
  await expect(page.getByText("Different Dimensions. One Connection.").first()).toBeVisible();
  await expect(page.getByText(/Temporary text wordmark/)).toBeVisible();
  await expect(page.getByTestId("phase-notice")).toContainText("No comparisons, scores or scientific results");

  // Frontend -> Next.js proxy -> FastAPI /api/v1/health -> SQLite
  const status = page.getByTestId("api-status");
  await expect(status).toHaveAttribute("data-state", "ok");
  await expect(page.getByTestId("schema-revision")).toHaveText("0002");

  expect(consoleErrors).toEqual([]);
});

test("health endpoint answers through the frontend origin with the agreed shape", async ({ request }) => {
  const r = await request.get("/api/v1/health");
  expect(r.status()).toBe(200);
  const body = await r.json();
  expect(body.status).toBe("ok");
  expect(body.database.foreign_keys).toBe(true);
  expect(body.database.journal_mode).toBe("wal");
});

test("unknown API route returns the {code, message, details} error shape", async ({ request }) => {
  const r = await request.get("/api/v1/does-not-exist");
  expect(r.status()).toBe(404);
  expect(Object.keys(await r.json()).sort()).toEqual(["code", "details", "message"]);
});
