// A screening score is shown with its declared meaning, and never in a blind audit.
import assert from "node:assert/strict";
import { chromium } from "@playwright/test";

const browser = await chromium.launch({
  headless: true,
  ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE
    ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE }
    : {}),
});
const declared = {
  declared: true,
  id: "bioclip-2/ranking-4/meaning-1",
  model_key: "bioclip-2",
  model_revision: "2957b322090f9cb17ae72c71981c7218a28d81e0",
  ranking_revision: 4,
  meaning_version: 1,
  calibrated: false,
  score: "The margin: the target weed's similarity minus the strongest comparison label's.",
  use: "Orders this run's review queue, highest first.",
  not_meaning: ["Not a probability or a confidence that a weed is visible."],
  operating_point: null,
  abstention: null,
  choosing_an_operating_point: "Only on reviewed and blind-audited development runs.",
  evidence: [
    {
      key: "incidental_positive_margin",
      count: 1,
      of: 24,
      finding: "1 of 24 pilot animal photos had a positive margin.",
      source: "benchmarks/model-comparison.json",
      labels: "Source labels from iNaturalist observations, not expert review",
    },
  ],
  run_evidence: "This run's own evidence is its blind audit summary.",
};
const undeclared = {
  ...declared,
  declared: false,
  id: null,
  model_key: null,
  evidence: [],
  use: "Orders the review queue; compare scores only within this run.",
};
const run = {
  id: "run",
  status: "completed",
  detail: "Test fixture",
  created_at: "2024-12-31",
  spec: { before: "2024-12-31", limit_per_region: 2, controls_per_species: 0 },
};
const photo = (id, sampled) => ({
  id,
  region: "Nelson",
  cohort: "incidental",
  original_taxon: `Bird ${id}`,
  original_common_name: `Bird ${id}`,
  review_status: "unreviewed",
  review_note: "",
  review_reviewer: "",
  reviewer_decisions: {},
  disputed: false,
  review_count: 0,
  audit_sample: sampled,
  audited: false,
  auditors: [],
  scores: {
    best_species: "Ulex europaeus",
    margin: 0.031,
    box: [0, 0, 10, 10],
    width: 20,
    height: 20,
    species: [
      { name: "Ulex europaeus", similarity: 0.3, margin: 0.031, box: [0, 0, 10, 10] },
      { name: "Clematis vitalba", similarity: 0.2, margin: -0.042, box: [0, 0, 10, 10] },
    ],
  },
  photo_license: "cc0",
  coordinate_status: "missing",
  attribution: "Test fixture",
});

async function open(meaning) {
  const page = await browser.newPage();
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/runs") return route.fulfill({ json: [run] });
    if (path.endsWith("/image")) return route.fulfill({ status: 404 });
    if (path.endsWith("/reviews")) return route.fulfill({ json: [] });
    const photos = [photo("ranked", false), photo("sampled", true)];
    await route.fulfill({ json: { run, photos, score_meaning: meaning } });
  });
  await page.goto(process.env.WEEDZ_WEB_URL ?? "http://127.0.0.1:3001");
  await page.getByText("Bird ranked").first().waitFor();
  return page;
}

try {
  const page = await open(declared);
  const notes = page.locator(".score-panel");
  await notes.getByRole("heading", { name: "Ranking score" }).waitFor();
  await notes.getByText("+0.031 above the strongest comparison label").waitFor();
  await notes.getByText("−0.042 below the strongest comparison label").waitFor();
  await notes.getByText("BioCLIP 2 · ranking revision 4 · meaning 1").waitFor();
  await page.locator(".screening-note").getByText("BioCLIP 2 ranks").waitFor();
  const details = notes.locator("details.score-meaning");
  assert.equal(await details.getByText("Not a probability").isVisible(), false, "starts closed");
  await details.locator("summary").click();
  await details.getByText("Not a probability or a confidence that a weed is visible.").waitFor();
  await details.getByText("1 of 24 pilot animal photos had a positive margin.").waitFor();
  await details.getByText("No threshold or abstention rule has been chosen").waitFor();
  await details.getByText("benchmarks/model-comparison.json", { exact: false }).first().waitFor();

  // A blind audit shows no score and no score meaning, so nothing hints at the rank.
  await page.getByRole("button", { name: "Audit sample" }).click();
  await page.getByText("Blind audit photo").first().waitFor();
  assert.equal(await page.getByRole("heading", { name: "Ranking score" }).count(), 0);
  assert.equal(await page.getByText("above the strongest comparison label").count(), 0);
  await page.close();

  const legacy = await open(undeclared);
  await legacy.locator(".score-panel").getByRole("heading", { name: "Ranking score" }).waitFor();
  await legacy.getByText("No declared meaning for this screening configuration").waitFor();
  await legacy.locator(".screening-note").getByText("The screening model ranks").waitFor();
  await legacy.close();
  console.log("Scores are shown with their declared meaning, and hidden in blind audits.");
} finally {
  await browser.close();
}
