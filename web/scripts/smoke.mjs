// Read-only browser checks against an already completed local regional run.
import assert from "node:assert/strict";
import { mkdir } from "node:fs/promises";
import { chromium } from "@playwright/test";

const origin = process.env.WEEDZ_WEB_URL ?? "http://127.0.0.1:3001";
const artifacts = new URL("../../runs/nelson-tasman-review/", import.meta.url);
await mkdir(artifacts, { recursive: true });
const browser = await chromium.launch({
  headless: true,
  ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE
    ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE }
    : {}),
});
try {
  const page = await browser.newPage({ viewport: { width: 1600, height: 1100 } });
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto(origin);
  const runsResponse = await page.request.get(`${origin}/api/runs`);
  assert.equal(runsResponse.status(), 200);
  const runs = await runsResponse.json();
  const run = runs.find((item) => item.status === "completed");
  assert.ok(run, "Complete a regional pilot before running the browser smoke checks");
  await page.locator(".run-settings summary").click();
  await page.locator(".settings-grid select").selectOption(run.id);
  await page.locator(".photo-row").first().waitFor({ timeout: 30_000 });
  const result = await (await page.request.get(`${origin}/api/runs/${run.id}`)).json();
  const animalCount = result.photos.filter((photo) => photo.cohort === "incidental").length;
  const references = result.photos.filter((photo) => photo.cohort === "reference").length;
  assert.equal(await page.locator(".photo-row").count(), animalCount);
  await page.getByLabel("Filter region").selectOption("Nelson");
  assert.equal(
    await page.locator(".photo-row").count(),
    result.photos.filter((photo) => photo.cohort === "incidental" && photo.region === "Nelson")
      .length,
  );
  await page.getByLabel("Filter region").selectOption("all");
  await page.getByRole("button", { name: "References", exact: true }).click();
  assert.equal(await page.locator(".photo-row").count(), references);
  assert.match((await page.locator(".image-caption").textContent()) ?? "", /Reference photo/);
  await page.getByRole("button", { name: "Incidental photos", exact: true }).click();
  await page.locator(".photo-row").first().click();
  await page.getByLabel("Show search window").uncheck();
  assert.equal(await page.locator(".image-stage rect").count(), 0);
  await page.getByLabel("Show search window").check();
  assert.equal(await page.locator(".image-stage rect").count(), 1);
  assert.equal(
    await page.locator(".image-stage svg image").evaluate((element) => {
      const image = new Image();
      return new Promise((resolve) => {
        image.onload = () => resolve(image.naturalWidth > 0);
        image.onerror = () => resolve(false);
        image.src = element.getAttribute("href");
      });
    }),
    true,
  );
  const exported = await page.request.get(`${origin}/api/runs/${run.id}/export`);
  assert.equal(exported.status(), 200);
  assert.equal((await exported.json()).photos.length, result.photos.length);
  await page.locator(".run-settings summary").click();
  await page.screenshot({ path: new URL("desktop.png", artifacts).pathname, fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: new URL("mobile.png", artifacts).pathname, fullPage: true });
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
  assert.deepEqual(errors, []);
  console.log(
    JSON.stringify({
      run: run.id,
      animalCount,
      references,
      browserErrors: errors.length,
      horizontalOverflow: false,
    }),
  );
} finally {
  await browser.close();
}
