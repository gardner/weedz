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
  await page.getByRole("button", { name: /Start bounded run/ }).click();
  await page.getByText("Regional run queued").waitFor();
  assert.equal(posted[0].after, "2015-01-01");
  assert.equal(posted[0].sampling, "stratified");
  console.log("New runs send a sampling period spread across seasons.");
} finally {
  await browser.close();
}
