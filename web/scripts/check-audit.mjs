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
  let audited = false;
  const photo = (id, sampled, margin) => ({
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
    audited: sampled && audited,
    scores: {
      best_species: "Cortaderia selloana",
      margin,
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
  const summary = () => ({
    sampled: 1,
    audited: Number(audited),
    remaining: Number(!audited),
    weed_found: Number(audited),
    found_as_top_suggestion: 0,
    found_not_top_suggestion: Number(audited),
    disputed: 0,
  });
  const posted = [];
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/runs") return route.fulfill({ json: [run] });
    if (path.endsWith("/image")) return route.fulfill({ status: 404 });
    if (path.endsWith("/reviews")) return route.fulfill({ json: [] });
    if (path.endsWith("/audit")) {
      posted.push(route.request().postDataJSON());
      audited = true;
      return route.fulfill({ json: { saved: true } });
    }
    const photos = [photo("sampled", true, 0.04), photo("other", false, 0.5)];
    await route.fulfill({ json: { run, photos, audit: summary() } });
  });
  await page.goto(process.env.WEEDZ_WEB_URL ?? "http://127.0.0.1:3001");

  // Until it is audited, a sampled photo stays out of the ranked queue, so nobody sees
  // its suggestion before answering blind.
  const rows = page.locator(".photo-row");
  const incidentalTab = page.getByRole("button", { name: "Incidental photos" });
  await page.getByText("Bird other").first().waitFor();
  assert.equal(await rows.count(), 1, "unaudited sampled photo is held out of the queue");
  assert.ok(!(await page.locator(".photo-list").textContent()).includes("Bird sampled"));
  await rows.first().click();

  await page.getByRole("button", { name: "Audit sample" }).click();
  await page.getByText("Is any watchlist weed visible?").waitFor();
  await rows.first().click();
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
  await page.getByText("1 of 1 sampled photos audited").waitFor();

  // Once audited, it rejoins the ranked queue, and the audit selection is not carried over.
  await incidentalTab.click();
  await page.locator(".photo-list").getByText("Bird sampled").waitFor();
  assert.equal(await rows.count(), 2, "audited photo rejoins the queue");
  const selected = await page.locator(".photo-row.selected").textContent();
  assert.ok(selected.includes("Bird other"), "switching views resets the open photo");
  console.log("The audit view stays blind until audited and records a blind finding.");
} finally {
  await browser.close();
}
