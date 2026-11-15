// Select by run/photo identity, never a subject label shared by several photos.
import assert from "node:assert/strict";

export async function selectCaptureSource(page, runId, photo) {
  const settings = page.locator("details.run-settings");
  if (!(await settings.evaluate((element) => element.open)))
    await settings.locator("summary").click();
  const runs = page.getByLabel(/^Saved run/);
  await runs.selectOption(runId);
  assert.equal(await runs.inputValue(), runId);
  await settings.locator("summary").click();
  await page.getByRole("button", { name: "References", exact: true }).click();
  const imagePath = `/api/runs/${runId}/photos/${photo.id}/image`;
  const row = page.locator("button.photo-row").filter({
    has: page.locator(`img[src=${JSON.stringify(imagePath)}]`),
  });
  await row.click();
  await page.waitForFunction((expected) => {
    const stage = document.querySelector(".image-stage");
    const image = stage?.querySelector("image");
    const fallback = stage?.querySelector("img");
    return (image?.getAttribute("href") ?? fallback?.getAttribute("src")) === expected;
  }, imagePath);
  assert.equal(await row.getAttribute("aria-pressed"), "true");
}
