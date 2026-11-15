// Capture the real review app against the external, read-only demo snapshot.
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { chromium } from "@playwright/test";
import { finishRecordingInterval } from "./capture-duration.mjs";

const output = path.resolve(process.env.WEEDZ_CAPTURE_DIR ?? "");
assert(process.env.WEEDZ_CAPTURE_DIR, "Set an external WEEDZ_CAPTURE_DIR");
const origin = process.env.WEEDZ_WEB_URL ?? "http://127.0.0.1:3012";
assert(new URL(origin).hostname === "127.0.0.1", "Capture only the local snapshot service");
await mkdir(output, { recursive: true });
assert.notEqual(
  spawnSync("git", ["-C", output, "rev-parse", "--is-inside-work-tree"]).status,
  0,
  "Capture artifacts must remain outside every git worktree",
);
const browser = await chromium.launch({ headless: true, args: ["--disable-dev-shm-usage"] });
const context = await browser.newContext({
  viewport: { width: 1920, height: 1080 },
  deviceScaleFactor: 1,
  recordVideo: { dir: output, size: { width: 1920, height: 1080 } },
  reducedMotion: "reduce",
});
const page = await context.newPage();
const recordingStarted = performance.now();
const errors = [];
let captureSuccess = false;
page.on("pageerror", (error) => errors.push(error.message));
try {
  await page.goto(origin, { waitUntil: "networkidle" });
  await page.locator(".photo-row").first().waitFor();
  await page.waitForTimeout(1500);
  await page.screenshot({ path: path.join(output, "web-ranked-queue.png") });
  await page.getByRole("button", { name: "References", exact: true }).click();
  await page.waitForTimeout(700);
  await page.locator(".photo-row").first().click();
  await page.waitForTimeout(1200);
  await page.evaluate(() =>
    window.scrollTo(
      0,
      document.querySelector(".evidence").getBoundingClientRect().top + scrollY - 24,
    ),
  );
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(output, "web-reference-evidence.png") });
  await page.getByLabel("Show search window").uncheck();
  await page.waitForTimeout(1000);
  await page.getByLabel("Show search window").check();
  await page.waitForTimeout(1000);
  await page.locator(".photo-row").nth(1).click();
  await page.waitForTimeout(1200);
  await page.screenshot({ path: path.join(output, "web-reference-comparison.png") });
  await page.getByRole("button", { name: "Incidental photos", exact: true }).click();
  await page.waitForTimeout(1000);
  await page.locator(".photo-row").first().click();
  await page.waitForTimeout(1500);
  await page.evaluate(() =>
    window.scrollTo(
      0,
      document.querySelector(".evidence").getBoundingClientRect().top + scrollY - 24,
    ),
  );
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(output, "web-candidate-window.png") });
  const result = await (await page.request.get(`${origin}/api/runs`)).json();
  await writeFile(
    path.join(output, "web-capture.json"),
    JSON.stringify(
      {
        disclosure:
          "Actual review web UI, curated public-photo subset, original pilot scores. Locations withheld. No review was submitted.",
        viewport: { width: 1920, height: 1080 },
        runs: result.map(({ id, status }) => ({ id, status })),
        browserErrors: errors,
      },
      null,
      2,
    ),
  );
  await finishRecordingInterval(page, recordingStarted, 13500);
  assert.deepEqual(errors, []);
  captureSuccess = true;
} finally {
  const video = page.video();
  await context.close();
  await video.saveAs(path.join(output, "web-review-interactions.webm"));
  await browser.close();
  if (captureSuccess) {
    assert.deepEqual(errors, []);
    const media_sha256 = {};
    for (const name of [
      "web-review-interactions.webm",
      "web-reference-comparison.png",
      "web-candidate-window.png",
    ]) {
      media_sha256[name] = createHash("sha256")
        .update(await readFile(path.join(output, name)))
        .digest("hex");
    }
    const filename = path.join(output, "web-capture.json");
    const evidence = JSON.parse(await readFile(filename, "utf8"));
    await writeFile(
      filename,
      JSON.stringify(
        { ...evidence, browserErrors: errors, media_sha256, captureSuccess: true },
        null,
        2,
      ),
    );
  }
}
