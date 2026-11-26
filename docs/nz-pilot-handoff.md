# NZ review pilot handoff

Reviewers now work in the hosted CVAT jobs listed in the
[reviewer brief](review-dossier.md#open-your-assigned-review). Each arm has
two independent replica jobs. The coordinator assigns each reviewer their
own replica. The [CVAT publication audit](../benchmarks/nz-cvat-review-pilot-20261126.json)
records the first hosted batch. Use the 12 blind and 12 assisted jobs in the
reviewer brief for new assignments. The [vegetation-focused batch audit](../benchmarks/nz-vegetation-review-v2-20261126.json)
records the new jobs, source checks and preflight. The earlier jobs remain
available as an intake baseline.

For hosted reviews, keep each replica’s annotations separate. Export from
the job using **CVAT for images 1.1** so the photo tags, attributes and masks
are preserved. Keep the job ID, reviewer account and session notes with the
export. [CVAT job replicas](https://docs.cvat.ai/docs/workspace/jobs-page/)
· [CVAT annotation format](https://docs.cvat.ai/docs/dataset_management/formats/format-cvat/)

## Earlier offline material

The Label Studio packages and JSON commands below preserve the offline pilot
and its evidence. The hosted CVAT export uses a different format.

The handheld pilot is ready for independent reviewers. The two projects use
16 blind photos and 21 assisted photos. The camera material adds three
optional tasks in two separate projects. The local test projects contain zero
human submissions. The [handoff audit](../benchmarks/nz-review-handoff-audit-20261125.json)
records the exact archive and task hashes.

## Material to distribute

The paths below are relative to the private evaluation artifact directory for
25 November 2026. Each ZIP contains its files, labeling configuration, task
JSON and setup instructions. Share the appropriate ZIP with each reviewer.
Keep the operator packages, cue receipts and blind decision seal private.

| Project | Reviewer ZIP | Photos |
| --- | --- | ---: |
| Handheld blind | `pilot-reviewer-handoff/nz-pilot-blind-v1.zip` | 16 |
| Handheld assisted | `pilot-reviewer-handoff/nz-pilot-assisted-v3.zip` | 21 |
| Camera disagreement | `nz-trailcam-discovery/nz-trailcam-disagreement-v1.zip` | 1 |
| Camera crop-local cues | `nz-trailcam-transfer/nz-camera-transfer-cues-v1.zip` | 2 |

Use separate Label Studio projects. Give reviewers working in both handheld
projects the blind work first. Ask them to inspect the whole photo and use
the unsure answer when image evidence is inadequate. Ask them to record any
interface problems or interruptions, and to defer opening source links until
their submission is complete.

One reviewer can provide usability and time observations. Independent
accounts are needed for agreement on plant presence or cue support. If two
reviewers each complete the full handheld pilot, expect 32 blind and 42
assisted submissions. Report actual completion, agreement and missing answers
from the exports. The handheld arms contain different photos and the timing
comparison is descriptive. Keep both camera projects outside those counts.

## Return the reviews

Export full Label Studio JSON from each project with original task data,
metadata and annotations. Keep reviewer notes and raw exports private.
Use a fresh output directory for the following commands. `PILOT_ROOT` is the
private artifact directory and `REVIEW_DIR` contains the returned exports.

```sh
uv run python -m weedz.annotation.pilot_effort \
  --blind-package "$PILOT_ROOT/nz-paired-pilot-blind-package-v1" \
  --blind-export "$REVIEW_DIR/blind-export.json" \
  --assisted-package "$PILOT_ROOT/nz-paired-pilot-assisted-package-v3" \
  --assisted-export "$REVIEW_DIR/assisted-export.json" \
  --output "$REVIEW_DIR/pilot-effort.json"

uv run python -m weedz.annotation.pilot_outcomes \
  --blind-package "$PILOT_ROOT/nz-paired-pilot-blind-package-v1" \
  --blind-export "$REVIEW_DIR/blind-export.json" \
  --sealed-decisions "$PILOT_ROOT/nz-blind-policy-seal/sealed-decisions.json" \
  --output "$REVIEW_DIR/blind-outcomes.json"

uv run python -m weedz.annotation.pilot_cue_outcomes \
  --package "$PILOT_ROOT/nz-trailcam-transfer/exploratory-package-v1" \
  --export "$REVIEW_DIR/camera-local-export.json" \
  --cue-receipt "$PILOT_ROOT/nz-trailcam-transfer/frozen-cue-targets.json" \
  --output "$REVIEW_DIR/camera-local-outcomes.json"
```

For the earlier camera disagreement, use its own export and the
`nz-trailcam-discovery/review-candidate-package-v1` package with
`nz-trailcam-discovery/frozen-cue-targets.json`.

## Evidence for the decision after the pilot

| Requirement | Current evidence |
| --- | --- |
| Evaluate localization, identification and final suggestions separately | The [benchmark program](benchmark-program.md) ties each claim to its source labels, split and measured budget. PlantCLEF plot truth remains unverified. |
| Decide which pipeline changes earned further testing | The [roadside reserve](benchmark-program.md#reserved-roadside-results) supports the tiled pixel baseline. The [crop-local study](benchmark-program.md#local-bioclip-verification-for-an-exploratory-nz-queue) supports a separate exploratory camera queue. |
| Preserve a frozen, traceable NZ pilot | The [handoff audit](../benchmarks/nz-review-handoff-audit-20261125.json) verifies four archives with 40 distinct source images. The [blind seal](../benchmarks/nz-blind-outcome-seal-20261125.json) covers the 16 blind tasks. |
| Measure actual review effort and test NZ incidental recovery | Pending independent human submissions and usability notes. Numeric pilot results and a wider labeling decision depend on those submissions. |
