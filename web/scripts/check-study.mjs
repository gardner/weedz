// A run's study is recorded, shown with what is still open, and edited as a new version.
import assert from "node:assert/strict";
import { chromium } from "@playwright/test";

const browser = await chromium.launch({
  headless: true,
  ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE
    ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE }
    : {}),
});
const run = {
  id: "run",
  status: "completed",
  detail: "Test fixture",
  created_at: "2024-12-31",
  spec: { before: "2024-12-31", limit_per_region: 2, controls_per_species: 0 },
};
const terms = {
  regions: ["Nelson", "Tasman"],
  species: { "Clematis vitalba": "Old man's beard", "Ulex europaeus": "Gorse" },
  lookalikes: [{ name: "Clematis paniculata", confusable_with: "Clematis vitalba" }],
  limits: {
    useful_incidental_yield: {
      measure: "Useful incidental yield",
      direction: "at least",
      unit: "independent site visits with a useful finding",
    },
    coverage: {
      measure: "Coverage and review usability",
      direction: "at least",
      unit: "% of incidental photos reviewed",
    },
  },
};
try {
  const page = await browser.newPage();
  const posted = [];
  let study = null;
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (request.method() === "POST") {
      const body = request.postDataJSON();
      posted.push([path, body]);
      if (path === "/api/studies" || path.endsWith("/versions")) {
        const version = body.base_version + 1;
        study = {
          id: "study-1",
          version,
          author: body.author,
          created_at: "2026-11-14T00:00:00+00:00",
          change_note: body.change_note,
          definition: body.definition,
          open_decisions: ["Review budget", "Success limit: Useful incidental yield"],
          differences: [
            "Ulex europaeus is screened by every run but not in this study's watchlist",
          ],
          budget_use: {
            hours: { budget: null, used: 0.5, lower_bound: true, state: "not set" },
            photos: { budget: null, used: 3, lower_bound: false, state: "not set" },
            note: "",
          },
        };
        return route.fulfill({ status: 201, json: { id: "study-1", version } });
      }
      return route.fulfill({ json: { saved: true } });
    }
    if (path === "/api/runs") return route.fulfill({ json: [run] });
    if (path === "/api/studies/terms") return route.fulfill({ json: terms });
    await route.fulfill({ json: { run, photos: [], study } });
  });
  await page.route("**/api/session", (route) =>
    route.fulfill({ json: { mode: "local", can_start_runs: true } }),
  );
  await page.goto(process.env.WEEDZ_WEB_URL ?? "http://127.0.0.1:3001");
  const panel = page.locator(".study-panel");
  await panel.locator("summary").click();
  await panel.getByText("No study is recorded for this run").waitFor();
  await panel.getByRole("button", { name: "Record the study" }).click();
  await panel.getByLabel("Discovery question").fill("Which overlooked sites would DOC visit?");
  await panel.getByLabel("Partner", { exact: true }).fill("Example team");
  await panel.getByLabel("Responsible people").fill("Coordinator: Ana\nSpecialist: Dr Wiri");
  await panel.getByRole("checkbox", { name: /^Clematis vitalba/ }).check();
  await panel.getByLabel("Why Clematis vitalba").fill("High management value");
  await panel.getByLabel("Not yet screened species").fill("Gunnera tinctoria: Wetland spread");
  await panel.getByRole("checkbox", { name: /^Clematis paniculata/ }).check();
  await panel.getByLabel("Why Clematis paniculata").fill("Native; flowers alike");
  await panel.getByLabel("Reference records").fill("DOC weed records: Snapshot; incomplete");
  await panel.getByLabel(/^Coverage and review usability:/).fill("80");
  await panel.getByLabel("Note on Coverage and review usability").fill("Half the queue");
  await panel.getByLabel("Budget note").fill("Pilot only");
  await panel.getByLabel("Recorded by").fill("Ana");
  await panel.getByRole("button", { name: "Save study version" }).click();
  await page.getByText("Study version 1 saved locally.").waitFor();

  assert.equal(posted.length, 1, "a new study is created and linked in one request");
  const [[createPath, created]] = posted;
  assert.equal(createPath, "/api/studies");
  assert.equal(created.author, "Ana");
  assert.equal(created.base_version, 0);
  const definition = created.definition;
  assert.equal(definition.status, "provisional");
  assert.equal(definition.partner, "Example team");
  assert.deepEqual(definition.people[1], { role: "Specialist", name: "Dr Wiri" });
  assert.deepEqual(definition.watchlist, [
    { species: "Clematis vitalba", rationale: "High management value", screened: true },
    { species: "Gunnera tinctoria", rationale: "Wetland spread", screened: false },
  ]);
  assert.deepEqual(definition.lookalikes, [
    { taxon: "Clematis paniculata", rationale: "Native; flowers alike", screened: true },
  ]);
  assert.deepEqual(definition.limits, { coverage: { value: 80, note: "Half the queue" } });
  assert.equal(definition.review_budget.hours, null);
  assert.equal(created.run_id, "run");

  // The saved study shows what is decided, what is open and how it differs from screening.
  await panel.getByText("Which overlooked sites would DOC visit?").waitFor();
  await panel.getByText("at least 80 % of incidental photos reviewed").waitFor();
  await panel.getByText("Useful incidental yield: not yet agreed").waitFor();
  await panel.getByText("Success limit: Useful incidental yield").waitFor();
  await panel.getByText(/Ulex europaeus is screened by every run/).waitFor();
  await panel.getByText(/at least 0\.5 h used so far · no budget set/).waitFor();
  await panel.getByText(/Version 1 by Ana/).waitFor();
  // A reference record shows its coverage note, not just its name.
  await panel.getByText("DOC weed records: Snapshot; incomplete").waitFor();
  // Notes qualifying the budget and a limit are shown with them.
  await panel.getByText(/no budget set · Pilot only/).waitFor();
  await panel.getByText(/80 % of incidental photos reviewed \(Half the queue\)/).waitFor();

  // A stored version may name what the screening no longer covers, or a measure since
  // removed; an edit must carry them rather than silently drop them.
  study.definition.watchlist.push({
    species: "Cortaderia selloana",
    rationale: "Plumes",
    screened: true,
  });
  study.definition.limits.old_measure = { value: 1, note: "" };
  await panel.getByText(/Cortaderia selloana: Plumes/).waitFor();

  // An edit starts from the saved version and is sent as the next one.
  await panel.getByRole("button", { name: "Edit study" }).click();
  // Someone else saves meanwhile; this edit must still name the version it started from.
  study = { ...study, version: 5 };
  await panel.getByText("provisional · version 5").waitFor({ timeout: 10_000 });
  // A lookalike stays declared when its rationale is cleared.
  await panel.getByLabel("Why Clematis paniculata").fill("");
  assert.equal(await panel.getByLabel("Partner", { exact: true }).inputValue(), "Example team");
  assert.equal(
    await panel.getByLabel("Why Clematis vitalba").inputValue(),
    "High management value",
  );
  await panel.getByLabel("Partner", { exact: true }).fill("Second team");
  await panel.getByLabel("Review hours").fill("40");
  await panel.getByLabel("What changed and why").fill("Partner confirmed");
  await panel.getByRole("button", { name: "Save study version" }).click();
  await page.getByText("Study version 2 saved locally.").waitFor();
  assert.equal(posted.length, 2, "an edit does not link the run again");
  const [editPath, edited] = posted[1];
  assert.equal(edited.run_id, undefined);
  assert.equal(editPath, "/api/studies/study-1/versions");
  assert.equal(edited.base_version, 1);
  assert.equal(edited.definition.partner, "Second team");
  assert.equal(edited.definition.review_budget.hours, 40);
  assert.equal(edited.change_note, "Partner confirmed");
  assert.deepEqual(edited.definition.watchlist[2], {
    species: "Cortaderia selloana",
    rationale: "Plumes",
    screened: false,
  });
  assert.deepEqual(edited.definition.lookalikes, [
    { taxon: "Clematis paniculata", rationale: "", screened: true },
  ]);
  assert.deepEqual(edited.definition.limits.old_measure, { value: 1, note: "" });

  // A person written without a role is refused before anything is sent.
  await panel.getByRole("button", { name: "Edit study" }).click();
  await panel.getByLabel("Responsible people").fill("Ana");
  await panel.getByText(/Write each line as Role: Name/).waitFor();
  assert.equal(await panel.getByRole("button", { name: "Save study version" }).isDisabled(), true);
  console.log("A study is recorded, shown with its open decisions, and edited as a version.");
} finally {
  await browser.close();
}
