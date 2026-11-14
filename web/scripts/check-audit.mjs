// The audit view is blind: no suggestion, search window or scores, and it posts a finding.
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
    spec: { before: "2024-12-31", limit_per_region: 2, controls_per_species: 0 },
  };
  const photo = (id, sampled) => ({
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
    audit_sample: sampled,
    audited: false,
    scores: {
      best_species: "Cortaderia selloana",
      margin: 0.04,
      box: [0, 0, 10, 10],
      width: 20,
      height: 20,
      species: [
        { name: "Cortaderia selloana", similarity: 0.3, margin: 0.04, box: [0, 0, 10, 10] },
      ],
    },
    photo_license: "cc0",
    coordinate_status: "missing",
    attribution: "Test fixture",
  });
  const audit = { sampled: 1, audited: 0, remaining: 1, weed_found: 0, missed_by_screening: 0 };
  const posted = [];
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/runs") return route.fulfill({ json: [run] });
    if (path.endsWith("/image")) return route.fulfill({ status: 404 });
    if (path.endsWith("/reviews")) return route.fulfill({ json: [] });
    if (path.endsWith("/audit")) {
      posted.push(route.request().postDataJSON());
      return route.fulfill({ json: { saved: true } });
    }
    const photos = [photo("sampled", true), photo("other", false)];
    await route.fulfill({ json: { run, photos, audit } });
  });
  await page.goto(process.env.WEEDZ_WEB_URL ?? "http://127.0.0.1:3001");
  await page.getByRole("button", { name: "Audit sample" }).click();

  const rows = page.locator(".photo-row");
  await page.getByText("Is any watchlist weed visible?").waitFor();
  assert.equal(await rows.count(), 1, "only sampled photos are listed");
  // Watchlist names appear as answers; the photo's own suggestion and scores must not.
  assert.ok(!(await rows.first().textContent()).includes("Pampas grass"), "row hides suggestion");
  assert.equal(
    await page.locator(".audit-panel h2").textContent(),
    "Is any watchlist weed visible?",
  );
  const text = await page.locator(".workspace").textContent();
  for (const hidden of ["Similarity comparison", "0.300", "0.040"]) {
    assert.ok(!text.includes(hidden), `audit view must not reveal "${hidden}"`);
  }
  assert.equal(await page.locator(".workspace svg rect").count(), 0, "no search window");
  await page.getByText("0 of 1 sampled photos audited").waitFor();
  await page.getByText("Fixed random sample · screening rank hidden").waitFor();
  assert.equal(await page.getByLabel("Filter review status").count(), 0);

  const gorse = page.getByRole("button", { name: "Gorse", exact: true });
  assert.equal(await gorse.isDisabled(), true, "an audit needs a reviewer name");
  await page.getByLabel("Your name").fill("Ana");
  await gorse.click();
  await page.getByText("Audit saved locally.").waitFor();
  assert.equal(posted.length, 1);
  assert.equal(posted[0].finding, "Ulex europaeus");
  assert.equal(posted[0].reviewer, "Ana");
  assert.equal(typeof posted[0].effort_seconds, "number");
  console.log("The audit view hides screening output and records a blind finding.");
} finally {
  await browser.close();
}
