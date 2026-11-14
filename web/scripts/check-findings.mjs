// Reviewers record a different or missed plant, with a box drawn or typed in image pixels.
import assert from "node:assert/strict";
import { chromium } from "@playwright/test";

const browser = await chromium.launch({
  headless: true,
  ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE
    ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE }
    : {}),
});
try {
  const page = await browser.newPage({ viewport: { width: 1400, height: 1000 } });
  const run = {
    id: "run",
    status: "completed",
    detail: "Test fixture",
    created_at: "2024-12-31",
    spec: { before: "2024-12-31", limit_per_region: 1, controls_per_species: 0 },
  };
  const photo = {
    id: "photo",
    region: "Nelson",
    cohort: "incidental",
    original_taxon: "Turdus merula",
    original_common_name: "Blackbird",
    review_status: "unreviewed",
    review_note: "",
    review_reviewer: "",
    reviewer_decisions: {},
    disputed: false,
    review_count: 0,
    scores: { best_species: "Clematis vitalba", box: [0, 0, 200, 150], width: 400, height: 300 },
    photo_license: "cc0",
    coordinate_status: "missing",
    attribution: "Test fixture",
    findings: [
      {
        id: 1,
        kind: "addition",
        species: null,
        other_taxon: "Clematis paniculata",
        box: [10, 10, 50, 50],
        note: "Native, in flower",
        reviewer: "Ben",
        created_at: "2026-11-13T20:00:00+00:00",
      },
    ],
  };
  const posted = [];
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/runs") return route.fulfill({ json: [run] });
    if (path.endsWith("/image")) return route.fulfill({ status: 404 });
    if (path.endsWith("/reviews")) return route.fulfill({ json: [] });
    if (path.endsWith("/findings")) {
      posted.push(route.request().postDataJSON());
      return route.fulfill({ json: { saved: true } });
    }
    await route.fulfill({ json: { run, photos: [photo] } });
  });
  await page.goto(process.env.WEEDZ_WEB_URL ?? "http://127.0.0.1:3001");
  await page.evaluate(() => localStorage.removeItem("weedz-reviewer"));
  await page.reload();

  // Recorded findings are listed with their reviewer and free text kept as typed.
  const recorded = page.locator(".recorded-findings li");
  await recorded.first().waitFor();
  assert.match(await recorded.first().textContent(), /Missed plant.*Clematis paniculata.*Ben/s);
  assert.equal(await page.locator("rect.finding-box").count(), 1, "recorded box is drawn");

  await page.getByLabel("Your name").fill("Ana");
  const open = page.getByRole("button", { name: "Record a different or missed plant" });
  assert.equal(await open.getAttribute("aria-expanded"), "false");
  await open.click();
  assert.equal(await open.getAttribute("aria-expanded"), "true");

  // A correction offers every watchlist species except the suggestion, plus other taxa.
  await page.getByLabel("A different species from the suggestion").check();
  const species = page.getByLabel("Species", { exact: true });
  const options = await species.locator("option").allTextContents();
  assert.ok(!options.some((text) => text.includes("Old man's beard")), "suggestion is excluded");
  assert.ok(options.some((text) => text.includes("Gorse")));
  await species.selectOption("other");
  await page.getByLabel("Other taxon").fill("Clematis forsteri");

  // Drag on the photo to draw a box; the pixel fields follow.
  const photoStage = page.locator(".image-stage svg");
  await photoStage.scrollIntoViewIfNeeded();
  const stage = await photoStage.boundingBox();
  await page.mouse.move(stage.x + stage.width * 0.3, stage.y + stage.height * 0.3);
  await page.mouse.down();
  await page.mouse.move(stage.x + stage.width * 0.6, stage.y + stage.height * 0.7, { steps: 5 });
  await page.mouse.up();
  const edge = async (label) => Number(await page.getByLabel(label, { exact: true }).inputValue());
  const [left, top, right, bottom] = [
    await edge("Left"),
    await edge("Top"),
    await edge("Right"),
    await edge("Bottom"),
  ];
  assert.ok(left < right && top < bottom, `drawn box ${[left, top, right, bottom]} is ordered`);
  assert.ok(right <= 400 && bottom <= 300, "drawn box stays inside the image");
  assert.equal(await page.locator("rect.draft-box").count(), 1, "draft box is drawn");

  // Without a pointer: type the edges. An unordered box blocks saving with a reason.
  const save = page.getByRole("button", { name: "Save finding" });
  await page.getByLabel("Left", { exact: true }).fill("300");
  await page.getByLabel("Right", { exact: true }).fill("100");
  await page.getByText("Left must be less than right").waitFor();
  assert.equal(await save.isDisabled(), true);
  await page.getByLabel("Left", { exact: true }).focus();
  await page.keyboard.press("Control+A");
  await page.keyboard.type("40");
  await page.getByLabel("Top", { exact: true }).fill("30");
  await page.getByLabel("Right", { exact: true }).fill("320");
  await page.getByLabel("Bottom", { exact: true }).fill("290");
  await page.getByLabel("Finding note").fill("Leaflets toothed");
  await save.click();
  await page.getByText("Finding saved locally.").waitFor();
  assert.deepEqual(
    posted.map(({ effort_seconds, ...finding }) => finding),
    [
      {
        kind: "correction",
        species: null,
        other_taxon: "Clematis forsteri",
        box: [40, 30, 320, 290],
        note: "Leaflets toothed",
        reviewer: "Ana",
      },
    ],
  );
  assert.equal(typeof posted[0].effort_seconds, "number");
  assert.equal(await open.getAttribute("aria-expanded"), "false", "the form closes once saved");

  // A missed watchlist plant with no box sends no box.
  await open.click();
  await page.getByLabel("A plant the screening missed").check();
  await page.getByLabel("Species", { exact: true }).selectOption("Ulex europaeus");
  assert.equal(await page.getByLabel("Left", { exact: true }).inputValue(), "", "form was reset");
  await save.click();
  for (let wait = 0; wait < 50 && posted.length < 2; wait++) await page.waitForTimeout(100);
  const { effort_seconds, ...missed } = posted[1];
  assert.deepEqual(missed, {
    kind: "addition",
    species: "Ulex europaeus",
    other_taxon: null,
    box: null,
    note: "",
    reviewer: "Ana",
  });
  console.log("Corrected and missed plants are recorded with a drawn or typed box.");
} finally {
  await browser.close();
}
