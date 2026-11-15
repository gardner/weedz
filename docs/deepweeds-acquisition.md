# Reproduce bounded DeepWeeds source batches

`deepweeds-batches` converts the already-cached official archive and authoritative labels. It does not download, infer, create annotations, or publish to Label Studio. Outputs must be outside Git and cannot contain the source files. An explicit image limit is required (1–17,509); closed batches contain 1–1,000 images each.

```sh
uv run main.py deepweeds-batches \
  --archive /home/gardner/src/weedz-bulk-artifacts/20261115/DeepWeeds-images.zip \
  --labels /home/gardner/src/weedz-bulk-artifacts/20261115/DeepWeeds-labels.csv \
  --output /home/gardner/src/weedz-source-artifacts/deepweeds-bounded-v1 \
  --limit 100 --batch-size 100
```

Reuse that exact command to resume. Verified closed batches skip image conversion; an interrupted partial batch repeats at most `batch-size` conversions, preserving already published identical pixels. Existing different bytes, changed budgets/input pins/Pillow version, unsafe paths, invalid labels and unrelated output directories are refused. Do not delete a marker to force a changed configuration into the same namespace; choose a new output directory. A missing `complete.json` means the whole requested conversion has not been acknowledged. Individual `batch-NNNN/ready.json` markers close only their corresponding batch.

The archive is read in place, not extracted. The complete member inventory must match all authoritative label filenames, even for a small selected limit. Image member sizes, total decoded ZIP bytes, label bytes, image pixels and canonical PNG bytes are bounded. Selected original image hashes must be distinct. Complete archive/label SHA256 pins are checked before conversion and again before the final completion marker; each converted image must match its preflight bytes. Invalid media stops the conversion with no ready marker for its unfinished batch, rather than inventing a successful or empty sample.

Each closed batch contains metadata-free EXIF-upright RGB PNGs, `samples.jsonl`, and a ready marker binding the manifest hash, source pins and count. The canonical Sample ID remains `deepweeds:<original JPEG filename>`; media identity is the exact derived PNG SHA256. Context retains the original JPEG SHA256, authoritative class ID, labels checksum and source URL. `original_label` is upstream source context, not human verification. Samples support inference only and have no annotations. The `Negative` source class does not establish that every possible weed is absent. DeepWeeds is a Queensland/Australian cohort, not evidence of New Zealand watchlist coverage or instance-mask ground truth.

The library entry point is `weedz.deepweeds.materialize`. Its `SourcePins` value makes trusted input identity explicit; the CLI always uses the verified official pins. Custom pins are for explicit independently verified source snapshots/tests, not a way to assert that arbitrary files are the official release.

## Official provenance and fresh downloads

The [official repository at revision da084f62](https://github.com/AlexOlsen/DeepWeeds/tree/da084f62bcd1a2b0afeb8b81f1a27be3186391a1) links the 468 MB image archive and explicitly states that images and annotations are CC BY 4.0. Its repository-code licence is separate. Credit: Alex Olsen et al. (2019), *DeepWeeds: A Multiclass Weed Species Image Dataset for Deep Learning*, Scientific Reports 9:2058, [doi:10.1038/s41598-018-38343-3](https://doi.org/10.1038/s41598-018-38343-3). Individual photographer names are not invented; `rights.creator` is absent and the authoritative dataset attribution is retained. Both media and label metadata are marked CC-BY-4.0 with the pinned README as the licence source.

- Archive SHA256: `0961f63c01b997bfab1559ad09e99c0e8130617fd96a8b92fdc09940e01b0ce8`.
- [Authoritative labels CSV](https://raw.githubusercontent.com/AlexOlsen/DeepWeeds/da084f62bcd1a2b0afeb8b81f1a27be3186391a1/labels/labels.csv) SHA256: `6fb95b89fd9d384f94e185a5cab6c5da7c987649399c90618ecc60acfb0112eb`.

The existing archive is already cached: do not download it again. For a fresh machine, resolve the image archive link from that official README (Google Drive may require its normal confirmation flow), then use the requested parallel downloader with the resolved public download URL:

```sh
aria2c -x4 -s4 -j4 --dir /absolute/cache --out DeepWeeds-images.zip "$DEEPWEEDS_OFFICIAL_ARCHIVE_URL"
curl --fail --location --output /absolute/cache/DeepWeeds-labels.csv \
  https://raw.githubusercontent.com/AlexOlsen/DeepWeeds/da084f62bcd1a2b0afeb8b81f1a27be3186391a1/labels/labels.csv
```

The converter refuses different bytes; a Google Drive HTML confirmation page is not an archive. No archive, images, batches or generated results belong in Git. Existing operational 17,509-image artifacts retain their old paths and identity; this command produces a separately versioned reproducible acquisition namespace and does not rewrite those artifacts. GPU BioCLIP remains a separate #144 follow-up.
