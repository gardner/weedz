# Image-processing conformance fixtures

These synthetic images and their committed expected crops are inputs for the
Flutter image-tower verifier. They contain no contributor photos. Rebuild with
`uv run python scripts/build_mobile_conformance.py` from the repository root.

`expected.json` records upright dimensions, window boxes, square letterboxed crops,
unpadded greyscale population standard deviations and window eligibility. The
orientation-6 JPEG has encoded dimensions 8x12 and upright dimensions 12x8. The
three checkerboard PNGs have standard deviations 7, 8 and 9 in their 6x6 tiles:
only 7 is featureless because the threshold is strictly below 8. The whole frame
remains eligible even when featureless.

A device verifier must decode the source, apply orientation, produce every box and
square, and compare against these goldens before accepting its preprocessing.
PNG values are lossless. For JPEG, different decoders may round channel values;
allow at most 2 levels per RGB channel against the expected upright image and
crops, then run the real-phone embedding parity gate as well. Decoder tolerance
is not a tolerance for box coordinates, orientation or eligibility.

The Flutter image-tower verifier has not been implemented yet. These fixtures
alone do not prove device conformance; #100 remains open until the verifier's
suite consumes them. The Python contract test protects the corpus against server
preprocessing changes without running or downloading a model.
