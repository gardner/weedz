# Versioned segmentation activities

The `sam2.1-tiny-v1` run profile executes real SAM2.1 proposals and BioCLIP proposal-view
scoring through the production `DiscoveryWorkflow`. It is opt-in; `segmentation: "off"`
keeps the existing full-frame/tile pipeline. This implements execution and provenance,
not a validated weed detector or a claim of better recall.

The activity order is `collect_photos` → `segment_photos_v1` → `screen_photos` →
`score_region_views_v1` → `export_run`. The `sam21-stages-v1` Temporal patch preserves
historical command order. Images and masks stay in the data store; activity results
contain small counts, not image payloads. Workers use `Activities.registered_activities()`.

## Worker configuration

Install the project and the optional SAM runtime in an isolated `uv` environment.
Use the official SAM source at `2b90b9f5ceec907a1c18123530e92e794ad901a4` and SAM2.1 Hiera
tiny checkpoint SHA-256 `7402e0d864fa82708a20fbd15bc84245c2f26dff0eb43a4b5b93452deb34be69`.
The existing adapter verifies both. Configure `WEEDZ_SAM2_CHECKPOINT` with the checkpoint
path and `WEEDZ_SAM2_DEVICE=cpu` or `cuda:0`. No weights or media belong in Git.
`preflight_segmentation()` loads and validates the runtime before a hosted worker can
advertise that profile. Missing dependencies/checkpoint or changed configuration fail
startup/activity execution; they are not recorded as negative evidence.

Profile v1 caps sources at 20 MB and 40 megapixels, proposals at 12, proposal geometry
at 768 pixels on the longest side, and prompts at 8×8 points with batches of 8. No
additional crop layers or postprocessing are enabled. Tight, neutral-masked and context
views retain their original-upright source transforms. Mask quality is distinct from
species comparisons; neither is identification confidence.

Hosted workers inject `allowed_photo_licences=frozenset({"cc0", "cc-by"})`. This controls
both observation/photo query parameters and admission before download and persistence.
It is trusted worker configuration, not a client-selectable relaxation. Local workers
retain the project's existing admitted-licence policy by default.

## Resume and failure records

`runs/<run-id>/pipeline-v1/` contains atomic, checksummed per-photo proposal and view
artifacts. Inputs pin the original image SHA, profile/config, SAM metadata and then the
classifier metadata plus proposal artifact checksum. Completed evidence is immutable;
a late retry cannot replace it. Failed work is not a successful cache hit. Changed
inputs or corrupt artifacts are refused rather than silently mixed into a run.

Transient per-photo runtime/I/O/memory failures get up to three local attempts with
heartbeats and bounded backoff, independently for every photo and stage. After three
failed attempts that photo becomes explicit fallback. Process/activity interruptions
use Temporal retries and reuse completed matching artifacts; batch-wide Temporal
attempt numbers do not consume a later photo's local retry budget.
Permanent image/proposal validation failures are recorded immediately. Startup/config
failures remain activity failures. Empty proposal sets are valid empty results and
leave the original baseline available. Long model operations heartbeat.

Scores retain the original baseline fields and `screened_at`; additional evidence is
attached under `scores.segmentation`. `proposal_status` and `view_status` distinguish
SAM from classifier failures. Classification failure can retain real masks with empty
`views` objects. Manifests contain per-stage counts/warnings and a partial outcome,
which is also carried by workflow completion. Missing requested stages cannot produce
a completed manifest. Legacy exports retain their original no-segmentation limitation.

## Actual model smoke

On 2026-11-15, actual production activity methods ran through Temporal's server-free
`ActivityEnvironment` against three seeded, CC BY public examples: gorse
`inat-250240131-447484684` (two masks), tern `inat-256864189-460643855` (one mask), and pampas
`inat-82387196-135212551` (zero masks). Full-frame baseline and all retained region views
were computed with the pinned BioCLIP 2 model. A repeated proposal activity reused all
three committed artifacts without further SAM generation. GPU0 peak allocated memory
was 617,309,696 bytes. The tern baseline margin remained −0.041927.

The closed evidence and full source credits are outside Git at
`/home/gardner/src/weedz-segmentation-artifacts/temporal-stages-smoke-20261115-v2/actual-activity-proof.json`.
This was an actual inference/activity smoke, not a collection run, durable-service
restart proof, independent accuracy evaluation or human annotation. The hosted Temporal
service/worker lifecycle is handled separately in #133; end-to-end restart verification
must use that real service and preserve its history.


CLI opt-in uses the same RunSpec field as the API:

```sh
uv run main.py discover --segmentation sam2.1-tiny-v1
```

The normal CLI default remains `off`; the connected worker must have the pinned SAM runtime and checkpoint configured.

View-cache revision 2 keys on the exact proposal input identity (source hash, model pins,
and configuration), rather than mutable failed-result/timing bytes. Completed proposal
outputs are canonical and immutable; their actual artifact SHA remains in view evidence
provenance for auditing. Evidence priority is completed views, then retained successful
proposals with failed classification, then failed-proposal fallback. Artifact and database
writes enforce that order atomically so a late fallback cannot erase real masks. Existing
prototype view-cache revision 1 inputs require a new run namespace when executing these
activities; completed historical runs and their exported evidence remain readable.

A failed-proposal fallback is re-read and committed under the same per-photo lock used
by proposal writers, including its database attachment. Recovery that already won is
consumed instead; immutable successful proposals release the lock before GPU scoring.
Recovery committed after that fallback boundary requires another view-stage invocation;
the completed partial outcome does not retroactively claim to have scored it.
