# Assisted image verification in Label Studio

The exporter copies verified public photos and real model results into a portable
import package. Machine proposals are editable starting points, not human labels.
It never creates annotations, marks ground truth, or writes to the source store.
Use separate blind projects for validation: assisted verification is not an
unbiased measurement of a model's accuracy.

Install the optional maintained converter with `uv sync --extra annotation`.
The lock pins Label Studio SDK 2.1.5; its official RLE output was also decoded
pixel-for-pixel using the hosted Label Studio 1.23.2 runtime's SDK 2.1.2.

## Export canonical batches

Use a closed canonical Sample JSONL manifest with already normalized RGB PNG media.
Each batch must contain 1–1000 photos; 100 is recommended. All model files are
optional, so tasks can arrive before inference finishes:

```sh
uv run --extra annotation python scripts/export_annotation_batch.py \
  --manifest /private/batch-0001/samples.jsonl \
  --frame-results /private/batch-0001/plantclef-frame.json \
  --proposals /private/sam/batch-0001/proposals.jsonl \
  --regional-results /private/sam/batch-0001/plantclef-regions.json \
  --tiled-results /private/batch-0001/plantclef-tiles.json \
  --output /private/exports/batch-0001-v1
```

The output directory must be new and outside Git/source data. Encoded image bytes,
geometry, model-input SHA, manifest SHA, regional proposal-file SHA and region IDs
are checked before publication. Only public CC0/CC BY media and metadata are
accepted. The canonical source class stays private context and never supplies a
proposed taxon. Media identity uses Sample.media.sha256, not an original JPEG hash
stored as provenance before normalization.

Each task's external ID is SHA256 of `sample.id + ':' + sample.media.sha256`;
Sample.id already contains the source namespace. Preserve that identity when
appending inference results. An image derivative with different bytes is a
different task unless a separate, explicit identity migration is designed.

## Import without overwriting human work

The package contains `tasks.json`, `label-config.xml`, `images/corpus/*.png`,
`private/provenance.json`, and `manifest.json` with file hashes. Copy only the
images to the service's published-images directory. Never expose the private
provenance directory or its parent as a web/document root.

Label Studio local-file serving requires both its local-file environment settings
and a project LocalFilesImportStorage whose path is a proper subdirectory of
LOCAL_FILES_DOCUMENT_ROOT. With document root `/private/published-images`, register
`/private/published-images/corpus`; task URLs use
`/data/local-files/?d=corpus/<sha>.png`. The validated `--image-prefix` option can
select another relative subdirectory. Merely setting the document root returns
404 in Label Studio 1.23.2 without the registered project storage.

An API publisher must serialize reconciliation by external ID. Import new tasks
once. On existing tasks append only missing prediction model_versions; never
reimport the task, replace annotations, or manufacture a human acceptance. If a
POST times out, reconcile the server before retrying. The same model_version with
different result bytes is a conflict, not permission to overwrite. This exporter
performs no HTTP requests and provides no distributed publication lock.

## What people verify

Select a prediction version, copy it into an annotation, and accept, correct or
reject its proposed taxa and masks. Image-level controls cover plant presence,
watchlist presence and other plants even when SAM proposes no mask. Required human
choices are deliberately not preselected. Free-text image/per-region taxa permit
species outside the three NZ watchlist comparisons.

SAM alone proposes class-agnostic masks labelled Unknown. BioCLIP watchlist margins
are relative comparisons: only finite positive recognized comparisons can propose
a target, and positivity is not calibrated detection confidence. PlantCLEF frame
and tiled top-k results propose an image taxon without inventing mask boundaries.
Regional PlantCLEF uses the predetermined masked view for each actual SAM region,
retaining alternative views privately. Its closed-set top taxon is tentative and
cannot establish that an image is a plant or reject non-plants reliably.

The shared regional version binds classifier weights, taxonomy mapping, transform,
precision/runtime, SAM checkpoint/configuration/filtering, mask expansion and
assignment policy. Corpus notes do not change it; changed inference settings do.
Full original metadata and semantic hashes remain in private provenance. No scores
are presented as calibrated confidence and no model output becomes human truth.

## Export an existing completed review run

```sh
uv run --extra annotation python scripts/export_label_studio.py \
  --source /private/review-store --run completed-run-id \
  --output /private/exports/review-run-v1 --mode assisted
```

This read-only adapter excludes private device reports and unsupported licences.
`--mode blind` removes model predictions, hints and original taxonomy from imported
tasks; the private provenance remains available to the experiment owner. The
canonical-batch assisted command does not promise a blind export mode.

The output follows the official [prediction import format](https://labelstud.io/guide/predictions),
[BrushLabels RLE format](https://labelstud.io/tags/brushlabels) and
[local storage requirements](https://labelstud.io/guide/storage_local).
