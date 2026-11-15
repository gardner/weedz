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
`scenes` array; each scene contains `segments`, each with `words` carrying `word`,
`start` and `end`. ASR provides timing anchors; captions use the canonical script.
Inspect pronunciation, timing and spelling rather than treating ASR as proof.

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
