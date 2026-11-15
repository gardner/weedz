# GPU BioCLIP margin batches

This optional pipeline reuses the pinned BioCLIP encoder and its existing whole-frame/tile and SAM crop scoring. It produces relative watchlist cosine margins, not softmax probabilities. A finite positive margin may propose one of the three watchlist taxa; otherwise the editable taxon is Unknown. Neither outcome verifies presence or absence. Raw comparisons, every species margin and all three region views remain available to the reviewer.

Canonical source taxonomy is never supplied as an original-subject prompt. This policy applies equally to camera-source images and DeepWeeds. DeepWeeds source classes stay private source context, not newly verified truth. No synthetic observations or observation IDs are created.

## Prepare and run

Use an isolated, CUDA-enabled runtime with the existing project dependencies and cached pinned model. CPU remains the discovery default; this registry explicitly requires `cuda-fp32-v1`, FP32 CUDA encoding with TF32/autocast disabled, and CPU FP32 cosine calculation. It does not install or alter a CUDA runtime. GPU model metadata and preprocessing hashes partition the embedding cache from historical CPU results.

Prepare an owned artifact root containing a closed canonical `samples.jsonl`, its checksum-bearing `ready.json`, and a verified completed SAM2 or SAM3 proposal JSONL. Keep every source sample ID, rights record and media SHA; any relocation must update the recorded `source_sample.media.uri` consistently and retain lineage separately.

```sh
PYTHONPATH="$PWD/src" /path/to/cuda-runtime/python scripts/prepare_bioclip_worker.py \
  --root /absolute/outside-git/proof \
  --proposals cached/proposals.jsonl --proposals-sha256 ACTUAL_SHA256
```

The resulting worker configuration registers frame and regions profiles. The frame profile explicitly includes the existing letterboxed full-frame and overlapping tile baseline. Regions retain tight, masked and context outputs independently; tentative assignment uses the highest finite positive recognized watchlist margin across those views, matching the documented existing assisted-verification policy. No view is selected using source labels or human truth.

Submit through `scripts/run_batch_worker.py` using variants `["frame", "regions"]` and `cached.proposals` with its exact owned relative path and SHA. Use a separate namespace and separate segmentation/classification worker processes; cached-only segmentation adopts the validated source masks and its loader refuses SAM inference. Control workers need the annotation extra. Publication needs the established explicit private configuration and sole-writer handoff; every publisher must use the same global import lock. Do not place credentials or generated media in Git.

The same model worker can process different valid batches: the configuration's proposal reference records where model metadata was discovered, not an artifact allowlist. Every request independently pins its manifest, source images, proposal bytes and complete mask/source joins. The trusted operator/producer boundary remains: hashes bind bytes, not a cryptographic attestation that a model generated them.

## Recovery and publication

A batch contains at most 1,000 samples; operational publication should use closed chunks of 100. Completed per-photo outputs are file/directory-synced and reused after interruption. Model/runtime failures propagate for Temporal retry; they are not converted into evidence of absence. Previously completed photos remain reusable, while invalid sources or changed metadata fail before publication. Empty SAM output remains a valid explicit coverage result with a separate baseline classification.

Final artifact adoption validates the complete native record, raw score aggregation and all three views, with matching source and model identities. The exporter creates separate frame and region prediction versions, actual editable masks and tentative taxa; it never writes human annotations. Existing source credits, task metadata, prior model predictions and human annotations must remain unchanged. Retry receipts prevent duplicate publication.

## Acceptance evidence

Unit tests and ActivityEnvironment tests exercise interfaces with fake encoders; they do not establish GPU execution. Actual three-image Temporal/publication, paired 133-image comparison and progressive 100/1,000/2,000-image GPU batches must be recorded outside Git with source/producer/runtime hashes, protected-state receipts and explicit coverage/failure counts. These are pipeline and numerical proofs; training overlap is unknown and they do not establish held-out accuracy or calibrated weed confidence.
