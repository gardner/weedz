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
   Use paths relative to `--data-root`, never absolute ones.
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
| Species identification, no training overlap | `plantclef2024-target-species` | PlantCLEF 2024 training set's own validation/test split | Planned |
| Region proposals | `imageweeds-region-recovery` | ImageWeeds v2 primary138 | Measured · 348/645 boxes recovered (54.0%, 95% CI 50.1–57.8%) |
| Species identification | `imageweeds-species` | ImageWeeds v2 primary138 | Measured · conditional top-1 48/348 (13.8%, 95% CI 10.6–17.8%); five-slot pair recall 23/303 (7.6%, 5.1–11.1%) |
| Region proposals | `phenobench-instance-recovery` | PhenoBench development64 | Measured · 535/853 instances recovered (62.7%, 95% CI 59.4–65.9%) |
| Region proposals | `cwfid-mask-coverage` | CWFID publisher test, excluding 028 | Measured · ≥90% of assessed positive pixels covered in 20/20 photos (100%, 95% CI 83.9–100%) |
| Whole-photo species list | `danish-roadside-species` | Danish roadside | Planned |

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

Nothing is tuned on iNat2021, so both checks score every eligible photo in
the validation set: 10 per species, 30 target photos and 40 lookalikes.
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

These datasets were already inspected during development. Nothing was tuned in
this port, so ImageWeeds and PhenoBench score their entire fixed cohorts as
`validation`; CWFID preserves the publisher `test` split after removing 028.
None is a new independent held-out claim. PhenoBench's website calls semantic
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

After full runs, rebuild the ordered scorecard:

```sh
uv run main.py validate scorecard benchmarks/validation/*.json \
  --output benchmarks/validation/scorecard.json \
  --markdown benchmarks/validation/scorecard.md
```

On the shared `cuda:0`, the final full commands took 3m 15s for ImageWeeds
regions, 3m 59s for ImageWeeds species, 1m 03s for PhenoBench and 25s for CWFID.
The species run reused the 50-image smoke classifier cache and all proposal
evidence; the other three final runs recomputed model evidence after the last
adapter change. Times include archive and checkpoint verification. All four
`--limit 50` smoke commands completed successfully (CWFID has 20 eligible images).
