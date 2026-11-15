// Real production UI + saved real model outputs; never invent an inference animation.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { chromium } from "@playwright/test";
import { finishRecordingInterval } from "./capture-duration.mjs";
import { selectCaptureSource } from "./capture-source.mjs";

const output = process.env.WEEDZ_CAPTURE_DIR;
assert(output && process.env.WEEDZ_FFMPEG);
const origin = process.env.WEEDZ_WEB_URL ?? "http://127.0.0.1:3022";
const runId = "segmentation-experiment-v1";
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1920, height: 1080 } });
const page = await context.newPage();
const errors = [];
const frames = [];
const acknowledgements = [];
const phases = [];
let start;
let end;
let recordingStarted;
let captureEvidence;
const cdp = await context.newCDPSession(page);
cdp.on("Page.screencastFrame", ({ data, metadata, sessionId }) => {
  frames.push({ data: Buffer.from(data, "base64"), time: metadata.timestamp });
  acknowledgements.push(cdp.send("Page.screencastFrameAck", { sessionId }));
});
page.on("pageerror", (error) => errors.push(error.message));
try {
  await page.goto(origin);
  const detail = await (await page.request.get(`${origin}/api/runs/${runId}`)).json();
  assert.equal(detail.run.id, runId);
  const photo = detail.photos.find((item) => item.photo_id === 447484684);
  assert(photo && photo.photo_license === "cc-by");
  assert.equal(photo.latitude, null);
  assert.equal(photo.longitude, null);
  await selectCaptureSource(page, runId, photo);
  const selector = page.getByLabel("Mask overlay", { exact: true });
  await selector.waitFor();
  await selector.selectOption("");
  const window = page.getByLabel("Show search window", { exact: true });
  if (await window.isChecked()) await window.uncheck();
  await page
    .locator(".evidence-heading")
    .evaluate((element) => element.scrollIntoView({ block: "start" }));
  const evidence = photo.scores.segmentation;
  assert.equal(evidence.status, "ok");
  assert.equal(evidence.regions.length, 2);
  const image = await page.request.get(`${origin}/api/runs/${runId}/photos/${photo.id}/image`);
  assert.equal(image.headers()["content-type"], "image/png");
  const source = await image.body();
  assert.equal(createHash("sha256").update(source).digest("hex"), photo.sha256);
  assert(["cc0", "cc-by", "cc-by-nc"].includes(photo.observation_license));
  await writeFile(path.join(output, "source-reference.png"), source);
  for (const [index, region] of evidence.regions.entries()) {
    await writeFile(
      path.join(output, `model-mask-${index + 1}.png`),
      Buffer.from(region.mask_png, "base64"),
    );
  }
  await writeFile(
    path.join(output, "model-evidence.json"),
    JSON.stringify({ run_id: runId, model: detail.run.model, photo }, null, 2),
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
  recordingStarted = performance.now();
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
    .getByRole("heading", { name: "Is the compared species visible: Gorse?", exact: true })
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
  await finishRecordingInterval(page, recordingStarted, 16000);
  end = Date.now() / 1000;
  await cdp.send("Page.stopScreencast");
  await Promise.all(acknowledgements);
  assert.deepEqual(errors, [], "Pipeline UI capture reported browser errors");
  captureEvidence = {
    selection: { run_id: runId, photo_id: photo.id, source_photo_id: photo.photo_id },
    description:
      "Actual production review UI replaying saved outputs from a completed real SAM2.1 + BioCLIP2 inference run. No model inference happens during this UI recording.",
    source: {
      creator: photo.attribution,
      licence: photo.photo_license,
      observation_licence: photo.observation_license,
      observer: photo.observer,
      source_url: photo.source_url,
      source_image_sha256: createHash("sha256").update(source).digest("hex"),
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
  };
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
assert.deepEqual(errors, [], "Pipeline UI capture reported browser errors");
assert(captureEvidence);
const media_sha256 = {};
for (const name of [
  "source-reference.png",
  "original-ui.png",
  "mask-1-ui.png",
  "mask-2-ui.png",
  "classification-1-ui.png",
  "classification-2-ui.png",
  "human-review-controls.png",
  "sam21-pipeline-ui.mp4",
  "model-evidence.json",
]) {
  media_sha256[name] = createHash("sha256")
    .update(await readFile(path.join(output, name)))
    .digest("hex");
}
await writeFile(
  path.join(output, "capture-manifest.json"),
  JSON.stringify({ ...captureEvidence, media_sha256, captureSuccess: true }, null, 2),
);
assert.deepEqual(errors, []);
