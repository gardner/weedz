# Reproduce the demo edit

The rendered movie, source photos, captures, audio and model weights live outside
Git. The renderer refuses an output directory inside any Git worktree and refuses
to reuse an existing output directory. The code and edit script are the only
production inputs committed here.

First follow `docs/demo-capture.md` and `tools/demo-audio/README.md`. Generate the
eight utterances in `docs/demo/narration.json`, retaining the native Breeze output.
The edit uses `breeze-intro-v1.wav` and `scene-02-raw-v3.wav` through
`scene-08-raw-v3.wav`, with explicit `audio_file` overrides in the script for
updated scenes. Each source WAV has its own generation metadata. Native output
is mono PCM16, 24 kHz. No voice EQ, normalization, compression or speed changes
are applied. The master inserts silence between the original, unchanged samples;
the movie receives ordinary delivery encoding at the final mixing stage.

Caption alignment uses the canonical script and measured Whisper word timestamps
in `audio/raw-final-transcripts.json`, an eight-item array. Each item contains `scene`,
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
  --transcript /absolute/path/to/artifacts/audio/raw-final-transcripts.json \
  --mobile-captures /absolute/path/to/artifacts/captures/live-flutter \
  --ffmpeg /absolute/path/to/ffmpeg \
  --credit-font /absolute/path/to/NotoSansCJKjp-Regular.otf \
  --output /absolute/path/to/artifacts/video/weedz-demo-v1
```

This produces a silent 180-second `picture.mp4`, a native narration master,
burned-in captions plus an SRT, eight inspection frames, the actual timeline,
full attribution and checksums. The real review recording plays once within the
review scene, followed by actual screenshots. The app footage records the
release-compiled Flutter application in Chromium using actual secure storage and
HTTPS deletion against an isolated intake. No widget fixture, mock transport,
seeded app state or demo banner is used. No native inference or camera-roll scan
is shown. Search windows and report fields explain the pipeline; the boxes do not
claim measured plant boundaries. Photos remain static, with no Ken Burns effect.
Pilot sample counts
describe the full benchmark, not the curated capture subset.

Mix the original instrumental quietly under the narration:

```sh
uv run python tools/demo-video/mix_demo.py \
  --render /absolute/path/to/artifacts/video/weedz-demo-v1 \
  --music /absolute/path/to/artifacts/music/music3-conservation-180s-v1.wav \
  --ffmpeg /absolute/path/to/ffmpeg \
  --output /absolute/path/to/artifacts/video/weedz-demo-v1/weedz-demo.mp4
```

This retains the native narration master separately, adds music at gain 0.055,
and uses a 48 kHz stereo AAC 256 kbps delivery track. The voice gain stays at one;
mix normalization is disabled. Captions are burned into the picture; the separate
English SRT is retained alongside it. The MP4 has only picture and audio streams,
avoiding players rendering a second subtitle layer over the burned captions.
Keep the native master when sharing
audio so listeners can hear exactly what Breeze generated. Attach
the instrumental's provenance, update final checksums, and verify the final
container with ffprobe. Listen to the whole movie and inspect the beginning,
scene changes, captions and credits. Include `credits.json` when sharing it.
Do not commit any generated media or checkpoint to the repository.

The mixer requires the selected score's adjacent `.assembly.json` and verifies
its encoded WAV SHA-256 before encoding. It gives FFmpeg a private checked copy
so replacing the original during mixing cannot inherit the Music3 attribution.
The delivered timeline contains narration basenames only; full paths are retained
only in memory for reading the local source audio.

Capture evidence must describe a completed, error-free recording. The live Flutter helper
checks its owned HTTPS child and per-invocation identity before using the local intake.
It writes `live-capture.json` with `captureSuccess: true` only after browser shutdown and
successful video encoding, with empty browser errors and verified 201/200/401 API outcomes.
The renderer requires that receipt as well as the separate zero-body/zero-crop erasure proof.
Older receipts without the success/status fields are not silently upgraded; reproduce a
new capture with the documented helper if making a new render. Existing delivered films
remain historical artifacts and are not modified by these source checks.

Both web and mobile source-video segments must decode their full requested frame counts
and exit successfully. Missing/truncated frames or decoder failures abort the render;
they are never replaced with frozen or blank footage.

UI typography defaults to the producing machine's DejaVu Sans regular/bold files.
On another system, pass `--ui-font /path/to/regular.ttf` and
`--ui-bold-font /path/to/bold.ttf` using existing readable font files. Both fonts
are loaded before creating the output or starting a render; no OS installation
is required. `--credit-font` remains separate for source-credit character coverage.

New browser capture receipts bind the three consumed web media files by SHA-256,
recorded only after capture closure. Rendering verifies them and consumes private
checked snapshots. Mixing likewise verifies `picture.mp4` and the native narration
against the render's `sha256.json`, then reads checked private copies. Replacement
media cannot inherit an earlier receipt. Historical hashless receipts and delivered
films remain untouched; a fresh render requires freshly produced complete receipts.
The same checksum/private-copy contract covers the mobile WebM and deletion
screenshot. The snapshot server copies only manifest-listed image bytes whose
checksums match their source credits. The credit font is loaded during preflight
alongside UI font checks, before output creation or encoding.
New snapshot manifests also pin the fully closed sanitized database bytes; the
server verifies and copies those exact bytes before initializing its private app.
Mobile erasure and recording receipts must share the same nonempty capture instance.
