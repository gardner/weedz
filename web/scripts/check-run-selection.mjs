import assert from "node:assert/strict";
import { initialRun } from "../lib/run-selection.ts";

const runs = [
  { id: "queued", status: "queued" },
  { id: "expanded", status: "completed" },
  { id: "plants", status: "completed" },
];
assert.equal(initialRun(runs, "plants"), "plants");
assert.equal(initialRun(runs, "missing"), "expanded");
assert.equal(initialRun(runs, "queued"), "expanded");
assert.equal(initialRun(runs), "expanded");
assert.equal(initialRun([runs[0]], "plants"), "queued");
assert.equal(initialRun([], "plants"), undefined);
console.log("An explicit completed plant collection stays the default as other runs are added.");
