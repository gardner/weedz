# Binding model preparation to parity evidence

A bundle may be signed only when the selected parity record describes both its
exact image-model bytes and its exact preprocessing configuration. The latter
comes from the text table's sidecar, so a changed sidecar must not silently reuse a
passing benchmark for another transform.

`weedz.bundles.text_table.preprocessing_sha256` defines the shared transform hash:
convert tuples to arrays and floating-point values to their decimal strings with
`portable`, encode using the bundle's canonical JSON rules, then SHA-256 those
bytes. Object order and tuple-versus-list storage do not change the hash. The
benchmark producer reads `open_clip.get_model_preprocess_cfg` from the loaded
model that prepares its windows and records this hash in every variant and the
reference metadata. The artifact-cache fingerprint includes it as well as weights,
library versions and export settings, preventing reuse across changed transforms.

The publisher recomputes the same hash from the sidecar's actual preprocessing
object, rejects missing/invalid benchmark hashes, and refuses a mismatch before
manifest creation or signing. The signed manifest already includes that complete
object, so no redundant required manifest field or schema change is necessary.
This is a configuration binding; it does not prove a different native library
implements the configuration correctly. Actual native preprocessing and model
parity still require measurement on the intended runtime/device.

Existing benchmark records without `preprocessing_sha256` remain historical and
cannot admit a new bundle. Rerun `scripts/compare_optimised.py` against the actual
pinned model and inputs to obtain new measured provenance. Never repair an old
benchmark by inventing a transform hash after the measurement. The screener's
embedding-cache hash is a different, library-inclusive serialization and is not
interchangeable with this portable configuration hash.
