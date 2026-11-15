# Aotearoa NZ full-frame baseline

This optional CPU classifier implements the published inference facts independently. It uses
Waikato/TAIAO's **Aotearoa Species Classifier**, not PlantCLEF. Its14,991 classes include6,172
plants plus animals, fungi and other organisms. A class being present does not establish
recognition quality on our images. There is no new training, mask generation or human truth.

## Pinned artifacts and rights

[Official release](https://github.com/Waikato/aotearoa-species-classifier/releases/tag/model-small-onnx-fp32-384-v1.0)
(tag commit `c36d8838f189d64de7dde8037ebb7a606dc39968`):

- `species_classifier_fp32_384_384.onnx`,157,384,295 bytes,
  SHA256 `1905b995f53f58cfab8c611c388ff670bab2dcb5019e8cceec0937e9f0291e68`.
- `wit-app/assets/labels/species_14991_metadata.json`,9,207,375 bytes,
  SHA256 `b2b27faf173e9b0613f3580fdc0b4c380c962341ef1466b4abd55b2bf078882e`.
  Numeric keys are the output indices; JSON insertion order is not the class order.

Attribute the model to Waikato/TAIAO's Aotearoa Species Classifier and retain the release link.
The weights are [CC BY-NC4.0](https://creativecommons.org/licenses/by-nc/4.0/).
The initial `timm/tf_efficientnetv2_s.in21k` component retains its Apache2 licence/notices.
Training images retain separate rights. The upstream application has no general code licence
in its inspected tree; this adapter does not copy that application implementation.
Keep models, class metadata, images and real results outside Git.

## Released full-frame policy

Correct EXIF orientation, convert RGB, resize the shorter edge to416 while retaining aspect
ratio with antialiased bilinear filtering, then take a centred384×384 crop. An odd spare
pixel stays on the bottom/right, matching the released application. Convert bytes to FP32,
scale by255, normalise each channel with mean/std0.5, and arrange NCHW `[1,3,384,384]`.
A40MP resized-intermediate guard rejects extreme aspect ratios before allocation.
Pillow implements the resize here; its version and this policy are part of pipeline identity.
This is not a claim of bitwise equivalence to the application's custom resize implementation.

Rank all14,991 finite logits, retaining non-plant alternatives. Report raw-logit softmax
shares as **uncalibrated closed-set scores**. The upstream application's temperature1.3034
is deliberately not applied: no calibration on our full frames or region crops is established.
No masked/tiled profile is supported. A whole-region policy requires separate validation
because centre cropping can discard long stems/leaves.

## Run locally

Use Python3.12 and `uv sync --extra aotearoa`; no CUDA installation is needed. Obtain the
model from the pinned release using `aria2c -x4 -s4 -j4`, then let the adapter verify its hash.
Fetch the class metadata at the pinned commit above; its hash is also checked before loading.

```sh
uv run --extra aotearoa python scripts/classify_aotearoa.py \
  --manifest /absolute/corpus/samples.jsonl --media-root /absolute/corpus \
  --checkpoint /absolute/models/species_classifier_fp32_384_384.onnx \
  --labels /absolute/models/species_14991_metadata.json \
  --output /absolute/new-results
```

Canonical metadata-free RGB PNGs, source rights and exact hashes are verified by the shared
batch runner. A new output directory is required. `predictions.json` contains top-five results;
`full-logits.npz` preserves every logit, ordered external task IDs and class labels.
`receipt.json` binds their hashes and records actual CPU timings. An interrupted run can leave
partial evidence; use a new output directory rather than overwriting it. No service or Label
Studio writes occur. Root's serialized publisher can append a separately named machine
prediction version after review; editable predictions must not be presented as verified truth.

A Temporal named variant should use the same frame-only model metadata and canonical
manifest contract. The resident worker owner must explicitly register it; this standalone
adapter does not silently replace any deployed classifier or change its profile registry.
