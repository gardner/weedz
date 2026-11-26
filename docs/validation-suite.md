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

Add `--limit 50` for a quick smoke run. Results from limited runs are not saved
to `benchmarks/validation/`.

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
| Plant presence | `openimages-plant-presence` | Open Images V7 validation | Planned |
| Plant presence by area | `cocostuff-vegetation-presence` | COCO-Stuff val2017 | Planned |
| Region proposals | `cocostuff-vegetation-proposals`, `openimages-plant-boxes` | COCO-Stuff val2017, Open Images V7 validation | Planned |
| Species identification | `inat2021-target-species` | iNat2021 validation | Planned |
| Target false alarms | `inat2021-target-false-alarms` | iNat2021 validation | Planned |
| Species identification, no training overlap | `plantclef2024-target-species` | PlantCLEF 2024 training set's own validation/test split | Planned |
| Whole-photo species list | `danish-roadside-species` and existing ports | Danish roadside, ImageWeeds, PhenoBench, CWFID | Planned |

### Running the iNat2021 checks

The checks verify the publisher's archives before extraction. Use the dataset
only for non-commercial research and education, and keep the images private.
The first run needs about 8.4 GB for the image archive plus space for the
extracted held-out images. Keep the same `--cache-dir` to reuse the download
and the per-image model evidence across both checks and subsequent runs.
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
