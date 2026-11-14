// Decisions need a named reviewer; disagreement and history are visible without colour.
import assert from "node:assert/strict";
import { chromium } from "@playwright/test";

const browser = await chromium.launch({
  headless: true,
  ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE
    ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE }
    : {}),
});
try {
  const page = await browser.newPage({ timezoneId: "Pacific/Auckland", locale: "en-NZ" });
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
    review_status: "rejected",
    review_note: "Native clematis",
    review_reviewer: "Ben",
    reviewer_decisions: { Ana: "confirmed", Ben: "rejected" },
    disputed: true,
    review_count: 3,
    scores: { best_species: "Clematis vitalba" },
    photo_license: "cc0",
    coordinate_status: "missing",
    attribution: "Test fixture",
  };
  const history = [
    {
      id: 1,
      reviewer: "",
      status: "uncertain",
      note: "Before attribution",
      created_at: "2026-11-12T01:00:00+00:00",
    },
    {
      id: 2,
      reviewer: "Ana",
      status: "confirmed",
      note: "Seed heads",
      created_at: "2026-11-13T02:30:00+00:00",
    },
    {
      id: 3,
      reviewer: "Ben",
      status: "rejected",
      note: "Native clematis",
      created_at: "2026-11-13T20:00:00+00:00",
    },
  ];
  const posted = [];
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/runs") return route.fulfill({ json: [run] });
    if (path.endsWith("/image")) return route.fulfill({ status: 404 });
    if (path.endsWith("/reviews")) return route.fulfill({ json: history });
    if (path.endsWith("/review")) {
      posted.push(route.request().postDataJSON());
      return route.fulfill({ json: { saved: true } });
    }
    await route.fulfill({ json: { run, photos: [photo] } });
  });
  await page.goto(process.env.WEEDZ_WEB_URL ?? "http://127.0.0.1:3001");
  await page.evaluate(() => localStorage.removeItem("weedz-reviewer"));
  await page.reload();

  await page.locator(".photo-row").getByText("Reviewers disagree").waitFor();
  const evidence = page.locator(".evidence");
  await evidence.getByText("Reviewers disagree").waitFor();
  await evidence.getByText("Ana: Species visible").waitFor();
  await evidence.getByText("Ben: Rejected").waitFor();
  const events = page.locator(".review-history li");
  await events.nth(2).waitFor();
  assert.match(await events.nth(0).textContent(), /Reviewer not recorded/);
  assert.match(await events.nth(1).textContent(), /Ana.*Species visible.*Seed heads/s);
  // 20:00 UTC on 13 Nov is 09:00 on 14 Nov in Nelson (NZDT, UTC+13).
  const decided = events.nth(2).locator("time");
  assert.equal(await decided.getAttribute("datetime"), "2026-11-13T20:00:00+00:00");
  assert.equal(await decided.textContent(), "14 Nov 2026, 9:00 am");

  const unsure = page.getByRole("button", { name: "Unsure" });
  assert.equal(await unsure.isDisabled(), true, "a decision needs a reviewer name");
  await page.getByLabel("Your name").fill("  Cara ");
  await unsure.click();
  await page.getByText("Review saved locally.").waitFor();
  assert.deepEqual(posted, [{ status: "uncertain", note: "Native clematis", reviewer: "Cara" }]);

  await page.reload();
  assert.equal(await page.getByLabel("Your name").inputValue(), "Cara");
  console.log("Review decisions are attributed; disagreement and history are visible.");
} finally {
  await browser.close();
}
