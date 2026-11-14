// Leads worth follow-up are selected by name with a reason, and exported as a package.
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
  const noJudgements = { identity: {}, location: {}, history: {}, novelty: {} };
  const vine = {
    id: "vine",
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
    scores: { best_species: "Clematis vitalba", margin: 0.3, width: 400, height: 300 },
    photo_license: "cc-by",
    coordinate_status: "missing",
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
        created_at: "2026-11-10T00:00:00+00:00",
        judgements: noJudgements,
        judgement_disputes: [],
      },
    ],
    judgements: noJudgements,
    judgement_disputes: [],
    referrals: [],
    lead: { suggestion: null, plants: {} },
  };
  const posted = [];
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path === "/api/runs") return route.fulfill({ json: [run] });
    if (path.endsWith("/image")) return route.fulfill({ status: 404 });
    if (path.endsWith("/reviews")) return route.fulfill({ json: [] });
    if (path.endsWith("/vine/leads") && request.method() === "POST") {
      const body = request.postDataJSON();
      posted.push(body);
      const standing = { selector: body.selector, reason: body.reason, created_at: "2026-11-14" };
      const selected = body.action === "selected" ? standing : null;
      if (body.finding_id === null) vine.lead.suggestion = selected;
      else if (selected) vine.lead.plants[String(body.finding_id)] = selected;
      else delete vine.lead.plants[String(body.finding_id)];
      return route.fulfill({ json: { saved: true } });
    }
    await route.fulfill({ json: { run, photos: [vine] } });
  });
  await page.goto(process.env.WEEDZ_WEB_URL ?? "http://127.0.0.1:3001");
  await page.evaluate(() => localStorage.removeItem("weedz-reviewer"));
  await page.reload();
  await page.locator(".photo-row").first().waitFor();

  // The package exports only selected leads, from the page header.
  const exportLink = page.getByRole("link", { name: /Follow-up package/ });
  assert.equal(await exportLink.getAttribute("href"), "/api/runs/run/package/archive");

  const section = page.getByRole("region", { name: "Follow-up" });
  await section.waitFor();
  assert.match(await section.textContent(), /Not selected for follow-up/);

  // Selecting needs a name and a reason.
  const choose = section.getByRole("button", { name: "Select for follow-up" });
  assert.equal(await choose.isDisabled(), true, "no name, no selection");
  await page.getByLabel("Your name").fill("Ana");
  assert.equal(await choose.isDisabled(), true, "no reason yet");
  await section.getByLabel("Why follow up?").fill("Clear leaflets by a stream");
  await choose.click();
  await page.getByText("Follow-up selection saved locally.").waitFor();
  const { effort_seconds, reviewer, ...sent } = posted[0];
  assert.equal(effort_seconds, undefined, "selecting is not timed review work");
  assert.equal(reviewer, undefined);
  assert.deepEqual(sent, {
    finding_id: null,
    action: "selected",
    selector: "Ana",
    reason: "Clear leaflets by a stream",
  });
  await section.getByText(/Selected by Ana on 2026-11-14: Clear leaflets by a stream/).waitFor();

  // A recorded plant is selected apart from the suggestion.
  await section.getByLabel("Lead").selectOption("7");
  await section.getByLabel("Why follow up?").fill("Gorse on the far bank");
  await section.getByRole("button", { name: "Select for follow-up" }).click();
  await section.getByText(/Recorded plant 1.*Selected by Ana.*Gorse on the far bank/s).waitFor();
  assert.equal(posted[1].finding_id, 7);

  // Deselecting is a later event with its own reason; the button says what it will do.
  await section.getByLabel("Lead").selectOption("suggestion");
  const deselect = section.getByRole("button", { name: "Deselect" });
  assert.equal(await deselect.isDisabled(), true, "a deselection needs a reason too");
  await section.getByLabel("Why deselect?").fill("Matches a DOC record");
  await deselect.click();
  await page.getByText("Follow-up selection saved locally.").waitFor();
  assert.deepEqual(
    { action: posted[2].action, reason: posted[2].reason, finding_id: posted[2].finding_id },
    { action: "deselected", reason: "Matches a DOC record", finding_id: null },
  );
  console.log("Leads are selected and deselected with a reason; the package exports them.");
} finally {
  await browser.close();
}
