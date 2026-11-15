// Operational smoke check: real authenticated read-only review, never saves decisions.
import assert from "node:assert/strict";
import { mkdir, readFile, stat } from "node:fs/promises";
import { chromium } from "@playwright/test";

const origin = process.env.WEEDZ_WEB_URL;
const tokenFile = process.env.WEEDZ_REVIEWER_TOKEN_FILE;
const evidence = process.env.WEEDZ_CHECK_OUTPUT;
assert(
  origin && tokenFile && evidence,
  "Set the site URL, private invite file and NEW evidence directory",
);
assert.equal((await stat(tokenFile)).mode & 0o077, 0, "Invite file must be owner-only");
const token = (await readFile(tokenFile, "utf8")).trim();
await mkdir(evidence, { recursive: false });
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
const errors = [];
page.on("pageerror", (error) => errors.push(error.message));
try {
  await page.goto(origin, { waitUntil: "domcontentloaded" });
  await page.getByLabel("Reviewer token", { exact: true }).fill(token);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.locator("button.photo-row").first().waitFor();
  assert.equal(await page.getByRole("link", { name: /Workflow history/ }).count(), 0);
  for (const width of [390, 768, 1440]) {
    await page.setViewportSize({ width, height: 1000 });
    const tabs = page.locator(".cohort-tabs");
    const bounds = await tabs.boundingBox();
    assert(bounds);
    for (const tab of await tabs.locator("button").all()) {
      const box = await tab.boundingBox();
      assert(
        box && box.x >= bounds.x - 1 && box.x + box.width <= bounds.x + bounds.width + 1,
        "Every cohort tab must fit the queue",
      );
    }
    await page.screenshot({ path: `${evidence}/${width}-review.png` });
  }
  assert.deepEqual(errors, []);
  console.log(
    "Authenticated real review renders without local-workflow links or clipped cohort tabs.",
  );
} finally {
  await page.request.delete(`${origin}/api/session`);
  await browser.close();
}
