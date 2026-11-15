// Known records are shown as distance and date from a dated snapshot, never as novelty.
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
  const nearest = { gbif_key: 1, distance_m: 2340, year: 2015, uncertainty_m: null };
  const comparable = {
    comparable: true,
    nearest,
    within_radius: 1,
    radius_m: 5000,
    photo_accuracy_m: 8,
  };
  const photo = (id, margin, comparison) => ({
    id,
    region: "Nelson",
    cohort: "incidental",
    original_taxon: `Bird ${id}`,
    original_common_name: `Bird ${id}`,
    review_status: "unreviewed",
    review_note: "",
    review_reviewer: "",
    reviewer_decisions: {},
    disputed: false,
    review_count: 0,
    scores: { best_species: "Ulex europaeus", margin },
    photo_license: "cc0",
    coordinate_status: "public",
    attribution: "Test fixture",
    ...(comparison ? { reference_comparison: { "Ulex europaeus": comparison } } : {}),
  });
  let references = null;
  let photos = [photo("a", 0.3)];
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/runs") return route.fulfill({ json: [run] });
    if (path.endsWith("/image")) return route.fulfill({ status: 404 });
    if (path.endsWith("/reviews")) return route.fulfill({ json: [] });
    await route.fulfill({ json: { run, photos, references } });
  });
  await page.route("**/api/session", (route) =>
    route.fulfill({ json: { mode: "local", can_start_runs: true } }),
  );
  await page.goto(process.env.WEEDZ_WEB_URL ?? "http://127.0.0.1:3001");
  const known = page.locator(".context-grid div", { hasText: "Known records" });
  await known.getByText("No reference snapshot loaded").waitFor();

  references = { retrieved_at: "2026-11-14T05:04:00+00:00", dataset: { title: "DOC weeds" } };
  photos = [
    photo("a", 0.3, comparable),
    photo("b", 0.2, { comparable: false, reason: "Photo location is obscured or missing" }),
    photo("c", 0.1, { comparable: false, reason: "Not queried in this reference snapshot" }),
  ];
  await page.reload();
  await known.getByText("Nearest DOC record of Gorse: 2.3 km (2015)").waitFor();
  assert.match(await known.textContent(), /snapshot as of 2026-11-14/);
  assert.match(await known.textContent(), /not evidence of a new locality/i);
  await page.locator(".photo-row").nth(1).click();
  await known.getByText("Not compared: Photo location is obscured or missing").waitFor();
  await page.locator(".photo-row").nth(2).click();
  await known.getByText("Not compared: Not queried in this reference snapshot").waitFor();
  assert.doesNotMatch(await known.textContent(), /No DOC record/);
  assert.match(
    await known.textContent(),
    /unexpected location is a reason to refer to a specialist, not to reject/i,
  );

  // Known range never reorders or hides a candidate (PRD P11): the queue follows margin.
  const rows = async () =>
    (await page.locator(".photo-row").allTextContents()).map((text) => text.match(/Bird (\w)/)[1]);
  assert.deepEqual(await rows(), ["a", "b", "c"]);
  const outOfRange = { ...comparable, nearest: null, within_radius: 0 };
  photos = [
    photo("a", 0.3, { comparable: false, reason: "Photo location is obscured or missing" }),
    photo("b", 0.2, outOfRange),
    photo("c", 0.1, { ...comparable, within_radius: 40 }),
  ];
  await page.reload();
  await page.locator(".photo-row").first().waitFor();
  assert.deepEqual(await rows(), ["a", "b", "c"]);
  console.log(
    "Known records are shown with distance, year and snapshot date, and never reorder the queue.",
  );
} finally {
  await browser.close();
}
