// Real product DOM regression: duplicate Gorse labels must not select another run/photo.
import assert from "node:assert/strict";
import { chromium } from "@playwright/test";
import { selectCaptureSource } from "./capture-source.mjs";

const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage();
  const target = "segmentation-experiment-v1";
  const photo = (id) => ({
    id,
    photo_id: id === "expected-gorse" ? 447484684 : 999,
    cohort: "reference",
    region: "Nelson",
    original_taxon: "Ulex europaeus",
    original_common_name: "Gorse",
    review_status: "unreviewed",
    photo_license: "cc-by",
    attribution: "Selector test fixture",
    reviewer_decisions: {},
    scores: { best_species: "Ulex europaeus", margin: 0.2, width: 3, height: 3 },
  });
  const runs = ["newer", target].map((id) => ({
    id,
    status: "completed",
    created_at: "2026-11-15",
    spec: {},
  }));
  await page.route("**/api/**", (route) => {
    assert.equal(route.request().method(), "GET", "Selection must not save a review");
    const url = new URL(route.request().url()).pathname;
    if (url === "/api/session")
      return route.fulfill({ json: { mode: "local", can_start_runs: false } });
    if (url === "/api/runs") return route.fulfill({ json: runs });
    if (url.endsWith("/image")) return route.fulfill({ status: 404 });
    const run = runs.find((item) => url === `/api/runs/${item.id}`);
    if (run)
      return route.fulfill({
        json: {
          run,
          photos:
            run.id === target
              ? [photo("expected-gorse"), photo("duplicate-gorse")]
              : [photo("wrong-gorse")],
        },
      });
    return route.fulfill({ json: [] });
  });
  await page.goto(process.env.WEEDZ_WEB_URL ?? "http://127.0.0.1:3001", {
    waitUntil: "domcontentloaded",
  });
  await selectCaptureSource(page, target, photo("expected-gorse"));
  assert.equal(await page.locator(".run-settings select").first().inputValue(), target);
  assert.equal(
    await page.locator(".image-stage image").first().getAttribute("href"),
    `/api/runs/${target}/photos/expected-gorse/image`,
  );
} finally {
  await browser.close();
}
