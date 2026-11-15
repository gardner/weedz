// Integration check against an actual segment_pilot output served by the review API.
import assert from "node:assert/strict";
import { chromium } from "@playwright/test";

const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1600, height: 1100 } });
  await page.goto(process.env.WEEDZ_WEB_URL ?? "http://127.0.0.1:3022");
  const origin = new URL(page.url()).origin;
  const detail = await page.request.get(`${origin}/api/runs/segmentation-experiment-v1`);
  assert.equal(detail.status(), 200);
  const { photos } = await detail.json();
  assert(photos.length > 0);
  for (const photo of photos) {
    assert(Array.isArray(photo.scores.box), "original baseline geometry retained");
    for (const region of photo.scores.segmentation.regions) {
      for (const score of Object.values(region.views)) {
        assert.match(score.method, /one letterboxed .* proposal view/);
        assert(!("box" in score), "single view has no ambiguous local box");
        assert(score.species.every((species) => !("box" in species)));
      }
    }
  }
  const image = await page.request.get(
    `${origin}/api/runs/segmentation-experiment-v1/photos/${photos[0].id}/image`,
  );
  assert.equal(image.headers()["content-type"], "image/png");
  const mask = page.getByLabel("Mask overlay", { exact: true });
  await mask.waitFor();
  assert.equal(await mask.inputValue(), "");
  assert.equal(
    await page.locator('image[aria-label="Model-produced segmentation mask"]').count(),
    0,
  );
  await mask.selectOption("0");
  const overlay = page.locator('image[aria-label="Model-produced segmentation mask"]');
  await overlay.waitFor();
  assert.match(await overlay.getAttribute("href"), /^data:image\/png;base64,/);
  await page
    .getByText(
      "Mask quality is separate from species ranking; neither is identification confidence.",
    )
    .waitFor();
  assert.equal(await page.getByText(/tight: .*relative margin/).count(), 1);
  assert.equal(await page.getByText(/masked: .*relative margin/).count(), 1);
  assert.equal(await page.getByText(/context: .*relative margin/).count(), 1);
  await mask.selectOption("");
  assert.equal(await overlay.count(), 0);
  console.log("Actual model-produced mask toggle and independent region scores verified");
} finally {
  await browser.close();
}
