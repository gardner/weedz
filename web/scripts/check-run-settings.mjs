// A new run sends its sampling period, so the corpus is not one recent week.
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
  const posted = [];
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path === "/api/runs" && request.method() === "POST") {
      posted.push(request.postDataJSON());
      return route.fulfill({ status: 202, json: { id: "new" } });
    }
    if (path === "/api/runs") return route.fulfill({ json: [] });
    await route.fulfill({ status: 404, json: { detail: "Run not found" } });
  });
  await page.goto(process.env.WEEDZ_WEB_URL ?? "http://127.0.0.1:3001");
  await page.locator(".run-settings summary").click();
  await page.getByLabel("Photographed on or after").fill("2015-01-01");
  const start = page.getByRole("button", { name: /Start bounded run/ });
  const before = page.getByLabel("Photographed on or before");
  const tomorrow = new Date(Date.now() + 86_400_000).toLocaleDateString("en-CA");
  await before.fill(tomorrow);
  assert.equal(await start.isDisabled(), true, "a future end date is rejected");
  await before.fill("2024-12-31");
  await start.click();
  await page.getByText("Regional run queued").waitFor();
  assert.equal(posted[0].after, "2015-01-01");
  assert.equal(posted[0].sampling, "stratified");
  console.log("New runs send a sampling period spread across seasons.");
} finally {
  await browser.close();
}
