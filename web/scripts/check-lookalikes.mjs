// Lookalike photos have their own queue so they can be botanically reviewed.
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
    spec: { before: "2024-12-31", limit_per_region: 1, controls_per_species: 0 },
  };
  const photo = (id, cohort, extra = {}) => ({
    id,
    region: "Nelson",
    cohort,
    original_taxon: `Taxon ${id}`,
    original_common_name: `Name ${id}`,
    review_status: "unreviewed",
    review_note: "",
    review_reviewer: "",
    reviewer_decisions: {},
    disputed: false,
    review_count: 0,
    scores: { best_species: "Cortaderia selloana", margin: 0.04 },
    photo_license: "cc0",
    coordinate_status: "missing",
    attribution: "Test fixture",
    ...extra,
  });
  const photos = [
    photo("animal", "incidental"),
    photo("toetoe", "lookalike", {
      lookalike_taxon: "Austroderia",
      lookalike_of: "Cortaderia selloana",
    }),
  ];
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/runs") return route.fulfill({ json: [run] });
    if (path.endsWith("/image")) return route.fulfill({ status: 404 });
    if (path.endsWith("/reviews")) return route.fulfill({ json: [] });
    await route.fulfill({ json: { run, photos } });
  });
  await page.route("**/api/session", (route) =>
    route.fulfill({ json: { mode: "local", can_start_runs: true } }),
  );
  await page.goto(process.env.WEEDZ_WEB_URL ?? "http://127.0.0.1:3001");
  await page.getByText("Name animal").first().waitFor();
  assert.equal(await page.getByText("Name toetoe").count(), 0, "lookalikes stay out of incidental");
  await page.getByRole("button", { name: "Lookalikes" }).click();
  await page.locator(".photo-row").getByText("Name toetoe").waitFor();
  await page.getByText("Lookalike photo · Austroderia, resembles Pampas grass").waitFor();
  console.log("Lookalike photos have their own queue with their lookalike context.");
} finally {
  await browser.close();
}
