# Explicit legacy task compatibility

Publication remains strict by default. Older camera tasks can have the correct
canonical external ID, image and visible credit while lacking `data.source_dataset`.
The optional publisher configuration `legacy_identity_allowlist` authorizes that
single absent display field for explicitly pinned tasks. It never updates task
`data`/`meta`, prior predictions, or human annotations. Null, empty or conflicting
present dataset fields still fail, even with authorization.

Configure a reference, not an inline exception:

```json
{"legacy_identity_allowlist": {"path": "/absolute/private/allowlist.json", "sha256": "FILE_SHA256"}}
```

The allowlist is a regular file owned by the service user, mode 0600, outside Git.
Symlink files are refused. It is read within the existing serialized publisher
lock and verified against its exact supplied file checksum. Its maximum size is
1 MiB and it contains 1–1,000 unique entries. The referenced original private
photo-export provenance is bounded to 128 MB, owned, outside Git and SHA-bound; it
is read without altering its bytes or permissions. This is the original export's
`schema_version: 1` document with `photos[].external_id` and `photos[].sample`, not a
newly inferred source claim. Source metadata with NC licences is still excluded
by the unchanged public CC0/CC BY contract.

```json
{
  "schema": 1,
  "project_id": 1,
  "provenance": {"path": "/absolute/original/private/provenance.json", "sha256": "FILE_SHA256"},
  "tasks": [{
    "task_id": 1,
    "external_id": "CANONICAL_EXTERNAL_ID",
    "sample_id": "inaturalist:inat-OBSERVATION-PHOTO",
    "source": "inaturalist",
    "source_id": "inat-OBSERVATION-PHOTO",
    "image_sha256": "CANONICAL_PNG_SHA256",
    "data_sha256": "FULL_EXISTING_DATA_JSON_SHA256",
    "meta_sha256": "FULL_EXISTING_META_JSON_SHA256"
  }]
}
```

Compute data/meta hashes with `weedz.segmentation.artifacts.digest`: SHA256 of
`json.dumps(value, sort_keys=True, allow_nan=False).encode()` with the standard
JSON separators and ASCII escaping. Hash the complete existing dictionaries,
including historical display fields and operator metadata. Do not normalize or
rewrite those dictionaries. File references use SHA256 of the exact file bytes.

Each entry must match the project/task ID and complete existing data/meta hashes.
The authoritative original Sample must match the source, source ID, sample ID and
image SHA; the external ID is SHA256 of `sample.id + ':' + sample.media.sha256`.
Its rights must derive the exact visible canonical credit. Normal image URL and
credit checks remain mandatory. The task index retains full metadata for this
comparison, without reading or writing annotations. Selected allowlisted tasks must
still exist under their approved IDs; missing rows are refused rather than recreated.
A selected grant also refuses changed state if someone subsequently adds the dataset
field: remove or replace that authorization explicitly after an intentional migration.
Approved identities are
rechecked after image copying and before mutation requests.

Only append-only machine prediction publication is permitted. The completion
receipt adds `legacy_adoption` containing the adopted task IDs, allowlist SHA and
original-provenance SHA. Those checksums identify the private authorization without
putting its paths or original source metadata into Temporal history. Correct
present dataset fields use the ordinary path and produce no compatibility entry.
The allowlist is an explicit operator authorization, not a model result or a
cryptographic attestation of source authorship.

Use a separate accepted workflow execution after a refused publication, preserving
the original failed Run ID. Reuse the already verified model receipts without
renaming model versions or recomputing scores. Runtime publication, protected
before/after data/meta/annotation checks and the sole-writer handoff remain the
operator's responsibility. No workflow or service is started by loading an allowlist.
