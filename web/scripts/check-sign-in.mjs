// A remote reviewer signs in with their token; their records carry the signed-in name.
import assert from "node:assert/strict";
import { chromium } from "@playwright/test";

const browser = await chromium.launch({
  headless: true,
  ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE
    ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE }
    : {}),
});
try {
  const page = await browser.newPage();
  const run = { id: "run", status: "completed", detail: "Test fixture", created_at: "2024-12-31" };
  const photo = {
    id: "photo",
    region: "Nelson",
    cohort: "incidental",
    original_taxon: "Turdus merula",
    original_common_name: "Blackbird",
    review_status: "unreviewed",
    reviewer_decisions: {},
    scores: { best_species: "Clematis vitalba" },
    photo_license: "cc0",
    coordinate_status: "missing",
    attribution: "Test fixture",
  };
  let signedIn = false;
  const tokens = [];
  const posted = [];
  let signedOut = 0;
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path === "/api/session") {
      if (request.method() === "POST") {
        const { token } = request.postDataJSON();
        tokens.push(token);
        signedIn = token === "weedz_1_right";
      }
      if (request.method() === "DELETE") {
        signedOut++;
        signedIn = false;
        return route.fulfill({ json: { signed_out: true } });
      }
      return signedIn
        ? route.fulfill({ json: { mode: "tokens", reviewer: "Ana" } })
        : route.fulfill({ status: 401, json: { detail: "That token is not valid" } });
    }
    if (!signedIn) return route.fulfill({ status: 401, json: { detail: "Sign in" } });
    if (path === "/api/runs") return route.fulfill({ json: [run] });
    if (path.endsWith("/image")) return route.fulfill({ status: 404 });
    if (path.endsWith("/reviews")) return route.fulfill({ json: [] });
    if (path.endsWith("/review")) {
      posted.push(request.postDataJSON());
      return route.fulfill({ json: { saved: true } });
    }
    await route.fulfill({ json: { run, photos: [photo] } });
  });
  await page.goto(process.env.WEEDZ_WEB_URL ?? "http://127.0.0.1:3001");
  // A name typed earlier in this browser never stands in for the signed-in reviewer.
  await page.evaluate(() => localStorage.setItem("weedz-reviewer", "Ben"));
  await page.reload();

  await page.getByRole("heading", { name: "Sign in to review" }).waitFor();
  const token = page.getByLabel("Reviewer token");
  assert.equal(await token.getAttribute("type"), "password");
  await token.fill("weedz_1_wrong");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.getByRole("alert").filter({ hasText: "That token is not valid" }).waitFor();

  await token.fill("  weedz_1_right ");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.getByText("Signed in as Ana").waitFor();
  assert.deepEqual(tokens, ["weedz_1_wrong", "weedz_1_right"]);
  const name = page.getByLabel("Your name");
  assert.equal(await name.inputValue(), "Ana");
  assert.equal(await name.getAttribute("readonly"), "");
  await page.getByRole("button", { name: "Species visible" }).click();
  await page.getByText("Review saved locally.").waitFor();
  assert.equal(posted[0].reviewer, "Ana");

  await page.getByRole("button", { name: "Sign out" }).click();
  await page.getByRole("heading", { name: "Sign in to review" }).waitFor();
  assert.equal(signedOut, 1);
  console.log("Remote reviewers sign in, write under their own name and sign out.");
} finally {
  await browser.close();
}
