// A ready collection worker does not make a private Temporal UI public.
import assert from "node:assert/strict";
import { chromium } from "@playwright/test";

const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage();
  await page.route("**/api/**", (route) =>
    route.fulfill({
      json:
        new URL(route.request().url()).pathname === "/api/session"
          ? { mode: "local", can_start_runs: true }
          : [],
    }),
  );
  await page.goto(process.env.WEEDZ_WEB_URL ?? "http://127.0.0.1:3001", {
    waitUntil: "domcontentloaded",
  });
  await page.locator(".run-settings summary").click();
  assert.equal(await page.getByRole("button", { name: "Start bounded run" }).isDisabled(), false);
  assert.equal(await page.getByRole("link", { name: /Workflow history/ }).count(), 0);
  console.log("Ready workflow processing does not expose an unconfigured private history URL.");
} finally {
  await browser.close();
}
