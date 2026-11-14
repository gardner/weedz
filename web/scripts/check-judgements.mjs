// Identity, location usefulness, historical relevance and novelty are judged separately.
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
  const at = "2026-11-13T20:00:00+00:00";
  const photo = {
    id: "photo",
    region: "Nelson",
    cohort: "incidental",
    original_taxon: "Turdus merula",
    original_common_name: "Blackbird",
    review_status: "confirmed",
    review_note: "",
    review_reviewer: "Ben",
    reviewer_decisions: { Ben: "confirmed" },
    disputed: false,
    review_count: 1,
    observed_on: "2019-05-01",
    scores: { best_species: "Clematis vitalba", box: [0, 0, 200, 150], width: 400, height: 300 },
    photo_license: "cc0",
    // No public location and no reference snapshot: some claims cannot be made.
    coordinate_status: "missing",
    // Only gorse was compared with records, so only a gorse plant can be judged against them.
    reference_comparison: {
      "Ulex europaeus": { comparable: true, nearest: null, within_radius: 0 },
      "Clematis vitalba": { comparable: false, reason: "Not queried in this reference snapshot" },
    },
    attribution: "Test fixture",
    findings: [
      {
        id: 7,
        kind: "addition",
        species: "Ulex europaeus",
        other_taxon: null,
        box: null,
        note: "",
        reviewer: "Ben",
        created_at: at,
        judgements: {
          identity: {},
          location: {},
          history: {},
          novelty: { Ben: { value: "new_in_photo", note: "", created_at: at } },
        },
        judgement_disputes: [],
      },
    ],
    judgements: {
      identity: {},
      location: {
        Ben: { value: "camera_point_only", note: "Vine is across the river", created_at: at },
        Carol: { value: "too_imprecise", note: "", created_at: at },
      },
      history: {},
      novelty: {},
    },
    judgement_disputes: ["location"],
  };
  const posted = [];
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/runs") return route.fulfill({ json: [run] });
    if (path.endsWith("/image")) return route.fulfill({ status: 404 });
    if (path.endsWith("/reviews")) return route.fulfill({ json: [] });
    if (path.endsWith("/findings")) return route.fulfill({ json: [] });
    if (path.endsWith("/judgements")) {
      if (route.request().method() !== "POST") return route.fulfill({ json: [] });
      posted.push(route.request().postDataJSON());
      return route.fulfill({ json: { saved: true } });
    }
    // Time measured only on judgements still counts; untimed ones are listed, never zero.
    const review_effort = {
      total_minutes: 0.5,
      measured_decisions: 0,
      unmeasured_decisions: 0,
      measured_judgements: 1,
      unmeasured_judgements: 1,
    };
    await route.fulfill({ json: { run, photos: [photo], review_effort } });
  });
  await page.goto(process.env.WEEDZ_WEB_URL ?? "http://127.0.0.1:3001");
  await page.evaluate(() => localStorage.removeItem("weedz-reviewer"));
  await page.reload();

  const section = page.getByRole("region", { name: "Separate judgements" });
  await section.waitFor();
  await page.getByText("0.5 min measured review time · 1 judgement not timed").waitFor();

  // Standing judgements are attributed, and disagreement on one dimension is surfaced.
  const location = section.locator(".judgement", { has: page.getByLabel("Location usefulness") });
  assert.match(await location.textContent(), /Reviewers disagree/);
  assert.match(await location.textContent(), /Ben.*Camera point only.*across the river/s);
  assert.match(await location.textContent(), /Carol.*Too imprecise/s);
  const identity = section.locator(".judgement", { has: page.getByLabel("Identity") });
  assert.match(await identity.textContent(), /Not assessed yet/);
  assert.doesNotMatch(await identity.textContent(), /Reviewers disagree/);

  // Saving needs a name, like every decision.
  const saveIdentity = page.getByRole("button", { name: "Save identity" });
  assert.equal(await saveIdentity.isDisabled(), true, "no name, no judgement");
  await page.getByLabel("Your name").fill("Ana");

  // Each dimension is saved on its own and leaves the decision alone.
  await page.getByLabel("Identity", { exact: true }).selectOption("confirmed");
  await page.getByLabel("Identity note").fill("Leaflets and achenes visible");
  await saveIdentity.click();
  await page.getByText("Judgement saved locally.").waitFor();
  const { effort_seconds, ...first } = posted[0];
  assert.deepEqual(first, {
    finding_id: null,
    dimension: "identity",
    value: "confirmed",
    note: "Leaflets and achenes visible",
    reviewer: "Ana",
  });
  assert.equal(typeof effort_seconds, "number");
  assert.equal(await page.getByLabel("Identity note").inputValue(), "", "note clears on save");

  // A camera point is not a plant point: a missing location cannot be judged usable.
  const usable = page.getByLabel("Location usefulness").locator("option[value=usable]");
  assert.equal(await usable.isDisabled(), true);
  assert.match(await location.textContent(), /obscured or missing/);

  // Without comparable reference records, novelty against records is unavailable.
  const novelty = page.getByLabel("Novelty", { exact: true });
  for (const value of ["absent_from_references", "earlier_than_records"]) {
    assert.equal(await novelty.locator(`option[value=${value}]`).isDisabled(), true, value);
  }
  assert.equal(await novelty.locator("option[value=new_in_photo]").isDisabled(), false);

  // A verified new locality needs its verification evidence.
  const saveNovelty = page.getByRole("button", { name: "Save novelty" });
  await novelty.selectOption("verified_new_locality");
  assert.equal(await saveNovelty.isDisabled(), true, "no evidence, no verified claim");
  await page.getByText(/needs the verification evidence/).waitFor();
  await page.getByLabel("Novelty note").fill("DOC ranger visit 2026-10-02 confirmed");
  await saveNovelty.click();
  for (let wait = 0; wait < 50 && posted.length < 2; wait++) await page.waitForTimeout(100);
  assert.equal(posted[1].dimension, "novelty");
  assert.equal(posted[1].value, "verified_new_locality");
  assert.equal(posted[1].note, "DOC ranger visit 2026-10-02 confirmed");

  // A dated photo can be judged recent or historical evidence.
  const history = page.getByLabel("Historical relevance");
  assert.equal(await history.locator("option[value=historical_evidence]").isDisabled(), false);

  // A recorded plant is judged on its own, so a claim always names what it is about.
  const target = page.getByLabel("Plant being judged");
  assert.match(await target.locator("option:checked").textContent(), /Suggested.*Old man's beard/);
  await target.selectOption("7");
  const absent = page
    .getByLabel("Novelty", { exact: true })
    .locator("option[value=absent_from_references]");
  assert.equal(await absent.isDisabled(), false, "gorse was compared with records");
  // With no nearby gorse record there is nothing for the photo to be earlier than.
  const earlier = page
    .getByLabel("Novelty", { exact: true })
    .locator("option[value=earlier_than_records]");
  assert.equal(await earlier.isDisabled(), true);
  assert.match(await section.textContent(), /Ben:\s*Newly noticed in this photo/);
  assert.doesNotMatch(await location.textContent(), /Reviewers disagree/, "no carry-over");
  await page.getByLabel("Novelty", { exact: true }).selectOption("already_recorded");
  await saveNovelty.click();
  for (let wait = 0; wait < 50 && posted.length < 3; wait++) await page.waitForTimeout(100);
  assert.equal(posted[2].finding_id, 7);
  assert.equal(posted[2].value, "already_recorded");

  // A draft belongs to its reviewer: another name starts from their own standing value.
  await page.getByLabel("Novelty", { exact: true }).selectOption("new_in_photo");
  await page.getByLabel("Your name").fill("Ben");
  await page.getByLabel("Your name").fill("Carol");
  assert.equal(await page.getByLabel("Novelty", { exact: true }).inputValue(), "unassessed");
  console.log("Identity, location, history and novelty are judged and saved separately.");
} finally {
  await browser.close();
}
