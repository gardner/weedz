// Review time counts visible, active seconds on the current photo, and nothing else.
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
  await page.clock.install();
  const run = {
    id: "run",
    status: "completed",
    detail: "Test fixture",
    created_at: "2024-12-31",
    spec: { before: "2024-12-31", limit_per_region: 1, controls_per_species: 0 },
  };
  const photo = {
    id: "photo",
    region: "Nelson",
    cohort: "incidental",
    original_taxon: "Turdus merula",
    original_common_name: "Blackbird",
    review_status: "unreviewed",
    review_note: "",
    review_reviewer: "",
    reviewer_decisions: {},
    disputed: false,
    review_count: 0,
    scores: { best_species: "Clematis vitalba" },
    photo_license: "cc0",
    coordinate_status: "missing",
    attribution: "Test fixture",
  };
  const posted = [];
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/runs") return route.fulfill({ json: [run] });
    if (path.endsWith("/image")) return route.fulfill({ status: 404 });
    if (path.endsWith("/reviews")) return route.fulfill({ json: [] });
    if (path.endsWith("/review")) {
      posted.push(route.request().postDataJSON());
      return route.fulfill({ json: { saved: true } });
    }
    const review_effort = { total_minutes: 12.5, measured_decisions: 3, unmeasured_decisions: 1 };
    await route.fulfill({ json: { run, photos: [photo], review_effort } });
  });
  await page.goto(process.env.WEEDZ_WEB_URL ?? "http://127.0.0.1:3001");
  await page.getByLabel("Your name").fill("Ana");
  await page.getByText("12.5 min measured review time · 1 decision not timed").waitFor();

  const setVisibility = (state) =>
    page.evaluate((value) => {
      Object.defineProperty(document, "visibilityState", { configurable: true, get: () => value });
      document.dispatchEvent(new Event("visibilitychange"));
    }, state);
  const decide = async (label) => {
    await page.getByRole("button", { name: label }).click();
    await page.getByText("Review saved locally.").waitFor();
  };

  await page.clock.runFor(30_000);
  await setVisibility("hidden");
  await page.clock.runFor(120_000);
  await setVisibility("visible");
  await page.mouse.move(10, 10);
  await page.clock.runFor(15_000);
  await decide("Unsure");
  const first = posted[0].effort_seconds;
  assert.ok(first >= 44 && first <= 47, `visible time only, got ${first}`);

  // A tab left open stops counting after ten minutes without input.
  await page.mouse.move(20, 20);
  await page.clock.runFor(30 * 60_000);
  await decide("Reject suggestion");
  const second = posted[1].effort_seconds;
  assert.ok(second >= 599 && second <= 602, `idle time capped at ten minutes, got ${second}`);
  console.log("Review effort counts visible, active time per decision.");
} finally {
  await browser.close();
}
