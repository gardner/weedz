// Unresolved findings are referred to a specialist with a reason and tracked until closed.
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
  const before = "2026-11-10T00:00:00+00:00";
  const referredAt = "2026-11-11T00:00:00+00:00";
  const after = "2026-11-12T00:00:00+00:00";
  const noJudgements = { identity: {}, location: {}, history: {}, novelty: {} };
  const referral = (id, fields = {}) => ({
    id,
    finding_id: null,
    reason: "lookalike",
    expertise: "Clematis specialist",
    note: "Leaflets could be native Clematis paniculata",
    referrer: "Ben",
    created_at: referredAt,
    status: "open",
    events: [],
    ...fields,
  });
  const photo = (id, margin, fields = {}) => ({
    id,
    region: "Nelson",
    cohort: "incidental",
    original_taxon: "Turdus merula",
    original_common_name: `Blackbird ${id}`,
    review_status: "uncertain",
    review_note: "",
    review_reviewer: "Ben",
    reviewer_decisions: { Ben: "uncertain" },
    disputed: false,
    review_count: 1,
    observed_on: "2019-05-01",
    scores: { best_species: "Clematis vitalba", margin, width: 400, height: 300 },
    photo_license: "cc0",
    coordinate_status: "missing",
    attribution: "Test fixture",
    findings: [],
    judgements: noJudgements,
    judgement_disputes: [],
    referrals: [],
    ...fields,
  });
  const vine = photo("vine", 0.3, {
    findings: [
      {
        id: 7,
        kind: "addition",
        species: "Ulex europaeus",
        other_taxon: null,
        box: null,
        note: "",
        reviewer: "Ben",
        created_at: before,
        judgements: noJudgements,
        judgement_disputes: [],
      },
    ],
    judgements: {
      ...noJudgements,
      identity: {
        Ben: { id: 10, value: "confirmed", note: "", created_at: before },
        "Dr Wiri": { id: 11, value: "disputed", note: "Toothed leaflets", created_at: after },
        Carol: { id: 12, value: "confirmed", note: "", created_at: after },
      },
    },
    referrals: [referral(3)],
  });
  const answered = photo("answered", 0.2, {
    referrals: [
      referral(2, {
        reason: "poor_view",
        status: "answered",
        events: [
          {
            id: 1,
            referral_id: 2,
            action: "answered",
            actor: "Dr Wiri",
            note: "Too blurred to say; rephotograph in flower",
            judgement_ids: [],
            created_at: after,
          },
        ],
      }),
    ],
  });
  // An audit-sample photo stays hidden from anyone who has not audited it, referral or not.
  const held = photo("held", 0.1, {
    audit_sample: true,
    auditors: [],
    referrals: [referral(1, { reason: "cultivated_or_wild" })],
  });
  const posted = [];
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path === "/api/runs") return route.fulfill({ json: [run] });
    if (path.endsWith("/image")) return route.fulfill({ status: 404 });
    if (path.endsWith("/reviews")) return route.fulfill({ json: [] });
    if (path.endsWith("/findings") || path.endsWith("/judgements")) {
      return route.fulfill({ json: [] });
    }
    if (path.endsWith("/vine/referrals") && request.method() === "POST") {
      const body = request.postDataJSON();
      posted.push({ path, body });
      vine.referrals.push(referral(4, { ...body, created_at: after }));
      return route.fulfill({ json: { saved: true, id: 4 } });
    }
    const closing = path.match(/\/referrals\/(\d+)\/events$/);
    if (closing && request.method() === "POST") {
      const body = request.postDataJSON();
      posted.push({ path, body });
      const target = vine.referrals.find((item) => item.id === Number(closing[1]));
      target.status = body.action;
      target.events = [{ id: 9, referral_id: target.id, ...body, created_at: after }];
      return route.fulfill({ json: { saved: true } });
    }
    if (path.endsWith("/referrals")) return route.fulfill({ json: [] });
    // Referral time is review effort; untimed actions are listed, never zero.
    const review_effort = {
      total_minutes: 1,
      measured_decisions: 0,
      unmeasured_decisions: 0,
      measured_referral_actions: 1,
      unmeasured_referral_actions: 1,
    };
    await route.fulfill({ json: { run, photos: [vine, answered, held], review_effort } });
  });
  await page.goto(process.env.WEEDZ_WEB_URL ?? "http://127.0.0.1:3001");
  await page.evaluate(() => localStorage.removeItem("weedz-reviewer"));
  await page.reload();
  await page.locator(".photo-row").first().waitFor();
  await page.getByText("1 min measured review time · 1 referral action not timed").waitFor();

  // Ranked rows flag open referrals; an answered one no longer needs a specialist.
  const rows = page.locator(".photo-row");
  assert.equal(await rows.count(), 2, "the sampled photo is held for audit");
  assert.match(await rows.nth(0).textContent(), /Needs specialist/);
  assert.doesNotMatch(await rows.nth(1).textContent(), /Needs specialist/);

  // The Needs specialist view lists open referrals, and still holds unaudited photos.
  await page.getByRole("button", { name: "Needs specialist", exact: true }).click();
  await page.getByText("Open referrals, longest waiting first · 1 held for blind audit").waitFor();
  assert.equal(await rows.count(), 1);
  assert.match(await rows.nth(0).textContent(), /Blackbird vine/);

  const section = page.getByRole("region", { name: "Specialist referrals" });
  await section.waitFor();
  const first = section.locator(".referral").first();
  assert.match(await first.textContent(), /Referral 1.*Open/s);
  assert.match(await first.textContent(), /Native or other lookalike/);
  assert.match(await first.textContent(), /Clematis specialist/);
  assert.match(await first.textContent(), /Referred by Ben/);
  assert.match(await first.textContent(), /could be native Clematis paniculata/);

  // Referring needs a name, a reason and a note.
  await section.getByRole("button", { name: "Refer for specialist assessment" }).click();
  const send = section.getByRole("button", { name: "Send referral" });
  assert.equal(await send.isDisabled(), true, "no name, no referral");
  await page.getByLabel("Your name").fill("Ana");
  assert.equal(await send.isDisabled(), true, "no reason or note yet");
  await section.getByLabel("Plant referred").selectOption("7");
  await section.getByLabel("Reason").selectOption("cultivated_or_wild");
  await section.getByLabel("Expertise needed").fill("Garden escapes, Nelson");
  assert.equal(await send.isDisabled(), true, "no note yet");
  await section.getByLabel("What is unresolved?").fill("Hedge or wild plant? Fence line");
  await send.click();
  await page.getByText("Referral saved locally.").waitFor();
  const { effort_seconds, ...sent } = posted[0].body;
  assert.equal(typeof effort_seconds, "number");
  assert.equal(sent.referrer, "Ana");
  assert.deepEqual(
    {
      finding_id: sent.finding_id,
      reason: sent.reason,
      expertise: sent.expertise,
      note: sent.note,
    },
    {
      finding_id: 7,
      reason: "cultivated_or_wild",
      expertise: "Garden escapes, Nelson",
      note: "Hedge or wild plant? Fence line",
    },
  );
  const second = section.locator(".referral").nth(1);
  await second.waitFor();
  assert.match(await second.textContent(), /Recorded plant 1: Missed plant, Gorse/);

  // A specialist answers under their own name and cites judgements made since the referral.
  await page.getByLabel("Your name").fill("Dr Wiri");
  const cite = first.getByRole("checkbox");
  assert.equal(await cite.count(), 1, "only judgements made since the referral can be cited");
  assert.match(await first.locator("fieldset").textContent(), /Identity: Disputed \(Dr Wiri\)/);
  const record = first.getByRole("button", { name: "Record answer" });
  assert.equal(await record.isDisabled(), true, "an answer needs a note");
  await first.getByLabel("Response to referral 1").fill("Toothed leaflets: Clematis vitalba");
  await cite.check();
  await record.click();
  await page.getByText("Referral answer saved locally.").waitFor();
  assert.match(posted[1].path, /\/photos\/vine\/referrals\/3\/events$/);
  assert.deepEqual(
    { ...posted[1].body, effort_seconds: undefined, reviewer: undefined },
    {
      action: "answered",
      actor: "Dr Wiri",
      note: "Toothed leaflets: Clematis vitalba",
      judgement_ids: [11],
      effort_seconds: undefined,
      reviewer: undefined,
    },
  );
  await first.getByText(/Answered by Dr Wiri/).waitFor();
  assert.equal(await first.getByRole("button", { name: "Record answer" }).count(), 0);

  // The referrer withdraws theirs with a reason; nothing is left waiting.
  await page.getByLabel("Your name").fill("Ana");
  await second.getByLabel("Response to referral 2").fill("A second photo shows a garden bed");
  await second.getByRole("button", { name: "Withdraw referral" }).click();
  await page.getByText("Referral withdrawal saved locally.").waitFor();
  assert.equal(posted[2].body.action, "withdrawn");
  assert.deepEqual(posted[2].body.judgement_ids, []);
  await page.getByText("No photos match this view.").waitFor();

  // Once audited, the sampled photo's open referral is listed too.
  held.auditors = ["Ana"];
  await page.reload();
  await page.getByRole("button", { name: "Needs specialist", exact: true }).click();
  await page.getByText("Open referrals, longest waiting first").waitFor();
  assert.equal(await rows.count(), 1);
  assert.match(await rows.nth(0).textContent(), /Blackbird held/);

  // The blind audit list never mentions a referral.
  await page.getByRole("button", { name: "Audit sample" }).click();
  await page.getByText("Fixed random sample").waitFor();
  assert.doesNotMatch(await rows.nth(0).textContent(), /specialist/i);

  // A closed referral keeps its history and offers no further action.
  await page.getByRole("button", { name: "Incidental photos" }).click();
  await rows.filter({ hasText: "Blackbird answered" }).click();
  const closed = page.getByRole("region", { name: "Specialist referrals" }).locator(".referral");
  await closed.getByText(/Answered by Dr Wiri.*rephotograph in flower/).waitFor();
  assert.match(await closed.textContent(), /Poor view/);
  assert.equal(await closed.getByRole("button").count(), 0);
  console.log("Referrals carry a reason, are answered or withdrawn, and respect audit holds.");
} finally {
  await browser.close();
}
