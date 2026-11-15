# Opt-in GPU BioCLIP encoding

The default BioCLIP/BioCLIP2 screening backend remains CPU. Saved specs that omit
`screening_backend` also use CPU. Their embedding keys and CPU score-meaning
metadata remain unchanged.

Select `--screening-backend cuda-fp32-v1` with `uv run main.py discover`
(or set that explicit field in a bounded discovery RunSpec). Run the discovery
worker in an isolated CUDA-enabled uv environment with matching Torch/torchvision
builds and the existing project dependencies. The normal locked environment uses
CPU Torch; selecting CUDA there fails clearly instead of silently falling back.
No OS packages or changes to the default dependency index are required. Use
`CUDA_VISIBLE_DEVICES` to choose the physical GPU before launching the process;
the profile uses its visible `cuda:0`.

The profile moves one resident pinned OpenCLIP encoder to CUDA in float32. Both
image and text encoding disable autocast and TF32 through the shared FP32 context,
restoring the caller's flags afterward. Tokenizer IDs retain integer dtype.
Normalized embeddings return to CPU float32; the existing cosine/margin ranking,
whole-frame/overlapping-window geometry and SAM tight/masked/context views are
reused. GPU-profile CPU cosine operations also disable ambient autocast. No half
precision or new detection threshold is introduced.

GPU execution metadata records the versioned backend, visible device/GPU name,
CUDA/cuDNN, numeric policy, NumPy and the existing Torch/OpenCLIP/torchvision/Pillow
and pinned weight/preprocessing identities. Execution metadata participates in the
preprocessing hash, so GPU embeddings cannot reuse CPU cache entries. An existing
run refuses changed model metadata. Future changes to this profile's numeric or
batching policy require a new profile version. Image encoding uses the existing
bounded 16-window batches and one proposal view per call.

GPU scores explicitly have no declared score meaning. The CPU pilot's measured
counts do not establish GPU performance, and neither backend emits calibrated
weed-presence probabilities. Positive margins remain candidates for human review;
negative margins do not establish absence. SAM proposals remain class-agnostic.

The first hardware proof uses the same three licensed source cases (one reference,
one lookalike, one incidental) for CPU and GPU baseline scoring and all three
views of their previously verified actual SAM2 masks. The reproduction script,
source/image identities, full raw results, runtime metadata and actual CUDA
forward-input observations are retained outside Git; no Label Studio or source
store changes are required. See issue #144 for the final measured receipt.

Actual 2026-11-15 hardware receipt: `/home/gardner/src/weedz-demo-artifacts/bioclip-gpu-144/receipt.json`
(and `proof.json`/`reproduce.py` alongside it). A physical RTX 5090 ran 24 image-tower
forwards over three cases and seven previously generated SAM masks. Every observed
forward used CUDA float32 with autocast/TF32 disabled. Both backend caches went
miss then hit with identical cold/warm results. Rounded CPU/GPU baseline margins
differed by at most 0.000001 on this bounded sample; that is numerical evidence,
not calibration or performance on a representative evaluation set. No SAM inference,
source-store changes, service restart or Label Studio writes occurred.
