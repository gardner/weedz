// A run's source suitability is fetched when opened, keeps unknowns explicit, and lists
// which photos cannot support which conclusions.
import assert from "node:assert/strict";
import { chromium } from "@playwright/test";
import { suitability } from "./suitability-fixture.mjs";

const browser = await chromium.launch({
  headless: true,
  ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE
    ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE }
    : {}),
});
const run = {
  id: "run",
  status: "completed",
  detail: "Test fixture",
  created_at: "2024-12-31",
  spec: { before: "2024-12-31", limit_per_region: 2, controls_per_species: 0 },
};
try {
  const page = await browser.newPage();
  let fetched = 0;
  let failing = false;
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/runs") return route.fulfill({ json: [run] });
    if (path === "/api/studies/terms") return route.fulfill({ json: { limits: {} } });
    if (path === "/api/runs/run/suitability") {
      fetched++;
      if (failing) return route.fulfill({ status: 503, json: { detail: "Python is down" } });
      return route.fulfill({ json: suitability });
    }
    await route.fulfill({ json: { run, photos: [], study: null } });
  });
  await page.goto(process.env.WEEDZ_WEB_URL ?? "http://127.0.0.1:3001");
  const panel = page.locator(".suitability-panel");
  await panel.locator("summary").waitFor();
  assert.equal(fetched, 0, "the summary is fetched only when the panel is opened");

  await panel.locator("summary").click();
  await panel.getByText("not evidence that no weed is there").waitFor();
  assert.equal(fetched, 1);
  await panel.getByText("Tasman returned 0 of 2 requested photos").waitFor();
  await panel.getByText(/Outside the study period: not assessed/).waitFor();
  await panel.getByText(/Visible vegetation: Not measured/).waitFor();
  await panel.getByText(/Years with no photos: unknown \(open start\)/).waitFor();
  await panel.getByText("No reference snapshot: novelty is unassessed", { exact: false }).waitFor();

  const table = panel.getByRole("table", { name: "What these photos cannot support" });
  const rows = table.getByRole("row");
  assert.deepEqual(await rows.nth(1).locator("th, td").allTextContents(), [
    "A field search lead",
    "1 photo: 0 site visits + 1 ungrouped photo",
    "No search area: the location is obscured, missing or of unknown accuracy",
  ]);
  assert.equal(await rows.nth(2).locator("td").first().textContent(), "Not assessed");
  assert.equal(await rows.nth(3).locator("td").first().textContent(), "None");

  // Reopening fetches again; a failure is said in the panel, not shown as empty coverage.
  failing = true;
  await panel.locator("summary").click();
  await panel.locator("summary").click();
  await panel.getByText(/Source suitability could not be loaded: Python is down/).waitFor();
  assert.equal(await table.count(), 0, "no stale or empty table is shown after a failure");
  console.log("Source suitability is fetched on opening and keeps unknowns explicit.");
} finally {
  await browser.close();
}
