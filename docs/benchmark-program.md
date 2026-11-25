# Pipeline benchmark program

Status: 25 November 2026. This implements the first work slice in
[the immediate goal](../immediate-goal.md). The pipeline is not ready for the main
NZ labeling effort. Existing labels reveal substantial localization,
identification and aggregation failures; reviewed NZ negatives and incidental
species labels remain absent.

## The problem

A single final score cannot tell us whether a plant was missed, cropped badly,
misidentified or discarded during ranking. Existing source-labeled development
datasets let us isolate those failures before commissioning new NZ labels.

## Source and evaluation matrix

The verified inventory below checks the actual local manifests, media/mask hashes
and source provenance receipts. It does not certify botanical label correctness
or training independence. All acquisition and inference artifacts stay outside Git.

| Source | Local evidence checked on 25 November | Eligible evaluation | Exposure and remaining gaps |
| --- | --- | --- | --- |
| ImageWeeds primary | 138 media files, 645 source boxes; manifest and provenance hashes verified | Labeled-region recovery; conditional species identification; recall of 303 labeled positive image-species pairs | Already inspected development data. Partial labels: no precision or negatives. Ambiguous pixel aliases and invalid geometry quarantined. No independently established site split or pretraining exclusion. |
| PhenoBench development | 64 images, 853 source plant instances; 192 raw image/semantic/instance files and canonical manifest verified | Foreground coverage and instance recovery; crop/weed semantics | Publisher validation subset already used for development. Agricultural/top-view domain. Crop/weed labels cannot measure weed-species identity. Archive/site license claims differ; retain private research handling. |
| CWFID | 60 images, 119 sparse category masks; 179 media/mask assets and manifest/provenance verified | Coverage of assessed crop/weed positive pixels | Already inspected. Multispectral false-color imagery and partial human support. Source image 028 overlaps train/test; exclude from held-out claims. Algorithmic vegetation boundaries are separate evidence. |
| NZ90 review preparation | 90 media assets and manifest/provenance verified; zero annotations | Review preparation only | Observation/observer groups exist, but site independence and botanical labels are not established. No predictions added during this audit. Recheck all prior exposure before assigning a blind holdout. |
| NZ300 subject controls | Prior cohort receipt and experiment documentation available; not re-audited by this source inventory | Existing subject-recovery diagnostic only | Already inspected six-species development cohort. Subject labels do not exhaustively label scenes. Neither incidental discovery nor fresh holdout evidence. |
| Danish roadside | Repository/Zenodo metadata retained in research artifacts | Intended species-presence benchmark and released-method replication | No locally closed dataset/inference receipt identified in the inspected inventory. Acquire and audit CSV completeness, duplicates, taxa and source splits before evaluation. |
| PlantCLEF | Released classifier checkpoint and cached ImageWeeds outputs available | Same-classifier whole-frame/tile/region comparisons on ImageWeeds | This is not an official PlantCLEF plot evaluation. Usable plot truth and a closed source split still need verification/acquisition. |

Leafy Spurge and DeepWeeds remain supporting point-classification and image-class
experiments, respectively. They are previously used sources, not substitutes for
mixed-scene localization or new independent origins. Their full caches were not
rehashed in this bounded inventory.

## Replayed localization and identification baseline

The current region evaluator rechecked the source-bound ImageWeeds138 SAM3 outputs
and PlantCLEF masked-crop classifications. Source pixels, proposal receipts,
classifier outputs and taxonomy mapping are checksum-bound. Its aggregate exactly
matches the saved predecessor report.

At IoU >=0.5, with at most the first 100 retained proposals per image:

- 348/645 labeled regions recovered (53.95%); 297 not localized.
- Correct top-one species for 48/348 matched regions (13.79%).
- 300 matched regions misidentified.
- 48/645 labeled regions both localized and correctly identified (7.44%).
- 5,590 actual proposals assessed for matching. All remain unassessed for false
  alarms because source labels are partial; unmatched does not mean false.

These are region/box diagnostics, not instance-mask accuracy, COCO AP, final
image-species recall or NZ performance. The distinct source-box crop control
previously recovered 74/645 as top one and 297/645 as top five, further motivating
classifier/domain and crop-context work. That control is a historical result, not
a new inference run or a guaranteed achievable upper bound.

