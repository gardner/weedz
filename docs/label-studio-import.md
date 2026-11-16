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
owner-private `private/` directory. The entire package root is created with mode0700
before any files are written. History embeds supported claims and checksum
references rather than raw RLE or arbitrary task data. Keep the whole import package
private; share only a deliberately assembled release under its recorded rights.
The importer preserves rights and task declarations; release promotion and expert
acceptance happen separately under the release policy.

The offline snapshot is bounded to 1,000 source samples, 10,000 package files,
512 MiB total package bytes, 256 MiB per asset, 8 MiB per human export, and 64 MiB per tasks/provenance JSON, and 40 megapixels per image.
The smaller export cap bounds JSON/RLE expansion before decoding. Split larger
exports into smaller task subsets. New outputs are refused before publication if
they would exceed the same byte/file limits used by the next replay. These are resource
limits, not claims about annotation quality or independent sampling.

Rights admission defaults to `--rights-profile public-cc0-by`, checking **both**
media and metadata licences through the shared source-rights policy. Use
`--rights-profile noncommercial-cc0-by-nc` explicitly for admitted CC BY-NC material.
This does not rewrite licences, authorize contributor images, admit custom publisher
terms as Creative Commons, or publish anything. The noncommercial profile is named
in the new receipt and must remain selected on later imports. A source package
with an explicitly recorded profile cannot silently change profiles. Historical
packages without a profile still require every source licence to pass the selected
policy; an explicit noncommercial choice is needed for legacy NC metadata too.

A previous import is bound to both the same project namespace and numeric project
ID. Reusing a namespace for another project or renaming it mid-chain is refused;
it cannot manufacture another agreeing reviewer or replace another project's claims.

An explicit, attributable cancelled revision of an annotation already in the
history retracts only that annotation's standing regions and completeness. It
retains the old events/assets and appends a retraction with its timestamp,
revision digest and `supersedes` link. Cancellation does not create a negative.
Never-imported skipped rows and missing rows in a partial export do not retract
anything. Repeated cancellation is idempotent; reopening needs a newer completed
revision with explicit review controls.

When present, `updated_by` identifies the exported revision account; `completed_by`
remains the original annotation author. If the export omits `updated_by`, history
explicitly attributes the account to `completed_by` and does not claim that it
independently identifies the editor/canceller. Account fields are source attribution,
not proof of a person's identity, independent expert review or authorization.

## Sample wire versions

Source packages may contain supported v1/v2 samples. Adding human completeness or
history uses `revise_sample()` and writes schema v2 in the **new** sample manifest;
original v1 source files stay unchanged. The import receipt's
`contract_schema_version` records the maximum actual sample version. Its separate
`schema_version` describes the closed-package envelope, not the embedded sample
contract. Replays allow the validated monotonic source-v1 → reviewed-v2 transition,
without allowing changes to original media/rights or a sample-version downgrade.

Unpublished prototype rows that declare v1 but contain meaningful v2 fields are
refused. Preserve those artifacts; regenerate from pinned source records into new
versioned directories rather than editing their JSONL or model outputs in place.
See [contract versions](contract-versions.md).

A prior human-import output is never a fresh source package. Keep the original
source package in `--package` and pass the pinned prior output through `--previous`,
so its project namespace and numeric project identity remain checked. Structural
`tasks.json` and `private/provenance.json` have a separate pre-decode 64 MiB JSON cap;
new outputs must fit those structural limits too, so revision history cannot grow
into a package that the next replay would reject.

The receipt retains a canonical external-ID to numeric task-ID bijection across
all exported subsets, including tasks without completed annotations. Reusing a task
ID for a different sample or renumbering an already seen sample refuses. Older
import receipts without the table recover it from their retained pinned human
exports; original package/project checks still apply.

These byte limits bound encoded snapshots, not decoded Python RAM. JSON/RLE and
model objects can use substantially more memory. The 64 MiB structural allowance
supports normal 1,000-sample review histories; image-heavy or large-mask packages
may need smaller subsets even below the sample limit. The overall closed package
remains limited to512 MiB and output uses identical replay limits. No existing
provenance is compacted or rewritten just to fit.

Pending reviewer-origin regions remain recorded but do not supervise any task
until accepted. Upstream unreviewed source labels remain usable. This intentionally
changes behavior for an old v1/v2 record declaring detection with only pending human
regions: that unsupported task claim now refuses validation. It is never silently
granted acceptance, downgraded or rewritten. If such a record needs preservation
for later review, keep its original raw bytes/history and explicitly validate a
NEW copy with only `tasks=["inference"]` using `Sample.model_validate`; retain all
annotations/history and rights, and store the new copy separately. Existing pending
inference records and legacy source-only v1 serialization remain unchanged.

