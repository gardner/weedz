# Mobile model verification

The pure Dart verifier in `mobile/lib/models/bundle_verifier.dart` establishes
publisher provenance and deterministic contract compatibility. It does not run a
native model or establish phone parity. The checked-in synthetic bundle contains
fake model bytes and a public deterministic test key. Never configure that key in
production.

Construct `BundleVerifier` with public keys pinned by trusted app configuration.
An empty list refuses everything. Keys from an envelope or an artifact host cannot
add trust. Pass the envelope bytes, complete model and text-table bytes, the last
persisted installed sequence, current app version, and current time to `verify`.
Only a fully checked result produces `VerifiedBundle`; there is no public
constructor. The manifest is capped at 1 MiB, signatures at 16. Artifacts must match
both signed length and SHA-256; returned bytes, rows and metadata are immutable
copies, protected from caller mutation while verification awaits crypto work.

The caller owns download limits, atomic cache installation and durable sequence
storage. Persist the new sequence only after verification and successful cache
installation. Reject stale or replayed downloads. Revalidate stored artifacts on
loading a cache with its own trusted installed-manifest policy: `verify` deliberately
requires a newer sequence and is the update boundary, not a same-sequence cache
loader. Do not bypass it by resetting the persisted sequence. This PR supplies no
cache or networking implementation.

Before every inference, including offline reuse of a verified in-memory bundle,
call `bundle.ensureUsable(now)`. Expiry dates include the whole UTC calendar day.
An expired bundle must not produce new candidates. The adapter must additionally
check that its actual runtime supports `bundle.runtime` and the preprocessing;
accepting signed ONNX provenance does not mean a native ONNX executor is installed.
The manifest names a publisher-validated parity admission at thresholds version 1.
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
