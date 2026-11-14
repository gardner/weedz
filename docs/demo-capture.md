# Reproduce real product captures for the demo

Keep every image, SQLite copy and video outside git. The helpers refuse artifact
folders within a git worktree. They require the existing Python environment,
web project dependencies/Playwright browser and Flutter SDK; they do not install
system packages or alter the live pilot.

## Review web

```sh
uv run python scripts/capture_demo_snapshot.py \
  --source-pilot "$HOME/src/weedz/data/pilot" \
  --output "$HOME/src/weedz-demo-artifacts/captures/review-snapshot"
pnpm --dir web install --frozen-lockfile
pnpm --dir web build
uv run python scripts/capture_review_demo.py \
  --snapshot "$HOME/src/weedz-demo-artifacts/captures/review-snapshot" \
  --output "$HOME/src/weedz-demo-artifacts/captures/web-final"
```

The snapshot helper opens the original discovery database with SQLite `mode=ro`
and uses the backup API, preserving a consistent view including committed WAL
contents. It never initializes a Store on the source, reads intake databases,
opens reviewer-token stores, or writes source images. All source operations are
reads. The independent destination is then filtered to completed, scored CC0/
CC BY photos. Decoded upright pixels are copied as metadata-free lossless PNGs;
original scores, margins, suggestions, window boxes and model stamps are retained.
Only coordinates are withheld. Human notes and review events are erased from the
copy with secure deletion and vacuuming; live decisions remain unchanged.

**The resulting 18-photo subset is for visual demonstration, not a pilot result.**
Do not narrate its displayed counts as full-pilot performance. The run detail and
`capture-provenance.json` explicitly disclose the subset and coordinate removal.
The manifest lists every potentially visible photo's creator, licence, source URL
and modification. Include those attributions in the video's credits/description
or companion credit document. Never copy exact locations into production assets.

The capture server binds loopback port 8312 and refuses every non-GET/HEAD request.
The real, production-built Next application binds loopback port 3012 and targets
only that snapshot. The orchestrator owns both process groups and stops only its
children after recording. No Temporal workflow, live review decision or intake
request is started. Playwright captures actual navigation, selection and search-
window toggling as 1920×1080 PNGs and a closed WebM; no HTML mock is substituted.

## Flutter approval and settings

Use a licensed public JPEG whose attribution accompanies the demo. Then run:

```sh
cd mobile
WEEDZ_CAPTURE_DIR="$HOME/src/weedz-demo-artifacts/captures/flutter" \
WEEDZ_DEMO_IMAGE="$HOME/src/weedz-demo-artifacts/captures/assets/gorse-reference.jpg" \
WEEDZ_FLUTTER_SDK="$HOME/.local/opt/flutter" \
  "$HOME/.local/opt/flutter/bin/flutter" test test/demo/capture_widgets_test.dart
```

This opt-in widget test is skipped by ordinary tests. It renders the production
`ApprovalScreen` and `DeviceSettings`, including real theme, layout and Roboto/
MaterialIcons fonts, into 1080×2160 PNGs. The report is synthetic and contains no
location or capture time; its illustrative score matches the cited public pilot
reference. An in-memory test enrollment and no-network deletion transport show
confirmation and recoverable pending state. Every capture has a visible prototype
banner. No upload, deletion request or native model inference occurs. These are
real Flutter widget renders, not proof of a finished native inference pipeline.

## Verification

`tests/test_demo_snapshot.py` checks that a source database's bytes remain unchanged,
model scores survive, copied human decisions disappear, coordinates are absent
from both the manifest and vacuumed SQLite bytes, and copied pixels have no EXIF.
Capture metadata records browser errors; the recording is closed before delivery.
Inspect the screenshots and video before adding them to the final edit. Do not
commit video, audio, downloaded photos, screenshots or local pilot snapshots.
