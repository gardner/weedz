// Device reports are labelled as such, with their provenance, version stamps and exact
// location; a report sent without image consent shows no image at all (issue #58).
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
    id: "device-reports",
    status: "receiving",
    detail: "2 reports in review · 1 withdrawn",
    created_at: "2026-11-14",
    spec: { before: "2024-12-31", limit_per_region: 12, controls_per_species: 1 },
  };
  const area = (accuracy) => ({
    status: "searchable",
    reason: "",
    centre: [-41.271234, 173.283456],
    centre_is: "observation point (where the photographer was), not a plant point",
    accuracy_m: accuracy,
    allowance_m: 100,
    allowance_reason: "100 m declared allowance for camera-to-plant distance",
    radius_m: accuracy + 100,
    site_context: accuracy <= 20,
  });
  const report = (id, consent, fields = {}) => ({
    id,
    region: "device",
    cohort: "device",
    reference_species: null,
    original_taxon: "Ulex europaeus",
    original_common_name: "Gorse",
    review_status: "unreviewed",
    review_note: "",
    review_reviewer: "",
    reviewer_decisions: {},
    disputed: false,
    review_count: 0,
    observed_on: "2026-10-01",
    uploaded_at: "2026-10-02T01:00:00.000000Z",
    scores: consent
      ? { best_species: "Ulex europaeus", margin: 0.12, width: 64, height: 48 }
      : { best_species: "Ulex europaeus", margin: 0.05 },
    image_path: consent ? `images/device/${id}.jpg` : "",
    photo_license: consent ? "cc-by" : "",
    observation_license: consent ? "cc-by" : "",
    attribution: consent ? "Aroha" : "Device report (no credit given)",
    source_url: "",
    observer: "submitter 1",
    coordinate_status: "public",
    latitude: -41.271234,
    longitude: 173.283456,
    positional_accuracy_m: 8,
    encounter_group: "device-1-a",
    encounter_size: 2,
    encounter_linkable: true,
    limits: {
      search_area: area(8),
      dates: {
        photographed: "2026-10-01",
        uploaded: "2026-10-02",
        screened: null,
        days_photo_to_upload: 1,
        days_photo_to_screening: null,
        current_presence: "If the plant is visible, the photo shows it was there then",
      },
    },
    lead: { suggestion: null, plants: {} },
    device: {
      submitter: 1,
      report_id: id,
      received_at: "2026-10-02T01:00:00.000000Z",
      captured_at: "2026-10-01T10:00:00+13:00",
      app_version: "0.1.0",
      model_key: "bioclip-2",
      revision: "f2b4c1d",
      ranking_revision: 4,
      score_meaning: "bioclip-2/ranking-4/meaning-1",
      consent_wording: "2026-11",
      image_consent: consent,
    },
    ...fields,
  });
  const photos = [
    report("device-1-a", true),
    report("device-1-b", false),
    // Consented, but the crop is not kept: nothing to request either.
    report("device-1-c", true, {
      image_path: "",
      scores: { best_species: "Ulex europaeus", margin: 0.01, width: 64, height: 48 },
    }),
  ];
  const images = [];
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/session") return route.fulfill({ json: { mode: "local" } });
    if (path === "/api/runs") return route.fulfill({ json: [run] });
    if (path.endsWith("/image")) {
      images.push(path);
      return route.fulfill({ status: 404 });
    }
    if (path.endsWith("/reviews")) return route.fulfill({ json: [] });
    if (path.endsWith("/study")) return route.fulfill({ json: null });
    if (path === "/api/studies") return route.fulfill({ json: [] });
    await route.fulfill({ json: { run, photos, withdrawn_reports: 1 } });
  });
  await page.goto(process.env.WEEDZ_WEB_URL ?? "http://127.0.0.1:3001");

  // The device run opens on its own view, not the empty incidental one.
  const rows = page.locator(".photo-row");
  await rows.nth(1).waitFor();
  const tab = page.getByRole("button", { name: "Device reports" });
  assert.equal(await tab.getAttribute("aria-pressed"), "true");

  const evidence = page.locator(".evidence");
  await evidence.getByText("DEVICE REPORT", { exact: false }).first().waitFor();
  const text = await evidence.textContent();
  for (const shown of [
    "Submitter 1",
    "App 0.1.0",
    "bioclip-2 f2b4c1d",
    "ranking revision 4",
    "bioclip-2/ranking-4/meaning-1",
    "Consent wording 2026-11",
    "CC-BY",
    "Aroha",
    "Margin 0.12",
  ]) {
    assert.ok(text.includes(shown), `provenance shows ${shown}`);
  }
  // The exact point the device recorded, with its accuracy.
  assert.match(text, /-41\.271234, 173\.283456 ±8 m/);
  assert.equal(await evidence.getByText("View on iNaturalist").count(), 0);
  await evidence.getByText("Same site visit as 1 other photo").waitFor();
  await evidence.getByRole("heading", { name: "Follow-up" }).waitFor();

  const axe = await new AxeBuilder({ page }).include(".evidence").analyze();
  assert.deepEqual(
    axe.violations.map((violation) => violation.id),
    [],
    "the device report passes axe",
  );

  // Without image consent there is no image to request, only the reason.
  await rows.nth(1).click();
  await evidence.getByText("did not consent to share it").first().waitFor();
  assert.equal(await page.locator(".image-stage img, .image-stage svg image").count(), 0);
  assert.equal(await evidence.getByText("Open full image").count(), 0);
  assert.equal(await evidence.getByText("Aroha").count(), 0);
  await rows.nth(2).click();
  await evidence.getByText("the crop was not received").first().waitFor();
  assert.equal(await page.locator(".image-stage img, .image-stage svg image").count(), 0);
  assert.ok(
    images.every((path) => !path.includes("device-1-b") && !path.includes("device-1-c")),
    "no image is requested for a report without a kept crop",
  );
  console.log("Device report checks passed");
} finally {
  await browser.close();
}
