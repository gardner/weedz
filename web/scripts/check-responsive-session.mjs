// Regression only: production components with controlled session responses, no review writes.
import assert from "node:assert/strict";
import { chromium } from "@playwright/test";

const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  await page.route("**/api/**", async (route) => {
    if (new URL(route.request().url()).pathname === "/api/session") {
      return route.fulfill({
        json:
          route.request().method() === "DELETE"
            ? { signed_out: true }
            : {
                mode: "tokens",
                reviewer: "Test reviewer with a longer name",
                can_start_runs: false,
              },
      });
    }
    return route.fulfill({ json: [] });
  });
  await page.goto(process.env.WEEDZ_WEB_URL ?? "http://127.0.0.1:3001", {
    waitUntil: "domcontentloaded",
  });
  await page.locator(".signed-in").waitFor({ state: "attached" });
  for (const width of [1440, 768, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    const signOut = page.getByRole("button", { name: "Sign out", exact: true });
    assert(await signOut.isVisible(), `Sign out must remain reachable at ${width}px`);
    assert.equal(
      await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
      true,
    );
  }
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await page.getByRole("button", { name: "Sign in", exact: true }).waitFor();
  console.log(
    "Signed-in identity and logout remain reachable without horizontal overflow at desktop, tablet and phone widths.",
  );
} finally {
  await browser.close();
}
