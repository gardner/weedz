# Canonical proposal batches

`weedz.segmentation.batch.propose_batch(manifest, media_root, output, proposer, *, expected_manifest_sha256=None, config=ProposalConfig())` accepts a closed JSONL of versioned `Sample` records. The caller preflights and schedules the model; this library never launches a GPU process. It does not change the existing Discovery RunSpec collection caps or human annotations.

Each batch contains 1–1000 unique canonical IDs and is bounded to 32 MB. Every image must be within the supplied media root (relative paths resolve there), have an exact encoded SHA-256, and support inference. Source and output namespaces must be independent in both directions, and generated outputs must remain outside Git. Source bytes are checked before processing and the same checked bytes are decoded; images are EXIF-upright RGB with 20 MB/40 MP limits. Source labels remain context, not new mask or background ground truth.

Pass the trusted expected manifest SHA from orchestration. For a standard source batch, use its directory as `media_root` and a separate proposal directory as `output`. A global common ancestor intentionally fails the independent-namespace check.

Successful per-image evidence resumes from checksummed, input-bound artifacts; interrupted work resumes only unfinished images. Failed photos remain explicit and are retried, so a ready file with failed counts is not proof of successful segmentation. Changing model provenance/configuration or a completed batch's manifest requires a new output namespace. `model_version` includes model metadata, proposal configuration and contract version. This formal producer has its own version prefix and does not relabel older external results.

The producer publishes `proposals.jsonl` before `ready.json`, syncing files and directory entries. The marker contains schema, manifest SHA, proposal JSONL SHA, model version, count and separate `ok`/`empty`/`failed` counts. Consumers must verify these hashes and their required failure policy, rather than infer success from file existence. Concurrent producers for the same output serialize using a file lock; per-sample successful evidence wins canonically. Cancellation before closing the batch leaves no new ready marker and retains completed per-sample work.

Rows preserve the operational external contract:

```text
schema: 1
sample_id, image_sha256, source_sample, model_version
segmentation:
  schema: 1
  status: ok | empty | failed
  proposal_status: same status
  view_status: not_requested
  baseline_retained: false
  provenance: actual proposer metadata
  regions: original-upright masks/boxes/transforms, views: {}
  elapsed_seconds, optional failure_type
```

The class-agnostic proposal stage does not classify species. Later classifier predictions join canonical `Sample.id` and `Sample.media.sha256`, with separate model versions. Source and model outputs never become human verification automatically.

## Actual DeepWeeds acquisition and baseline proposal run

The [official DeepWeeds repository](https://github.com/AlexOlsen/DeepWeeds) supplies 17,509 Australian vegetation photographs and image-class labels under CC BY 4.0; the source code has a separate license. This domain is not evidence of New Zealand watchlist coverage. The original negative class is not proof of weed absence in every background region.

The official archive was downloaded with the requested `aria2c -x4 -s4 -j4` from its repository-linked Google Drive source. The verified archive SHA-256 is `0961f63c01b997bfab1559ad09e99c0e8130617fd96a8b92fdc09940e01b0ce8`; ZIP CRC validation passed all 17,509 JPEGs. Materialization deduplicated original encoded hashes (17,509 distinct), retained real source filenames, source class as context, attribution/license/source URLs and original JPEG SHA, then produced metadata-free EXIF-upright RGB PNGs. Canonical media identity is the PNG SHA, with the JPEG SHA retained separately as context. No source annotation was fabricated.

The execution-host roots are `/home/gardner/src/weedz-bulk-artifacts/20261115/DeepWeeds-images.zip`, `deepweeds-2000/` (a historical folder name now holding all 17,509 images in 176 closed batches), and `sam21-proposals/`. The latter completed a real SAM2.1-tiny proposal run on all images, with model version `sam2.1-tiny-proposals-v1:34f75faa4e6be1f4bc1276745f972c36dd458c4ee3294f42d94f987bb5624d50`. Those existing artifacts and their model versions remain unchanged. They were produced by the earlier operational runner, not retroactively claimed as outputs of this new formal helper. The helper's tests cover cancellation/resume, failure retry, checksum replacement, independent namespaces, relative URI handling, geometry and provenance changes.

GPU BioCLIP throughput work and a fully packaged acquisition command remain separate follow-ups within issue #144. The existing default CPU scorer and historical score stamp remain unchanged.
