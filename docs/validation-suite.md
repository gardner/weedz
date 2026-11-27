# Validation suite

Each part of the pipeline is checked against a public dataset that people
labelled, using the pipeline's own code. Every check can be rerun with one
command, so a change to the vegetation screen, the prompts or a classifier can
be measured against the same labels as before. The plan and the reasons for each
dataset choice are in [#183](https://github.com/gardner/weedz/issues/183).

```sh
uv run main.py validate list
uv run main.py validate run <check> --data-root ~/src/weedz-validation-data \
  --device cuda:0 --output benchmarks/validation
uv run main.py validate scorecard benchmarks/validation/*.json \
  --output benchmarks/validation/scorecard.json --markdown benchmarks/validation/scorecard.md
```

Add `--limit 50` and change `--output` to a separate directory for a smoke run.

## Reading a result

Every rate has a 95% Wilson interval. A gate with a target (for example recall
≥ 95%) passes only when the **whole interval** is at or above it, and a ceiling
(for example false alarms ≤ 5%) passes only when the whole interval is at or
below it. A small sample therefore can't pass a strict gate by luck: 23 of 24 is
95.8%, but its interval starts at 79.8%, so it fails a 95% gate.

`unmeasured` means there were no labelled items for that metric. It is not zero.

Proposal, species-identification and whole-photo headline pass marks are
**regression floors learned on development data**, not production quality
targets. For development successes `s_d/n_d`, take the 95% Wilson interval
`[L_d, U_d]`. At the development rate, compute the expected held-out interval
`wilson(round((s_d/n_d) * n_h), n_h)` and its half-width `h`. A higher-is-better
metric has target `max(0, L_d - h)`; a lower-is-better metric has ceiling
`min(1, U_d + h)`. Only the held-out denominator enters this calculation, never
its successes. The whole held-out interval must still clear the gate. Missing
development or held-out trials leave it ungated with a reason in `limits`.
Receipts record each development count as `gate_development_<metric> = "s/n"`.
Small cohorts can produce permissive, even zero, floors; passing says held-out
performance is consistent with development, not that the pipeline is ready.
The existing presence and target-false-alarm gates retain their fixed targets.

Use publisher development/test splits when available: PlantCLEF `val`/`test`,
CWFID `train`/`test` excluding overlap 028, and Danish roadside `val`/`test`
positive labels. Otherwise `split_of(source_id)` freezes development and
held-out halves. Pooled `all` rows remain diagnostic where they mix the halves;
gates apply only to held-out strata. Prior inspection and training overlap
remain limits on independence.

The scorecard starts with stage check/gate counts and headline gates, including
development-derived `held-out` and publisher `test` strata, then the full table.
A stage without gates has no pass/fail claim.

## Comparing a change

Compare the committed baseline with rerun result JSON files or a rerun scorecard:

```sh
uv run main.py validate compare benchmarks/validation/scorecard.json rerun/*.json \
  --markdown comparison.md
```

Metrics match by check, name and stratum. Deltas are rerun minus baseline in
percentage points, with 95% [Newcombe method 10](https://doi.org/10.1002/(SICI)1097-0258(19980430)17:8%3C873::AID-SIM779%3E3.0.CO;2-I) intervals combining Wilson intervals without continuity correction.
An interval excluding zero means **better** or **worse**; otherwise **no clear change**.
Targets mean higher is better; ceilings mean lower. Otherwise explicit direction
wins, then the name: false_alarm, wrong_subject, confusion, worst_species and
nonvegetation are lower-is-better (checked first); recall, recovery, coverage,
covered, identified, top1, top5 and _at5 are higher-is-better. A test requires
every committed metric to have a direction, so name new metrics accordingly.
A metric with no known direction is **changed** when its interval excludes 0, without a better/worse verdict. Missing metrics are **new**
or **removed**; an empty side is **unmeasured**. Baseline gates remain in force.

The console shows 20 rows, worst first; markdown includes every row. Changed input
hashes, cohorts (configuration keys that decide which items are scored: limits,
selection and split rules, target, lookalike and class lists, salts, stratum definitions, per-split sampling budgets and image counts, such as a
`--limit` smoke run's `smoke_limit` or PhenoBench's `selection`), datasets or splits are
flagged as **not like-for-like**, with the changed keys listed. Measured values kept
in configuration, such as timings, fitted thresholds and versions, are not compared. A gated regression
exits **1** even then, so compare full runs, not smoke runs. So does a gate that
passed in the baseline but fails in the rerun when held to the baseline's gate, even
without a clear change (990/1000 clears a 95% target; 99/100 doesn't), and a gate that
was measured in the baseline but is unmeasured or missing in a rerun check (for example a
target that became unreachable). Otherwise it exits **0**, including new metrics,
checks a partial rerun skipped, and metrics unmeasured in both runs. Pass one result file or scorecard per check. This does not certify completeness.

For a worked example, compare the committed scorecard with itself:

```sh
uv run main.py validate compare benchmarks/validation/scorecard.json \
  benchmarks/validation/scorecard.json
```

This exits 0 across 1,030 metrics: **894 no clear change** and 136 unmeasured.
Metrics unmeasured in both runs are listed last.
SegFormer's Open Images recall is 1,433/1,500 each: difference 0.0 points (95% CI −1.5 to +1.5).

Runs on the same images are **paired**, but results don't keep per-image outcomes,
so the interval treats them as independent. That is usually wider than a paired
interval, but not always: when outcomes are negatively correlated it can be too
narrow, so read a borderline **worse** with care.
Intervals are per metric without multiplicity adjustment; no clear change does not prove equivalence.

## Adding a check

One module per dataset, in `src/weedz/validation/<dataset>.py`:

1. **Read the public labels into items.** Each item has a stable source ID, the
   human label the stage needs, and a stratum where the source supports one,
   such as `small` / `medium` / `large` vegetation area. Keep the source's label
   meaning; don't invent negatives the labels don't support.
2. **Freeze the split.** Use the publisher's split where there is one. Within
   it, assign items to `development` or `held-out` by a stable hash of the
   source ID (`weedz.validation.splits.split_of`), so the same item always
   lands in the same place. Set thresholds and pass marks on `development`
   only, and report `held-out`. A check whose rules are all frozen, with
   nothing tuned on the dataset, scores the whole split and reports
   `validation`.
3. **Run the real pipeline code** (`VegetationScreener`, `Sam3Image`,
   `PlantClassifier`, `BioClipClassifier`, `aggregate_taxa`). Load models
   behind a small predictor function, so tests can pass a fake and never need
   a GPU or the network.
4. **Score into `Outcome`s or `rate`s**, and return a `CheckResult` with
   `limits` (what the labels can't support), `inputs` (SHA-256 of each label
   file and model checkpoint) and `configuration` (thresholds, prompts, budgets).
   Use paths relative to `--data-root`, never absolute ones. Also record
   `cohort_sha256` in `configuration`: the SHA-256 of the sorted scored item IDs
   and their strata. `validate compare` matches cohort keys by name, so this
   digest is what reliably catches a change in which items were scored.
5. **Register it** with `register(Check(...))` and import the module in
   `weedz/validation/checks.py`.

Data goes under `--data-root/<dataset>/` and never into Git. Record each
download's URL and checksum in the module and verify it before use. Tests use
tiny fixtures written in the test itself.

Commit the full-run result as `benchmarks/validation/<check>.json`, and update
the table below from the scorecard.

## Checks

The [scorecard](../benchmarks/validation/scorecard.md) lists every metric, stratum
and gate from the latest full runs.

| Stage | Check | Dataset | Status |
| --- | --- | --- | --- |
| Plant presence | `openimages-plant-presence` | Open Images V7 validation | Measured · 95.5% recall and 38.7% false alarms for SegFormer, 94.7% and 23.7% for SAM3 |
| Plant presence by area | `cocostuff-vegetation-presence` | COCO-Stuff val2017 | Measured · at the pipeline's cutoff SAM3 flags 36.9% of photos with vegetation |
| Region proposals | `cocostuff-vegetation-proposals` | COCO-Stuff val2017 | Measured · half the vegetation covered in 12.3% of photos |
| Region proposals | `openimages-plant-boxes` | Open Images V7 validation | Measured · 39.2% box recall at IoU ≥ 0.5 in the first 100 proposals |
| Species identification | `inat2021-target-species` | iNat2021 validation | Measured, pilot cue recall 21/30 (70.0%, 95% CI 52.1–83.3%), local 20/30 (66.7%) |
| Target false alarms | `inat2021-target-false-alarms` | iNat2021 validation | Measured, pilot 15/42,680 (0.035%) and local 107/42,680 (0.251%) wrong-subject cues |
| Species identification, no training overlap | `plantclef2024-target-species` | PlantCLEF 2024 training set's own validation/test split | Measured · test: PlantCLEF top-1 25/30 (83.3%), pilot cues 16/30 (53.3%) |
| Target false alarms | `plantclef2024-target-false-alarms` | PlantCLEF 2024 training set's own validation/test split | Measured · pilot cues 49/20,503 (0.239%); local 223/20,503 (1.088%), missing the 1% ceiling |
| Whole-photo species list | `danish-roadside-species` | Danish roadside | Measured · 82/778 positive pairs recovered at five suggestions: 10.5% (95% CI 8.6–12.9%) |
| Whole-photo species list, comparison | `danish-roadside-publisher-baseline` | Danish roadside | Measured · released XP4 cutoffs recover 642/778: 82.5% (95% CI 79.7–85.0%), with a variable suggestion count |
| Region proposals | `imageweeds-region-recovery` | ImageWeeds v2 primary138 | Measured · 348/645 boxes recovered (54.0%, 95% CI 50.1–57.8%) |
| Species identification | `imageweeds-species` | ImageWeeds v2 primary138 | Measured · conditional top-1 48/348 (13.8%, 95% CI 10.6–17.8%); five-slot pair recall 23/303 (7.6%, 5.1–11.1%) |
| Region proposals | `phenobench-instance-recovery` | PhenoBench development64 | Measured · 535/853 instances recovered (62.7%, 95% CI 59.4–65.9%) |
| Region proposals | `cwfid-mask-coverage` | CWFID publisher test, excluding 028 | Measured · ≥90% of assessed positive pixels covered in 20/20 photos (100%, 95% CI 83.9–100%) |

### What this showed

#### Open Images V7

Both presence screeners missed the overall recall and false-alarm gates. Keep
their scores for review ranking. On small-vegetation photos, SAM3 recovered
199/202 and SegFormer recovered 177/202. SAM3's default proposal prompts matched
500/1,468 small boxes (34.1%). Test explicit tree prompts and focused views for
proposal recall before relying on boxes to surface small plants.

#### COCO-Stuff val2017

**At the pipeline's current cutoff, SAM3 flags only 36.9% of photos with
vegetation** (406 of 1,100), and half of those where plants cover 0.5% of the
photo or less. Lowering its score threshold on development recovers 93.3%, but
then flags 24.3% of photos with no vegetation. SegFormer can't reach 95%
development recall without flagging every photo (its vegetation share is 0 on
too many small-plant photos). Counting any predicted vegetation pixel
recovers 95.0%, but only 25 of 44 tiny positives, with 26.1% false alarms.
Keep the presence scores for review ranking, not for dropping photos.
[Presence results](../benchmarks/validation/cocostuff-vegetation-presence.json)

The default SAM3 prompts cover at least half the labelled vegetation in only
12.3% of photos, and recover 2.9% of tiny connected regions at IoU ≥ 0.5.
Compare `tree`, `grass` and `shrub` prompts before relying on these proposals
for small or diffuse vegetation. [Proposal results](../benchmarks/validation/cocostuff-vegetation-proposals.json)

#### iNat2021 validation

The cue rules remain frozen on iNat2021, and pooled diagnostics still score
every eligible validation photo: 10 per species, 30 target photos and 40
lookalikes. Species regression gates use source-ID development and held-out
halves; the pooled rows are ungated.
BioCLIP 2 ranked the correct target first on 28 of 30 photos. PlantCLEF ranked
it first on 16 of 30, and in its top five on 26. The pilot cue rule recovered
21 of 30 and the local rule 20 of 30. On pampas the pilot recovered 8 of 10
and the local rule 5 of 10. Keep the pilot as the comparison and review more
pampas photos before changing the cue rule. Only PlantCLEF top-1 named a target
on a lookalike photo: 3 of 10 toetoe (*Austroderia richardii*) photos.
[Species results](../benchmarks/validation/inat2021-target-species.json)

Both cue rules cleared the 1% wrong-subject ceiling across 42,680 photos.
The local rule raised 37 cues on 110 same-genus photos, compared with 14
for the pilot, and 65 on 38,140 unrelated plants, compared with none.
Unfiltered BioCLIP ranked a watchlist prompt first on 38.7% of non-target
subjects. Keep the agreement gate and prioritize same-genus
comparisons when testing changes. The labels cover photographed subjects.
[False-alarm results](../benchmarks/validation/inat2021-target-false-alarms.json)

#### PlantCLEF 2024 val/test

On the cleaner publisher `test` target photos, PlantCLEF and BioCLIP 2 each
ranked the subject first on 25/30 (83.3%, 95% CI 66.4–92.7%). PlantCLEF's
top five recovered 27/30. The pilot cue recovered 16/30 (53.3%, 36.1–69.8%)
and the local cue 11/30 (36.7%, 21.9–54.5%). Local cues recovered only 1/10
test pampas photos, against 4/10 for the pilot. Keep the pilot as the comparison
and investigate local pampas agreement before replacing it. These are labelled
single-plant subjects, not scene inventories. The `val` photos were used by the
publisher for model selection, so their results are reported separately.
[Species results](../benchmarks/validation/plantclef2024-target-species.json)

Across 20,503 non-target subjects, the pilot raised 49 wrong-subject cues
(0.239%, 95% CI 0.181–0.316%), clearing the 1% ceiling. The local rule raised
223 (1.088%, 0.955–1.239%), missing it. Same-genus subjects drew 36/214 pilot
cues and 76/214 local cues, especially other *Ulex* species. Unfiltered BioCLIP
ranked a target first on 36.9% of subjects. Keep the pilot baseline and test
explicit other-gorse comparison prompts on development data. These rates
describe labelled subjects; they do not establish absence elsewhere in a photo.
[False-alarm results](../benchmarks/validation/plantclef2024-target-false-alarms.json)

#### Danish roadside

Production tiles recover **82/778 labelled photo–group pairs (10.5%, 95% CI
8.6–12.9%)** within five full-vocabulary suggestions. Held-out publisher test
recall is 76/577 (13.2%); the distance-filtered subset is 74/468 (15.8%).
The separate multilabel cohort is 6/201 (3.0%). A 4×4 grid improves pooled
recovery to 122/778 (15.7%, 13.3–18.4%). Broom recovery remains just 1/125
for production and 2/125 for the grid. Compare finer views and aggregation policies on development,
and inspect broom's candidate ranks before adopting a change.
[Pipeline results](../benchmarks/validation/danish-roadside-species.json)

The earlier 16/21 result ranked only six Danish groups on 25 reserved photos.
The same grid diagnostic now recovers 562/778 (72.2%, 69.0–75.3%) at rank one;
that restricted ranking explains much of the gap from the broad five-slot list.
XP4's released cutoffs recover 642/778 (82.5%, 79.7–85.0%) with 1,254 suggestions
across 1,160 photos. Its six trained outputs, variable budget and supplied
features give a useful recovery comparison, with a different cost and task.
Watchlist recovery and the distance-filtered multilabel subset are unmeasured;
labels do not support precision. [Publisher comparison](../benchmarks/validation/danish-roadside-publisher-baseline.json)

#### Agricultural datasets

ImageWeeds exactly reproduces 348/645 box matches, 48/348 correct conditional
identifications and 23/303 positive image-species pairs at five suggestions
with maximum-score aggregation, versus 5/303 with frequency voting. Even
publisher-box crops identify only 74/645 as top one. Improve classifier and
crop transfer alongside localization; aggregation alone leaves most labelled
species unrecovered. Partial labels cannot establish precision.
[Region results](../benchmarks/validation/imageweeds-region-recovery.json),
[species results](../benchmarks/validation/imageweeds-species.json)

PhenoBench reproduces the earlier **535/853** one-to-one mask matches. Recovery
is 171/334 for weeds (51.2%) and 127/344 for plants under 512 pixels (36.9%).
The union covers at least half the labelled foreground in all 64 photos, which
hides these individual misses. Prioritize small weed instances when comparing
proposal changes. Crop/weed strata describe localization, not species or
crop/weed recognition. [PhenoBench results](../benchmarks/validation/phenobench-instance-recovery.json)

On CWFID, SAM3 covers at least 90% of assessed positive pixels in all 20
nonoverlapping publisher test photos. Mean per-image coverage is 93.8% overall,
92.4% for crop and 94.1% for weed. These sparse human regions use algorithmic
vegetation boundaries and false-colour imagery; they do not establish proposal
precision. The earlier 60-photo SAM2 diagnostic used a different method and
cohort. Keep dense-mask and small-instance checks alongside this result.
[CWFID results](../benchmarks/validation/cwfid-mask-coverage.json)

These datasets were already inspected during development. ImageWeeds and
PhenoBench retain their entire fixed cohorts as pooled `validation` diagnostics,
and add source-ID development/held-out strata for regression gates. CWFID uses
39 nonoverlapping publisher train photos for development and preserves its 20
publisher test photos after removing 028. All 39 train photos have assessed
positive masks, so a development gate is supported. None is a new independent
held-out claim. PhenoBench's website calls semantic
ID 4 partial-crop twice; its devkit identifies 4 as partial weed. Its archive
and website also disagree on licensing, so retain private noncommercial
research handling.

### Rerun the Open Images checks

Place or link your existing SAM3 checkpoint at `openimages-v7/models/sam3.pt`
under the data root. For the presence check, place or link the pinned SegFormer
snapshot at `openimages-v7/models/segformer/`. The check verifies the checkpoint
and snapshot files before use. It downloads the required Open Images metadata and
sampled CVDF JPEGs as needed.

Use the [isolated CUDA SAM3 runtime](sam3-image-comparison.md#reproduce).
Set `SAM3_SITE_PACKAGES` to its Python 3.12 site-packages directory. The
command below uses the CUDA packages from that runtime and the repo's other
dependencies from the normal uv environment. The local Transformers overlay
provides the versions used for SegFormer.

```sh
uv sync --locked
uv pip install --target .venv/openimages-overlay \
  'transformers==4.57.6' 'huggingface-hub==0.36.2' 'numpy==1.26.4' \
  'scipy==1.16.3' 'scikit-learn==1.7.2'
export PYTHONPATH="$PWD/.venv/openimages-overlay:$SAM3_SITE_PACKAGES"
export CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=0
for check in openimages-plant-presence openimages-plant-boxes; do
  uv run main.py validate run "$check" --data-root "$DATA_ROOT" --device cuda:0 \
    --output benchmarks/validation
done
```

For a smoke run, add `--limit 50` and use a separate output directory. Presence
uses up to 50 images per split. Use the same `--cache-dir` on subsequent runs to
reuse verified JPEGs and predictions. The default cache is `$DATA_ROOT/.cache`.

### Rerun the COCO-Stuff checks

Use the [isolated SAM3 CUDA runtime](sam3-image-comparison.md#reproduce) with
`httpx`, `scipy==1.16.3` and `transformers==4.57.6` installed alongside
its pinned SAM3 dependencies. Set `SAM3_RUNTIME` to that project's directory.
The default project environment uses CPU PyTorch.

Under the data root, link the existing SegFormer snapshot directory at
`cocostuff/models/de01bae28967510f9ddd496c60a969357195400c` and the existing
SAM3 checkpoint at `cocostuff/models/3c879f39826c281e95690f02c7821c4de09afae7/sam3.pt`.
The checks verify the public archives and resume downloads and inference from
the cache. Run presence first to populate the SAM3 cache for proposals.

```sh
export CUDA_VISIBLE_DEVICES=0 PYTHONPATH="$PWD/src"
export UV_PROJECT_ENVIRONMENT="$SAM3_RUNTIME/.venv"
data_root="$HOME/src/weedz-validation-data"
for check in cocostuff-vegetation-presence cocostuff-vegetation-proposals; do
  uv run --no-sync main.py validate run "$check" --data-root "$data_root" \
    --cache-dir "$data_root/cocostuff/.cache" --device cuda:0 \
    --output benchmarks/validation
done
```

Presence selects the highest score cutoff that retains at least 95% of
development positives. SegFormer scores the share of predicted vegetation
pixels. SAM3 scores the strongest raw concept match and also reports recall
using the pipeline's retained proposals. The proposal check uses the default
`plant` and `flower` prompts and 0.5 retention cutoff.
COCO-Stuff uses PNG index 255 for void and PNG index 0 for person. Annotations
are CC BY 4.0 and images are subject to Flickr terms. [COCO-Stuff dataset](https://github.com/nightrome/cocostuff)

On the shared CUDA device, the initial full presence pass took 21m 19s.
The proposal pass took 3m 32s with the presence cache available. The
presence receipt records a 45s full replay from cached predictions.

### Rerun the iNat2021 checks

The checks verify the publisher's archives before extraction. Use the dataset
only for non-commercial research and education, and keep the images private.
The first run needs about 8.4 GB for the image archive plus space for the
extracted validation images. Keep the same `--cache-dir` to reuse the download
and the per-image model evidence across both checks and subsequent runs.
Each extracted image's SHA-256 is recorded in `inat2021/extracted-sha256.json`, and
an image that doesn't match is extracted again from the verified archive. The
result's inputs record one digest over the scored images' bytes.
[Publisher terms and archive checksums](https://github.com/visipedia/inat_comp/tree/master/2021)

Under `--data-root`, link the existing checkpoint files into these locations.
The checks verify each file's SHA-256 before inference.

| Directory | Files |
| --- | --- |
| `inat2021/models/plantclef/` | `plantclef2024.safetensors`, `species_id_mapping.txt` |
| `inat2021/models/bioclip2/` | `open_clip_model.safetensors`, `open_clip_config.json` from BioCLIP 2 revision `2957b322090f9cb17ae72c71981c7218a28d81e0` |
| `inat2021/models/native/` | The frozen NZ pilot's `s.pth` and `waikato-class-metadata.json` |

For the optional overlap audit, place the publisher's training CSV at
`inat2021/metadata/plantclef2024-training.csv`.
[PlantCLEF 2024 training metadata](https://www.imageclef.org/PlantCLEF2024)

Use `--device cuda:0` with an existing CUDA-enabled runtime and `--no-sync`
to keep uv from replacing that runtime with the project's locked CPU Torch.
Send smoke-run output to an external directory.
[CUDA runtime setup](temporal-segmentation.md)

### Rerun the PlantCLEF 2024 checks

These checks reuse the six verified checkpoints at `inat2021/models/` listed
above. No new models or image archives are needed. Place or link the existing
training CSV at `plantclef2024/metadata/plantclef2024-training.csv` under the
data root. The adapter verifies its pinned SHA-256, or downloads it from the
publisher if absent. Only `learn_tag=val` and `learn_tag=test` are scored.
The pinned export contains 99,134 such photos covering 6,598 binomial taxa;
7,806 is the model's class count. The publisher used `val` for model selection,
so emphasize the separately reported `test` estimates.
[Publisher split and model notes](https://zenodo.org/records/10848263)

The species check scores all 60 target photos and 20 broom lookalikes. The
false-alarm check scores every non-target same-genus and same-family photo,
plus the 5,000 other plants with the lowest salted source-ID hash (20,503
photos total). Both use the frozen pilot and local cue rules, with no tuning.
Each result reports `all`, `val` and `test`, including per-species or relatedness
strata. Wrong-subject rates do not establish absence elsewhere in the frame.

Individual photos and their URL, author, licence and SHA-256 receipts live in
`$CACHE_DIR/plantclef2024/images/`. Three download workers pause between requests,
resume partial downloads, and verify every cached image. The publisher supplies
no per-image checksums: the first HTTPS download establishes each local byte
receipt. Photos stay outside Git and retain their individual licence terms.
Predictions resume per model stage and image hash under the same cache directory;
their identity includes the adapter's imported pipeline sources and libraries.
All metadata and checkpoint hashes are verified even when predictions are cached.
One batch of up to 512 photos downloads while the preceding batch is scored.

Set `CUDA_RUNTIME` to a uv environment with CUDA Torch and a `cuda-runtime`
overlay, as for iNat2021. Use it without syncing it back to CPU Torch:

```sh
export CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=0 HF_HUB_OFFLINE=1
export UV_PROJECT_ENVIRONMENT="$CUDA_RUNTIME"
export PYTHONPATH="$PWD/src:$UV_PROJECT_ENVIRONMENT/cuda-runtime"
for check in plantclef2024-target-species plantclef2024-target-false-alarms; do
  uv run --no-sync main.py validate run "$check" --data-root "$DATA_ROOT" \
    --cache-dir "$CACHE_DIR" --device cuda:0 --output benchmarks/validation
done
uv run --no-sync main.py validate scorecard benchmarks/validation/*.json \
  --output benchmarks/validation/scorecard.json --markdown benchmarks/validation/scorecard.md
```

For a smoke run, add `--limit 50` and send `--output` to a separate directory.
Keep the same `--cache-dir` for the full run and later replays.
The full false-alarm receipt records 2 h 12 min including downloads and inference.
The species receipt records 24 s with evidence reused from the 50-photo smoke run.

### Rerun the Danish roadside checks

Set `DATA_ROOT` to the external validation-data directory and `CLASSIFIER_RUNTIME`
to the existing iNat2021 CUDA runtime's project directory. Keep that runtime;
`uv sync` would replace its CUDA Torch with this project's CPU build.
Reuse the already pinned PlantCLEF files from the iNat2021 data directory:

```sh
mkdir -p "$DATA_ROOT/danish-roadside/models/plantclef"
for file in plantclef2024.safetensors species_id_mapping.txt; do
  ln -s "../../../inat2021/models/plantclef/$file" \
    "$DATA_ROOT/danish-roadside/models/plantclef/$file"
done
export CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=0 HF_HUB_OFFLINE=1
export UV_PROJECT_ENVIRONMENT="$CLASSIFIER_RUNTIME/.venv"
export PYTHONPATH="$PWD/src:$UV_PROJECT_ENVIRONMENT/cuda-runtime"
for check in danish-roadside-species danish-roadside-publisher-baseline; do
  uv run --no-sync main.py validate run "$check" --data-root "$DATA_ROOT" \
    --cache-dir "$DATA_ROOT/.cache" --device cuda:0 --output benchmarks/validation
done
uv run --no-sync main.py validate scorecard benchmarks/validation/*.json \
  --output benchmarks/validation/scorecard.json --markdown benchmarks/validation/scorecard.md
```

For a smoke run add `--limit 50` and write to a separate output directory.
Both checks retain the same 1,160 hash-held-out diagnostic photos: 1,060 of the publisher's
2,140 test photos and 100 of its separate 206 multilabel photos. The source ID
is the JPEG filename; `split_of` freezes membership before inference. No
inference operating point is fitted on either scoring cohort. For the new
regression gates, development uses the publisher's 1,181 positive `val` photos,
and held-out uses all 1,145 positive `test` photos. The pinned folder labels
support these positives; blank/no-species photos add no recall trials. No
route-hash fallback is needed because publisher validation labels exist. These
new strata exclude multilabel photos; the historical rows stay unchanged.
XP4 uses its published
validation cutoffs, with the upstream strict `>` comparison and CUDA FP16
autocast. Its suggestion count varies; it is a separate comparison.

The main result is labelled-positive recovery in five full-vocabulary
PlantCLEF suggestions, using the production `region_boxes`/`square_view`
geometry and `aggregate_taxa` maximum-score policy. A frame control keeps the
production centre crop. A fixed 4×4 grid and six-group top-one/top-three rows
retain the earlier roadside method as diagnostics, including Pillow’s original
rounded padding for odd margins. The six-group rankings
restrict alternatives to Danish labels, so they do not measure the same task
as the main five-slot list. Neither method uses dataset labels as inference
inputs. No screening or segmentation gate discards photos in this check.

Metadata, original JPEGs and publisher feature tensors are downloaded from
pinned URLs under `danish-roadside/` in the data root. The checked-in
`src/weedz/validation/roadside_pins.json` records their URLs and SHA-256 hashes.
Image bytes and CSV rows stay outside Git. Interrupted downloads use staging
under `--cache-dir` and
resume with HTTP ranges. Every completed file and checkpoint is verified even
when SQLite evidence under `--cache-dir/danish-roadside/` is reused. Cache
identities include transitive pipeline sources, model hashes, actual imported
library versions (including CUDA build suffixes), geometry and budgets. The
result records total command time and the sum of
per-photo inference durations, including cached durations; the latter covers
all diagnostic methods and excludes model initialization.

Distance-filtered rows require more than 100 m from publisher training,
validation and the other scoring cohort, using the filename-coordinate Earth
chord rule. Scored neighbours are not separated from one another. These rows
reduce a known leakage risk without establishing independent routes or sites.
Only explicit positive pairs count. Blank CSV cells and the no-species folder
supply no negatives to these checks. Watchlist recovery is unmeasured; broom
is the only labelled pipeline lookalike. Wilson intervals do not account for
correlation between neighbouring frames or labels within one photo.

The publisher provides no per-file SHA-256 manifest, so the pins freeze bytes
acquired over HTTPS, rather than independently authenticating them. The
[dataset](https://zenodo.org/api/records/14013930) and
[XP4 model release](https://zenodo.org/api/records/13891416) declare CC BY 4.0;
the [publisher code](https://github.com/plantnet/roadside-invasive-plant-identification)
is MIT-licensed. The reused PlantCLEF checkpoint is CC BY-NC 4.0. XP4 timing
covers only loading supplied BEiT features and running the head, with no feature
extraction; compare its recovery, not its runtime, with the image pipeline.

The final full checks took 14m 20s for PlantCLEF and 10.5s for XP4 on the shared
RTX 5090 (`cuda:0`), with verified downloads and 50 smoke predictions cached.
The PlantCLEF duration includes the frame, production tiles and historical grid.
Its per-photo inference ledger totals 14m 33s including reused smoke durations;
XP4's ledger totals 2.7s. Initial source acquisition took about 20 minutes.

### Rerun ImageWeeds

The check reconstructs the 138-image primary cohort from the two pinned
[Weed-AI publisher archives](https://weed-ai.sydney.edu.au/datasets/cfe6e919-6ddd-4b4e-aa63-58483841a11f).
It quarantines all 36 decoded-pixel alias records and the one image with an
out-of-bounds box, retaining 645 boxes and 303 labelled image-species pairs.
It reads the original JPEG/MPO primary frame with the same decoded pixels as
the earlier lossless PNGs. Labels are partial: no negatives or precision.

Set `SAM3_ENV` to the existing CUDA SAM3 virtual environment and
`CLASSIFIER_ENV` to the existing PlantCLEF virtual environment. Keep their
installed packages with `--no-sync`; the normal project environment uses CPU
Torch. Use the same verified checkpoints as the COCO-Stuff and iNat2021 checks:
`cocostuff/models/3c879f39826c281e95690f02c7821c4de09afae7/sam3.pt`,
`inat2021/models/plantclef/plantclef2024.safetensors` and
`inat2021/models/plantclef/species_id_mapping.txt` under `DATA_ROOT`.
No model downloads are needed.

```sh
export CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=0 HF_HUB_OFFLINE=1
export PYTHONPATH="$PWD/src" UV_PROJECT_ENVIRONMENT="$SAM3_ENV"
uv run --no-sync main.py validate run imageweeds-region-recovery \
  --data-root "$DATA_ROOT" --cache-dir "$DATA_ROOT/.cache" --device cuda:0 \
  --output benchmarks/validation

export UV_PROJECT_ENVIRONMENT="$CLASSIFIER_ENV"
export PYTHONPATH="$PWD/src:$CLASSIFIER_ENV/cuda-runtime"
export WEEDZ_SAM3_PYTHON="$SAM3_ENV/bin/python"
uv run --no-sync main.py validate run imageweeds-species \
  --data-root "$DATA_ROOT" --cache-dir "$DATA_ROOT/.cache" --device cuda:0 \
  --output benchmarks/validation
```

`WEEDZ_SAM3_PYTHON` runs the proposal stage in the SAM3 environment, then releases
it before loading PlantCLEF. The species check also works in a single CUDA
environment that supports both models. The five-slot comparisons call
`aggregate_taxa` with frequency and maximum-score policies, using the full
7,806-class PlantCLEF vocabulary. The pipeline's BioCLIP vocabulary contains
none of these five agricultural taxa, so it cannot identify them.

### Rerun PhenoBench

The [publisher v1.1.0 archive](https://www.phenobench.org/dataset.html) contains
772 validation photos. The adapter reproduces the earlier label-independent
64-photo selection by the lowest SHA-256 of
`weedz-phenobench-development64-v1:` plus filename. It retains partial crop
and weed labels and scopes native instance IDs by crop/weed category. The
instance metric uses maximum-cardinality one-to-one mask matching at IoU ≥0.5,
with date, category, visibility and size strata. Coverage rates use images as
trials; raw mean coverage and mean foreground IoU are separate descriptive
numbers. The earlier pooled foreground IoU is a different statistic.

```sh
export CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=0 HF_HUB_OFFLINE=1
export PYTHONPATH="$PWD/src" UV_PROJECT_ENVIRONMENT="$SAM3_ENV"
uv run --no-sync main.py validate run phenobench-instance-recovery \
  --data-root "$DATA_ROOT" --cache-dir "$DATA_ROOT/.cache" --device cuda:0 \
  --output benchmarks/validation
```

### Rerun CWFID

The adapter reads the pinned [publisher revision](https://github.com/cwfid/dataset/tree/36290d0912a032f0bd1a5678ed55457ddafde217).
Of its 60 images and 119 positive category masks, 20 images belong only to test.
Image 028 also belongs to train and is excluded. Red/green pixels establish
weed/crop positives; black pixels are unassessed. A rate counts images whose
assessed pixels are at least 50% or 90% covered. Pixels are never treated as
independent Wilson trials. CWFID is for noncommercial research only.

```sh
export CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=0 HF_HUB_OFFLINE=1
export PYTHONPATH="$PWD/src" UV_PROJECT_ENVIRONMENT="$SAM3_ENV"
uv run --no-sync main.py validate run cwfid-mask-coverage \
  --data-root "$DATA_ROOT" --cache-dir "$DATA_ROOT/.cache" --device cuda:0 \
  --output benchmarks/validation
```

All three adapters verify publisher archive SHA-256 before reading any data,
then verify extracted images and labels against the archive on each run.
They verify checkpoints even on fully cached runs. Existing archive copies
can be placed at these locations under `DATA_ROOT`; otherwise downloads resume
from `.part` files. Raw data stays outside Git.

| Dataset | Archive path |
| --- | --- |
| ImageWeeds | `imageweeds/source/imageweeds-soybean.zip` and `imageweeds/source/imageweeds-maize.zip` |
| PhenoBench | `phenobench/source/PhenoBench-v110.zip` |
| CWFID | `cwfid/source/cwfid-36290d0912a032f0bd1a5678ed55457ddafde217.tar.gz` |

Inference evidence is cached under `--cache-dir/agri`, keyed by source bytes,
the adapter's transitive pipeline imports, installed library versions and
model settings. Add `--limit 50 --output "$DATA_ROOT/.cache/agri-smoke"` for smoke
runs. The default SAM3 prompts are `plant, flower`, with the default 0.5
retention cutoff and 128-region cap per prompt. ImageWeeds uses the first 100
retained proposals; the mask checks use all retained proposals.

On the shared `cuda:0`, the final full commands took 3m 15s for ImageWeeds
regions, 3m 59s for ImageWeeds species, 1m 03s for PhenoBench and 25s for CWFID.
The species run reused the 50-image smoke classifier cache and all proposal
evidence; the other three final runs recomputed model evidence after the last
adapter change. Times include archive and checkpoint verification. All four
`--limit 50` smoke commands completed successfully (CWFID has 20 eligible images).
