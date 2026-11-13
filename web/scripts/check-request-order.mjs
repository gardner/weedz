// Regression: late responses from the previous run must not replace current evidence.
import assert from "node:assert/strict";
import { chromium } from "@playwright/test";

const browser = await chromium.launch({
  headless: true,
  ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE
    ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE }
    : {}),
});
try {
  const page = await browser.newPage();
  let releaseOld;
  const held = new Promise((resolve) => {
    releaseOld = resolve;
  });
  const runs = ["old", "current"].map((id) => ({
    id,
    status: "completed",
    detail: "Test fixture",
    created_at: "2024-12-31",
    spec: { before: "2024-12-31", limit_per_region: 1, controls_per_species: 0 },
  }));
  const photo = (id) => ({
    id,
    region: "Nelson",
    cohort: "incidental",
    original_taxon: `Bird ${id}`,
    original_common_name: `Bird ${id}`,
    review_status: "unreviewed",
    review_note: "",
    scores: {},
    photo_license: "cc0",
    coordinate_status: "missing",
    attribution: "Test fixture",
  });
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/runs") return route.fulfill({ json: runs });
    const id = path.split("/")[3];
    if (path.endsWith("/image")) return route.fulfill({ status: 404 });
    if (id === "old") await held;
    await route.fulfill({ json: { run: runs.find((run) => run.id === id), photos: [photo(id)] } });
  });
  await page.goto(process.env.WEEDZ_WEB_URL ?? "http://127.0.0.1:3001");
  await page.locator(".run-settings summary").click();
  await page.locator(".settings-grid select").selectOption("current");
  await page.getByText("Bird current", { exact: true }).first().waitFor();
  const lateResponse = page.waitForResponse((response) => response.url().endsWith("/api/runs/old"));
  releaseOld();
  await lateResponse;
  await page.waitForTimeout(300);
  assert.equal(await page.locator(".context-grid strong").first().textContent(), "Bird current");
  console.log("Delayed previous-run responses cannot replace the selected run's evidence.");
} finally {
  await browser.close();
}
