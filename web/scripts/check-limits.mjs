// Each photo states its search area and dates: never a plant point, never presumed present.
import assert from "node:assert/strict";
import { chromium } from "@playwright/test";

const browser = await chromium.launch({
  headless: true,
  ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE
    ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE }
    : {}),
});
const allowance = {
  centre_is: "observation point (where the photographer was), not a plant point",
  allowance_m: 100,
  allowance_reason: "100 m declared allowance for camera-to-plant distance",
};
const searchable = {
  status: "searchable",
  reason: "",
  centre: [-41.27, 173.28],
  accuracy_m: 12,
  radius_m: 112,
  site_context: true,
  ...allowance,
};
const dates = {
  photographed: "2024-06-01",
  uploaded: "2024-06-03",
  screened: "2026-11-14",
  days_photo_to_upload: 2,
  days_photo_to_screening: 896,
  current_presence:
    "If the plant is visible, the photo shows it was there on 2024-06-01, not that it is there now",
};
const notSearchable = (status, reason) => ({
  status,
  reason,
  centre: null,
  accuracy_m: null,
  radius_m: null,
  site_context: false,
  ...allowance,
});
try {
  const page = await browser.newPage();
  const run = {
    id: "run",
    status: "completed",
    detail: "Test fixture",
    created_at: "2026-11-14T05:04:00+00:00",
    spec: { before: "2024-12-31", limit_per_region: 3, controls_per_species: 0 },
  };
  const photo = (id, margin, search_area, photoDates, fields = {}) => ({
    id,
    region: "Nelson",
    cohort: "incidental",
    original_taxon: `Bird ${id}`,
    original_common_name: `Bird ${id}`,
    review_status: "unreviewed",
    review_note: "",
    reviewer_decisions: {},
    scores: { margin },
    photo_license: "cc0",
    attribution: "Test fixture",
    observed_on: photoDates.photographed,
    uploaded_at: photoDates.uploaded && `${photoDates.uploaded}T08:00:00Z`,
    coordinate_status: "public",
    latitude: -41.27,
    longitude: 173.28,
    positional_accuracy_m: 12,
    limits: { search_area, dates: photoDates },
    ...fields,
  });
  const undated = {
    photographed: null,
    uploaded: null,
    screened: null,
    days_photo_to_upload: null,
    days_photo_to_screening: null,
    current_presence:
      "Photo date unknown: even if the plant is visible, the photo cannot show when it was there",
  };
  const photos = [
    photo("a", 0.3, searchable, dates),
    photo(
      "b",
      0.2,
      notSearchable("obscured", "Location obscured by the source; no search area"),
      undated,
      { coordinate_status: "obscured" },
    ),
    photo("c", 0.1, notSearchable("accuracy_unknown", "Location accuracy not supplied"), dates, {
      positional_accuracy_m: null,
    }),
  ];
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/runs") return route.fulfill({ json: [run] });
    if (path.endsWith("/image")) return route.fulfill({ status: 404 });
    if (path.endsWith("/reviews")) return route.fulfill({ json: [] });
    await route.fulfill({ json: { run, photos } });
  });
  await page.goto(process.env.WEEDZ_WEB_URL ?? "http://127.0.0.1:3001");

  const rows = page.locator(".photo-row");
  await rows.nth(2).waitFor();
  const evidence = page.locator(".evidence");
  const area = evidence.locator(".search-area");
  const when = evidence.locator(".photo-dates");

  await area.getByText("112 m radius around the observation point").waitFor();
  const areaText = await area.textContent();
  assert.match(areaText, /-41\.270, 173\.280/);
  assert.match(areaText, /where the photographer was, not the plant/);
  assert.match(areaText, /Reported accuracy ±12 m \+ 100 m allowance/);
  assert.match(areaText, /no camera bearing or pose/i);
  assert.match(areaText, /aerial site context/);
  const whenText = await when.textContent();
  assert.match(whenText, /Photographed 2024-06-01/);
  assert.match(whenText, /Uploaded 2024-06-03 \(2 days after the photo\)/);
  assert.match(whenText, /Screened 2026-11-14 \(896 days after the photo\)/);
  assert.match(whenText, /not that it is there now/);

  await rows.nth(1).click();
  await area.getByText("Not searchable: obscured location").waitFor();
  const obscured = await area.textContent();
  assert.match(obscured, /Location obscured by the source/);
  assert.match(obscured, /Reported accuracy ±12 m/, "the source's accuracy is still shown");
  assert.doesNotMatch(obscured, /-41\.27/, "an obscured point is never shown");
  assert.doesNotMatch(obscured, /radius/);
  const undatedText = await when.textContent();
  assert.match(undatedText, /Photo date unknown/);
  assert.match(undatedText, /Uploaded unknown/);
  assert.match(undatedText, /Screening date not recorded/);
  assert.doesNotMatch(undatedText, /days after/);

  await rows.nth(2).click();
  await area.getByText("Not searchable: accuracy not supplied").waitFor();
  assert.match(await area.textContent(), /-41\.270, 173\.280/);
  assert.doesNotMatch(await area.textContent(), /radius/);
  console.log("Search areas and dates are stated per photo; unknowns stay unsearchable.");
} finally {
  await browser.close();
}
