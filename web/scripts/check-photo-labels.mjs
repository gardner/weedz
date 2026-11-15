import assert from "node:assert/strict";
import { sourceSubject, watchlistHint } from "../lib/photo-labels.ts";

const names = { "Ulex europaeus": "Gorse" };
const tern = {
  cohort: "incidental",
  original_common_name: "Black-fronted Tern",
  original_taxon: "Chlidonias albostriatus",
};
assert.equal(sourceSubject(tern), "Black-fronted Tern");
assert.equal(
  sourceSubject({ ...tern, cohort: "device", original_common_name: "Gorse" }),
  "Device report",
);
for (const margin of [-0.041927, 0])
  assert.equal(
    watchlistHint({ best_species: "Ulex europaeus", margin }, true, names),
    "No positive watchlist match",
  );
for (const margin of [undefined, NaN, Infinity])
  assert.equal(
    watchlistHint({ best_species: "Ulex europaeus", margin }, true, names),
    "Screening comparison unavailable",
  );
assert.equal(
  watchlistHint({ best_species: "Ulex europaeus", margin: 0.01 }, true, names),
  "Model hint: Gorse · needs review",
);
assert.equal(
  watchlistHint({ best_species: "Ulex europaeus", margin: 0.99 }, false, names),
  "Screening result has no declared interpretation",
);
assert.equal(watchlistHint({}, true, names), "Awaiting screening");
console.log("Source subjects remain distinct from signed, declared watchlist comparisons.");

assert.equal(
  watchlistHint({ best_species: "Unknown species", margin: 0.99 }, true, names),
  "Unrecognized watchlist comparison",
);
