// Core review actions meet WCAG 2.2 AA checks and work from the keyboard alone.
import assert from "node:assert/strict";
import AxeBuilder from "@axe-core/playwright";
import { chromium } from "@playwright/test";
import { suitability } from "./suitability-fixture.mjs";

// axe leaves very short text (e.g. a "2" count) as "incomplete" and never checks
// placeholders, so compute WCAG contrast directly for every text node on a solid colour.
async function lowContrast(page) {
  return page.evaluate(() => {
    const rgb = (value) => (value.match(/[\d.]+/g) ?? []).map(Number);
    const luminance = ([r, g, b]) => {
      const channel = (c) => {
        const v = c / 255;
        return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
      };
      return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
    };
    const background = (element) => {
      for (let node = element; node; node = node.parentElement) {
        const style = getComputedStyle(node);
        if (style.backgroundImage !== "none") return null;
        const colour = rgb(style.backgroundColor);
        if (colour.length === 3 || colour[3] === 1) return colour.slice(0, 3);
        if (colour[3] > 0) return null;
      }
      return [255, 255, 255];
    };
    const failures = [];
    const check = (element, colour, label) => {
      const back = background(element);
      if (!back) return;
      const [a, b] = [luminance(rgb(colour)), luminance(back)].sort((x, y) => y - x);
      const ratio = (a + 0.05) / (b + 0.05);
      const style = getComputedStyle(element);
      const size = Number.parseFloat(style.fontSize);
      const large = size >= 24 || (size >= 18.66 && Number(style.fontWeight) >= 700);
      if (ratio < (large ? 3 : 4.5)) failures.push(`${label} ${ratio.toFixed(2)}:1`);
    };
    for (const element of document.querySelectorAll("body *")) {
      const style = getComputedStyle(element);
      if (style.visibility === "hidden" || style.display === "none") continue;
      if (element.closest("[aria-hidden='true']")) continue;
      if (["TITLE", "SCRIPT", "STYLE", "NOSCRIPT"].includes(element.tagName.toUpperCase()))
        continue;
      const text = [...element.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
      const name = `${element.tagName.toLowerCase()}.${[...element.classList].join(".")}`;
      if (text) check(element, style.color, name);
      if (element.matches("input[placeholder], textarea[placeholder]")) {
        check(element, getComputedStyle(element, "::placeholder").color, `${name}::placeholder`);
      }
    }
    return failures;
  });
}

const browser = await chromium.launch({
  headless: true,
  ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE
    ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE }
    : {}),
});
try {
  const context = await browser.newContext({ viewport: { width: 1400, height: 1000 } });
  const page = await context.newPage();
  const run = {
    id: "run",
    status: "completed",
    detail: "Test fixture",
    created_at: "2024-12-31",
    spec: { before: "2024-12-31", limit_per_region: 2, controls_per_species: 0 },
  };
  const photo = (id, status) => ({
    id,
    region: "Nelson",
    cohort: "incidental",
    original_taxon: "Turdus merula",
    original_common_name: `Blackbird ${id}`,
    review_status: status,
    review_note: "",
    review_reviewer: "",
    reviewer_decisions: {},
    disputed: false,
    review_count: 0,
    observed_on: "2024-12-30",
    uploaded_at: "2024-12-31T00:00:00Z",
    scores: {
      best_species: "Ulex europaeus",
      margin: id === "a" ? 0.2 : 0.1,
      similarity: 0.3,
      box: [0, 0, 10, 10],
      width: 20,
      height: 20,
      species: [{ name: "Ulex europaeus", similarity: 0.3, margin: 0.1, box: [0, 0, 10, 10] }],
    },
    photo_license: "cc-by",
    observation_license: "cc-by",
    coordinate_status: "public",
    latitude: -41.2,
    longitude: 173.3,
    positional_accuracy_m: 10,
    limits: {
      search_area: {
        status: "searchable",
        reason: "",
        centre: [-41.2, 173.3],
        centre_is: "observation point (where the photographer was), not a plant point",
        accuracy_m: 10,
        allowance_m: 100,
        allowance_reason: "100 m declared allowance for camera-to-plant distance",
        radius_m: 110,
        site_context: true,
      },
      dates: {
        photographed: "2024-12-30",
        uploaded: "2024-12-31",
        screened: "2024-12-31",
        days_photo_to_upload: 1,
        days_photo_to_screening: 1,
        current_presence:
          "If the plant is visible, the photo shows it was there when photographed (2024-12-30), not that it is there now",
      },
    },
    attribution: "Test fixture",
    source_url: "https://www.inaturalist.org/observations/1",
    findings: [
      {
        id: 1,
        kind: "addition",
        species: null,
        other_taxon: "Clematis paniculata",
        box: [1, 1, 5, 5],
        note: "Native, in flower",
        reviewer: "Ben",
        created_at: "2026-11-13T20:00:00+00:00",
      },
    ],
    judgements: {
      identity: {
        Ben: { value: "confirmed", note: "Leaflets visible", created_at: "" },
        "Dr Wiri": { id: 5, value: "disputed", note: "", created_at: "2026-11-14T00:00:00+00:00" },
      },
      location: {
        Ben: { value: "camera_point_only", note: "", created_at: "" },
        Carol: { value: "usable", note: "", created_at: "" },
      },
      history: {},
      novelty: {},
    },
    judgement_disputes: ["location"],
    lead: {
      suggestion: {
        selector: "Ana",
        reason: "Clear leaflets by a stream",
        created_at: "2026-11-14",
      },
      plants: {},
    },
    referrals: [
      {
        id: 1,
        finding_id: null,
        reason: "lookalike",
        expertise: "Clematis specialist",
        note: "Could be native Clematis paniculata",
        referrer: "Ben",
        created_at: "2026-11-13T00:00:00+00:00",
        status: "open",
        events: [],
      },
      {
        id: 2,
        finding_id: 1,
        reason: "poor_view",
        expertise: "",
        note: "Blurred",
        referrer: "Ben",
        created_at: "2026-11-13T00:00:00+00:00",
        status: "withdrawn",
        events: [
          {
            id: 1,
            action: "withdrawn",
            actor: "Ben",
            note: "Better photo found",
            judgement_ids: [],
            created_at: "2026-11-13T01:00:00+00:00",
          },
        ],
      },
    ],
  });
  const posted = [];
  let photos = [photo("a", "unreviewed"), photo("b", "rejected")];
  const limit = { measure: "Coverage and review usability", direction: "at least", unit: "%" };
  const terms = {
    regions: ["Nelson", "Tasman"],
    species: { "Ulex europaeus": "Gorse" },
    lookalikes: [{ name: "Kunzea ericoides", confusable_with: "Ulex europaeus" }],
    limits: { coverage: limit },
  };
  const use = { budget: 40, used: 2, lower_bound: true, state: "within so far" };
  const study = {
    id: "study-1",
    version: 2,
    author: "Ana",
    created_at: "2026-11-14T00:00:00+00:00",
    change_note: "Budget agreed",
    definition: {
      status: "provisional",
      question: "Which gorse sites would the partner visit?",
      partner: "",
      people: [{ role: "Coordinator", name: "Ana" }],
      regions: [{ name: "Nelson", rationale: "Partner's area", screened: true }],
      period_start: "2010-01-01",
      period_end: null,
      period_rationale: "",
      watchlist: [{ species: "Ulex europaeus", rationale: "", screened: true }],
      lookalikes: [],
      source_collection: "",
      subject_selection: "",
      review_budget: { hours: 40, photos: null, note: "" },
      reference_records: [],
      limits: { coverage: { value: 80, note: "" } },
    },
    open_decisions: ["Partner", "Source collection"],
    differences: ["Tasman is queried by every run but not one of this study's regions"],
    budget_use: { hours: use, photos: { ...use, budget: null, state: "not set" }, note: "" },
  };
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path === "/api/runs") return route.fulfill({ json: [run] });
    if (path === "/api/studies/terms") return route.fulfill({ json: terms });
    if (path.endsWith("/suitability")) return route.fulfill({ json: suitability });
    if (path.endsWith("/image")) return route.fulfill({ status: 404 });
    if (path.endsWith("/reviews")) return route.fulfill({ json: [] });
    if (path.endsWith("/review")) {
      posted.push(request.postDataJSON());
      return route.fulfill({ json: { saved: true } });
    }
    await route.fulfill({ json: { run, photos, study } });
  });
  await page.goto(process.env.WEEDZ_WEB_URL ?? "http://127.0.0.1:3001");
  await page.locator(".photo-row").nth(1).waitFor();
  await page.locator(".run-settings summary").click();
  // Audit the study as shown, then leave its edit form open for the full audit below.
  const studyPanel = page.locator(".study-panel");
  await studyPanel.locator("summary").click();
  await studyPanel.getByText("Which gorse sites would the partner visit?").waitFor();
  const shown = await new AxeBuilder({ page }).include(".study-panel").analyze();
  assert.deepEqual(
    shown.violations.map((v) => v.id),
    [],
    "the study view meets WCAG AA",
  );
  assert.deepEqual(await lowContrast(page), [], "study view text meets AA contrast");
  // Audit the source suitability open; it stays open for the full and phone audits below.
  const suitabilityPanel = page.locator(".suitability-panel");
  await suitabilityPanel.locator("summary").click();
  await suitabilityPanel.getByRole("table").waitFor();
  const suits = await new AxeBuilder({ page }).include(".suitability-panel").analyze();
  assert.deepEqual(
    suits.violations.map((v) => v.id),
    [],
    "the source suitability meets WCAG AA",
  );
  await studyPanel.getByRole("button", { name: "Edit study" }).click();
  await studyPanel.getByLabel("Recorded by").waitFor();
  // Audit the finding form open, with its free-text field and a box error showing.
  await page.getByRole("button", { name: "Record a different or missed plant" }).click();
  await page.getByLabel("Species", { exact: true }).selectOption("other");
  await page.getByLabel("Left", { exact: true }).fill("5");
  await page.getByText("Enter all four edges").waitFor();
  // Audit the judgements with a required-note hint and unavailable claims showing.
  await page.getByLabel("Novelty", { exact: true }).selectOption("verified_new_locality");
  await page.getByText(/needs the verification evidence/).waitFor();
  // Audit referrals with an open one's response form and the new-referral form showing.
  await page.getByRole("button", { name: "Refer for specialist assessment" }).click();
  await page.getByLabel("What is unresolved?").waitFor();
  // Only the answerer's own judgements can be cited, so answer as their author.
  await page.getByLabel("Your name").fill("Dr Wiri");
  await page.getByText("Judgements this answer informed").waitFor();

  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();
  const summary = results.violations.map(
    (v) => `${v.id} (${v.impact}): ${v.nodes.length} × ${v.nodes[0]?.target.join(" ")}`,
  );
  assert.deepEqual(summary, [], `WCAG violations:\n${summary.join("\n")}`);

  assert.deepEqual(await lowContrast(page), [], "every text node meets AA contrast");

  // The phone layout reflows the same content; audit it too.
  await page.setViewportSize({ width: 390, height: 844 });
  const phone = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();
  const phoneSummary = phone.violations.map((v) => `${v.id}: ${v.nodes.length}`);
  assert.deepEqual(phoneSummary, [], `Phone-width WCAG violations:\n${phoneSummary.join("\n")}`);
  await page.setViewportSize({ width: 1400, height: 1000 });

  await page.getByLabel("Your name").fill("");
  // Keyboard only: reach the second photo, then decide without a pointer.
  await page.locator(".photo-row").first().focus();
  await page.keyboard.press("Tab");
  await page.keyboard.press("Enter");
  await page.locator(".evidence h2").waitFor();
  // Decisions need a reviewer name; enter it by keyboard as well.
  const name = page.getByLabel("Your name");
  for (
    let step = 0;
    step < 40 && !(await name.evaluate((el) => el === document.activeElement));
    step++
  ) {
    await page.keyboard.press("Tab");
  }
  assert.ok(
    await name.evaluate((el) => el === document.activeElement),
    "name field reachable by Tab",
  );
  await page.keyboard.type("Ana");
  const decision = page.getByRole("button", { name: "Reject suggestion" });
  for (
    let step = 0;
    step < 40 && !(await decision.evaluate((el) => el === document.activeElement));
    step++
  ) {
    await page.keyboard.press("Tab");
  }
  assert.ok(
    await decision.evaluate((el) => el === document.activeElement),
    "decision reachable by Tab",
  );
  // SC 1.4.11: the offset focus ring sits on the surrounding background and needs 3:1.
  const ring = await decision.evaluate((el) => {
    const rgb = (value) => (value.match(/[\d.]+/g) ?? []).map(Number);
    const luminance = ([r, g, b]) => {
      const channel = (c) => {
        const v = c / 255;
        return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
      };
      return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
    };
    let behind = [255, 255, 255];
    for (let node = el.parentElement; node; node = node.parentElement) {
      const colour = rgb(getComputedStyle(node).backgroundColor);
      if (colour.length === 3 || colour[3] === 1) {
        behind = colour.slice(0, 3);
        break;
      }
    }
    const style = getComputedStyle(el);
    const [a, b] = [luminance(rgb(style.outlineColor)), luminance(behind)].sort((x, y) => y - x);
    return { style: style.outlineStyle, ratio: (a + 0.05) / (b + 0.05) };
  });
  assert.notEqual(ring.style, "none", "focused controls show a visible focus indicator");
  assert.ok(ring.ratio >= 3, `focus ring contrast ${ring.ratio.toFixed(2)}:1 is below 3:1`);
  await page.keyboard.press("Enter");
  await page.getByText("Review saved locally.").waitFor();
  assert.equal(posted[0].status, "rejected");
  // Empty states render different text; audit them with a run that has no photos.
  photos = [];
  await page.reload();
  await page.getByText("No photos match this view.").waitFor();
  const empty = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();
  assert.deepEqual(
    empty.violations.map((v) => v.id),
    [],
    "empty states meet WCAG AA",
  );
  assert.deepEqual(await lowContrast(page), [], "empty-state text meets AA contrast");
  console.log("No WCAG 2.2 AA violations; the core decision works from the keyboard.");
} finally {
  await browser.close();
}
