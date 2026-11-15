# Reproduce the value-first website video

`docs/demo/script-v3.md` is the readable script; `docs/demo/narration-v3.json`
is the timed edit. The film opens with conservation value, follows real SAM2.1
masks and BioCLIP comparisons into human review, and mentions mobile only as a
closing next step. Original screening scores retain their queue ordering;
segmentation scores remain separate exploratory evidence.

First follow `docs/demo-capture.md` for the licensed public-photo snapshot and
`docs/demo-segmentation-capture.md` for real pipeline captures. Generate the eight
script utterances with the native Breeze runner, named `scene-01.wav` through
`scene-08.wav`. Use `--gpu 1` if Music3 is generating auditions on GPU 0. Keep the
native mono PCM16 / 24 kHz audio untouched. The script includes its filenames and
scene lengths; the renderer rejects speech that does not fit.

Transcribe those exact WAVs with word timestamps. The transcript JSON has a
`scenes` array. Every entry requires `scene` (a unique one-based integer, not the
script ID string), `file` (the actual selected narration filename), and `segments`,
each containing timestamped `words` with `word`, `start` and `end`. For example,
this abbreviated schema example represents the first scene, not a full transcript:

```json
{"scenes":[{"scene":1,"file":"scene-01.wav","segments":[{"words":[{"word":"Help","start":0.1,"end":0.4}]}]}]}
```

Provide one entry per script scene in script order. A custom `audio_file` override
must use that selected take's filename in `file`; identities are checked against
the actual narration and are never inferred from list position. Missing, invalid
or duplicate identity fields fail before output creation. ASR provides timing
anchors; captions use the canonical script. Inspect pronunciation, timing and
spelling rather than treating ASR as proof.

```sh
uv run python tools/demo-video/render_web_demo.py \
  --captures /absolute/path/to/artifacts/captures \
  --pipeline /absolute/path/to/artifacts/pipeline-sam21-web-final \
  --audio /absolute/path/to/artifacts/narration-native \
  --transcript /absolute/path/to/artifacts/narration-native/raw-transcripts.json \
  --credit-font /absolute/path/to/NotoSansCJKjp-Regular.otf \
  --ffmpeg /absolute/path/to/ffmpeg \
  --output /absolute/path/to/artifacts/video/weedz-demo-v3
```

The output contains a silent 180-second picture, unchanged native voice samples
with silence between utterances, burned captions, companion SRT, source credits
and inspection frames. The website recording plays at its recorded speed and
shows saved outputs from completed real inference. The masks are real model
outputs; playback does not claim to measure inference latency. No review decision
is staged, no app screen is mocked, and no image pan or zoom is used.

Use `tools/demo-video/mix_demo.py` with an actual full-length instrumental, retain
its source/licence provenance and record the chosen take in the companion credits.
The delivered edit currently uses the earlier 180-second conservation bed while
ten new songs are auditioned. Update checksums after the mix and any credit edits.
Check the final container and full decode, inspect captions and credits, and keep
all generated media, captures, photos and model checkpoints outside Git.

New renders require a completed pipeline capture receipt: `capture-manifest.json` must
contain `captureSuccess: true` and an empty `browser_errors` list. The capture helper
publishes that success marker only after browser closure and successful encoding.
Historical media is not rewritten or silently given new proof fields. For a new render,
reproduce the capture with the documented helper if the older receipt lacks those fields.

The renderer checks every requested pipeline video frame and the decoder exit status.
The 15.6-second segment is sampled at 24 fps with its fractional final interval retained
(`fps` EOF pass), giving 375 required frames; truncated footage aborts rather than freezing.

Fresh captures now require a closed success receipt with SHA-256 pins for every
consumed pipeline PNG/video and model-evidence JSON. Rendering checks those bytes
and uses private copies, including the separately verified source photograph.
Photo and observation-data credits remain separate; CC BY-NC observation data is
retained for this explicitly non-commercial demonstration. Generic codes do not
imply a licence version. Existing films and historical hashless receipts remain
unchanged; a fresh render requires new complete receipts and snapshot rights.

Optional `--ui-font` and `--ui-bold-font` select existing regular/bold UI fonts.
These and `--credit-font` are loaded before output creation. No OS installation
or historical media regeneration is part of this source-tooling update.


The fixed film accepts only the semantic recipe in
`tools/demo-video/pipeline-profile.json`: the recorded SAM2.1 Hiera tiny code,
checkpoint, proposal/filter/transform policy and BioCLIP2 model, weights,
preprocessing and ranking policy. The source/evidence must match those pins even
if a different experiment reuses the run/photo IDs. Machine names, device IDs and
runtime versions are retained as evidence but are not additional film claims.
This contract describes the originally recorded recipe; it does not replace
historical stamps with today's settings or newly attest old model weights.