## First improvement experiment: aggregation

Question declared before running the comparison: does frequency voting suppress
strong, infrequent species candidates? Compare frequency with each taxon's maximum
individual crop score, keeping the same final five-species budget. No source labels
or target vocabulary enter ranking. Uncalibrated softmax scores are ranking
heuristics, not presence probabilities.

The experiment reuses checksum-verified predictions from the same classifier
checkpoint and vocabulary. Source image identities and cohort coverage must match
exactly; duplicates, missing records, mismatched images and incomplete taxonomy
mappings fail rather than disappear from the denominator.

| Branch | Frequency: recovered positive pairs | Maximum score: recovered positive pairs |
| --- | ---: | ---: |
| 4x4 tiles | 0/303 (0%) | 5/303 (1.65%) |
| SAM3 masked regions | 5/303 (1.65%) | 23/303 (7.59%) |

Whole-frame top five recovers 0/303. All methods retain the full 7,806-class
vocabulary during inference; the five source taxa are used only for scoring.
The tile branch has 2,208 crops versus 5,590 region crops, so cross-branch compute
is unequal. Frequency and maximum-score comparisons within each branch reuse the
same predictions and require zero new inference calls.

Before the final budget, correct labeled species appear somewhere in cached
top-five crop lists for 35/303 tile pairs and 178/303 region pairs. Those unbounded
unions are candidate-coverage diagnostics, not deployable results or precision.
Only top-five crop scores were cached; other taxa's full logits are unavailable.

Decision: keep maximum-score aggregation as a development comparison, not a
production replacement. The gain is real on these inspected images but the final
recall is still poor. Next work must address weak region identification and crop
context as well as proposal misses. Partial labels prevent concluding that the new
policy reduces reviewer workload; false alarms could increase.

## Reproduction and evidence

Private evidence root:

```text
/home/gardner/src/weedz-evaluation-artifacts/20261125/
```

It contains source inventory verification, pinned replay/aggregation commands,
the closed region replay and versioned aggregation reports. Raw images, per-image
predictions and review material are not committed. The tracked aggregate summary
is [benchmarks/pipeline-diagnostics-20261125.json](../benchmarks/pipeline-diagnostics-20261125.json).

The reusable comparison command is:

```sh
uv run python scripts/benchmark_species_aggregation.py \
  --manifest "$MANIFEST" --manifest-sha256 "$MANIFEST_SHA" \
  --frames "$FRAMES" --frames-sha256 "$FRAMES_SHA" \
  --regions "$REGIONS" --regions-sha256 "$REGIONS_SHA" \
  --taxonomy "$TAXONOMY" --taxonomy-sha256 "$TAXONOMY_SHA" \
  --vocabulary "$VOCABULARY" --budget 5 \
  --output /absolute/private/new-output-directory
```

The command reads cached rankings and canonical source annotations; it does not
invoke models, change source data or upload tasks. A separate closed region replay
verifies original media and proposal geometry. Always use a new output namespace.

## Remaining work and next experiment

1. Audit a new source development/validation/evaluation selection before running
   more policies. The 138-image cohort is already exposed and cannot become a
   fresh held-out test merely by splitting it now. Check overlapping source sites,
   dates and decoded pixels, and document unknown foundation-model training overlap.
2. Compare source-box tight/context crops and eligible domain-suited classifiers.
   Audit vocabulary first. Use source truth only for crop construction/scoring,
   never to limit candidate species. Train only on declared training partitions.
3. Reproduce the released roadside baseline, then compare whole-photo, tiled and
   region methods on common evaluable taxa. Add usable PlantCLEF plot labels if
   available; preserve domain-specific reports.
4. Declare numerical quality/cost gates and a bounded experiment budget before
   final held-out evaluation. Neither this development gain nor a candidate union
   satisfies the readiness gate in the immediate goal.
5. Freeze a justified model/crop/aggregation policy only after comparisons. Then
   prepare diverse NZ candidate and blind-review packages, preserving random
   unflagged photos, lookalikes, uncertainty, provenance and encounter separation.
6. Run a small human usability pilot to measure actual effort. Specialist NZ
   verification remains necessary before claims about background discovery.
