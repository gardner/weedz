# Sample and release wire versions

`weedz.contract.SCHEMA_VERSION` is the latest supported sample version (2).
`LEGACY_SCHEMA_VERSION` is 1. The unified `Sample` reader accepts both; it does not
rewrite stored manifests. Existing plain v1 samples still serialize to the same
bytes, and plain legacy releases keep format 1 and the same content IDs.

A sample using a source category, a mask checksum, scoped completeness or review
history must declare schema version 2. A constructor with no explicit version
selects the minimum required version. None/empty extensions are omitted from the
canonical wire format and do not force an upgrade. Explicit version 1 combined
with meaningful v2 extensions is refused, rather than producing a misleading v1 row.

Use the validated revision helper when adding review evidence to an existing sample:

```python
from weedz.contract import revise_sample

reviewed = revise_sample(original, completeness=(coverage,), review_history=(event,))
```

It preserves existing fields, validates the result and upgrades the version when
needed. It never downgrades a v2 sample, even after removing extensions. Pydantic's
`model_copy(update=...)` deliberately bypasses validation and is not a migration
API. Editing a v1 dictionary and passing it to `Sample.model_validate()` with the
old explicit version will correctly refuse a new extension.

A manifest may contain v1 and v2 rows. A release records the maximum actual sample
version. Releases with v2 samples or new category counts use release format 2;
legacy-only releases retain format 1. Readers verify the advertised sample version
against the manifest. Future release-level extensions must also select format 2.
An old reader may refuse v2 explicitly; v2 is not presented as compatible v1 data.

## Unpublished prototype artifacts

Early development snapshots labelled v1 while carrying experimental extensions
were never a supported v1 format. Preserve those snapshots and their model outputs
unchanged. Regenerate canonical manifests from pinned source records into **new**
directories using the current producer; do not relabel old JSONL in place. Manifest
checksums change with the wire version. Any model-result adoption must still verify
its original source/media/proposal identities and explicitly record that lineage;
a new manifest digest does not authorize reusing unrelated cached results.
