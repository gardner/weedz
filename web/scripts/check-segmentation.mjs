// Integration check against an actual segment_pilot output served by the review API.
import assert from "node:assert/strict";
import { chromium } from "@playwright/test";

const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1600, height: 1100 } });
  await page.goto(process.env.WEEDZ_WEB_URL ?? "http://127.0.0.1:3022");
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
