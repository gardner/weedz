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
| Whole-photo species list | `danish-roadside-species` and existing ports | Danish roadside, ImageWeeds, PhenoBench, CWFID | Planned |

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
Both checks score the same 1,160 hash-held-out photos: 1,060 of the publisher's
2,140 test photos and 100 of its separate 206 multilabel photos. The source ID
is the JPEG filename; `split_of` freezes membership before inference. No
operating point is fitted on either scoring cohort. XP4 uses its published
validation cutoffs, with the upstream strict `>` comparison and CUDA FP16
autocast. Its suggestion count varies; it is a separate comparison.

The main result is labelled-positive recovery in five full-vocabulary
PlantCLEF suggestions, using the production `region_boxes`/`square_view`
geometry and `aggregate_taxa` maximum-score policy. A frame control keeps the
production centre crop. A fixed 4×4 grid and six-group top-one/top-three rows
retain the earlier roadside method as diagnostics. The six-group rankings
restrict alternatives to Danish labels, so they do not measure the same task
as the main five-slot list. Neither method uses dataset labels as inference
inputs. No screening or segmentation gate discards photos in this check.

Metadata, original JPEGs and publisher feature tensors are downloaded from
pinned URLs under `danish-roadside/` in the data root. The checked-in
`src/weedz/validation/roadside_pins.json` records their SHA-256 hashes; it contains
no images or labels. Interrupted downloads use staging under `--cache-dir` and
resume with HTTP ranges. Every completed file and checkpoint is verified even
when SQLite evidence under `--cache-dir/danish-roadside/` is reused. Cache
identities include transitive pipeline sources, model hashes, library versions,
geometry and budgets. The result records total command time and the sum of
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
