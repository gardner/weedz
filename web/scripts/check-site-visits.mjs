// Photos from one site visit are shown as related evidence, and counted once.
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
  const run = {
    id: "run",
    status: "completed",
    detail: "Test fixture",
    created_at: "2024-12-31",
    spec: { before: "2024-12-31", limit_per_region: 3, controls_per_species: 0 },
  };
  const photo = (id, group, size, margin) => ({
    id,
    region: "Nelson",
    cohort: "incidental",
    original_taxon: `Bird ${id}`,
    original_common_name: `Bird ${id}`,
    review_status: "unreviewed",
    review_note: "",
    scores: { margin },
    photo_license: "cc0",
    coordinate_status: "public",
    attribution: "Test fixture",
    encounter_group: group,
    encounter_size: size,
  });
  const photos = [photo("a", "a", 2, 0.3), photo("b", "a", 2, 0.2), photo("c", "c", 1, 0.1)];
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/runs") return route.fulfill({ json: [run] });
    if (path.endsWith("/image")) return route.fulfill({ status: 404 });
    if (path.endsWith("/reviews")) return route.fulfill({ json: [] });
    await route.fulfill({ json: { run, photos } });
  });
  await page.goto(process.env.WEEDZ_WEB_URL ?? "http://127.0.0.1:3001");

  const rows = page.locator(".photo-row");
  await rows.nth(2).waitFor();
  const visits = page.locator(".stats-grid div", { hasText: "Independent site visits" });
  assert.match(await visits.textContent(), /Independent site visits: 02/);
  assert.match(await rows.nth(0).textContent(), /Same site visit as 1 other photo/);
  assert.doesNotMatch(await rows.nth(2).textContent(), /Same site visit/);
  await page.locator(".evidence").getByText("Same site visit as 1 other photo").waitFor();
  console.log("Site-visit groups are visible and counted once.");
} finally {
  await browser.close();
}
