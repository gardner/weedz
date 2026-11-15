# Canonical annotation batches in Temporal

`BatchAnnotationWorkflow` consumes a closed canonical sample manifest, not a
synthetic discovery run. It verifies source bytes, executes segmentation and
classification on cache misses, builds an immutable Label Studio package, and
publishes only machine predictions. Each activity returns a small SHA-256-bound
artifact reference; image pixels, masks and classifier rows remain outside
Temporal history.

The ordered stages are validate, segment, frame classification, tiled
classification, masked-region classification, package, and publish. A request
selects the classifier variants explicitly. Each resident worker loads its model
once per process. Segmentation and classification cannot share a process: model
imports can mutate global CUDA math settings. SAM2 and SAM3 use separate pinned profiles; SAM3 partial or
failed prompts remain retryable. Successful per-photo work survives process
loss. Completed artifacts and their directory hierarchy are verified and synced
again when adopted after interruption.

## Running

Install the control role with `uv sync --extra annotation` (the official Label
Studio RLE encoder is required). Use `uv run scripts/run_batch_worker.py --help`. The service address defaults to
`127.0.0.1:7258`, namespace `weedz-hosted`; this runner connects to the existing
service and never starts another server. The hosted single-machine persisted
SQLite service is an evaluation service, not a production Temporal cluster.

Run `prepare --root PATH --sam-checkpoint PATH --classifier-checkpoint PATH
--labels PATH --device cuda:0`. Add `--proposer sam3 --prompts plant flower
--concept-threshold 0.5` for SAM3. Preparation loads and records actual model,
code, preprocessing and runtime metadata. Store its returned configuration
reference with the source manifest. Choose the physical GPU through
`CUDA_VISIBLE_DEVICES`; SAM3 uses logical `cuda:0`.

Start `worker --config PATH --roles control` and a resident
separate `worker --config PATH --roles segmentation` and
`worker --config PATH --roles classification` processes in the appropriate
isolated model runtime. These use distinct versioned task queues, separate from
the hosted discovery workflow. Submit with `submit --request PATH --workflow-id
UNIQUE_ID`. A request contains pinned `manifest` and `ready` references,
`segmentation_profile`, `classifier_profile`, selected `variants`, and the
explicit destination `project_id`. Normal submission rejects duplicate workflow
IDs. `--retry-failed` permits a **new execution** after failure; record both the
workflow ID and execution run ID when reporting recovery.

## Existing outputs

The optional `cached` mapping explicitly pins existing proposals, frame, tiles
or region result files. Adoption verifies their original model metadata, source
identities, image bytes, geometry, row coverage and file digest. Its receipt says
`external-compute`; it does not claim historical inference happened in Temporal.
A missing cache runs the actual model activity. Historical outputs keep their
original metadata and versions rather than acquiring today's preprocessing
claims. Source JPEG context and canonical PNG identity are distinct.

Use `adopt --root PATH --request PATH --proposer sam2` to prepare a cache-only
configuration from an explicitly pinned request. Every selected cache is required
and fully validated before configuration publication; a missing cache can never
load a model. Start its workers with the returned configuration. Operator-wide
corpus queueing and additional classifier registrations remain separate follow-ups;
existing supervised bulk jobs are not retroactively Temporal executions.

## Publication boundary

Publication is a separate role, absent unless explicitly started with
`--publication-config PATH`. Its owner-private configuration identifies the
allowed project, loopback API, PAT file, read-only task-index SQLite file,
published image root, state directory and shared writer lock. Never put token
contents in configuration, source control or logs. Coordinate ownership of the
same lock with every other publisher before enabling this role.

The writer verifies every package file and credited image before REST writes.
It exclusively copies new images, verifies and reseals existing images, imports
new tasks, and appends missing model versions through the bounded official
prediction-import endpoint. It never writes human annotations or overwrites
existing task data or predictions. Same-version conflicting results fail.
Durable pre-request intents prevent blind retransmission after uncertain HTTP
outcomes: the next attempt reconciles server state, and an unresolved intent
requires operator investigation. Heartbeats cover validation, file operations,
lock waits, reconciliation and REST chunks. Do not clear uncertain intents just
to force a retry.

## Actual verification, 15 November 2026

A fresh 100-image canonical batch ran actual SAM2, frame, tiles and masked-region
PlantCLEF activities. During segmentation, the owned compute process was killed
after one per-photo artifact became durable. The same execution retried that
activity after heartbeat timeout, preserved that artifact's SHA, and completed
all model and package stages: 100 unique samples and 119 masks.

Workflow ID: `canonical-batch-148-recovery100-20261115`.
The recovery execution was `01a1dda9-d149-7622-a8e9-80b3ba855edb`.
It subsequently failed at publication because of a client-context lifecycle bug;
that failure history is retained. After fixing the bug, a new execution
`01a1ddb0-fb7c-74d6-a07e-b8f24b5a3588` reused all closed model receipts without
loading GPU libraries and completed all seven activities. It appended 300
predictions to 100 existing tasks, created zero tasks, and made zero annotation
writes. This second execution proves cache reuse and publication, not a
same-execution resume. The publication worker was stopped and the shared lock
released afterward.

Outside-Git evidence is retained under
`/home/gardner/src/weedz-bulk-artifacts/temporal-proof-148-20261115`:
`proof-recovery100-compute.json`, `history-recovery100-compute.json`,
`proof-cache-reuse.json`, `proof-publication.json`, and
`history-completed.json`. These are operational evidence paths, not portable
repository fixtures. Unit tests use small model doubles and do not replace the
actual inference proof.

A separate actual SAM3 execution, `canonical-batch-148-sam3-20261115`, run
`01a1dddf-bb7b-77e8-b205-f218c697a13b`, completed six compute/package activities
for three canonical images: two masks, two ok results, one empty result and no
partial/failed results. History references and output SHA joins were verified.
A later bounded publication attempt correctly refused existing same-version
classifier results with different numeric scores, before any REST writes. SAM3
imports had changed global TF32 flags, which the historical classifier identity
did not record. That execution is retained as failed; it is compute/package
proof, not a completed workflow or a SAM3 restart test. No existing prediction
was overwritten. Protected task/annotation snapshots remained identical. Evidence
is `proof-sam3-package.json` and `history-sam3-package.json` in the same directory.
All owned smoke/publication workers were stopped and the shared lock released.
The refusal history, snapshots and exact score/metadata/source diagnosis are
retained alongside it as `proof-sam3-publication-refused.json` and
`diagnostic-sam3-math-policy-conflict.json`.

The corrected fresh execution `canonical-batch-148-sam3-fp32-20261115`, run
`01a1ddf1-4694-7638-a353-4ebf89a823bf`, completed all seven activities with
explicitly recorded IEEE FP32 policy and NumPy1.26.4. Three images produced two
masks (two ok, one empty, zero partial/failed). It appended twelve predictions
to three existing tasks, created no tasks and made no annotation writes. Exact
protected task-data/meta and annotation snapshots were unchanged. All four owned
workers stopped and the shared writer lock was released. This is the successful
end-to-end SAM3 execution; it does not rewrite or erase the earlier failure.
Evidence is `proof-sam3-fp32-final.json` and
`history-sam3-fp32-completed.json` in the same outside-Git directory.
