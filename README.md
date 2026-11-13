# Weedz

A reproducible invasive-weed baseline: Leafy Spurge survey crops → model scores →
spatial evaluation → an offline review map and GeoJSON points.

See [Datasets, curation, and detection methods](docs/datasets.md) for the source
shortlist, the implemented pipeline, and proposed processing paths for each
candidate dataset. Only Leafy Spurge crops are currently supported by the CLI.

## Run it

Install [uv](https://docs.astral.sh/uv/) and run from this repository:

```sh
uv run main.py
```

The first run downloads **900 small 39×39 crops**, two metadata files, and the
dataset attribution. It trains a CPU baseline and writes a new timestamped
directory under `runs/`. No account, GPU, API key, or server is required.
Open the printed `map.html` path in your browser; the report embeds the images
and works offline.

```sh
# Download and verify inputs without training.
uv run main.py fetch

# Repeat using only verified local files; preserve the previous experiment.
uv run main.py run --offline --output-dir runs/experiment-02

# Choose the operating recall on validation, before seeing test results.
uv run main.py run --offline --target-recall 0.95
```

`--data-dir` changes the local dataset location. Interrupted downloads resume;
recorded SHA-256 checksums are verified before every experiment. A modified
dataset fails verification. To obtain a fresh copy, use a new `--data-dir`.
Data and experiment outputs are excluded from Git. Existing nonempty experiment
directories are never overwritten. `uv run weedz` provides the same CLI.

## What is measured

The starting model uses RGB/HSV histograms, colour summaries, and simple texture
features with standardized, class-balanced logistic regression. It learns only
from pixels. Coordinates and survey labels are never model inputs. Model weights
are plain JSON and predictions use the saved model.

- Preserve the publisher's 100-observation test cluster.
- Reserve the highest-numbered training survey cluster for validation.
- Fit the scaler and model on the remaining training clusters only.
- Exclude fitting observations within 2 m of validation or test observations;
  exclude validation observations within 2 m of test observations. The small
  crops span approximately 0.51 m at the published resolution. This buffer is
  specific to these crops, not appropriate for larger context tiles.
- Choose the highest threshold that meets the requested validation recall,
  then evaluate on the published test set. The validation target is not a
  guarantee of test recall.

The report includes precision, recall, F1, accuracy, average precision, ROC AUC,
confusion counts, and a majority-class baseline chosen from fitting labels.
Model scores are not calibrated probabilities. Training predictions are marked
as in-sample; test observations open by default in the review map.

Each run produces:

| File | Contents |
| --- | --- |
| `map.html` | Offline geographic point map with partition/error filters and crop inspection |
| `predictions.geojson` | WGS84 longitude/latitude points, labels, predictions, scores, and partitions |
| `predictions.csv` | The same predictions in tabular form |
| `metrics.json` | Validation and test results at the validation-selected threshold |
| `model.json` | Versioned features, scaler statistics, and linear model weights |
| `run.json` | Source revision, input checksums, exact partition IDs, threshold, and package versions |

The [recorded CPU baseline](benchmarks/leafy-spurge-cpu.json) uses 700 fitting,
100 validation, and 100 test observations. At the 90% validation-recall operating
point, test recall is **82.4%**, precision **63.6%**, and accuracy **67%**
(majority-class baseline: 51%). It catches 42 of 51 positives, misses 9, and
raises 24 false alarms. A second offline run reproduced the results exactly.
This is a starting measurement, not a field-ready detector.

## Data and limits

Source: Doherty et al., [Leafy Spurge Dataset](https://huggingface.co/datasets/mpg-ranch/leafy_spurge),
[DOI: 10.57967/hf/2508](https://doi.org/10.57967/hf/2508), **CC BY 4.0**.
The upstream revision is pinned in `src/weedz/dataset.py`; the source README and
attribution are retained with the downloaded data. Review images are converted
to PNG; other data changes are described by the experiment manifest.

This is **survey-point classification at one Montana site**, not weed-patch
segmentation, infestation area estimation, or validated NZ performance. Absence
is a field observation at a survey point, not a negative label for every pixel in
the surrounding scene. False alarms per hectare cannot be derived from these
sampled points. The map has a coordinate grid rather than an online basemap.

Next steps, in order:

1. Inspect misses and false alarms; compare candidate models on validation only.
   Repeated test-set inspection turns it into a development set; obtain a new
   independent holdout before claiming improvements.
2. Add [MAVSD](https://doi.org/10.6084/m9.figshare.28428707.v1), CC BY 4.0, for
   pixel segmentation. Keep its multi-angle views of the same scene together.
3. Label a small, independently reviewed NZ dataset for one target species,
   provisionally gorse. Use [LINZ imagery](https://github.com/linz/imagery) or
   permitted drone surveys at the intended deployment resolution. Split by site
   before tiling; record imagery capture dates, resolution, and attribution.
4. Use [DOC weed observations](https://doi.org/10.15468/kknfpc) to select survey
   areas. Historical, approximate occurrence points are not image labels.

## Development

Tests use synthetic local imagery and never need the downloaded dataset or
network. Core behavior was introduced with failing tests first.

```sh
uv run pytest
uv run ruff check
uv run ruff format --check
uv run pyright
uv run python scripts/check_file_length.py
```

Ruff checks McCabe complexity (maximum 8), Pyright checks annotated Python,
and source files are limited to 500 lines. Local pre-commit hook definitions
are in `.pre-commit-config.yaml`.
