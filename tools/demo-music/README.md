# Original Music3 documentary score

This isolated GPU environment leaves Weedz's CPU screening dependencies and the
Breeze narration environment unchanged. It generates original music from an
instrumental description and section tags, with no textual lyrics or named-artist
imitation. The runner uses physical **GPU 0 only** and refuses to overwrite audio
or provenance. Coordinate GPU ownership before starting it.

The [official integration](https://github.com/huggingface/diffusers/pull/14456)
merged before this run; released Diffusers 0.43.0 supports the model, so the model
card's older PR-install pin is unnecessary. `uv.lock` pins the tested runtime.
The model revision is `1b525ccb685ae809f33027c51c351eeb5833cf72`; only converted
Diffusers components are fetched, excluding duplicate original checkpoints.

From the repository root:

```sh
UV_PROJECT_ENVIRONMENT="$HOME/.cache/weedz-demo/tools/music3-venv" \
  uv sync --project tools/demo-music --locked
CUDA_VISIBLE_DEVICES=0 \
UV_PROJECT_ENVIRONMENT="$HOME/.cache/weedz-demo/tools/music3-venv" \
  uv run --locked --project tools/demo-music python tools/demo-music/main.py \
  --seconds 180 --seed 113 \
  --output /path/outside/the/repository/music3-score.wav
```

The exact pinned snapshot is downloaded when absent, then loaded locally before
component loading, avoiding mutable
component revisions embedded in the upstream model index. Generation uses
bfloat16, 30 flow-matching steps and a seeded CUDA generator. The tested RTX 5090
has 32 GiB VRAM; the runner requires 26 GiB free before loading. GPU 1 is untouched.
The raw PCM16 WAV is not normalized, stretched or faded. Its JSON sidecar records
the prompt, structure tags, revision, package/tool versions, duration, sample rate,
peak/RMS/full-scale fraction, GPU usage and checksum. A `.started.json` preserves
the request even if inference fails.

## Limitations and mixing

`--seconds` is an upper bound, not a promised duration. The first seed-112 take
ended at 57.423 seconds despite a 180-second bound; that raw take and its original
provenance are retained outside Git. Instrumental section tags encourage but do
not guarantee the absence of vocals. Screen/audition output before mixing.

Use the actual WAV/JSON sample rate: this pinned vocoder produces **44.1 kHz**,
while the cached model card mentions 32 kHz. If assembling distinct original
passages into a longer bed, retain every raw source and record crossfades/trims
in a separate assembly manifest. Keep the raw Breeze voice unchanged; mix only
the music bed to the required video duration/level.

## License and disclosure

Read the pinned [Music3 Community License](https://huggingface.co/MiniMaxAI/MiniMax-Music3/blob/1b525ccb685ae809f33027c51c351eeb5833cf72/LICENSE).
Weights/code are not redistributed with this runner. The license includes an
acceptable-use policy requiring clear disclosure for public machine-generated
content; the video credits identify the AI-generated instrumental as MiniMax
Music3. Generated music is not a guarantee of third-party rights clearance.

## Delivered three-minute bed

Two raw, distinct takes were generated: seed 112 (57.423 s, first seven-tag
structure) and seed 113 (133.445 s, the current longer structure). Their original
WAVs and JSON requests/results remain in `weedz-demo-artifacts/music/` outside
Git. Both used the same original instrumental caption and no textual lyrics.

The delivered `music3-conservation-180s-v1.wav` is assembled with:

```sh
UV_PROJECT_ENVIRONMENT="$HOME/.cache/weedz-demo/tools/music3-venv" \
  uv run --locked --project tools/demo-music python tools/demo-music/assemble.py \
  /path/to/music3-conservation-seed112-v1.wav \
  /path/to/music3-conservation-seed113-v2.wav \
  --output /path/outside/the/repository/music3-conservation-180s-v1.wav
```

Assembly uses a four-second linear crossfade, trims 6.868 seconds from the joined
tail, and applies two-second fade-in/four-second fade-out. The result is exactly
180 s, stereo 44.1 kHz PCM16, RMS 0.0917, peak 1.0. No looping, normalization,
silence padding or narration processing occurs. Source arrays/files are preserved;
insufficient material is refused. The `.assembly.json` records source checksums,
settings and the output checksum. The video mixer applies its own quiet bed gain.

CPU faster-whisper `base.en` with VAD found zero speech segments in both raw takes
and the assembled bed. The screen resampled only an in-memory mono copy to 16 kHz;
no raw audio changed. This is a heuristic check for intelligible speech, not a
listening guarantee that every voice-like texture is absent. Each `.asr.json`
records that limitation beside its result.

## Ten-track auditions

`auditions.json` contains ten distinct original quiet documentary prompts/seeds.
Tracks 7 and 10 request restrained percussion; the others vary felt-piano, guitar,
cello/string emphasis, harmony and tempo subtly. No named artist or textual lyrics
are requested. Prefer instrumental; model control cannot rule out voice-like texture.

```sh
CUDA_VISIBLE_DEVICES=0 \
UV_PROJECT_ENVIRONMENT="$HOME/.cache/weedz-demo/tools/music3-venv" \
  uv run --locked --project tools/demo-music python tools/demo-music/main.py \
  --seconds 180 --batch-output /path/outside/git/auditions-v1
```

The model loads once. Each request has its own seeded generator, raw output and
provenance, then releases output tensors/allocator cache before the next request.
Diffusers also resets stateful component caches between calls. The model itself
stays loaded. Requested seconds remain an upper bound: do not pad or loop a take
to claim a longer composition. Actual WAV frames/durations/checksums are recorded.
The batch writes an incremental HTML listening index, M3U playlist and JSON catalog,
plus all prompts and the full pinned model license outside Git. Existing outputs
are refused before model loading. A failed generation leaves its started request
for diagnosis; it is never silently replaced or represented as completed.
