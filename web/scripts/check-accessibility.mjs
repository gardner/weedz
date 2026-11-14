// Core review actions meet WCAG 2.2 AA checks and work from the keyboard alone.
import assert from "node:assert/strict";
import AxeBuilder from "@axe-core/playwright";
import { chromium } from "@playwright/test";

const browser = await chromium.launch({
  headless: true,
  ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE
    ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE }
    : {}),
});
try {
  const context = await browser.newContext({ viewport: { width: 1400, height: 1000 } });
  const page = await context.newPage();
  const run = {
    id: "run",
    status: "completed",
    detail: "Test fixture",
    created_at: "2024-12-31",
    spec: { before: "2024-12-31", limit_per_region: 2, controls_per_species: 0 },
  };
  const photo = (id, status) => ({
    id,
    region: "Nelson",
    cohort: "incidental",
    original_taxon: "Turdus merula",
    original_common_name: `Blackbird ${id}`,
    review_status: status,
    review_note: "",
    observed_on: "2024-12-30",
    uploaded_at: "2024-12-31T00:00:00Z",
    scores: {
      best_species: "Ulex europaeus",
      margin: id === "a" ? 0.2 : 0.1,
      similarity: 0.3,
      box: [0, 0, 10, 10],
      width: 20,
      height: 20,
      species: [{ name: "Ulex europaeus", similarity: 0.3, margin: 0.1, box: [0, 0, 10, 10] }],
    },
    photo_license: "cc-by",
    observation_license: "cc-by",
    coordinate_status: "public",
    latitude: -41.2,
    longitude: 173.3,
    positional_accuracy_m: 10,
    attribution: "Test fixture",
    source_url: "https://www.inaturalist.org/observations/1",
  });
  const posted = [];
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path === "/api/runs") return route.fulfill({ json: [run] });
    if (path.endsWith("/image")) return route.fulfill({ status: 404 });
    if (path.endsWith("/review")) {
      posted.push(request.postDataJSON());
      return route.fulfill({ json: { saved: true } });
    }
    await route.fulfill({
      json: { run, photos: [photo("a", "unreviewed"), photo("b", "rejected")] },
    });
  });
  await page.goto(process.env.WEEDZ_WEB_URL ?? "http://127.0.0.1:3001");
  await page.locator(".photo-row").nth(1).waitFor();
  await page.locator(".run-settings summary").click();

  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();
  const summary = results.violations.map(
    (v) => `${v.id} (${v.impact}): ${v.nodes.length} × ${v.nodes[0]?.target.join(" ")}`,
  );
  assert.deepEqual(summary, [], `WCAG violations:\n${summary.join("\n")}`);

  // The phone layout reflows the same content; audit it too.
  await page.setViewportSize({ width: 390, height: 844 });
  const phone = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();
  const phoneSummary = phone.violations.map((v) => `${v.id}: ${v.nodes.length}`);
  assert.deepEqual(phoneSummary, [], `Phone-width WCAG violations:\n${phoneSummary.join("\n")}`);
  await page.setViewportSize({ width: 1400, height: 1000 });

  // Keyboard only: reach the second photo, then decide without a pointer.
  await page.locator(".photo-row").first().focus();
  await page.keyboard.press("Tab");
  await page.keyboard.press("Enter");
  await page.locator(".evidence h2").waitFor();
  const decision = page.getByRole("button", { name: "Reject suggestion" });
  for (
    let step = 0;
    step < 40 && !(await decision.evaluate((el) => el === document.activeElement));
    step++
  ) {
    await page.keyboard.press("Tab");
  }
  assert.ok(
    await decision.evaluate((el) => el === document.activeElement),
    "decision reachable by Tab",
  );
  const outline = await decision.evaluate((el) => getComputedStyle(el).outlineStyle);
  assert.notEqual(outline, "none", "focused controls show a visible focus indicator");
  await page.keyboard.press("Enter");
  await page.getByText("Review saved locally.").waitFor();
  assert.equal(posted[0].status, "rejected");
  console.log("No WCAG 2.2 AA violations; the core decision works from the keyboard.");
} finally {
  await browser.close();
}
