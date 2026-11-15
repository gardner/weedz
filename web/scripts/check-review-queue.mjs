import assert from "node:assert/strict";
import { chromium } from "@playwright/test";

const browser = await chromium.launch();
try {
  const page = await browser.newPage();
  const run = { id: "queue", status: "completed", created_at: "2026-11-15", spec: {} };
  const photos = Array.from({ length: 12 }, (_, index) => ({
    id: `photo-${index}`,
    cohort: "incidental",
    region: "Nelson",
    original_taxon: `Bird ${index}`,
    original_common_name: `Bird ${index}`,
    review_status: "unreviewed",
    scores: { best_species: "Ulex europaeus", margin: 1 - index / 20 },
    photo_license: "cc0",
    attribution: "Test fixture",
    reviewer_decisions: {},
  }));
  await page.route("**/api/**", (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/session")
      return route.fulfill({ json: { mode: "local", can_start_runs: false } });
    if (path === "/api/runs") return route.fulfill({ json: [run] });
    if (path === "/api/runs/queue") return route.fulfill({ json: { run, photos } });
    if (path.endsWith("/image")) return route.fulfill({ status: 404 });
    return route.fulfill({ json: [] });
  });
  await page.goto(process.env.WEEDZ_WEB_URL ?? "http://127.0.0.1:3001", {
    waitUntil: "domcontentloaded",
  });
  await page.locator(".photo-row").first().waitFor();
  for (const width of [1440, 768, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    const queue = await page.locator(".queue").boundingBox();
    const evidence = await page.locator(".evidence").boundingBox();
    assert(
      queue && evidence && queue.y + queue.height <= evidence.y,
      `Queue must be above evidence at ${width}`,
    );
    assert(
      await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
      `No document overflow at ${width}`,
    );
    const rows = page.locator(".photo-row");
    if ((await rows.count()) > 1) {
      await rows.last().focus();
      await page.keyboard.press("Enter");
      assert.equal(await rows.last().getAttribute("aria-pressed"), "true");
      await page.waitForFunction(() => {
        const selected = document.querySelector(".photo-row.selected")?.getBoundingClientRect();
        const strip = document.querySelector(".photo-list")?.getBoundingClientRect();
        return (
          selected && strip && selected.left >= strip.left - 1 && selected.right <= strip.right + 1
        );
      });
      const selected = await rows.last().boundingBox();
      const strip = await page.locator(".photo-list").boundingBox();
      assert(
        selected &&
          strip &&
          selected.x >= strip.x - 1 &&
          selected.x + selected.width <= strip.x + strip.width + 1,
        "Selected last card stays within horizontal strip",
      );
    }
  }
  console.log(
    "Queue above evidence; keyboard selection and viewport bounds verified at 1440/768/390.",
  );
} finally {
  await browser.close();
}
