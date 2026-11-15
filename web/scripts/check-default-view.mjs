// A reference-only run opens real evidence without relabelling it incidental.
import assert from "node:assert/strict";
import { chromium } from "@playwright/test";

const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage();
  const run = { id: "plants", status: "completed", created_at: "2026-11-15", spec: {} };
  const photo = {
    id: "gorse",
    cohort: "reference",
    region: "Nelson",
    original_taxon: "Ulex europaeus",
    original_common_name: "Gorse",
    review_status: "unreviewed",
    scores: { best_species: "Ulex europaeus", margin: 0.2 },
    photo_license: "cc-by",
    attribution: "Fixture",
    reviewer_decisions: {},
  };
  await page.route("**/api/**", (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/session")
      return route.fulfill({ json: { mode: "local", can_start_runs: false } });
    if (path === "/api/runs")
      return route.fulfill({ json: [{ ...run, id: "queued", status: "queued" }, run] });
    if (path.endsWith("/image")) return route.fulfill({ status: 404 });
    if (path === "/api/runs/plants") return route.fulfill({ json: { run, photos: [photo] } });
    return route.fulfill({ json: [] });
  });
  await page.goto("http://127.0.0.1:3001", { waitUntil: "domcontentloaded" });
  await page.locator("button.photo-row").waitFor({ timeout: 3000 });
  assert.match((await page.locator("button.photo-row").textContent()) ?? "", /Gorse/);
  await page.getByRole("button", { name: "Incidental photos", exact: true }).click();
  await page.waitForTimeout(5200);
  assert.equal(
    await page.locator("button.photo-row").count(),
    0,
    "Refresh preserves chosen empty view",
  );
  await page.close();
} finally {
  await browser.close();
}
