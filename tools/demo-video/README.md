# Reproduce the demo edit

The rendered movie, source photos, captures, audio and model weights live outside
Git. The renderer refuses an output directory inside any Git worktree and refuses
to reuse an existing output directory. The code and edit script are the only
production inputs committed here.

First follow `docs/demo-capture.md` and `tools/demo-audio/README.md`. Generate the
eight utterances in `docs/demo/narration.json`, retaining the native Breeze output.
The delivered edit uses `breeze-intro-v1.wav`, `scene-02-raw-v3.wav` through
`scene-08-raw-v3.wav`, with `scene-06-raw-v4.wav` replacing scene 6 when present.
The replacement uses the same text and voice reference, seed 43, to check the
sentence ending. Each source WAV has its own generation metadata. Native output
is mono PCM16, 24 kHz. No voice EQ, normalization, compression or speed changes
are applied. The master inserts silence between the original, unchanged samples;
the movie receives ordinary delivery encoding at the final mixing stage.

Caption alignment uses the canonical script and measured Whisper word timestamps
in `audio/raw-v3-transcripts.json`, an eight-item array. Each item contains `scene`,
`file`, `text`, and `words` with `word`, `start`, `end` in seconds relative to its
utterance. Run the `faster-whisper` dependency in the isolated audio environment
on native PCM converted to a temporary 16 kHz array. Retain native source WAVs.
Match the correct transcript to each selected utterance. Review caption timing
and spelling against the delivered movie; ASR alignment is approximate.

Use an existing FFmpeg build with libx264. No OS installation is required on the
production machine: a standalone FFmpeg/ffprobe pair was already available.
For full creator names, supply Noto Sans CJK Japanese Regular from
[notofonts/noto-cjk](https://github.com/notofonts/noto-cjk/tree/main/Sans/OTF/Japanese),
licensed under the [SIL Open Font License](https://github.com/notofonts/noto-cjk/blob/main/LICENSE).
DejaVu Sans is used for all other typography. Keep downloaded fonts outside Git.

From the repository root:

```sh
uv run python tools/demo-video/render_demo.py \
  --captures /absolute/path/to/artifacts/captures \
  --audio /absolute/path/to/artifacts/audio \
  --ffmpeg /absolute/path/to/ffmpeg \
  --credit-font /absolute/path/to/NotoSansCJKjp-Regular.otf \
  --output /absolute/path/to/artifacts/video/weedz-demo-v1
```

This produces a silent 180-second `picture.mp4`, a native narration master,
burned-in captions plus an SRT, eight inspection frames, the actual timeline,
full attribution and checksums. The real review recording plays once within the
review scene, followed by actual screenshots. The mobile views are production
Flutter widget captures explicitly marked as prototypes. Search windows are
schematic; their boxes do not claim measured detections. Pilot sample counts
describe the full benchmark, not the curated capture subset.

Mix the original instrumental quietly under the narration:

```sh
uv run python tools/demo-video/mix_demo.py \
  --render /absolute/path/to/artifacts/video/weedz-demo-v1 \
  --music /absolute/path/to/artifacts/music/music3-conservation-seed112-v1.wav \
  --ffmpeg /absolute/path/to/ffmpeg \
  --output /absolute/path/to/artifacts/video/weedz-demo-v1/weedz-demo.mp4
```

This retains the native narration master separately, adds music at gain 0.055,
and uses a 48 kHz stereo AAC 256 kbps delivery track. The voice gain stays at one;
mix normalization is disabled. Captions are burned into the picture and included
as an optional English subtitle track. Keep the native master when sharing
audio so listeners can hear exactly what Breeze generated. Attach
the instrumental's provenance, update final checksums, and verify the final
container with ffprobe. Listen to the whole movie and inspect the beginning,
scene changes, captions and credits. Include `credits.json` when sharing it.
Do not commit any generated media or checkpoint to the repository.
