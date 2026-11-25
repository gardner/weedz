# Pipeline benchmark program

Status: 25 November 2026. This tracks the work in
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
| Danish roadside | Published split indexes, multilabel CSV, XP4 checkpoint and 46 score-checked publisher tensors | Positive species recovery on a bounded replication fixture | Route proximity crosses source splits. A separate 25-frame test selection meets the filename-coordinate distance rule. Full threshold replication and cross-method image comparisons remain open. |
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

## Crop context and roadside replication

The paired ImageWeeds run varied crop geometry on all 645 publisher boxes using
the pinned PlantCLEF checkpoint and full vocabulary. Each box ran through raw
tight cropping with the original center-crop preprocessing, neutral square
padding of the tight crop, and neutral square padding of a crop extended by
25% of the longer box side on each edge. The same box and checkpoint were used
for all three views. Inference processed 1,935 crops in 69.35 seconds on an
RTX 5090, including per-image decoding and checksum verification.

| Crop view | Top one | Top five |
| --- | ---: | ---: |
| Legacy tight | 74/645 | 297/645 |
| Square tight | 60/645 | 278/645 |
| Square with context | 42/645 | 264/645 |

On square crops, context added 16 top-one hits and lost 34. Keep tight cropping
as the comparison baseline and prioritize a better classifier. The crop test
uses publisher geometry on previously inspected agricultural images, so its
decision scope is the next development experiment.

