// Review time counts visible, active seconds on the current photo, and nothing else.
import assert from "node:assert/strict";
import { chromium, expect } from "@playwright/test";

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
  const second = { ...photo, id: "second", original_common_name: "Tui" };
  const posted = [];
  const details = [];
  let held = null;
  const holdNextSave = () => {
    const gate = Promise.withResolvers();
    held = gate.promise;
    return gate.resolve;
  };
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/runs") return route.fulfill({ json: [run, { ...run, id: "other" }] });
    if (!path.endsWith("/image") && !path.endsWith("/review") && !path.endsWith("/reviews")) {
      details.push(path);
    }
    if (path === "/api/runs/other") return route.fulfill({ status: 503, body: "Unavailable" });
    if (path.endsWith("/image")) return route.fulfill({ status: 404 });
    if (path.endsWith("/reviews")) return route.fulfill({ json: [] });
    if (path.endsWith("/review")) {
      posted.push(route.request().postDataJSON());
      const gate = held;
      held = null;
      if (gate) await gate;
      return route.fulfill({ json: { saved: true } });
    }
    const review_effort = { total_minutes: 12.5, measured_decisions: 3, unmeasured_decisions: 1 };
    await route.fulfill({ json: { run, photos: [photo, second], review_effort } });
  });
  await page.route("**/api/session", (route) =>
    route.fulfill({ json: { mode: "local", can_start_runs: true } }),
  );
  await page.goto(process.env.WEEDZ_WEB_URL ?? "http://127.0.0.1:3001");
  await page.getByLabel("Your name").fill("Ana");
  await page.getByText("12.5 min measured review time · 1 decision not timed").waitFor();

  const setVisibility = (state) =>
    page.evaluate((value) => {
      Object.defineProperty(document, "visibilityState", { configurable: true, get: () => value });
      document.dispatchEvent(new Event("visibilitychange"));
    }, state);
  const click = async (label) => {
    const count = posted.length;
    await page.getByRole("button", { name: label }).click();
    while (posted.length === count) await new Promise((resolve) => setTimeout(resolve, 20));
  };
  const decide = async (label) => {
    await click(label);
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
  const idle = posted[1].effort_seconds;
  assert.ok(idle >= 599 && idle <= 602, `idle time capped at ten minutes, got ${idle}`);

  // A slow save must not wipe the time already spent on the next photo.
  const release = holdNextSave();
  await page.mouse.move(30, 30);
  await page.clock.runFor(5_000);
  await click("Unsure");
  await page.getByRole("button", { name: /Tui/ }).click();
  await page.clock.runFor(20_000);
  release();
  await page.getByText("Review saved locally.").waitFor();
  await page.clock.runFor(10_000);
  await click("Reject suggestion");
  const next = posted[3].effort_seconds;
  assert.ok(next >= 29 && next <= 32, `next photo keeps its time across a slow save, got ${next}`);

  // A glance at the references keeps the time already spent on the photo.
  const saved = () => expect(page.getByRole("button", { name: "Unsure" })).toBeEnabled();
  await saved();
  await page.clock.runFor(20_000);
  await page.getByRole("button", { name: "References" }).click();
  await page.clock.runFor(5_000);
  await page.getByRole("button", { name: "Incidental photos" }).click();
  await page.clock.runFor(10_000);
  await click("Unsure");
  const resumed = posted[4].effort_seconds;
  assert.ok(resumed >= 29 && resumed <= 32, `time survives a view change, got ${resumed}`);

  // Changing runs during a slow save shows the new run, not the old run's evidence or time.
  await saved();
  const releaseOld = holdNextSave();
  await click("Reject suggestion");
  await page.getByText("Run & collection settings").click();
  await page.getByLabel("Saved run").selectOption("other");
  await page.getByText("No review time yet").waitFor();
  const seen = details.length;
  releaseOld();
  while (details.length === seen) await new Promise((resolve) => setTimeout(resolve, 20));
  await new Promise((resolve) => setTimeout(resolve, 500));
  const reloaded = details.slice(seen).filter((path) => path.startsWith("/api/runs/"));
  assert.deepEqual([...new Set(reloaded)], ["/api/runs/other"], "the old save reloaded its run");
  assert.equal(await page.getByRole("button", { name: /Tui/ }).count(), 0);
  await page.getByText("No review time yet").waitFor();
  console.log("Review effort counts visible, active time per decision.");
} finally {
  await browser.close();
}
