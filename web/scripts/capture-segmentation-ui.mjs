// Real production UI + saved real model outputs; never invent an inference animation.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { writeFile } from "node:fs/promises";
import path from "node:path";
import { chromium } from "@playwright/test";

const output = process.env.WEEDZ_CAPTURE_DIR;
assert(output && process.env.WEEDZ_FFMPEG);
const origin = process.env.WEEDZ_WEB_URL ?? "http://127.0.0.1:3022";
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1920, height: 1080 } });
const page = await context.newPage();
const errors = [];
const frames = [];
const acknowledgements = [];
const phases = [];
let start;
let end;
const cdp = await context.newCDPSession(page);
cdp.on("Page.screencastFrame", ({ data, metadata, sessionId }) => {
  frames.push({ data: Buffer.from(data, "base64"), time: metadata.timestamp });
  acknowledgements.push(cdp.send("Page.screencastFrameAck", { sessionId }));
});
page.on("pageerror", (error) => errors.push(error.message));
try {
  await page.goto(origin);
  await page.getByRole("button", { name: "References", exact: true }).click();
  await page.locator("button.photo-row").filter({ hasText: "Gorse" }).click();
  const selector = page.getByLabel("Mask overlay", { exact: true });
  await selector.waitFor();
  await selector.selectOption("");
  const window = page.getByLabel("Show search window", { exact: true });
  if (await window.isChecked()) await window.uncheck();
  await page
    .locator(".evidence-heading")
    .evaluate((element) => element.scrollIntoView({ block: "start" }));
  const detail = await (
    await page.request.get(`${origin}/api/runs/segmentation-experiment-v1`)
  ).json();
  const photo = detail.photos.find((item) => item.photo_id === 447484684);
  assert(photo && photo.photo_license === "cc-by");
  assert.equal(photo.latitude, null);
  assert.equal(photo.longitude, null);
  const evidence = photo.scores.segmentation;
  assert.equal(evidence.status, "ok");
  assert.equal(evidence.regions.length, 2);
  const image = await page.request.get(
    `${origin}/api/runs/segmentation-experiment-v1/photos/${photo.id}/image`,
  );
  assert.equal(image.headers()["content-type"], "image/png");
  const source = await image.body();
  await writeFile(path.join(output, "source-reference.png"), source);
  for (const [index, region] of evidence.regions.entries()) {
    await writeFile(
      path.join(output, `model-mask-${index + 1}.png`),
      Buffer.from(region.mask_png, "base64"),
    );
  }
  await writeFile(
    path.join(output, "model-evidence.json"),
    JSON.stringify({ model: detail.run.model, photo }, null, 2),
  );
  await page.waitForTimeout(600);
  await cdp.send("Page.startScreencast", {
    format: "jpeg",
    quality: 95,
    maxWidth: 1920,
    maxHeight: 1080,
    everyNthFrame: 1,
  });
  start = Date.now() / 1000;
  phases.push({ stage: "original", seconds: 0 });
  await page.waitForTimeout(2500);
  await page.locator(".image-stage").screenshot({ path: path.join(output, "original-ui.png") });
  for (const index of [0, 1]) {
    await selector.selectOption(String(index));
    phases.push({
      stage: `actual-mask-${index + 1}-and-view-scores`,
      seconds: Date.now() / 1000 - start,
    });
    await page.waitForTimeout(3500);
    await page
      .locator(".image-stage")
      .screenshot({ path: path.join(output, `mask-${index + 1}-ui.png`) });
    await page
      .locator(".segmentation-controls")
      .screenshot({ path: path.join(output, `classification-${index + 1}-ui.png`) });
    await page.screenshot({ path: path.join(output, `pipeline-state-${index + 1}.png`) });
  }
  await page
    .getByText("Is the suggested species visible?", { exact: true })
    .evaluate((element) => element.scrollIntoView({ block: "center" }));
  phases.push({
    stage: "actual-review-controls-no-decision-saved",
    seconds: Date.now() / 1000 - start,
  });
  await page.waitForTimeout(3500);
  await page.screenshot({ path: path.join(output, "human-review-controls.png") });
  await page
    .locator(".evidence-heading")
    .evaluate((element) => element.scrollIntoView({ block: "start" }));
  await selector.selectOption("");
  phases.push({ stage: "return-to-original", seconds: Date.now() / 1000 - start });
  await page.waitForTimeout(2000);
  end = Date.now() / 1000;
  await cdp.send("Page.stopScreencast");
  await Promise.all(acknowledgements);
  await writeFile(
    path.join(output, "capture-manifest.json"),
    JSON.stringify(
      {
        description:
          "Actual production review UI replaying saved outputs from a completed real SAM2.1 + BioCLIP2 inference run. No model inference happens during this UI recording.",
        source: {
          creator: photo.attribution,
          licence: photo.photo_license,
          source_url: photo.source_url,
          source_pixels_sha256: createHash("sha256").update(source).digest("hex"),
          modification:
            "Metadata-free upright lossless PNG from the eligible public reference; actual mask overlay is drawn by the product UI.",
        },
        segmentation: evidence.provenance,
        baseline: detail.run.model,
        phases,
        duration_seconds: end - start,
        browser_errors: errors,
        interpretation:
          "Class-agnostic masks; partial regions are not complete plant boundaries. View margins are not confidence. No improved recall claim.",
      },
      null,
      2,
    ),
  );
} finally {
  await context.close();
  await browser.close();
}
assert(start && end && frames.length);
const encoder = spawn(
  process.env.WEEDZ_FFMPEG,
  [
    "-v",
    "error",
    "-n",
    "-f",
    "image2pipe",
    "-framerate",
    "25",
    "-i",
    "pipe:0",
    "-an",
    "-c:v",
    "libx264",
    "-preset",
    "fast",
    "-crf",
    "18",
    "-pix_fmt",
    "yuv420p",
    "-movflags",
    "+faststart",
    path.join(output, "sam21-pipeline-ui.mp4"),
  ],
  { stdio: ["pipe", "inherit", "inherit"] },
);
const finished = new Promise((resolve, reject) =>
  encoder.once("exit", (code) =>
    code === 0 ? resolve() : reject(new Error(`Encoder exited ${code}`)),
  ),
);
let cursor = 0;
for (let index = 0; index < Math.ceil((end - start) * 25); index++) {
  const now = start + index / 25;
  while (cursor + 1 < frames.length && frames[cursor + 1].time <= now) cursor++;
  if (!encoder.stdin.write(frames[cursor].data))
    await new Promise((resolve) => encoder.stdin.once("drain", resolve));
}
encoder.stdin.end();
await finished;
assert.deepEqual(errors, []);