The [roadside publisher](https://zenodo.org/records/14013930) serves individual
feature tensors and the multilabel CSV from its
[original-data directory](https://lab.plantnet.org/DanishRoadsData/). The
directory audit reproduced all 10,302 train, 2,160 validation and 2,140 test
memberships, and matched all 206 multilabel tensor names to CSV rows. The
`val_16` and `test_14` quick checks are subsets of their respective main splits.
CSV taxon cells contain `1` or blank. Score the explicit positives while
completeness for each target remains unverified.

There are zero exact filename matches between the main train and test splits.
Filename coordinates place 129 test frames within 100 m of a training frame.
In the multilabel cohort, 153 of 206 frames meet that proximity condition, and
128 share a training frame's coordinates. These counts describe spatial
proximity and cannot establish whether pixels overlap or depict the same plant.

The XP4 smoke test ran the checksum-verified released six-output head over the
publisher's 926-by-768 BEiT features for each of 46 frames. A direct CPU FP32
linear, max and sigmoid calculation matched the upstream model's scores exactly.
The quick test recovered 3/12 positive pairs with one output and 11/12 with three.
The deterministically sampled 16 multilabel frames recovered 1/32 and 19/32
respectively. The run used ranked outputs because the official validation
threshold file was unavailable in the acquired assets. Image feature extraction,
official threshold metrics and false-alarm claims remain outside this run.

The reserved source-test selection has 25 frames across seven source folders,
including four from the publisher's no-species folder. The deterministic selection
uses filename and class, with a 100 m minimum distance from the published train,
validation and multilabel frames, the test smoke fixture and every other reserved
frame. The four-frame cap per folder left two classes short under the distance
rule. All four source dates remain shared. Training exposure outside the publisher
split and independent acquisition sites remain unknown.

The 46 smoke images and 25 reserved originals were downloaded and checksum
verified. The reserved frames passed exact decoded RGB matching and a 64-bit
dHash check at Hamming distance <=4 against the acquired smoke images and one
another. This image check covers those 71 files. The broader source-split audit
uses filenames and coordinates. The reserved images remain unscored.

A PlantCLEF pixel baseline screened the same 46 smoke frames for the six
declared roadside targets. It retained the full softmax denominator, took the
maximum score across mapped species for each grouped target and compared one
whole-image crop with the maximum over 16 equal-grid crops. The table uses the
same one- and three-target budgets as the XP4 smoke check.

| Smoke split | XP4 top 1 / top 3 | PlantCLEF whole top 1 / top 3 | PlantCLEF tiles top 1 / top 3 |
| --- | ---: | ---: | ---: |
| Validation, 13 positive pairs | 2 / 13 | 6 / 9 | 9 / 13 |
| Test, 12 positive pairs | 3 / 11 | 5 / 10 | 9 / 11 |
| Multilabel, 32 positive pairs | 1 / 19 | 8 / 24 | 14 / 29 |

The PlantCLEF run processed 782 crops in 18.90 seconds on an RTX 5090, including
image loading. Use the tiled variant as the stronger pixel baseline for the next
development comparison. The smoke fixture is bounded and spatially exposed,
and positive-pair recovery does not measure false alarms or reviewer effort.

The private reports and producer scripts are indexed in
[the tracked aggregate summary](../benchmarks/crop-roadside-diagnostics-20261125.json).

## Reserved roadside evaluation protocol

Freeze the candidate methods and gates before scoring the 25 reserved images.
Run whole-image PlantCLEF, the 4×4 PlantCLEF grid, the SAM3 masked-region branch,
and publisher-feature XP4. Score the same six target groups throughout.
For SAM3, use the existing plant and flower prompts and keep up to 16 unique
masks by concept score. The PlantCLEF branches use max aggregation within
target groups and across crops. Score the first one and three target slots.
Run each method once on the reserved set, excluding any failed run from claims
until the full original cohort has been retried with identical settings.

The primary quality gate for a candidate pixel pipeline is at least 60% of
explicit positive pairs recovered at rank one and 80% at rank three. At least
two more rank-one recoveries than the whole-photo control justify a more
expensive crop stage on this small fixture. If multiple crop methods meet the
gate, prefer higher rank-one recovery, then lower measured time. Report paired
gains and losses, denominators and per-target counts. Treat small differences
as development evidence. Use the publisher folder only for explicit positive
targets, with the no-species folder carried separately as a control.

Bound the study to 25 reserved frames and 16 classifier crops per image per
crop method. Measure wall time including source decoding and proposal
generation and report model-load time separately. Set a mean ceiling of
2 seconds per image on the local RTX 5090 for a candidate pixel pipeline and
report the 95th percentile. XP4 head timing covers publisher features and is
reported separately. These thresholds are provisional development gates.
NZ precision, missed plants and reviewer benefit require the blind and assisted
NZ review packages and human review.

## Reserved roadside results

Tiled PlantCLEF passed all three provisional gates on the reserved cohort.
Each method scored 25 frozen images with 21 explicit positive pairs and four
separate no-species controls. The top-one counts compare paired outcomes on the
same positives. Runtime covers local image loading for the pixel branches and
preserved uncached SAM3 proposal durations for the region branch.

| Method | Top one | Top three | Top-one gains / losses vs. whole | Mean / p95 seconds | Empty frames |
| --- | ---: | ---: | ---: | ---: | ---: |
| PlantCLEF whole photo | 10/21 | 17/21 | — | 0.171 / 0.174 | 0 |
| PlantCLEF 4×4 grid | 16/21 | 21/21 | 8 / 2 | 0.349 / 0.362 | 0 |
| SAM3 masked regions + PlantCLEF | 1/21 | 3/21 | 0 / 9 | 0.576 / 1.160 | 17 |
| XP4 publisher-feature head | 5/21 | 16/21 | 2 / 7 | 0.003 / 0.003 | 0 |

The XP4 row covers cached-feature loading and CPU head inference. PlantCLEF
and XP4 model initialization together took 1.55 seconds. The existing SAM3
proposal script recorded runtime after initialization, so separate SAM3 load
duration remains unavailable. The SAM3 smoke comparison similarly had 24
empty frames out of 46 and recovered 6/32 positive multilabel pairs at rank
three. The profile often loses the plant before species identification starts.

Freeze PlantCLEF 4×4 as the first NZ transfer candidate with fixed crop geometry,
full-softmax scores, and per-target maximum across tiles. Preserve the winning
tile's source bounds for any assisted task. A NZ abstention policy still needs
an explicit development choice. Rankings by themselves force a target even
when all scores are weak, so the four no-species control scores remain
descriptive and do not establish a false-alarm rate.

The reserved results mainly measure recognition of the publisher's labeled
roadside subjects. They support choosing a cheaper crop policy and rejecting
the tested SAM3 profile for this fixture. NZ background localization,
lookalike behavior, calibrated operating thresholds, and reviewer effort
need separate evidence.

## NZ transfer controls and pilot policy

The same crop and scoring policy ran on the existing 300 NZ source-subject
photos in 81.44 seconds for 5,100 classifier crops. Source labels were joined
after the predictions were saved. Among the three watchlist subjects, the
4×4 grid ranked the photographed subject first in 149/150 images. Whole-photo
PlantCLEF ranked it first in 143/150. With broom added as a fourth target, the
counts were 198/200 and 191/200, respectively.

The pinned PlantCLEF vocabulary lacks the NZ cohort's two native lookalike
subjects, *Austroderia fulvida* and *Clematis paniculata*. Thirteen of the 100
native-subject images reached the median tile score of the 150 watchlist
subjects. A priority rule using that score floor and agreement with PlantCLEF
whole-photo ranking admitted 75 of 150 watchlist-subject photos and 13 of
100 native-subject photos. Adding agreement with the broad native
EfficientNet classifier retained 69 of 150 watchlist subjects and zero of
those 13 native-subject images on these development controls. The native
classifier can itself confuse or miss lookalikes, and agreement may suppress
a valid incidental target when a different subject fills the frame.

For the assisted pilot, freeze the three-target watchlist, one priority
suggestion per image, the PlantCLEF 4×4 geometry and max policy, and a score
floor of 0.13646656274795532. The whole-photo PlantCLEF top watchlist target
and broad native EfficientNet top species must both agree with the tile
target to receive priority. This floor is a development triage heuristic.
Record source pixels, the winning tile's bounds, model identities and both
classifiers' suggestions. A winning tile is a search area for the reviewer.
The reviewer supplies any plant location and species label.

Preserve above-floor disagreements, native lookalikes, and visually
difficult candidates as distinct assisted strata. Both low scores and absent
agreement remain eligible for an independently sampled blind stratum.
Collect blind frames by a fixed, seeded ordering of source-eligible incidental
photos before looking at scores, with no predictions in the reviewer payload.
Keep priority suggestions separate from verified labels and retain uncertain
and visually unresolvable outcomes.

The existing NZ90 blind package passed a checksum and payload audit on all
90 images. It has 90 unique decoded images, 90 observations and 90 observers,
with zero annotations or predictions in the bundle. It includes 19
animal-subject incidental photos and no encoded encounter groups. It is useful
for testing the review format. A paired assisted and blind incidental pilot
still needs a wider incidental pool and an encounter audit across both splits.

The source-control and package-audit reports are indexed in
[the NZ transfer summary](../benchmarks/nz-tile-transfer-20261125.json).

## First incidental NZ acquisition

The frozen pilot source frame contains 368 eligible animal-subject
observations from the first two ID-ordered iNaturalist pages in each of four
2025 months. It is a bounded sampling frame. Seeded order within each month
assigned blind photos before assisted-pool selection and before model inference.
Both observation and original-photo licenses had to be CC0 or CC BY, and the
source coordinates had to be public with reported accuracy of 100 m or better.

The resulting offline blind package contains 16 images, four per month. The
package audit verified checksums, independent observer and observation IDs,
unique decoded images, and prediction-free and annotation-free task payloads.
The two-arm source selection excluded near-duplicate hashes and encounters
within two days and 100 m plus both coordinate uncertainties. Exact locations
stay in private acquisition evidence.

The first assisted pool yielded eight images against the planned quota of 48.
The capped search encountered 268 known-observation or observer exclusions,
including attempts repeated across arms. All eight assisted photos fell below
the frozen priority floor. Retain those results as low-score evidence and expand
the assisted source using later incidental pages and distinct botanical
lookalike and target-subject strata. The expanded source changes the assisted
sampling frame and leaves the blind sample frozen.

The first acquisition and bundle verification are indexed in the
[pilot acquisition summary](../benchmarks/nz-paired-pilot-20261125.json).

## Remaining work and next experiment

1. Expand the split audit to another species-box source with documented capture
   groups. Compare eligible domain-suited classifiers against the measured
   ImageWeeds crop baseline and preserve a fresh evaluation cohort.
2. Apply the frozen NZ pilot policy to eligible images. Separate model
   disagreement, lookalike and hard-case selection from probability sampling.
3. Obtain or recreate the official validation thresholds before claiming
   reproduction of XP4's published operating point. Add usable PlantCLEF plot
   labels if available and preserve domain-specific reports.
4. Prepare and validate NZ candidate and blind-review packages. Verify no
   observation, photographer, exact decoded image, near duplicate or known
   encounter crosses the two sets, and record the coverage of the encounter audit.
5. Run a small human usability pilot to measure actual effort. Specialist NZ
   verification remains necessary before claims about background discovery.
