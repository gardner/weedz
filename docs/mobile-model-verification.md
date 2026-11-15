# Mobile model verification

The pure Dart verifier in `mobile/lib/models/bundle_verifier.dart` establishes
publisher provenance and deterministic contract compatibility. It does not run a
native model or establish phone parity. The checked-in synthetic bundle contains
fake model bytes and a public deterministic test key. Never configure that key in
production.

Construct `BundleVerifier` with public keys pinned by trusted app configuration and
an `artifactDirectory` in the app's private storage. An empty pin list refuses
everything. Keys from an envelope or artifact host cannot add trust. Pass envelope
and text-table bytes, a downloaded `imageModelFile`, last persisted installed
sequence, current app version and current time to `verify`. Only a fully checked
result produces the final `VerifiedBundle` type; there is no public constructor.
The manifest is capped at 1 MiB, signatures at 16, and the table at 16 MiB. The
configurable model limit defaults to 2 GiB and is a storage/verification limit,
not a claim that a phone can execute a model of that size.

The model never becomes a full in-memory Dart byte array. A worker isolate streams
it in bounded chunks into a fresh owned `bundle-*` directory. It hashes/counts the
copied bytes, refuses excess bytes immediately, flushes the completed file and
renames it to `<sha256>.onnx` only after both signed size and digest match. Each
verification gets its own directory: existing digest-named files are never trusted
or overwritten. Failed invocations remove only their own staging directory. Small
input bytes and metadata are defensively copied. The returned
`bundle.imageModel` contains `path`, `sha256` and `size`; source-path replacement or
later source deletion cannot change that verified snapshot.

The native adapter opens only `bundle.imageModel.path`. App code must keep this
private owned directory unchanged for the capability's lifetime, including every
native session using it. Cache updates create new snapshots rather than replacing
live files. Do not put this root in user-editable/shared storage, write these
paths, or garbage-collect them while verification/native sessions are active.
Retire a snapshot only after all users have released it. A killed process can
leave an unpublished private stage or an unreferenced completed snapshot; cache
recovery may remove such orphans only after establishing no live owner. Neither
an incomplete stage nor its path is returned as a verified capability.

The caller still owns network download limits, installed-manifest registration,
durable sequence storage, cache loading and eviction. Persist the new sequence
only after verification and successful registration of its owned artifact. Reject
stale/replayed updates. Loading a previously installed cache needs its own trusted
installed-manifest policy: `verify` deliberately requires a newer sequence and is
the update boundary, not a same-sequence loader. Do not bypass it by resetting the
persisted sequence. This PR provides managed artifact staging, not a downloader or
complete persistent bundle cache.

Before every inference, including offline reuse of a verified in-memory bundle,
call `bundle.ensureUsable(now)`. Expiry dates include the whole UTC calendar day.
An expired bundle must not produce new candidates. The adapter must additionally
check that its actual runtime supports `bundle.runtime` and the preprocessing;
accepting signed ONNX provenance does not mean a native ONNX executor is installed.
The target and comparison label order is pinned to ranking revision 4; a signed
publisher regression cannot redefine it. The manifest names a parity admission
at thresholds version 1.
Its measurements are checked before signing by the Python publisher; a phone does
not rerun that benchmark or infer hardware parity from the identifier.

The shared inference functions are:

- `regionBoxes(width, height)` returns exclusive pixel-edge `PixelBox` records for
  ranking revision 4, whole frame first, with Python half-to-even rounding.
- `decodeUpright(bytes)` decodes a single frame, bakes EXIF orientation, and converts
  to 8-bit RGB. It refuses more than 50 MiB encoded bytes or 40 MP decoded pixels.
- `squareWindow(image, box)` pads a crop with `(124,116,104)`; square outputs above
  40 MP are refused. `isFeatureless` measures the unpadded crop using PIL integer
  luma and population deviation strictly below 8. Whole-frame index zero remains
  eligible. These synchronous CPU functions should run away from the UI isolate.
- `cosineSimilarities(embedding, bundle.textRows)` normalizes a native output and
  scores the verified unit rows. `summarizeMargins` selects a target's best eligible
  window, then the best target. It rounds target results to six decimal places as
  the server does before choosing the best species; first window/target wins ties.

The native adapter must implement and verify the exact signed tensor preprocessing
(RGB, bicubic shortest-side resize/crop, mean/std and input dtype); the square crop
helper is not that transform. It must return embeddings aligned with window order.
No stand-in embeddings, synthetic fixture, or successful host Dart test constitutes
native model execution. Native preprocessing/embedding parity needs actual runtime
measurement before a phone inference claim is made.

Scores are uncalibrated target-minus-comparison margins, not probabilities of a
weed being present. These modules do not attach `meaning-1` to device reports.
Device population evidence and a device score-meaning decision remain outstanding;
fixed prompts matching server arithmetic alone do not establish that meaning.

Regenerate public conformance data with:

```sh
uv run python scripts/build_mobile_conformance.py
uv run python scripts/build_mobile_bundle_conformance.py
```

Flutter tests compare geometry and scoring against publisher vectors and decoded
images against Python crops. PNG threshold pixels must match exactly. JPEG pixels
allow at most three intensity levels per channel because decoders differ in IDCT;
geometry, EXIF-upright dimensions and eligibility must still match. This tolerance
is not a tensor or embedding parity threshold.
