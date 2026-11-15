# Capture the real website segmentation flow

Requires the segmentation experiment from #130 and the shared `scripts/demo_paths.py`
output guard from the demo helpers. Generate an eligible public experiment using
[the actual model instructions](segmentation-experiment.md) first. Model outputs,
photos, screenshots and video must remain outside Git.

Serve only that isolated public experiment on loopback in one terminal:

```sh
uv run python -c 'import sys; from pathlib import Path; import uvicorn; from weedz.discovery.api import create_app; uvicorn.run(create_app(Path(sys.argv[1])),host="127.0.0.1",port=8022)' /absolute/experiment
```

Build and run the actual production website in another terminal:

```sh
pnpm --dir web install --frozen-lockfile
pnpm --dir web build
WEEDZ_API_URL=http://127.0.0.1:8022 pnpm --dir web exec next start --hostname 127.0.0.1 --port 3022
```

Then capture the real reference-photo controls:

```sh
uv run python scripts/capture_segmentation_ui.py \
 --output /absolute/outside-git/NEW-capture-folder \
 --web-url http://127.0.0.1:3022 \
 --ffmpeg /absolute/path/to/full/ffmpeg
```

The narrowly scoped helper selects the public gorse reference (iNaturalist photo
447484684), hides the baseline search window using its real checkbox, then records
original → two actual model masks with independent view scores → the actual review
controls → original. It saves no review decision and sends only GET requests.
Original bytes and mask PNGs come from the real API's saved model evidence; no
mask, HTML screen, transport or score is synthesized. Browser errors fail capture.
The encoder preserves actual browser frame timing in a silent H264 MP4.

This UI recording replays **saved outputs from previously completed real inference**;
it does not show a model computing live. The accompanying `capture-manifest.json`
records that distinction, phase timings, the actual model/checkpoint/configuration,
source creator/licence/URL and the upright source pixel checksum. `model-evidence.json`
contains the real API evidence. The public reference is not an independently
reviewed incidental discovery, and mask quality is not identification confidence.

Inspect the closed video and PNGs before editing. The source creator includes
Japanese characters; install/register an existing suitable OFL CJK font in the
user-local font directory if the browser otherwise shows missing glyphs. No system
package installation or image alteration is needed. Credits must retain the full
creator string and source/licence from the manifest even when composing a cropped
UI view. Capture assets are never committed.

The launcher refuses existing output directories and any Git worktree. It resolves
paths before running the project from its own root. The current compared-species
heading is selected semantically; no review action is submitted. Recording waits
at least 16 seconds so the strict 15.6-second edit has complete source frames.
The closed receipt pins consumed media/model-evidence bytes and carries both photo
and observation-data rights, observer credit and the exact encoded source-image
SHA-256. Existing recordings/receipts are not retroactively upgraded.

The capture explicitly selects `segmentation-experiment-v1` through the real saved-run
control, selects photo 447484684 by its run-qualified image URL, and waits for that
exact image in the evidence stage. The receipt and saved model evidence must agree
on run/photo identity, source image/credit and both model stamps before rendering.
