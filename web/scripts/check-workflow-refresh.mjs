// Dynamic worker health changes controls without reloading the review desk or its filters.
import assert from "node:assert/strict";
import { chromium, expect } from "@playwright/test";

const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage();
  let ready = false;
  let unavailable = false;
  let hold = false;
  let started;
  let release;
  const held = new Promise((resolve) => {
    started = resolve;
  });
  const delayed = new Promise((resolve) => {
    release = resolve;
  });
  await page.route("**/api/**", async (route) => {
    if (new URL(route.request().url()).pathname === "/api/session") {
      if (route.request().method() === "DELETE")
        return route.fulfill({ json: { signed_out: true } });
      if (hold) {
        started();
        await delayed;
      }
      return route.fulfill({
        status: unavailable ? 503 : 200,
        json: unavailable
          ? { detail: "Unavailable" }
          : {
              mode: "tokens",
              reviewer: "Stable reviewer",
              can_start_runs: ready,
            },
      });
    }
    return route.fulfill({ json: [] });
  });
  await page.goto(process.env.WEEDZ_WEB_URL ?? "http://127.0.0.1:3001", {
    waitUntil: "domcontentloaded",
  });
  await page.getByLabel("Filter region").selectOption("Nelson");
  await page.locator(".run-settings summary").click();
  const start = page.getByRole("button", { name: "Start bounded run" });
  await expect(start).toBeDisabled();
  ready = true;
  await expect(start).toBeEnabled({ timeout: 8000 });
  assert.equal(await page.getByLabel("Filter region").inputValue(), "Nelson");
  unavailable = true;
  await expect(start).toBeDisabled({ timeout: 8000 });
  await expect(page.locator(".signed-in")).toContainText("Stable reviewer");
  assert.equal(await page.getByLabel("Filter region").inputValue(), "Nelson");
  unavailable = false;
  hold = true;
  await held;
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await page.getByRole("button", { name: "Sign in", exact: true }).waitFor();
  release();
  await page.waitForTimeout(100);
  await expect(page.getByRole("button", { name: "Sign in", exact: true })).toBeVisible();
  assert.equal(await page.locator(".signed-in").count(), 0);
  console.log(
    "Worker recovery/outage refreshes controls while preserving identity and review filters.",
  );
} finally {
  await browser.close();
}
