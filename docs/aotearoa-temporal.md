# Aotearoa CPU frame workflow

This optional variant registers the released NZ ONNX classifier in the canonical
`BatchAnnotationWorkflow`. It depends on the baseline adapter (#154) and batch
orchestration (#155). It is frame-only; no PlantCLEF identity, plant-only label
conversion or fabricated torch/timm runtime pins are used.

The existing workflow contains a proposal stage. This variant **requires an explicit
SHA-bound completed SAM2 artifact**, validates its source/masks, and adopts it as
`external-compute`. Its proposer loader refuses to run inference. This reuses the
original proposal evidence; it does not claim the NZ classifier generated masks.
A future workflow that omits that stage entirely is a separate change.

## Prepare and run

Keep every input, config and output outside Git. Install the optional dependencies:

```sh
uv sync --extra annotation --extra aotearoa
uv run python scripts/prepare_aotearoa_worker.py \
  --root /absolute/owned-artifacts \
  --checkpoint /absolute/models/species_classifier_fp32_384_384.onnx \
  --labels /absolute/models/species_14991_metadata.json \
  --proposals closed-proposals.jsonl --proposals-sha256 <exact-sha256>
```

The command checks the model/class-map hashes and actual ONNX interface, records
CPU/ONNXRuntime/NumPy/Pillow/preprocessing identity, and pins the proposal metadata.
`proposal_metadata_source_reference` records where those model/configuration declarations
were discovered; it is not an artifact allowlist. The same worker can process other
closed batches whose independently SHA-bound proposal artifacts pass the full source,
semantic-model and mask validation. Hash integrity is not cryptographic attestation
that a model generated the masks: operator-provided artifacts remain a trust boundary.
The activity subsequently validates the complete proposal/source join against the
closed manifest before frame inference. Requests must select only `frame` and
provide `cached.proposals`. Unknown classifier kinds and a misleading cache-only
flag fail closed. Existing PlantCLEF/legacy adoption configurations remain unchanged.

Use a dedicated, already registered namespace on the existing Temporal service.
Batch queues have fixed names, so separate namespaces isolate independently configured
worker registries. Run two worker processes with the generated config:

```sh
uv run python scripts/run_batch_worker.py --namespace <isolated-namespace> \
  worker --config /absolute/worker-config.json --roles control,segmentation
uv run python scripts/run_batch_worker.py --namespace <isolated-namespace> \
  worker --config /absolute/worker-config.json --roles classification
uv run python scripts/run_batch_worker.py --namespace <isolated-namespace> \
  submit --request /absolute/request.json --workflow-id <unique-id>
```

No publication worker should run until the operator grants the sole-writer handoff.
The workflow can complete its compute/package stages and wait safely on the
publication queue. Publication uses the existing reviewed publisher and its private
configuration, not a second ad-hoc writer.

## Scientific and annotation semantics

All14,991 species remain valid alternatives, including animals and fungi. The editable
image-level taxon is a machine suggestion, never human verification. The NZ frame
prediction contains no brush labels or species masks. Scores are all-class raw-logit
softmax shares, uncalibrated on Weedz; upstream temperature scaling is not applied.

`Aotearoa NZ frame verification v1` binds the registered presentation policy and model
metadata. This new presentation version is deliberately distinct from the manually
published133-image baseline whose evidence includes a corpus-wide full-logit archive
hash. Existing predictions, human annotations, image URLs, source credit and task
identities must remain unchanged. Reused SAM predictions retain their own version.

A bounded proof must record the original proposal artifact/selected row hashes, exact
source samples and any media-path relocation, Temporal history, CPU inference receipts,
package SHA, and before/after protected-state comparisons. Choosing a few development
images does not establish accuracy, training-set exclusion or calibrated confidence.

## Executed bounded proof

The isolated `weedz-aotearoa-153/aotearoa-frame3-v1` workflow completed on15 November2026.
It reused the first three previously published DeepWeeds SAM2 rows, with source image
hashes, masks, model versions and rights unchanged. Only materialized media paths were
relocated; the external subset-lineage record binds original/derived sample and row hashes.
Three actual ONNX CPU frame predictions exactly matched their counterparts in the133-image
baseline. Segmentation was recorded as `external-compute`, classification as
`temporal-activity`; no SAM inference ran.

Package SHA256 `a19ee2a9097beb710a5b9904af54119e478fc3307d6f17eb6156ee8a7c3742e1`
was published during the authorized sole-writer handoff: exactly three new machine
predictions on existing tasks34–36, zero new tasks and zero human annotation writes.
Global task-data/meta and human-annotation hashes stayed identical; all prior prediction
rows on those three tasks were unchanged. Existing SAM versions were reused. Every proof
worker exited before the shared import lock was checked free and the handoff returned.

The private operational receipt, immutable source subset lineage, exact compute-source
snapshot, stage artifacts and Temporal history are outside Git under
`/home/gardner/src/weedz-demo-artifacts/aotearoa-153/temporal-proof3-v1/`.
This is execution/recovery evidence, not a species-accuracy or independent holdout result.
