# Optional desktop segmentation experiment

Default discovery still uses BioCLIP 2 with the original full-image/tile route.
`scripts/segment_pilot.py` adds an explicit **separate experimental run**, not a
production switch or a phone implementation. Original ranking scores and revision
4 remain unchanged. `scores.segmentation` stores schema 1 proposal evidence and
three independently scored views; it never replaces the queue's baseline margin.

## Model decision

The official [SAM 3 implementation](https://github.com/facebookresearch/sam3)
provides `build_sam3_image_model` and `Sam3Processor` for concept/exemplar image
segmentation. Its checkpoints require approved Hugging Face access; its
[SAM licence](https://github.com/facebookresearch/sam3/blob/main/LICENSE) is not
Apache2. No SAM3 accuracy comparison was performed here. SAM3.1 Object Multiplex
is a video tracking release, not the still-image builder used for this decision.

The initial runnable alternative is official [SAM 2.1](https://github.com/facebookresearch/sam2):
Hiera tiny, public direct checkpoint, Apache2 code and checkpoints. The source is
pinned to `2b90b9f5ceec907a1c18123530e92e794ad901a4`; runtime loading checks its
installed VCS revision. Checkpoint SHA256 is
`7402e0d864fa82708a20fbd15bc84245c2f26dff0eb43a4b5b93452deb34be69`.
Automatic grid proposals are **class-agnostic**, not a plant detector. Neither
predicted mask IoU nor mask stability is species confidence.

## Bounds and provenance

The stage applies EXIF orientation before defining any coordinates. It resizes
the proposal image to at most 768 pixels per side; uses an 8×8 point grid, batch 8,
no extra crop layers and no optional CUDA connected-component postprocessing.
Retain at most 12 masks of at least 16 thumbnail pixels, sorted by predicted mask
IoU. Exact duplicates are removed; overlapping/nested regions remain available.
Compressed source files are limited to 20 MB / 40 MP. The CLI reuses the exact
upright RGB pixels it saved as lossless PNG, so expansion of that derivative does
not incorrectly reapply the compressed-file cap. Prepared pixels retain the 40 MP
bound; direct file callers still have the 20 MB cap. Retained BioCLIP views are also capped at 768
pixels per side. These are experiment caps, not evidence of adequate small-plant
recall. Masks are lossless translucent PNGs aligned to the whole upright image.

Each region records an exclusive-right/bottom original-pixel box and a context
box expanded by 25% of its longest side, clipped at image edges. Tight, neutral-
background masked, and context views record their source box/resized size and are
centrally padded to square before the pinned BioCLIP preprocessing. The unchanged
baseline supplies original-scene plus tile context. Quality values remain separate
from the species cosine margins. Single-view results omit local boxes; their
original-frame extent is recorded only in `view_transforms.source_box`. An empty or failed stage explicitly retains the
baseline, so missing proposals cannot silently become confirmed negatives.

Mask caches key exact image pixels/dimensions, pinned source/checkpoint/config,
Torch version and transform revision. BioCLIP retains its existing separate cache.
Run metadata contains both model stamps; per-photo evidence contains transform
provenance. Do not mix these results with an ordinary run or infer proposal status
from the baseline's `segmentation: false` field: the additional experiment is
explicitly named `proposal_experiment` in the model stamp.

## Reproduce without changing the source pilot

Use a separate environment; no system packages or model weights belong in Git:

```sh
uv init --bare --python 3.12 /absolute/cache/sam-runtime
SAM2_BUILD_CUDA=0 uv add --project /absolute/cache/sam-runtime \
 'sam-2 @ git+https://github.com/facebookresearch/sam2.git@2b90b9f5ceec907a1c18123530e92e794ad901a4' \
 open-clip-torch pillow numpy pydantic temporalio scikit-learn fastapi cryptography httpx
curl -L --fail -o /absolute/cache/sam2.1_hiera_tiny.pt \
 https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_tiny.pt
PYTHONPATH="$PWD/src" uv run --project /absolute/cache/sam-runtime python scripts/segment_pilot.py \
 --source /absolute/public/pilot --source-run RUN_ID \
 --output /absolute/artifacts/NEW-experiment \
 --checkpoint /absolute/cache/sam2.1_hiera_tiny.pt --limit 6 --device cuda:0
```

The output directory must be new and outside Git/source pilot. Source SQLite is
opened with `mode=ro`. Only CC BY/CC0 photos are copied; their source checksums are
verified, pixels made upright and metadata stripped into lossless PNGs. Coordinates
and capture dates are omitted from the new records. Source decisions, tokens and
private intake are not read. `experiment.json` retains creator/licence/source URL,
model stamps, per-photo timing/GPU peak and process maximum RSS. This is an isolated
visual experiment, not a clone of expert review decisions or full-pilot metrics.

Serve the resulting directory through `create_app(Path(output))` on loopback and
point the production review web app's `WEEDZ_API_URL` at that API. Under photo
evidence, select a region in **Mask overlay**, then return to **Original image**.
`WEEDZ_WEB_URL=http://127.0.0.1:3022 pnpm --dir web exec node scripts/check-segmentation.mjs`
verifies the real output's toggle and three view scores. No fake mask/API is injected.

## Actual checkpoint smoke run, 15 November 2026

Pinned tinySAM2.1 + pinned BioCLIP2 ran on 6 eligible public photos (two references,
four animal-subject coastal photos) from `nelson-tasman-3e62ad801459`, sorted by ID.
CUDA GPU0 was an RTX 5090; Torch 2.15.0+cu132, Pillow 13.0.0, NumPy 2.5.4.
This is a feasibility smoke run, not a representative accuracy comparison.

| Public photo ID | Retained masks | Total seconds | Proposal + region scoring seconds |
| --- | ---: | ---: | ---: |
|447484684|2|6.24|3.13|
|455546899|2|5.73|2.80|
|460262550|4|7.63|5.42|
|460262714|3|6.23|4.07|
|460262865|6|10.25|8.08|
|460263038|5|9.04|6.86|

Peak allocated GPU memory was 617,309,696 bytes (~589MiB) for each photo; process
maximum RSS was 4,621,944KiB (~4.41GiB), including both loaded models. These timings
exclude model startup/download and include CPU BioCLIP2 encoding. The proposal
column includes region classification, not solely SAM execution. These are single-run shared-workstation timings, not an isolated latency benchmark.
CUDA reserved memory/whole-system peak, phone heat/battery and sustained throughput were not measured.

Visual inspection found partial flower/leaf masks on the gorse/clematis references,
and shell/crab regions on coastal photos. This demonstrates why generic masks do
not establish plant completeness. A coastal image's baseline margin was −0.069,
while one masked view reached +0.023; taking an unvalidated maximum over proposals
could manufacture stronger-looking false suggestions. Those view scores therefore
do not change the ranking. No expert boundary masks or independently reviewed
background-plant ground truth were available: **no IoU/Dice, recall improvement,
weed identification confidence or mobile readiness is claimed**.

The measured default decision is to keep the baseline unchanged. Issue 122 remains
open for access-authorized SAM3 comparison, independent masks/positive-negative
holdouts and fixed review budgets, proposal-stage misses, and separate native
resource/privacy feasibility. No segmentation service receives private phone photos.
