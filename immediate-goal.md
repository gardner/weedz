# Immediate goal: validate and improve the pipeline before NZ labeling

Build and repeatedly run a diagnostic benchmark suite using existing human-labeled
datasets, improve the weakest pipeline stages, and use the resulting pipeline to
assemble a diverse, traceable NZ dataset ready for human review.

This supports the [overall goal](goal.md). Prioritize this work before the main NZ
human-labeling effort, so reviewers spend their time on botanical judgments rather
than avoidable pipeline errors.

## The problem

The pipeline produces plant regions and species suggestions, but we need to know
which plants it misses, whether its crops preserve identification features, and
whether its final suggestions are useful. Mask counts and recovery of an image's
original subject do not establish reliable background discovery.

Existing human labels let us diagnose and improve much of this before asking
reviewers to label NZ scenes. External benchmarks cannot establish transfer to
incidental NZ photography; that remains a later human-review question.

## 1. Assemble a complementary benchmark suite

Reuse existing adapters, canonical manifests and region evaluation tools. Add
datasets when they supply a missing label type, species or difficulty, rather than
optimizing image count alone.

| Source | Diagnostic role | Limits |
| --- | --- | --- |
| PhenoBench | Plant-instance recovery, fragmentation and overlap | Agricultural geometry; crop/weed categories do not establish NZ species identity |
| ImageWeeds | Localization and species identification using source boxes | Existing cohort has partial labels and quarantined duplicate/geometry defects |
| Danish roadside data | Species presence in cluttered scenes; reproduce released baseline | Audit label completeness, vocabulary and split semantics first |
| PlantCLEF | Multi-species recognition in mixed vegetation | Use only accessible evaluation labels; image-level lists do not validate masks |
| Eligible NZ subject and lookalike photos | Target identification and confusion with similar plants | Subject labels do not exhaustively identify background plants |

For every source, record rights, annotation origin and completeness, taxonomy,
pixel identity, duplicates, encounter/site groups where available, split membership
and known or unknown model-training overlap. Preserve source labels as source
evidence. Unlabeled plants are not automatically false predictions.

Keep development, validation and held-out evaluation separate. Preserve sound
publisher splits, quarantine overlap, and group related images to prevent leakage.
Already inspected cohorts remain development evidence. Do not pool incompatible
domains or label types into a misleading overall accuracy score.

## 2. Diagnose stages independently

Run three complementary evaluations on compatible labels:

1. **Human regions to classifier.** Classify source-labeled boxes or masks to
   measure identification when localization is supplied. Compare tight, masked and
   contextual views using a policy fixed before scoring.
2. **Pipeline proposals to human regions.** Measure recovery and misses at declared
   overlap thresholds and proposal budgets. Report fragmentation and duplicates
   where the source's instance labels support those claims. Foreground coverage
   remains separate from whole-plant recovery.
3. **Whole image to final findings.** Measure species recovery and, where labels
   are complete within the target scope, precision and false alarms after ranking,
   filtering and deduplication.

Break results down by species, plant size, clutter, occlusion and scene type where
annotations support those categories. Track runtime and compute use alongside
quality. Unmatched proposals under partial labels remain unassessed.

## 3. Improve the largest measured failures

Compare whole-photo recognition, multi-scale tiles and segmented regions at the
same final suggestion budget, with compute differences reported. Reproduce the
released roadside implementation as one comparison within this suite.

Use diagnostics to choose changes:

- Good source-region identification but poor pipeline crops: improve proposal
  coverage, resolution, crop context or retention policy.
- Poor identification even on source regions: investigate vocabulary, classifier
  suitability and targeted training on eligible training labels.
- Good intermediate results but weak final findings: improve aggregation,
  thresholds, uncertainty handling and deduplication.

Freeze input/model versions, preprocessing, thresholds and output budgets for each
run. Cache expensive stages and retain raw outputs so comparisons are repeatable.
Tune only on development/validation data. Do not repeatedly select improvements
using held-out results or choose a crop view using its ground-truth answer.

## 4. Prepare the NZ collection for efficient review

Use the improved pipeline to prepare ordinary ground-level NZ photos, initially
targeting old man's beard, pampas grass and gorse. Preserve source resolution,
geometry, rights, attribution, uncertainty and encounter grouping.

Include strong candidate positives, native lookalikes, model disagreements,
difficult small/distant/occluded plants, and randomly selected photos including
unflagged scenes. Keep sampling strata and inclusion rules so targeted enrichment
is not mistaken for natural prevalence.

Remove duplicate encounters from independent splits. Check review-package image
quality and coordinate alignment. Retain unknown and visually unresolvable cases.
Machine suggestions remain proposed labels; only completed human checks establish
confirmed positives or negatives.

Keep a separate blind review sample without model suggestions for measuring
misses and false alarms. A collection containing only confident predictions would
hide failures and give a biased assessment.

## Readiness for the main human-labeling effort

The aim is measurable readiness rather than an indefinitely perfect pipeline:

- Reproducible benchmark reports separate localization, identification and final
  findings, with explicit label scope and evaluation limits.
- Major avoidable failures are corrected or documented, and improvements are
  supported by comparisons under declared budgets.
- Numerical quality/cost targets and an experiment budget are recorded before
  final benchmark evaluation; remaining gaps have explicit dispositions.
- The selected pipeline and decision policy are frozen for NZ preparation.
- Review packages are diverse, deduplicated, source-aligned and traceable, with
  a separate blind sample and clear uncertainty handling.

A small human pilot must still check annotation usability and actual reviewer
effort. Specialist NZ review establishes transfer, confirms species and reveals
remaining domain-specific failures; external benchmark success cannot replace it.

## Current status and next steps

The [benchmark program](docs/benchmark-program.md) records the source inventory,
split and label limits, reproducible baselines, and improvement experiments.
On ImageWeeds, maximum-score aggregation raised recall from 5 to 23 of 303
labeled image-species pairs at five suggestions per image. On the held-out
Danish roadside subset, tiled PlantCLEF recovered 16 of 21 labeled positives at
top one versus 10 for whole-photo classification. The released XP4 thresholds
recovered 15 of 21 positives on that same subset using a variable number of
suggestions. Incidental species recovery in NZ remains unmeasured.

The frozen NZ policy has verified offline packages for 16 blind and 21 assisted
tasks. The assisted set includes uncertain incidental scenes, lookalikes and
target-subject controls. All package images and search crops passed a local
review-interface check. Real incidental candidates above the priority threshold
are still missing, and no human submissions or measured review times exist.

1. Keep the blind NZ sample and its sealed outputs fixed. Use a separate
   discovery pool for any additional independently sourced candidate positives
   and record the inclusion criteria.
2. Run the small NZ usability pilot with independent human submissions. Measure
   completion, time and uncertainty in both arms. Compare frozen predictions
   against agreed, assessable blind outcomes before deciding whether to widen
   labeling or revise the policy.

## Supporting documents

- [Benchmark program, verified inventory and current results](docs/benchmark-program.md)
- [Overall goal](goal.md)
- [Region evaluation protocol and existing diagnostics](docs/region-evaluation.md)
- [Labeled-source preparation](docs/datasets/labelled-sources.md)
- [Prior-art investigation](docs/background-plant-prior-art.md)
- [Problem statement](docs/problem-statement.md)
- [Reviewed dataset release workflow](docs/gold-release-workflow.md)
