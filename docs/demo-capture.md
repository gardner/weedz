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
and modification, with snapshot-relative image paths. Explicit `--run` selections
must exist and be completed; an invalid selection fails without a successful manifest.
Include those attributions in the video's credits/description
or companion credit document. Never copy exact locations into production assets.

The capture server binds loopback port 8312 and refuses every non-GET/HEAD request.
The real, production-built Next application binds loopback port 3012 and targets
only that snapshot. The orchestrator owns both process groups and stops only its
children after recording. No Temporal workflow, live review decision or intake
request is started. Playwright captures actual navigation, selection and search-
window toggling as 1920×1080 PNGs and a closed WebM; no HTML mock is substituted.

## Actual Flutter settings and deletion

Use an isolated worktree with Flutter's web bootstrap (`flutter create --platforms
web --project-name weedz .` inside mobile), then build the actual application:

```sh
cd mobile
flutter build web --release --dart-define=WEEDZ_INTAKE_BASE_URL=https://127.0.0.1:8443
cd ..
uv run python scripts/capture_live_flutter.py \
  --output "$HOME/src/weedz-demo-artifacts/captures/live-flutter" \
  --source-pilot "$HOME/src/weedz/data/pilot" \
  --public-image "$HOME/src/weedz-demo-artifacts/captures/assets/gorse-reference.jpg" \
  --ffmpeg /absolute/path/to/full/ffmpeg
```

The helper runs the release-compiled app with its actual secure-storage web plugin
and real HTTPS intake in a private temporary directory. A self-signed loopback
certificate is accepted only by the local capture browser. A read-only public pilot
record supplies its original model score/revision and attributed CC BY gorse crop;
no location or private image is included. The helper submits that report through
the real API, securely enrolls the actual app, then starts recording only after
the token form is gone. The app performs DELETE /submitter; receipt retry,
revoked upload access and actual database/image erasure are verified afterward.
Temporary credentials, browser state, certificate and intake are destroyed.

The output includes real PNG states, a closed `live-flutter-settings.webm`, and
verification JSON without credentials. This shows browser app settings/deletion,
not native model inference or an integrated scan-to-approval flow. No app state,
transport, screen or successful response is mocked. Keep source photo credit with
the video; the gorse source is Saryu Mae 前 朝琉, CC BY,
https://www.inaturalist.org/observations/250240131.

## Verification

`tests/test_demo_snapshot.py` checks that a source database's bytes remain unchanged,
model scores survive, copied human decisions disappear, coordinates are absent
from both the manifest and vacuumed SQLite bytes, and copied pixels have no EXIF.
Capture metadata records browser errors; the recording is closed before delivery.
Inspect the screenshots and video before adding them to the final edit. Do not
commit video, audio, downloaded photos, screenshots or local pilot snapshots.
