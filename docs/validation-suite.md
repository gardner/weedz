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
   only, and report `held-out`.
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

| Stage | Check | Dataset | Status |
| --- | --- | --- | --- |
| Plant presence | `openimages-plant-presence` | Open Images V7 validation | Measured, 95.5% recall and 38.7% false alarms for SegFormer, 94.7% and 23.7% for SAM3 |
| Plant presence by area | `cocostuff-vegetation-presence` | COCO-Stuff val2017 | Planned |
| Region proposals | `cocostuff-vegetation-proposals` | COCO-Stuff val2017 | Planned |
| Region proposals | `openimages-plant-boxes` | Open Images V7 validation | Measured, 39.2% box recall at IoU ≥ 0.5 in the first 100 proposals |
| Species identification | `inat2021-target-species` | iNat2021 validation | Planned |
| Target false alarms | `inat2021-target-false-alarms` | iNat2021 validation | Planned |
| Species identification, no training overlap | `plantclef2024-target-species` | PlantCLEF 2024 training set's own validation/test split | Planned |
| Whole-photo species list | `danish-roadside-species` and existing ports | Danish roadside, ImageWeeds, PhenoBench, CWFID | Planned |

### What this showed

Both presence screeners missed the overall recall and false-alarm gates. Keep
their scores for review ranking. On small-vegetation photos, SAM3 recovered
199/202 and SegFormer recovered 177/202. SAM3's default proposal prompts matched
500/1,468 small boxes (34.1%). Test explicit tree prompts and focused views for
proposal recall before relying on boxes to surface small plants.

### Running Open Images

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
