// Preserve the full interval a strict downstream decoder consumes, even on a fast machine.
export async function finishRecordingInterval(page, started, minimumMilliseconds) {
  await page.waitForTimeout(Math.max(0, minimumMilliseconds - (performance.now() - started)));
}
