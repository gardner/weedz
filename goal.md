# Weedz long-term goal

Make Weedz a reproducible, open system that discovers overlooked invasive plants
in New Zealand photographs and produces human-verified evidence useful to
conservation work.

## The problem

Existing photographs contain invasive plants that were not the original subject
and therefore were never recorded. Weedz should turn those photographs into a
manageable queue of locatable, species-specific findings for human verification.

The pipeline runs, but useful background discovery has not yet been established.
The 300-photo NZ experiment produced 3,930 candidate masks and species suggestions;
those are unverified proposals, not verified plants or independent discoveries.
Recovering the original photographed subject does not measure additional finds.

## Lasting outcomes

- A reviewed NZ benchmark covering incidental weeds, native lookalikes and negatives.
- A reproducible detection pipeline with measured accuracy, cost and review effort.
- Traceable, human-verified findings that conservation workers and researchers can
  reuse, preserving attribution, permissions and location uncertainty.

## Milestones

### 1. Establish a trustworthy comparison

Reproduce the released Danish roadside invasive-plant baseline on a bounded,
fixed source test selection. Audit labels, vocabulary, duplicates and split
semantics before interpreting results.

Compare whole-photo, tiled and segmented approaches on the same evaluable images
and taxa, under the same final candidate and human-review budget. Measure whether
segmentation helps rather than treating it as a prerequisite.

Deliver a repeatable experiment with pinned inputs and model versions, saved
outputs, explicit evaluation limits and a recommendation for the NZ comparison.

### 2. Build the first reviewed incidental NZ benchmark

Prepare a fixed cohort of ordinary ground-level NZ photos, initially targeting
old man's beard, pampas grass and gorse. Include actual background weeds, native
lookalikes, confirmed negatives and randomly selected unflagged photographs.

Obtain independent human review within a declared target scope. Retain uncertain
and visually unresolvable cases, review history and source-aligned geometry.
Keep related encounters apart across fitting, validation and test partitions.
Freeze the reviewed dataset with provenance and applicable reuse terms.

### 3. Demonstrate practical conservation value

Evaluate the selected pipeline on held-out incidental NZ scenes. Measure:

- Verified additional discoveries and independent encounters.
- Useful verified findings per reviewer-hour.
- Wrong, duplicate and inconclusive suggestions per useful finding.
- Missed visible targets, including those in sampled unflagged photos.
- Processing throughput, compute cost and repeatability.

Agree numerical acceptance targets for the watchlist and review budget before
the final evaluation. Distinguish additional photographic evidence from a
verified new locality; camera coordinates alone do not locate a distant plant.
Scale collection and deployment only after the pilot demonstrates useful results.

## Next work slice

Run a small, reproducible replication of the released Danish roadside baseline.
This follows the prior-art investigation and supplies evidence for choosing the
next model approach while the NZ review cohort is prepared.

## Supporting documents

- [Problem statement](docs/problem-statement.md)
- [Prior-art investigation and recommended experiment](docs/background-plant-prior-art.md)
- [Dataset problem](docs/problem-dataset.md)
- [Reviewed dataset release workflow](docs/gold-release-workflow.md)
- [Region evaluation protocol](docs/region-evaluation.md)
