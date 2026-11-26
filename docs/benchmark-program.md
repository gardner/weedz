# Pipeline benchmark program

## Plant-presence intake benchmark protocol

Use the [MIT ADE20K scene-parsing validation set](https://github.com/CSAILVision/sceneparsing#benchmark-details)
as an external vegetation proxy. Map the human mask labels for tree, grass,
plant, flower and palm. Sample 12 photos per stratum in each of two disjoint
scene-category splits. Include mapped vegetation above 0.5% of the image,
mapped vegetation at or below 0.5%, and no mapped vegetation with low ignore
coverage and without the ambiguous field, hill or land classes. Cap each
scene category at six frames per stratum. Use deterministic hash order for
selection and verify the input pairs and duplicate exclusions before inference.
The third stratum supports only a class-scoped prompt comparison.

Compare the existing SAM3 `plant` and `flower` whole-frame pass with that
same pass plus four overlapping half-scale tiles. Use one call per view and
keep the existing model settings. Evaluate threshold choices 0.50, 0.60 and
0.70. Select on development by requiring at least 95% retention of labeled
plant-positive frames; among eligible choices minimize comparison-frame calls,
then prefer the cheaper method. Report omitted-split retention by plant size,
any proposal versus mapped-region recovery, and runtime. Withhold an intake
deprioritization policy if the held-out positive retention falls below 95%.
Scene categories and pixel checks bound overlap; physical-site and model
pretraining overlap remain unknown. Use the existing stage benchmarks for
geometry and weed taxonomy, which this source does not supply.

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
| Danish roadside | Published split indexes, multilabel CSV, XP4 checkpoint, released thresholds and checksum-verified publisher tensors | Positive species recovery, crop comparisons and released threshold replay on bounded test cohorts | Route proximity crosses source splits. A separate 25-frame test selection meets the filename-coordinate distance rule. Annotation completeness and full test-split scores remain unknown. |
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
respectively. This initial comparison uses ranked outputs. The released
threshold replay below uses fixed cutoffs. Image feature extraction and
false-alarm claims remain outside both comparisons.

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
uses filenames and coordinates. The reserve remained unscored until the
evaluation protocol below was frozen.

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

The assisted-only supplement acquired 30 photos from later incidental pages
and separate botanical queries. Eighteen are incidental and 12 are labeled
botanical subjects. Observer, observation, pixel and encounter checks included
both original arms. The illustrated package selects 15 photos: six uncertain
incidental cases, five lookalikes and four target-subject references.
All 26 screened incidental photos were below the priority floor. The two
priority verdicts and one above-floor disagreement came from botanical
subjects. The separate gorse reference query yielded zero eligible originals
within its acquisition cap. These shortfalls limit the pilot's usefulness for
testing candidate discovery. The existing tasks can test annotation usability.

The assisted bundle shows each model hint and an exact source-pixel crop.
The full source image remains the annotation target. Each search crop's
pixel bounds, dimensions and checksum are bound to its source image in the
private receipt. The package creates zero annotations and zero seeded
predictions. Both task sets offer an unsure outcome. The audit rechecked
31 task checksums, source bindings, policy version and zero shared pixels,
observations or observers. The pairwise proximity and dHash checks cover
all selected frames.

The two offline bundles live under the private evidence root as
`nz-paired-pilot-blind-package-v1` and `nz-paired-pilot-assisted-package-v1`.
For a human usability pilot, have reviewers inspect the whole image for each
watchlist species, draw regions where identities are resolvable, and record
an unsure outcome for inadequate evidence. Use image credits for attribution
and defer opening linked source observations until the task is submitted.
Record task duration, uncertain outcomes and problems with the instructions,
image zoom or geometry. Keep times by arm. These are different sets of
photos, so their effort difference alone cannot isolate the effect of hints.
No timing or botanist review outcome has been collected.

The first acquisition and bundle verification are indexed in the
[pilot acquisition summary](../benchmarks/nz-paired-pilot-20261125.json).

## Incidental agreement and habitat diagnostics

Agreement with a whole-photo classifier penalizes incidental detections when
the photographed subject dominates the image. A controlled stress test pasted
24 source-labeled watchlist photo crops into separate animal-subject frames in
known tiles. Each was tested at two sizes. The model received image pixels and
the same three-target watchlist. The planted images stay outside both review
arms and serve as a diagnostic of the decision rule.

| Planted crop size | Correct target and tile | Retained by whole-photo rule | Retained by local agreement at frozen floor | Local agreement before the floor |
| --- | ---: | ---: | ---: | ---: |
| Full tile | 19/24 | 0 | 4 | 14 |
| Half tile width and height | 18/24 | 0 | 1 | 13 |

The local check classifies the selected tile with native EfficientNet. It agreed
with zero PlantCLEF target suggestions on the 26 real incidental controls.
The pasted crop sizes and source subjects are known. Their realism, botanical
visibility within each crop, and performance in real background scenes remain
unverified. Preserve the frozen priority rule and retain local agreement as a
development comparison.

A separate habitat search queried 12 public watchlist neighborhoods using
1.2 km axis-aligned bounds from each anchor. It returned 648 records before
eligibility, overlap and image checks. Ten original bird, mammal or reptile
photos passed acquisition and separation checks. All ten fell below the floor.
Proximity to a watchlist observation is an acquisition cue. Species presence
in a returned image needs image evidence and human review.

Assisted package v2 preserves the 15 v1 tasks and adds four below-floor
challenge cases. Two have the highest remaining incidental scores from the
previous pools, and two have the highest scores in the habitat pool. All
four retain their uncertain priority status. The first of the old-pool
examples shows small yellow flowers in distant shrubbery, a visual cue worth
checking without treating the model's species suggestion as verified. The
v2 package pairs **19 assisted** with the original **16 blind** tasks,
with observer, observation, image and encounter separation rechecked.

A separate gorse query across three fixed observation intervals acquired
three original photos whose source subject is *Ulex europaeus*. All three
fell below the frozen priority score. Assisted v3 adds two of those photos as
reference cases. It preserves all 19 v2 tasks and their search crop pixels.
The v3 bundle has **21 assisted** tasks, paired with the original **16 blind**
tasks. All package hashes and task bindings were checked. A separate local
Label Studio 1.23.2 run imported both arms, served and verified all 37
source images and all 21 assisted search crops, and opened a new gorse task
in the browser. These gorse-subject controls can reveal how reviewers
handle low scores for an expected subject.
No incidental target is verified by the new stratum.
[Acquisition and package evidence](../benchmarks/nz-gorse-controls-20261125.json).

## External source-box benchmark with recording sessions

The [CropAndWeed authors' release](https://github.com/cropandweed/cropandweed-dataset)
provides source boxes and identifies acquisition sessions in filenames. The
full annotation archive has 8,034 image records and 929 session keys. The
[dataset paper](https://openaccess.thecvf.com/content/WACV2023/papers/Steininger_The_CropAndWeed_Dataset_A_Multi-Modal_Learning_Approach_for_Efficient_Crop_and_Weed_Manipulation_WACV_2023_paper.pdf)
describes sessions as site or experimental plot at a capture time. The
downloaded annotation parameters contain capture conditions. They do not
prove that different sessions use distinct physical sites.

Acquisition was bounded to the first 40 MiB of each of the four official
image archives. After checking complete JPEG records, decoded duplicates and
boxes mapped to the pinned classifier vocabularies, the bounded fixture covered
13 sessions. Eight development sessions supplied 14 images and 49 sampled
boxes. Five reserve sessions supplied ten images for the later classifier
adaptation comparison.
Results apply to the selected prefixes, rather than estimating population
performance across the archive. The terms permit noncommercial research
and restrict distribution. Images and annotations stay private.

| Box crop | PlantCLEF top 1 / top 5 | NZ EfficientNet top 1 / top 5 |
| --- | ---: | ---: |
| Tight | 1 / 1 | 0 / 1 |
| Square with 25% context | 0 / 2 | 1 / 2 |

Each model's full vocabulary covers the taxon for every scored box. The
crops represent five supported taxa. Low accuracy persists with source box geometry,
and neither preprocessing nor substituting the NZ model provides a useful
improvement here. Keep this fixture for classifier and domain diagnostics.
It says nothing about nameable plants missed by a proposal stage or NZ field
accuracy.

The [PlantCLEF 2024](https://www.imageclef.org/PlantCLEF2024) and
[2025](https://www.imageclef.org/PlantCLEF2025) publisher archives exposed test
image headers and metadata CSVs through HTTP range requests. The 2024 CSV has
1,695 entries and the 2025 CSV has 2,105. Both contain plot identities, author,
date and license. These CSVs provide provenance. Row-level species truth
remains unverified in the public download, so no official plot scores were computed.

The grouped-source, decision-rule and packet results are indexed in the
[latest diagnostic summary](../benchmarks/nz-context-and-grouped-source-20261125.json).

## Blind outcome analysis

The unchanged `aa4db4a` decision policy was run on the 16 blind photos
before reviewer submissions. The decisions are sealed under
`nz-blind-policy-seal/sealed-decisions.json` in the private evidence root.
The seal binds the source manifest, package manifest, exact task payloads and
scorer. The reviewer bundle retains only the original task data and credits.
Keep the seal outside the review workspace until independent submissions are
finished.

After review, use full Label Studio JSON with task metadata and annotations.
Use the package and private seal from the same pilot revision.

```sh
uv run python -m weedz.annotation.pilot_outcomes \
  --blind-package /private/path/to/blind-v1 \
  --blind-export /private/path/to/blind-export.json \
  --sealed-decisions /private/path/to/sealed-decisions.json \
  --output /private/path/to/blind-outcomes.json
```

The report counts exact taxon-set agreement from at least two distinct
reviewer accounts. A single reviewer can contribute usability and timing
evidence. The outcome analysis keeps single-reviewer, conflicting and unsure
cases separate. A completed submission must explicitly name visible watchlist
taxa or answer that none are visible. A suggestion unsupported by those
answers is reported as unsupported in the pilot, with expert adjudication
and exhaustive site absence outside its scope.

The local synthetic export produced one unsure task and 15 unreviewed tasks.
It serves as an integration check. Use actual submissions for the pilot
decision. The artifact hashes are recorded in
[the pilot seal summary](../benchmarks/nz-blind-outcome-seal-20261125.json).

## Pilot timing analysis

Use the verified blind v1 and assisted v3 packages as separate projects for a
small human usability pilot. Use the same review instructions across arms and
record interface problems and any interruptions separately. Export full Label
Studio JSON with task data, metadata and annotations when the pilot ends.
Label Studio records annotation time in seconds in
[`lead_time`](https://labelstud.io/guide/export#Relevant-JSON-property-descriptions).

Portable reviewer bundles are available under `pilot-reviewer-handoff/`
in the private evidence root. Each ZIP contains the original task JSON,
labeling configuration, source images, attribution and setup instructions.
The assisted archive also includes its search crops. Use the original
operator package when summarizing returned exports. The blind decision seal
and operator source manifests remain in the private directories. The ZIP
file hashes are in [the handoff summary](../benchmarks/nz-pilot-handoff-20261125.json).

```sh
uv run python -m weedz.annotation.pilot_effort \
  --blind-package /private/path/to/blind-v1 \
  --blind-export /private/path/to/blind-export.json \
  --assisted-package /private/path/to/assisted-v3 \
  --assisted-export /private/path/to/assisted-export.json \
  --output /private/path/to/pilot-effort.json
```

The report binds each export to the original task payloads and keeps distinct
counts for submitted, cancelled, untimed and unsure outcomes. A missing or zero
lead time counts as unmeasured. Task coverage uses the package size because
exports can omit untouched tasks. Ground-truth rows and drafts do not contribute
to timing. Keep the report with the reviewer notes. The two arms use different
images, which limits what a timing difference can establish. The report
describes submissions and does not adjudicate biological observations.

A loopback-only Label Studio 1.23.2 smoke test imported blind v1 and assisted v2
into separate temporary projects. It verified HTTP-served bytes for all 35
originals and all 19 assisted crops. A headless browser opened one task in
each arm and clicked a watchlist choice. The assisted search preview loaded
only in the assisted project. Two explicitly synthetic submissions were
exported and summarized through the command above, recovering their 12.5
second test values. The original bundles still contain no submitted labels.
The smoke test supplies technical workflow evidence. Human usability findings
and review effort remain unmeasured.

The [review handoff](nz-pilot-handoff.md) lists the exact packages for
reviewers and the commands for separate handheld and camera exports.

## Remaining work and next experiment

1. Acquire additional independent, class-balanced crop sessions before pursuing
   another seedling classifier. The first fixed prototype experiment failed
   its improvement gate.
2. Verify candidate quality on real incidental photos with human outcomes
   before selecting a revised operating point. The controlled multiscale
   comparison gave similar recovery at about twice the runtime.
3. Add usable PlantCLEF plot labels if available. The bounded Danish replay
   leaves full publisher test-split performance and NZ transfer unmeasured.
4. Extend the verified pilot packages with the missing assisted strata where
   evidence supports them. Recheck all independence and source bindings.
5. Run a small human usability pilot to measure actual effort. Specialist NZ
   verification remains necessary before claims about background discovery.

## Separate NZ botanical discovery pool

Screen plant-subject photographs near the same 12 public target neighborhoods
used for the animal-subject habitat search. Plant-subject scenes may offer
more visible habitat, especially when the foreground is a different plant.
Use the first 100 ID-descending research observations from 2023–2025 within
two kilometres of each anchor along each coordinate axis. Keep CC0 or CC BY
originals with public coordinates and declared accuracy of at most 100 m.
Exclude observations in all three target genera and records identified only
above genus. This keeps the source identification distinct from the three
target hints. Geography and subject labels are sampling cues for background
discovery.

Use the existing seeded acquisition order and admit up to three originals per
neighborhood, considering at most 90 eligible rows per neighborhood. Apply the
prior-pool observer, observation, pixel and encounter checks, plus the same
checks within the discovery pool. Record source receipts before inference.
Keep the blind and assisted pilot packages fixed during screening. Report
fitness for a new assisted stratum against the frozen threshold and agreement
rule. Incidental presence remains unverified until reviewed. This enriched
sample cannot estimate incidental prevalence.

The 12 queries returned 820 records before source filtering. Of 425 unique
eligible records, 420 were excluded by the prior or within-pool observation
and observer rules. Five originals from three neighborhoods passed the
checks. All five were below the frozen threshold. The highest tile score
was 0.00177 against a floor of 0.13647. This source yielded no new priority
stratum. The pilot package and seal hashes still match their release receipts.
[Botanical pool evidence](../benchmarks/nz-botanical-discovery-20261125.json)

## NZ trail-camera discovery protocol

Use the [public LILA NZ trail-camera release](https://lila.science/datasets/nz-trailcams)
as a separate source. The release supplies animal tags and camera identifiers.
It has no plant labels or usable coordinates for these frames. Compare plant
hints on the cached pixels and retain the site as the sampling unit.

Exclude the camera sites of the 12 previously inspected images from the
[source assessment](../benchmarks/nz-trailcams-assessment.json). Select 12 projects
with at least four remaining midday sites, four sites per project and one
frame per site, using SHA-256 order with the fixed `weedz-lila-site-v1` seed
and separate project, site and frame keys. Midday means camera timestamp
09:00 to before 16:00. No replacement is made for a failed media download
or duplicate. Verify source dimensions, bytes, distinct sites, and exact and
perceptual uniqueness against the prior pilot pools and within the set. Keep
mono or infrared images visible in the audit if the timestamps select them.
Run the unchanged NZ policy and report all outcomes separately from the
handheld NZ pilot. Any candidate must be reviewed before a plant label or
occurrence can be claimed.

All 48 source originals were acquired and passed the site, pixel and
perceptual checks. The frozen policy classified 47 as below-floor uncertain
and one as a model disagreement. The strongest tile scored 0.39786 for
*Cortaderia selloana* against the 0.13647 floor. Whole-photo PlantCLEF
favored the same watchlist taxon, while the broad NZ model ranked song
thrush first. The search crop contains grasslike foliage. It lacks enough
reviewed evidence to assign a plant name. This is a real example of the
agreement gate deferring a high-scoring background hint. Its correctness
and the other frames' plant labels remain unmeasured.

The separate one-task archive contains its full 2592×1944 source image,
an exact source-pixel search crop, and the unverified hint. The archive
passed checksum and task-payload verification. The case stays outside both
handheld pilot arms and their analysis. No camera photo met the complete
priority rule. [Camera evidence and bundle hashes](../benchmarks/nz-trailcam-discovery-20261125.json)

## Frozen classifier adaptation experiment

Evaluate a session-balanced nearest-centroid classifier on the five reserved
CropAndWeed sessions. Fit prototypes from the eight development sessions
using frozen PlantCLEF embeddings of tight source box crops. Include a class
only if two or more development sessions carry it. Normalize crop embeddings,
average crops within each session and class, normalize those means, then
average the session means per class and normalize the resulting prototypes.
This gives each eligible session equal weight within a class.

Use the same candidate vocabulary for both the adapted classifier and the
unmodified PlantCLEF head. Report coverage of the reserved labels by the
development vocabulary, top-one accuracy on covered boxes, and per-class
results. Keep out-of-vocabulary cases visible and report correct assignments
over all reserved boxes. A ten-percentage-point increase in covered-box
top-one accuracy is the development gate. Inference is limited to one tight
crop per frozen source box and at most six crops per image. Hold crop policy
and model weights fixed for this comparison.

The reserve has 28 boxes, of which 27 are covered by the development vocabulary.
The original restricted head recovered 20/27 and the prototypes recovered
19/27. Prototypes lost one correct thistle assignment and tied on goosefoot.
The covered-box change was −3.7 percentage points and missed the frozen
improvement gate. This paired comparison used known source boxes and a small
training vocabulary. It does not measure localization or identification of
unseen taxa.

## XP4 validation cutoffs and fixed test replay

The release includes a quick-validation configuration for 16 publisher
frames. Replaying it computes the first maximum of Youden's J on validation
and applies the upstream strict score cutoff. One positive per taxon lies
exactly on its validation cutoff. The rule retained 7/13 validation positive
pairs. An inclusive comparison retained 13/13 and serves here only to
illustrate the difference at the boundary.

The frozen quick cutoffs recovered 6/12 labeled positives on the separate
14-frame test set and 22/32 on the 16-frame multilabel smoke set. They selected
8 and 27 pairs, respectively. The extra selections disagree with the supplied
row labels and do not establish false alarms for incompletely labeled scenes.

The full CPU FP32 reconstruction scored all 2,160 publisher validation
feature tensors. All 16 shared quick-validation tensors matched by checksum
and yielded identical scores. The first maximum of Youden's J and the strict
cutoff recovered 1,005/1,181 validation positives. Exactly one positive per
taxon landed on its cutoff and was excluded by the strict comparison.

The upstream XP4 configuration uses the published `xp4_val` threshold table
and CUDA autocast. Replaying those released settings on the cached publisher
features recovered the same number of annotated positives as the CPU
reconstruction in each test cohort. The largest cutoff difference was 0.00437.
No cutoff was fit on a test frame. Test tensor checksums and source filenames
were distinct from those used for validation.

| Test cohort | Recovered positive pairs, CPU / released | Selected pairs, CPU / released | No-species controls with a suggestion, CPU / released |
| --- | ---: | ---: | ---: |
| Publisher quick test, 14 frames | 10/12 both | 14 / 15 | 0/2 both |
| Multilabel sample, 16 frames | 30/32 both | 41 / 42 | — |
| Distance-screened reserve, 25 frames | 15/21 both | 26 / 26 | 2/4 both |

The published operating point uses six Danish target groups. These counts
apply to the sampled source frames and their supplied labels. Full paper test
metrics, exhaustively verified negatives and NZ transfer remain unmeasured.
The NZ pilot policy stays frozen.

Run `evaluate_full_thresholds.py` from the private `roadside-source/`
evidence directory with the closed calibration receipts in place. Run
`evaluate_released_thresholds.py` with CUDA-enabled PyTorch and the cached
tensors. Use a fresh output directory populated with the corresponding inputs
for a rerun. The reports bind source memberships, settings, producer scripts,
and score and tensor receipts. See the
[aggregate results and hashes](../benchmarks/xp4-full-validation-20261125.json).

## Bounded multiscale incidental screening

The development comparison added a second pass of 16 child tiles to the
fixed 4×4 grid by subdividing the four highest-scoring parent tiles. The
winner was the highest watchlist score across both scales. Geometry was
scored using a minimum 25% coverage of the planted patch and 20% coverage
of the selected tile. Both methods checked local EfficientNet agreement at
the frozen subject-derived score floor.

| Fixture | 4×4 correct target and overlap | Two-scale correct target and overlap | Above-floor agreements with correct overlap, 4×4 / two-scale |
| --- | ---: | ---: | ---: |
| 24 planted full-tile crops | 19 | 18 | 4 / 6 |
| 24 planted quarter-area crops | 18 | 17 | 1 / 1 |

On the 36 intact incidental photos, neither method produced an above-floor
local agreement. The largest score rose from 0.0380 to 0.0585. Mean tile
processing time increased from 0.189 to 0.367 seconds per photo. The smaller
crops did not earn a policy change. Human review of the uncertain cases is
the next source of scene-level evidence.

These experiments and the local review checks are indexed in the
[follow-up summary](../benchmarks/nz-readiness-followup-20261125.json).

## Whole-photo and local agreement on labeled roadside scenes

Use the 206-image Danish publisher multilabel frame to find a fresh paired
proxy for background discovery. Exclude filenames or frames within 100 m
of publisher training, publisher validation, the inspected smoke sets and
the previously scored 25-frame reserve. Keep the remaining multilabel
frames, audit proximity to the publisher mono-label test partition, and
screen for exact decoded copies and dHash distance at most four against
the 71 previously acquired source pixels. Within the new cohort collapse
the same types of pixel duplicates in seeded filename order. Keep all
remaining labels, including frames with several positive targets. This
selection is independent of model scores. Run the 25 already scored
monolabel frames as a separate comparison.

Freeze the six PlantCLEF target groups and their pinned native-model
synonyms. Rank one maximum-scoring 4×4 tile target per image using the
full softmax denominator. Compare the original proposal, whole-photo
PlantCLEF agreement alone, and native-model agreement on the full photo
or on the winning tile. Run each native agreement rule both with and
without the whole-photo PlantCLEF check. Run at a
ceiling of one suggestion per image. Apply the same checked tile-score
floor to every rule, the median maximum tile score among the 13 explicitly
positive quick validation frames. Also report the floor-free comparison
to separate the gate from threshold coverage. Keep both native branches
to one view per image, and time them separately.

Join source positives after saving scores. Report recovery of annotated
pairs, losses and gains on the same proposals, accepted suggestions without
an explicit source label, and calls on the four monolabel no-species
controls. No unlabeled target contributes a false-positive count. The
Danish scene labels have no within-image plant locations. This is a proxy
for gate behavior on real mixed vegetation, and its thresholds and error
rates do not transfer automatically to the NZ pilot. Keep the NZ policy
and reviewer packages fixed.

All 15 newly scored frames passed the pixel checks. They carry 30
publisher positives, two per image. The 100 m grouping resolves just four
spatial components with 10, 2, 2 and 1 frames. Every frame is within 100 m of
an image in the publisher's monolabel test partition. This proxy separates
the fresh pixels from the project's inspected images and from publisher
training and validation by the filename-coordinate rule. It has correlated
scenes and unknown classifier pretraining exposure.

At the 0.00545144 validation floor, the results were:

| Rule | Mixed positives / suggestions | Monolabel reserve positives / suggestions |
| --- | ---: | ---: |
| Tile score only | 5 / 6 | 13 / 13 |
| Tile and whole-photo PlantCLEF agreement | 2 / 3 | 7 / 7 |
| Tile and whole-photo native-model agreement | 0 / 0 | 2 / 2 |
| Tile and winning-crop native-model agreement | 0 / 0 | 0 / 0 |
| Both whole-photo checks | 0 / 0 | 1 / 1 |
| Whole-photo PlantCLEF and winning-crop native-model agreement | 0 / 0 | 0 / 0 |

The one-suggestion budget caps mixed recovery at 15 of 30 positives. Crossing
the floor without an agreement check recovered five. Removing the floor
raised tile-only recovery to ten, while both native view rules still returned
zero on the mixed scenes. The four monolabel no-species controls received no
suggestions from any rule at the fixed floor. The small control set leaves
precision unresolved. Tile-plus-whole PlantCLEF processed 17 views in about
0.33 seconds per frame. The single native whole and tile checks averaged
0.046–0.049 and 0.012–0.013 seconds per frame including preprocessing.

The NZ model suppresses known Danish positives even on localized crops. Its
vocabulary contains a member of every declared group and omits *Solidago
gigantea*. None of the mixed images had an explicit *Solidago* label. The
results explain a failure mode of the veto on this external proxy. A change
to the NZ priority rule requires assessable local outcomes.

A post hoc native rank audit of the five labeled, above-floor tile wins
found zero in the full-vocabulary top five on either view. If restricted to
the six target groups, the native head ranked the proposed target first on
one of those five tiles and zero full photos. Broad vocabulary competition
accounts for only a small part of the observed disagreement. Three of the
five recoveries came from the largest spatial component and two from one
other component. [Evaluation receipts and rank audit](../benchmarks/roadside-agreement-20261125.json)

## Fresh NZ subject and lookalike agreement controls

Compare the frozen agreement policy with variants on NZ photos outside the
examined 2024–2025 source-subject cohort. Query the three watchlist subjects,
two native lookalikes (*Austroderia fulvida*, *Clematis paniculata*) and broom.
Use the first 100 descending observation IDs in January–June and July–October
2026 for each exact taxon. Require research grade, an upload in 2026, CC0 or
CC BY observation and photo rights, public coordinates and reported accuracy
of at most 100 m. Take at most eight originals per taxon using a fixed hash
order. Rotate through taxa to share the eligible observer pool. Keep one
photo per observation and observer, and apply the existing pixel, near-copy
and encounter exclusions against the earlier pools and within this set.
Freeze the manifest before inference. Source identifications describe the
photographed subject only.

Use the original three-target PlantCLEF 4×4 tile scorer, its fixed score
floor and one suggestion per image. Compare score-only triage, the frozen
whole-photo conjunction, agreement with the native model on the winning
tile alone, and replacing just the native whole-photo check with the
winning-tile check. Report recoveries of photographed targets, photo-level
lookalike suggestions, and paired differences. Treat at least three new
subject recoveries and zero additional suggestions across the lookalike and
broom controls as the follow-up gate. Require at least four independent
photos in each of the six strata to apply the gate. Report shortfalls
explicitly. Passing would justify a separate incidental comparison. NZ
pilot settings and existing reviewer tasks remain frozen.

Replay the same four decisions separately on the existing 300 development
controls. Reuse the cached 17-view PlantCLEF scores and cached whole-photo
native predictions. Run one new native inference on the original winning
tile of each above-floor photo. Below-floor photos contribute no suggestion
under any rule, so they need no new inference. Keep the fresh and development
denominators separate. The development controls can explain trade-offs when
fresh strata are sparse and can motivate future validation.

The 2026 source frame returned 206 eligible observations. The observer or
observation exclusion removed 197, including all 101 for the three watchlist
taxa. The remaining originals comprised five native clematis, two toetoe and
two broom subjects. All nine passed source and pixel rechecks. The score-only
rule suggested a watchlist species on two photos. The original agreement
rule and both winning-tile variants withheld both suggestions. The source
labels identify the photographed lookalike or broom. Plants elsewhere in the
same image remain unassessed. Since there was no target stratum and two
control strata fell below four images, the advancement gate was unevaluable.

On the 300 previously inspected subjects, the replay reproduced the existing
69 recoveries and zero suggestions on comparison subjects. The target and
comparison columns each contain 150 photos.

| Rule | Watchlist subject recoveries | Suggestions on lookalike or broom photos |
| --- | ---: | ---: |
| Tile score only | 75 | 13 |
| Frozen whole-photo agreement | 69 | 0 |
| Native winning-tile agreement | 60 | 2 |
| Whole-photo PlantCLEF and native winning-tile agreement | 60 | 2 |

Both tile agreement variants recovered five targets the original rule missed
and lost 14 it had recovered. The five net losses among pampas subjects and
four among gorse subjects explain the total decline. The variants also added
one suggestion each on a native clematis and a toetoe photo. New inference
was limited to 88 above-floor crops and averaged 0.013 seconds per crop for
native preprocessing and forward inference. These development results favor
keeping the original agreement as the pilot baseline. The fresh cohort can
only check how often the rules generate review prompts on comparison
photos. Local incidental recall still needs human evidence.
[Frozen inputs and paired result counts](../benchmarks/nz-fresh-agreement-20261125.json)

## Score floor replay with both NZ classifiers

Compare the frozen score floor, no floor, a fitted shared floor and fitted
taxon-specific floors. Require both whole-photo agreement checks for every
suggestion. Reuse the cached PlantCLEF and native predictions. The proposal
budget remains one per image. This tests a less restrictive review threshold
without weakening the agreement condition.

Group the 300 already inspected subject controls by observer, exact or
perceptual image copies and public location proximity. Connect any two
photos within 100 m plus their reported location uncertainties when both
uncertainties are at most 100 m. Keep unsupported locations visible in the
audit. Assign whole groups to five fixed stratified folds before loading
model outputs. Fit each floor on four folds and report paired results on
the omitted fold. Consider only floors at or below the frozen value. Pick
the highest floor among those with maximum photographed-target recovery
and no newly prompted comparison-subject photos. Comparison subjects
include both native lookalikes and broom. In the taxon-specific variant,
retain the original floor for a group with no additional recoveries.

A variant needs at least three additional pooled out-of-fold subject
recoveries and zero new comparison-subject prompts to advance. Fit the
advancing rule once on all 300 development controls and replay it on the
nine 2026 comparison photos and the separately screened, unreviewed NZ
incidental pools. Require zero new prompts on the 2026 photos. Report new
incidental suggestions as candidates for review. Photographed subject
labels and cached, previously used model outputs limit the claims to
development evidence. Keep the pilot rule and sealed blind decisions fixed.

As a separate diagnostic, count how many unreviewed incidental photos would
still be withheld if scoring used agreement alone. Use the already acquired
89 incidental photos from the handheld, habitat, botanical and camera pools.
Keep the 48 camera frames separate from the 41 handheld frames. Do not apply
the fitted floors to these pools unless their advancement gate passes. For
the floor-free count, report each agreement check separately and the joint
count. Any joint-agreement case below the pilot floor remains an exploratory
review candidate, with no new priority verdict. The blind arm is outside
this diagnostic.

The 300 development photos formed 203 groups and five folds of 59 to 61
photos. Of those photos, 182 had public coordinates and usable accuracy.
Observer and location groups stayed together during fitting and evaluation.
The remaining photos could only be grouped by observer and image evidence.

| Rule | Recovered watchlist subjects, out of 150 | New comparison prompts, out of 150 |
| --- | ---: | ---: |
| Frozen floor | 69 | 0 |
| No floor, agreement still required | 124 | 4 |
| Fitted shared floor | 122 | 1 |
| Fitted taxon-specific floors | 119 | 1 |

The shared floor gained recoveries in all five folds, including 33 more
gorse photos across the folds. The fitted rules both introduced a pampas
suggestion on the same held-out toetoe-subject photo in one fold. It counts
as additional reviewer work. The photo's background remains unassessed.
Neither variant met the predeclared zero-new-prompt gate.

The floor-free incidental diagnostic showed whole-photo PlantCLEF agreement
on 28/41 handheld photos and 29/48 trail-camera frames. Native whole-photo
agreement was zero in both sets, so all 89 remained withheld even without a
floor. No additional review candidates came from this rule. Threshold tuning
addresses misses on photographed subjects, while incidental recovery in
these pools is limited by the native whole-photo check. The pilot baseline
and sealed blind hashes were verified after both runs.
[Fold results and source receipts](../benchmarks/nz-score-floor-20261125.json)

## Local BioCLIP verification for an exploratory NZ queue

Use the pinned BioCLIP 2 model to check the winning PlantCLEF tile, with
one new image view per photo. Keep the existing fixed watchlist, native
lookalikes and scene prompts. Fill all prompts identically for every image
and omit the photographed subject. Use the original tile bounds and square
padding. Calculate the tile's BioCLIP target-minus-best-comparison cosine
margin. Ask for a positive margin and agreement with PlantCLEF's tile
taxon, independent of whole-photo classifiers. The review budget remains
at most one suggestion per photo.

Compare the frozen tile score floor and 0.01173484418541193, the shared
development floor found in four of the five earlier grouped folds. Fixed
floor tests use the 300 previously inspected controls and the separate nine
2026 comparison photos. Run both floors without further fitting. For an
exploratory queue, require at least 72 photographed-target recoveries out
of 150, at most three new prompts among the 150 comparison subjects, and
zero on the nine fresh photos. Score-only and existing-policy counts are
comparators. This small prompt allowance is for review workload. It does
not establish scene precision or change pilot priority. Evaluate the 89
incidental photos only for a rule that passes. Any admitted candidate stays
outside both main pilot arms, with a full source image and a search crop for
independent human review.

If the lower fixed floor misses the prompt budget, run one follow-up on
the saved scores. Fit a shared positive BioCLIP margin using the earlier
five observer and location folds. At each fit, allow at most two prompts
on the training comparison subjects. Choose the highest margin that
maximizes known-target recoveries with that limit. Report omitted-fold
results and hold the same pooled development gate. If the fitted variant
passes, refit once with the same two-prompt budget on all 300 development
controls and verify zero prompts on the nine already screened fresh photos
before applying it to the incidental pools. This follow-up is exploratory
because the fixed-margin comparison already exposed aggregate results.

Both fixed-margin BioCLIP rules missed the review gate. The 309 control
photos required 190 crops at or above the lower score floor. Inference and
source verification took 12.55 seconds after loading the encoder.

| Rule | Known targets recovered, out of 150 | Comparison prompts, out of 150 | Fresh comparison prompts, out of 9 |
| --- | ---: | ---: | ---: |
| Frozen whole-photo policy | 69 | 0 | 0 |
| Tile score alone, frozen floor | 75 | 13 | 2 |
| Tile score alone, lower floor | 141 | 45 | 3 |
| Local BioCLIP, frozen floor, positive margin | 71 | 4 | 0 |
| Local BioCLIP, lower floor, positive margin | 133 | 9 | 1 |

The stronger fitted margin recovered **105/150** photographed targets in
the omitted folds and added three comparison prompts, meeting the exploratory
gate. The final refit used a 0.02411 cosine margin, recovered 95 photographed
targets with two comparison prompts on the development fit, and prompted on
zero of the nine fresh comparison photos. These are the same previously
inspected subject controls and a small fresh comparison set.

Of the 89 incidental photos, two handheld and ten camera frames reached the
lower tile-score floor. Applying the fitted margin retained one handheld
gorse suggestion and zero camera suggestions. The gorse photo already sits
in assisted v3, so no additional reviewer task was created. Its identity
remains unverified. This crop-local test produced an exploratory cue on a
photo withheld by the whole-photo policy. The pilot tasks, original priority
rule and sealed blind scores all stayed fixed.
[Control, margin and incidental receipts](../benchmarks/nz-local-bioclip-20261125.json)

## Camera-project transfer of the crop-local cue

Freeze a second LILA camera sample before running the crop-local verifier.
Exclude all projects represented in the first 48-camera experiment or the
12 photos in the original visual audit. Apply the earlier midday timestamp
rule. Choose up to 16 remaining projects with at least eight eligible camera
sites, eight sites per project and one image per site. Use the fixed
`weedz-lila-transfer-v1` seed with separate project, site and frame keys.
Test decoded pixel and perceptual uniqueness against the prior pools,
including the 48 tested cameras, and within the new pool. Preserve source
rights and native pixels, and keep failed downloads out with a recorded
reason. Do not replace them.

Compare the pilot baseline with the fixed crop-local suggestion at the
0.01173484418541193 PlantCLEF floor and 0.02411 BioCLIP margin. Preserve
the camera domain separately. Report the number of sites screened and
suggestions withheld or retained. For a separate supplemental review
bundle, retain up to six exploratory suggestions at most one per project.
Select by descending BioCLIP margin, then PlantCLEF score and source ID.
Full images and exact search tiles remain unreviewed. No supplemental case
enters the handheld pilot or the blind outcome analysis.

Fourteen projects met the eight-site minimum after excluding 20 exposed
projects. All 112 selected sites supplied an original, with no exact or
near-pixel duplicates admitted. Acquisition resumed from 77 saved originals
after widening the loader to accept a nested publisher image path. The
source selection stayed fixed.

The pilot rule returned zero priority suggestions, one model disagreement
and 111 low-score outcomes. Eleven tiles reached the local score floor.
BioCLIP produced two matching margins above 0.02411, on frames from different
projects. One suggests gorse in a color frame and one suggests old man's
beard in a monochrome frame. The crops contain visible vegetation and match
their source geometry. Both identities remain unreviewed.

The separate two-task archive uses full source images, exact search crops
and standard watchlist choices, including uncertainty. The cases exercise
the crop-local rule on fresh camera projects. They cannot establish plant
presence, recall or precision. The pilot packages and sealed hashes still
match their receipts. [Camera transfer and packet evidence](../benchmarks/nz-camera-transfer-20261125.json)

The camera packet has its own operator-side `frozen-cue-targets.json`.
It binds the original cue taxa to the task IDs, image hashes, package and
score receipts. Import the camera tasks into a separate review project.
Use the project's full Label Studio JSON export with task data and metadata.

```sh
uv run python -m weedz.annotation.pilot_cue_outcomes \
  --package /private/path/to/exploratory-package-v1 \
  --export /private/path/to/camera-export.json \
  --cue-receipt /private/path/to/frozen-cue-targets.json \
  --output /private/path/to/camera-review-report.json
```

The report records effort and counts cue support only after agreeing
submissions from at least two reviewer accounts. Uncertain or unresolved
cases remain unassessed. Keep the camera report outside the handheld
pilot's recall and timing analysis. The disposable local project verified
both task payloads and all four image files. Both tasks rendered in a
browser with clickable watchlist choices. The full JSON export produced
two unreviewed cases and zero submissions.

## Instance localization errors and proposal windows

A replay of the cached PhenoBench development masks reproduced all 535 SAM3
and 452 Weeds Are Weird matches across the same 853 source instances.
One-to-one matching still uses mask IoU ≥0.5. For this diagnostic, a duplicate
is an unmatched proposal with sufficient IoU to an already matched instance.
A fragment case has no sufficient individual proposal. It needs at least two
masks that each cover ≥10% of that instance and place ≥80% of their pixels
inside it. Their union must cover ≥50% and add ≥20 percentage points over the
best piece. A merge covers ≥20% of each of at least two source instances.

| Proposer, saved proposal order | Cap per image | Actual proposals | Matched instances | Repeat proposals | Fragmented instances | Merged proposals |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| SAM3 | 16 | 658 | 527 | 5 | 0 | 89 |
| SAM3 | all | 676 | 535 | 8 | 0 | 98 |
| Weeds Are Weird | 16 | 837 | 181 | 8 | 40 | 18 |
| Weeds Are Weird | all | 2,412 | 452 | 81 | 69 | 100 |

At the uncapped setting, SAM3 recovered 127/344 source instances below
512 pixels and 277/337 instances at 2,048 pixels or larger. Weeds Are Weird
recovered 85/344 and 249/337. Its fragment criterion was mostly met by crops
(68 of 69), consistent with pieces of large plants being proposed separately.
Ranks across the two methods use their own saved proposal order, so truncation
does not establish an equal-compute ranking. The counts describe morphology
on the source mask grid. Unmatched regions remain unassessed.

On a fixed 16-image development subset, the whole-image control was compared
with four new overlapping SAM3 windows at the same 16-proposal cap. Scores
were sorted globally for the first windowed comparison. The follow-up retained
up to 12 whole-image proposals and suppressed window candidates with IoU ≥0.5
against a retained proposal. It reused the same window predictions.

| Selection | Matches among 207 source instances | Matches among 87 under 512 pixels | Repeat proposals |
| --- | ---: | ---: | ---: |
| Whole image | 133 | 36 | 1 |
| Global rank across whole image and windows | 114 | 38 | 101 |
| Whole-image reservation with window suppression | 134 | 37 | 2 |

Global score ordering allowed repeats to displace usable masks. Reserving
whole-image candidates and suppressing overlaps recovered that loss. The
follow-up gained six matches and lost five relative to the whole-image control.
Four extra model input frames cost an average of 0.85 seconds per source photo,
including window preparation and proposal handling. The small net gain does not
justify switching the frozen NZ workflow. The development-only results are
indexed in [the mask localization summary](../benchmarks/phenobench-mask-errors-20261125.json).

## Final weed-presence decisions on PhenoBench

The saved Weeds Are Weird semantic decisions also allow a coarse image-level
check where the source provides a pixel label. Treat any source weed or
partial-weed pixel as the positive label. Count one suggested review per
frame when the model marks at least the declared number of weed pixels.

| Minimum predicted weed pixels | Annotated positives recovered | Candidate frames | Annotated-negative frames suggested |
| --- | ---: | ---: | ---: |
| 1 | 58/61 | 59 | 1/3 |
| 64 | 57/61 | 58 | 1/3 |
| 512 | 52/61 | 53 | 1/3 |

The largest fixed mask-area floor dropped six calls and lost six annotated
positives relative to the smallest floor. The one suggestion on an
annotated-negative frame persisted. The three annotated-negative frames
provide a denominator for this development fixture only. These are weed
category labels in crop frames. Do not extrapolate them to watchlist species,
real NZ false alarms or site-level absence.
[Presence decision evidence](../benchmarks/phenobench-weed-presence-20261125.json).

## Balanced crop adaptation protocol

Use 32 fixed 16 MiB ranges spread across the four CropAndWeed image
archives. Admit complete JPEG records with verified source boxes and
exclude sessions from the earlier adaptation experiment. Within these
ranges, admit a class only when seven distinct sessions can be assigned
without reuse across classes or splits. Select one source box per session,
with three development, two validation and two reserve sessions per class.
Record the classes skipped by this rule and keep the sample scope explicit.

Freeze tight source box crops and the existing PlantCLEF backbone for both
models. Fit L2-regularized multinomial logistic regression on normalized
development embeddings. Test C values 0.1, 1 and 10 on validation. Select the
highest macro top-one score with smaller C breaking ties. Compare the
selected head with the original head restricted to the same classes on a
single reserve pass. Fit and select using development and validation only.
The pilot comparison requires at least three eligible classes and a
ten-percentage-point macro top-one gain on the reserve to merit a larger
evaluation. Keep inference at one crop per image and report coverage,
per-species results and paired gains or losses.

The publisher ranges yielded 343 complete JPEGs. Of those, 109 had
usable boxes under the declared taxonomy. Three classes met the independent
session quota: white goosefoot, creeping thistle and field milk thistle.
Five additional classes had mapped boxes but insufficient unassigned sessions,
and two had no usable boxes in the downloaded ranges. The closed manifest
contains 21 photos from 21 sessions, distributed as nine development,
six validation and six reserve images. The earlier benchmark's sessions and
decoded image identities were excluded. These are recording-session groups.
Site independence remains unaudited.

Validation chose C=0.1. On the six reserve boxes, the original restricted
head and the fitted head each recovered 4/6. The fitted head gained a milk
thistle match and lost a goosefoot match. Its zero-point macro change did
not meet the frozen improvement gate. The result does not support carrying
this head into the NZ workflow. The selected range receipts, split and
comparison are indexed in
[the balanced crop benchmark](../benchmarks/cropandweed-balanced-source-20261125.json).
