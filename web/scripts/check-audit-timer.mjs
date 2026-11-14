// Audit time belongs to the auditor who spent it, even when auditors share a browser.
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
  const auditors = [];
  const photo = () => ({
    id: "sampled",
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
    audit_sample: true,
    audited: auditors.length > 0,
    auditors: [...auditors],
    scores: {},
    photo_license: "cc0",
    coordinate_status: "missing",
    attribution: "Test fixture",
  });
  const posted = [];
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/runs") return route.fulfill({ json: [run] });
    if (path.endsWith("/image")) return route.fulfill({ status: 404 });
    if (path.endsWith("/reviews")) return route.fulfill({ json: [] });
    if (path.endsWith("/audit")) {
      const body = route.request().postDataJSON();
      posted.push(body);
      auditors.push(body.reviewer);
      return route.fulfill({ json: { saved: true } });
    }
    await route.fulfill({ json: { run, photos: [photo()] } });
  });
  await page.goto(process.env.WEEDZ_WEB_URL ?? "http://127.0.0.1:3001");
  await page.getByRole("button", { name: "Audit sample" }).click();
  await page.getByLabel("Your name").fill("Ana");
  await page.clock.runFor(20_000);
  await page.getByRole("button", { name: "Gorse", exact: true }).click();
  await page.getByText("Audit saved locally.").waitFor();

  // Ana lingers on the answered photo, then hands the browser to Ben.
  await page.mouse.move(10, 10);
  await page.clock.runFor(30_000);
  await page.getByLabel("Your name").fill("Ben");
  await page.clock.runFor(10_000);
  await page.getByRole("button", { name: "None visible" }).click();
  // The notice is already showing from Ana's save, so wait for Ben's request itself.
  for (let attempt = 0; attempt < 50 && posted.length < 2; attempt++) {
    await page.waitForTimeout(100);
  }
  assert.equal(posted.length, 2);
  const ben = posted[1].effort_seconds;
  assert.ok(ben >= 9 && ben <= 12, `Ben's audit time excludes Ana's, got ${ben}`);
  console.log("Audit time is scoped to the auditor who spent it.");
} finally {
  await browser.close();
}
