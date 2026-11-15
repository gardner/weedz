// Actual compiled Flutter application, real HTTPS intake and real browser secure storage.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { chromium } from "@playwright/test";

const output = process.env.WEEDZ_CAPTURE_DIR;
assert(output && process.env.WEEDZ_PRIVATE_STATE);
await mkdir(output, { recursive: true });
const enrollment = JSON.parse(
  await readFile(path.join(process.env.WEEDZ_PRIVATE_STATE, "enrollment.json"), "utf8"),
);
const origin = "https://127.0.0.1:8443";
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  ignoreHTTPSErrors: true,
  viewport: { width: 430, height: 932 },
  deviceScaleFactor: 2,
});
const page = await context.newPage();
const errors = [];
const frames = [];
const frameWrites = [];
let recordingStart;
let recordingEnd;
const cdp = await context.newCDPSession(page);
cdp.on("Page.screencastFrame", ({ data, sessionId, metadata }) => {
  frames.push({ data: Buffer.from(data, "base64"), time: metadata.timestamp });
  frameWrites.push(cdp.send("Page.screencastFrameAck", { sessionId }));
});
page.on("pageerror", (error) => errors.push(error.message));
try {
  const upload = await page.request.put(`${origin}/reports/11200000-0000-4000-8000-000000000001`, {
    headers: { Authorization: `Bearer ${enrollment.token}` },
    data: enrollment.report,
  });
  assert.equal(upload.status(), 201, await upload.text());
  await page.goto(origin, { waitUntil: "networkidle" });
  await page.locator("flt-semantics-placeholder").evaluate((element) => element.click());
  await page.waitForTimeout(1200);
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await page.waitForTimeout(800);
  await page.getByRole("textbox", { name: "Submitter token" }).fill(enrollment.token);
  await page.getByRole("button", { name: "Save enrollment securely" }).click();
  await page.getByRole("button", { name: "Delete my data", exact: true }).waitFor();
  await page.waitForTimeout(500);
  await cdp.send("Page.startScreencast", {
    format: "jpeg",
    quality: 95,
    maxWidth: 860,
    maxHeight: 1864,
    everyNthFrame: 1,
  });
  recordingStart = Date.now() / 1000;
  await page.waitForTimeout(3200);
  await page.screenshot({ path: path.join(output, "live-settings-enrolled.png") });
  await page.getByRole("button", { name: "Delete my data", exact: true }).click();
  await page.getByText("Delete all reports from this phone?", { exact: true }).waitFor();
  await page.waitForTimeout(3200);
  await page.screenshot({ path: path.join(output, "live-settings-confirmation.png") });
  await page.getByRole("button", { name: "Delete reports and revoke access", exact: true }).click();
  await page.getByText("Deletion confirmed", { exact: true }).first().waitFor();
  await page.waitForTimeout(3200);
  await page.screenshot({ path: path.join(output, "live-settings-deleted.png") });
  recordingEnd = Date.now() / 1000;
  await cdp.send("Page.stopScreencast");
  await Promise.all(frameWrites);
  const stable = await page.request.delete(`${origin}/submitter`, {
    headers: { Authorization: `Bearer ${enrollment.token}` },
  });
  assert.equal(stable.status(), 200);
  const revoked = await page.request.put(`${origin}/reports/11200000-0000-4000-8000-000000000002`, {
    headers: { Authorization: `Bearer ${enrollment.token}` },
    data: enrollment.report,
  });
  assert.equal(revoked.status(), 401);
  await writeFile(
    path.join(output, "live-capture.json"),
    JSON.stringify(
      {
        runtime:
          "Actual release-compiled Flutter web application in Chromium, real secure-storage web plugin",
        backend:
          "Real isolated HTTPS intake, not a mock; self-signed loopback development certificate",
        report_created_via_real_api: upload.status(),
        report_source:
          "Public CC BY gorse photo with its original desktop pilot model revision, score and ranking revision",
        stable_deletion_receipt: await stable.json(),
        upload_after_deletion: revoked.status(),
        browser_errors: errors,
      },
      null,
      2,
    ),
  );
} finally {
  await context.close();
  await browser.close();
}
assert(frames.length > 0 && recordingStart && recordingEnd);
const encoder = spawn(
  process.env.WEEDZ_FFMPEG,
  [
    "-hide_banner",
    "-loglevel",
    "error",
    "-f",
    "image2pipe",
    "-framerate",
    "25",
    "-i",
    "pipe:0",
    "-an",
    "-c:v",
    "libvpx-vp9",
    "-b:v",
    "0",
    "-crf",
    "20",
    "-pix_fmt",
    "yuv420p",
    path.join(output, "live-flutter-settings.webm"),
  ],
  { stdio: ["pipe", "inherit", "inherit"] },
);
const finished = new Promise((resolve, reject) =>
  encoder.once("exit", (code) =>
    code === 0 ? resolve() : reject(new Error(`Encoder exited ${code}`)),
  ),
);
let cursor = 0;
for (let i = 0; i < Math.ceil((recordingEnd - recordingStart) * 25); i++) {
  const now = recordingStart + i / 25;
  while (cursor + 1 < frames.length && frames[cursor + 1].time <= now) cursor++;
  if (!encoder.stdin.write(frames[cursor].data)) {
    await new Promise((resolve) => encoder.stdin.once("drain", resolve));
  }
}
encoder.stdin.end();
await finished;