Human-region work is preflighted across the entire selected export before the first
brush decode: at most64 region controls per completed annotation,160 million
canonical source pixels of brush grids per annotation, and400 million brush pixels
across the import. Each brush counts the complete canonical width×height grid;
compressed RLE length or foreground area does not reduce this cost. Boxes count
toward the region limit but require no brush-grid budget. Use smaller brush batches
for high-resolution images. Exact already-recorded revisions reuse their verified
history without decoding; attributable cancellations remain available without a
new decode allowance. All declared geometry and the combined budget must pass first.
Generated mask paths may reuse retained bytes only if identical; conflicting source
or historical assets are refused, never silently replaced.

Before publication the importer rechecks media, current masks, supported historical
claim/annotation masks and any assessed-mask references against the final closed files.
Derived metadata may be revised only when doing so does not replace a referenced asset.
Checksum-addressed source, export and configuration snapshots are immutable: different
retained bytes at their paths cause refusal; exact byte reuse is allowed.

`completeness_task` scopes whole-image coverage, not every annotation's geometry.
The explicit review decision applies to the supplied regions in their native form:
a box stays a box and a brush stays a mask, including mixed annotations. No geometry
conversion or task promotion is inferred. Exhaustive named coverage still requires
matching geometry for those targets; partial/unknown coverage establishes no absence
or completeness for another task. Gold acceptance remains a separate policy.

The receipt's `owned_export_sha256` records the verified export snapshots that this
importer owns, including empty exports and exports with no completed human rows.
Replay reads only these receipt-proven snapshots, verifies their actual hashes, and
checks their task identities against the pinned task table. Other source-owned files
under `private/exports/` remain opaque preserved data; a pathname never grants authority.
Legacy receipts may use their explicit current-export anchor and genuinely added
importer-event anchors, excluding source history. A complete pinned task table keeps
its previous IDs. Before-table legacy chains with unprovable earlier captures refuse
with an ownership error rather than guessing or rewriting the old prototype.

For before-table legacy receipts, even a source-shaped export file can be ambiguous:
it may also have been an actual zero-human capture. Without a recorded table or
owned lineage, any such unproven retained capture causes refusal; original bytes
are left untouched. New receipts do not have this ambiguity and keep unrelated
source JSON inert, regardless of its filename or task-shaped content.

Immutable source history does not become import-chain authority by naming a matching
annotation key or event ID. Selected records that collide with those source-history
identities refuse before revision replay, replacement or cancellation handling.
Only events added beyond the pinned original source belong to the import chain.

Previous human state is reconstructed from the immutable source and an ordered
`capture_journal`, before any previous revision or ownership payload is trusted.
Each entry binds the captured export, archived configuration and the exact ordered
taxon/category scope. Empty, zero-human and repeated captures stay in the journal;
a repeated previously unknown cancellation is reconsidered in its actual position.
The receipt-owned export set and task bijection must agree with the journal.
Reconstruction compares complete typed samples/history and regenerated mask bytes.
A mismatch may indicate changed evidence or a different SDK/Pillow codec runtime;
it refuses without rewriting prior artifacts. Keep the locked import runtime.

Historical validation permits at most 10,000 captures, 100,000 total task/annotation
visits (including zero-human tasks), and 2 billion decoded brush-grid pixels across
distinct revisions, in addition to the existing per-record and per-capture caps.
The next capture is included in these limits before publication. Identical already
applied revisions are decoded once during reconstruction, not once per capture.
Large or long-running chains need smaller closed batches. Legacy receipts without
a journal are accepted only when a single capture and its exact current declared
configuration are provable; ambiguous multi-capture prototypes remain unchanged
and are refused, rather than guessing order from human history or SHA sorting.
Distinct capture snapshots (including the next export, deduplicated by verified
SHA) additionally have a shared 64 MiB encoded JSON cap checked before replay
parsing; each export still has its separate 8 MiB pre-decode cap. These are input
byte bounds, not promises that decoded Python objects occupy the same memory.
All original closed-package files must also remain byte-identical in a previous
import, including task predictions/credits, source configuration and ordinary
metadata. Only the generated sample manifest and private sample provenance may
change; existing referenced-asset checks still protect those paths when used as
media or masks.
