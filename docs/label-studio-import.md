# Offline completed-human review import

This importer is a separate opt-in review handoff. Existing prediction exports and
`label_config()` retain their original format. It does not call Label Studio,
submit annotations, infer expert credentials, or turn predictions into truth.

Use Label Studio's full JSON export, not JSON-MIN or a model prediction download.
The official [export format](https://labelstud.io/guide/export) distinguishes
`annotations` from `predictions` and `drafts`. Only attributable, noncancelled human
annotation records are eligible. Keep the export private: it can contain account
identities and notes. The import receipt records its SHA-256.

The opt-in configuration retains the `regions` brush control and readonly
`model_evidence` evidence control, and adds `review_boxes`, explicit review status,
and completeness scope. Completing a task is not an accepted expert review.
An explicit `accepted` decision records what that account declared; the release
policy decides whether it qualifies. Never describe a synthetic test fixture as
real human review or independently accepted NZ gold.

Each completeness claim names taxa or functional categories, the whole original
image, and whether annotation was exhaustive, partial or unknown. Empty results,
unknown model assignments and old presence controls cannot establish a negative.
A negative for one named taxon does not imply any other taxon was checked.

Rectangles use Label Studio's percentage coordinates, converted to exclusive-edge
original-image pixel boxes. Nonzero image/rectangle rotations are unsupported and
refused. Brushes use the official SDK RLE decoder and remain `dense_mask`
annotations with pinned PNG bytes; no mask-to-box promotion is performed. Image
and region geometry must match the original closed package exactly.

Input trust boundary: an operator supplies the actual exported configuration and
its expected SHA. Offline export bytes cannot cryptographically prove who used a
Label Studio account or which server configuration was active. Preserve that
provenance honestly; it is not an authorization or expertise certificate.

## Commands

Create a separate opt-in project/configuration before collecting these answers:

```sh
uv run python scripts/import_label_studio_reviews.py config \
  --taxon 'Ulex europaeus' --taxon 'Clematis vitalba' \
  --output /absolute/outside-git/review-v1.xml
```

The scope arguments must match exactly when importing. Record the actual project
configuration and its SHA; do not retroactively attach this configuration to old
answers. Select the completeness task explicitly: detection requires boxes,
segmentation requires masks. Partial/unknown coverage never establishes a negative.

```sh
uv run python scripts/import_label_studio_reviews.py import \
  --package /absolute/original-annotation-package --package-sha256 PACKAGE_MANIFEST_SHA \
  --export /absolute/private/completed.json --export-sha256 EXPORT_SHA \
  --config /absolute/outside-git/review-v1.xml --config-sha256 CONFIG_SHA \
  --project nz-review-project1 --project-id 1 \
  --taxon 'Ulex europaeus' --taxon 'Clematis vitalba' \
  --output /absolute/outside-git/new-human-import-v1
```

`--package-sha256` hashes the original package's `manifest.json`. Its closed
manifest must pin `tasks.json`, `private/provenance.json` and canonical image bytes.
The full export must preserve `meta.external_id`, the original `data.image`, numeric
project/task IDs, and each human annotation's actual ID, account, timezone-bearing
creation/update times, cancellation flag and result objects. The project namespace
identifies the source installation/project; it is not an expert credential.

To import a later export, supply the same original `--package` plus
`--previous /absolute/prior-import --previous-sha256 PRIOR_MANIFEST_SHA` and a new
output directory. Exact repeated revisions do not change sample/history bytes.
Changed content under the same revision identity is refused. A newer revision
replaces that annotation's standing claims while retaining the earlier event and
explicit `supersedes` link; older unseen revisions cannot roll standing labels back.
Account identities remain separate; no adjudication or quorum is inferred.

The result contains `samples.jsonl`, verified image/mask assets and a closed
`manifest.json`. Raw exports and configuration snapshots are retained under the
owner-private `private/` directory. History embeds supported claims and checksum
references rather than raw RLE or arbitrary task data. Keep the whole import package
private; share only a deliberately assembled release under its recorded rights.
The importer preserves rights and task declarations; release promotion and expert
acceptance happen separately under the release policy.
