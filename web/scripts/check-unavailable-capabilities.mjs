// Missing or invalid session capabilities must never enable hosted workflows.
import assert from "node:assert/strict";
import { chromium } from "@playwright/test";

const browser = await chromium.launch({ headless: true });
try {
  for (const body of [{ error: "Unavailable" }, {}, { can_start_runs: "true" }, null]) {
    const page = await browser.newPage();
    await page.route("**/api/**", (route) =>
      route.fulfill({
        status: new URL(route.request().url()).pathname === "/api/session" ? 503 : 200,
        json: new URL(route.request().url()).pathname === "/api/session" ? body : [],
      }),
    );
    await page.goto("http://127.0.0.1:3001", { waitUntil: "domcontentloaded" });
    await page.locator(".run-settings summary").click();
    await page.getByRole("button", { name: "Start bounded run" }).waitFor();
    assert(await page.getByRole("button", { name: "Start bounded run" }).isDisabled());
    assert.equal(await page.getByRole("link", { name: /Workflow history/ }).count(), 0);
    await page.close();
  }
  const page = await browser.newPage();
  await page.route("**/api/**", (route) => {
    const session = new URL(route.request().url()).pathname === "/api/session";
    return route.fulfill({
      status: session && route.request().method() === "GET" ? 401 : 200,
      json: session ? { mode: "tokens", reviewer: "Test reviewer" } : [],
    });
  });
  await page.goto("http://127.0.0.1:3001", { waitUntil: "domcontentloaded" });
  await page.getByLabel("Reviewer token", { exact: true }).fill("test-token");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.locator(".run-settings summary").click();
  assert(await page.getByRole("button", { name: "Start bounded run" }).isDisabled());
  assert.equal(await page.getByRole("link", { name: /Workflow history/ }).count(), 0);
  await page.close();
  console.log("Missing and malformed session capabilities refuse collection and workflow links.");
} finally {
  await browser.close();
}
