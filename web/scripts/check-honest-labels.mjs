// Regression fixtures for source labels, signed model comparisons and blind auditing.
import assert from "node:assert/strict";
import { chromium } from "@playwright/test";

const browser = await chromium.launch();
try {
  const page = await browser.newPage();
  const run = { id: "labels", status: "completed", created_at: "2026-11-15", spec: {} };
  const make = (id, margin, fields = {}) => ({
    id,
    cohort: "incidental",
    region: "Nelson",
    original_common_name: "Black-fronted Tern",
    original_taxon: "Chlidonias albostriatus",
    review_status: "unreviewed",
    reviewer_decisions: {},
    photo_license: "cc-by",
    attribution: "Regression fixture",
    scores: {
      best_species: "Ulex europaeus",
      margin,
      species: [{ name: "Ulex europaeus", margin, similarity: 0.616141, box: [0, 0, 10, 10] }],
    },
    ...fields,
  });
  const photos = [
    make("tern", -0.041927),
    make("positive", 0.01, { original_common_name: "Comparison source" }),
    make("audit", 0.9, { audit_sample: true, auditors: [] }),
    make("phone", 0.99, { cohort: "device", region: "device", original_common_name: "Gorse" }),
  ];
  const meaning = {
    declared: true,
    id: "test",
    model_key: "bioclip-2",
    calibrated: false,
    score: "Relative margin",
    use: "Ranking only",
    not_meaning: ["Not identification confidence"],
    operating_point: null,
    abstention: null,
    choosing_an_operating_point: "Requires evaluation",
    evidence: [],
    run_evidence: "Regression fixture",
  };
  photos[3].original_taxon = "Ulex europaeus";
  photos[3].scores.width = 64;
  photos[3].scores.height = 48;
  photos[0].scores.segmentation = {
    status: "ok",
    baseline_retained: true,
    regions: [
      {
        id: "region1",
        box: [0, 0, 10, 10],
        context_box: [0, 0, 10, 10],
        mask_png: "AA==",
        mask_quality: { predicted_iou: 0.9, stability_score: 0.9 },
        views: { tight: { best_species: "Ulex europaeus", margin: -0.177123 } },
      },
    ],
  };
  await page.route("**/api/**", (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/session")
      return route.fulfill({ json: { mode: "local", can_start_runs: false } });
    if (path === "/api/runs") return route.fulfill({ json: [run] });
    if (path === "/api/runs/labels")
      return route.fulfill({ json: { run, photos, score_meaning: meaning } });
    if (path.endsWith("/image")) return route.fulfill({ status: 404 });
    return route.fulfill({ json: [] });
  });
  await page.goto(process.env.WEEDZ_WEB_URL ?? "http://127.0.0.1:3001", {
    waitUntil: "domcontentloaded",
  });
  await page.locator(".photo-row").filter({ hasText: "Black-fronted Tern" }).click();
  assert.equal(await page.locator(".evidence-heading h2").textContent(), "Black-fronted Tern");
  assert.match(
    await page.locator(".evidence-heading").textContent(),
    /No positive watchlist match/,
  );
  assert.doesNotMatch(await page.locator(".evidence-heading").textContent(), /Model hint: Gorse/);
  assert.match(
    await page.locator(".review-form h3").textContent(),
    /compared species visible: Gorse/,
  );
  assert.match(await page.locator(".score-panel").textContent(), /0.042 below/);
  await page.getByLabel("Mask overlay", { exact: true }).selectOption("0");
  assert.match(
    await page.locator(".segmentation-controls").textContent(),
    /No positive watchlist match; top watchlist comparison: Ulex europaeus/,
  );
  await page.locator(".photo-row").filter({ hasText: "Comparison source" }).click();
  assert.match(
    await page.locator(".evidence-heading").textContent(),
    /Model hint: Gorse · needs review/,
  );
  await page.getByRole("button", { name: "Audit sample", exact: true }).click();
  assert.doesNotMatch(
    await page.locator(".queue").textContent(),
    /Model hint|No positive watchlist match/,
  );
  assert.equal(await page.locator(".score-panel").count(), 0);
  await page.getByRole("button", { name: "Device reports", exact: true }).click();
  assert.equal(await page.locator(".evidence-heading h2").textContent(), "Device report");
  assert.match(
    await page.locator(".evidence-heading").textContent(),
    /Screening result has no declared interpretation/,
  );
  assert.match(await page.locator(".image-stage svg").getAttribute("aria-label"), /Device report/);
  assert.doesNotMatch(
    await page.locator(".image-stage svg").getAttribute("aria-label"),
    /Gorse|Ulex/,
  );
  console.log(
    "Original subject titles, negative/positive hints, explicit target review and blind/device boundaries verified.",
  );
} finally {
  await browser.close();
}
