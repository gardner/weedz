# WeedScan frame and SAM-region comparison

The public [CSIRO collection61320 v1](https://data.csiro.au/collection/csiro:61320)
([DOI](https://doi.org/10.25919/rcj3-5m69)) contains a MobileNetV2 ORT model with488
classes. This is a separately selectable comparison, not the newer expanded
WeedScan website service and not a replacement for the existing models.
The released model is CC BY-NC4.0; using the open-source Weedz application does
not remove the separate model terms.

The supported path is:

```text
closed canonical image batch ───────────────→ WeedScan frame suggestion
          │
          └→ verified SAM2/SAM3 masks → source crops → WeedScan per region
                                                     │
                                editable masks/taxa in Label Studio
```

Classifier workers reuse an explicitly pinned completed proposal artifact and
never load or rerun SAM. Compute new proposals with the existing segmentation
worker first. A missing/failed proposal artifact is an error; valid empty masks
produce an empty regional result while the independently requested frame baseline
remains available. Empty masks do not establish absence of plants.

## Model and pixels

The adapter validates these bytes before creating an ORT session from the verified
in-memory snapshot:

| Artifact | SHA256 |
| --- | --- |
| `weedscan19_epoch_300.ort` | `5b564b88511211b63e5a6a50101779c34b940e040fd0c099e75fcd97146cc0dc` |
| `taxonomy.json` | `315474e605c2bd5543e8241f256ebd63ff336ee3f6dc14f72571017391767fa4` |

Download outside Git, using the user's requested acceleration settings:

```bash
aria2c -x4 -s4 -j4 -d /path/to/model-cache -o weedscan19_epoch_300.ort \
  https://data.csiro.au/dap/ws/v2/collections/61320/data/67666968
aria2c -x4 -s4 -j4 -d /path/to/model-cache -o taxonomy.json \
  https://data.csiro.au/dap/ws/v2/collections/61320/data/67666963
```

Frame input is already-upright canonical metadata-free RGB PNG. Resize the short
edge to480 with Pillow bicubic, floor the long edge, then centre-crop480 using
nearest/ties-to-even offsets. Normalise RGB bytes using mean123.675/116.28/103.53
and standard deviation58.395/57.12/57.375, yielding NCHW float32. ORT is explicitly
CPU-only with four intra-op and one inter-op thread. The output is already a
softmax vector; applying another softmax would change the released scores.

For each retained region, preserve tight/unmasked, masked and surrounding-context
views separately. Each complete crop is centred on a neutral square before the
same480 transform, preserving its aspect ratio and avoiding removal of the ends
of elongated regions. The masked view is the declared primary classification;
the other two remain visible in model evidence rather than selecting whichever
answer looks best. Model/runtime, view policy, SAM policy and exact source/mask
identities participate in cache/version validation. Changing any of these creates
different evidence. Existing PlantCLEF/Aotearoa versions retain their identities.

The adapter does not rotate EXIF pixels itself: canonical inputs are already
upright, while the historical reference JPEG oracle intentionally uses stored
pixels. No plant deskew, orientation-invariance or individual-plant guarantee is
claimed. Masks can be leaves, clumps, overlapping regions or nonplants. Resizing
a tiny crop cannot recover detail absent from the source.

Taxonomy strings are preserved exactly: `Cortaderia` is a genus suggestion,
not an asserted `Cortaderia selloana`; subspecies remain subspecies. Scores are
closed-set, uncalibrated rankings, with no validated unknown/nonplant rejection.

## Prepare and run

Use an isolated project environment; no separately installed OS service is needed:

```bash
uv sync --extra weedscan --extra annotation
uv run scripts/prepare_weedscan_worker.py \
  --root /path/to/artifacts \
  --checkpoint /path/to/model-cache/weedscan19_epoch_300.ort \
  --labels /path/to/model-cache/taxonomy.json \
  --proposals proposals/batch-0001.jsonl \
  --proposals-sha256 <exact-sha256>
```

This prints a checksum-bearing immutable worker-config reference. Its proposal
reference seeds the reusable worker's model policy; each submitted batch still
requires its own exact source-bound proposal artifact and closed manifest.

Use `scripts/run_batch_worker.py` with that config and the existing Temporal
service. Run `control,classification` and `segmentation` in separate owned worker
processes; the segmentation role only validates/adopts the supplied proposals.
The sole publication worker also needs its explicit private publication config.
All Label Studio writers share the existing import lock. Use a dedicated Temporal
namespace for this model/profile pool because task queues are fixed. Submit a
normal batch request selecting `classifier_profile: weedscan488-v1`,
`variants: [frame, regions]`, the config's `segmentation_profile`, and
`cached.proposals: {path, sha256}`. Source/ready references and project ID remain
required. See [Temporal annotation batches](canonical-temporal-batches.md) for
the worker, request and publication contracts.

Publication creates separate machine prediction versions, preserving all prior
models, task data and human annotations. The regional result supplies actual
source-coordinate brushes and editable taxon text; the frame result supplies
image-level taxon text. Neither fills human verification choices automatically.
Runtime evidence records ONNX Runtime/NumPy/Pillow, not fictional timm/torch pins.

## Measured conformance and limitations

The packaged adapter reproduces all109 released reference top labels, with maximum
absolute difference2.96e-8 from their published maximum scores. These reference
files are model outputs, **not human ground truth**. On the133 canonical-photo
development cohort, all133×488 output values match the earlier conformed frame
adapter exactly (2.37seconds CPU).

A separate actual SAM3 plant0.2 experiment classified886 regions from those133
photos through all three views. It did not consistently improve source-class
agreement over the frame baseline. Its reports, real crop sheets and raw vectors
remain outside Git under
`/home/gardner/src/weedz-weedscan-artifacts/20261115/`.
Training overlap is unverified; image-level source classes do not identify every
plant in a photograph or provide mask truth. Model conformance, proposal coverage,
classification quality and independently verified discovery yield are separate
measurements. High-resolution tiling before SAM and held-out instance evaluation
remain work under#122/#152.
