# Nelson / Tasman pilot

Weedz is an open-source, non-commercial conservation project. This local pilot
tests incidental-plant screening on real, attributed iNaturalist photos. It is
an operational starting point, awaiting independent botanical review.

## Start and run

Requirements: Python 3.12 via uv, Node.js 20.9+ and pnpm, internet for the first
source/model downloads. PyTorch is resolved from its CPU index; other packages
come from PyPI. No GPU, inference provider or source API key is required.

```sh
pnpm --dir web install --frozen-lockfile
uv run main.py dev
```

The development command launches a real Temporal development server through the
Python SDK's local-server helper. It uses persistent SQLite state, not the
time-skipping test server. Activities run in a Python worker, with one acquisition
or inference activity at a time. The CLI downloads the official Temporal binary
on first use; an existing Temporal installation is not required.

| Service | Default |
| --- | --- |
| Next.js review | http://127.0.0.1:3001 |
| Python FastAPI | http://127.0.0.1:8000/docs |
| Temporal gRPC | localhost:7234 |
| Temporal UI | http://127.0.0.1:8234 |

Dedicated Temporal ports avoid interfering with another local Temporal instance.
`dev --pilot-dir`, `--api-port`, `--web-port`, `--temporal-port` and
`--temporal-ui-port` override defaults. `dev --no-web` runs the Python stack alone;
start the frontend separately with `pnpm --dir web dev`. `WEEDZ_API_URL` configures
the frontend's server-side Python origin and `NEXT_PUBLIC_TEMPORAL_UI_URL` its
workflow-history link. Both are supplied automatically by `dev`.

Queue a run from collection settings in the app or a second terminal:

```sh
uv run main.py discover --limit 12 --controls 1 --before 2024-12-31 --wait
```

`--limit` accepts 1–50 animal photos per region; `--controls` accepts 0–3 per
target species per region. The date is the observed/photo date cutoff, not an
upload cutoff. Photos uploaded later can belong to this historical-photo corpus.
Non-default connections use `discover --api-url` and `--temporal-address`.

Stop the development stack with Ctrl+C. Restart with the same `--pilot-dir` to
resume workflow history and retain photos and decisions. This stack binds its
services locally and provides no authentication. Reviewers type their name, which is
recorded with each decision as attribution, not verified identity. The stack is
intended for local development, not shared public hosting.

## What the workflow actually does

1. **Acquire bronze.** Query iNaturalist's Nelson council area **40493** and
   Tasman District **40494**, rather than the broader historic “Nelson” place
   11512. The incidental cohort uses Animalia, research-grade observations,
   photos and a capture-date cutoff. Separate queries request *Clematis vitalba*,
   *Cortaderia selloana* and *Ulex europaeus* reference observations.
2. **Select and retain.** Take one eligible photo per observation, up to each
   requested cap, in descending observed-date order from the first 100 results
   per query. Both metadata and photo licences must be CC0, CC BY or CC BY-NC.
   Preserve query/response snapshots, original subject, attribution and licence
   fields. Download the publisher's `large` image derivative, retain its bytes
   and SHA-256 checksum, and deduplicate source photo IDs within a run. This is
   a small, recent-first convenience sample, not a random regional survey.
3. **Screen.** Load [BioCLIP](https://huggingface.co/imageomics/bioclip) at revision
   `ce901ab3c6a913f9e9ef94ce6d27761069f4f01c`; retain the weights checksum.
   Correct EXIF orientation and convert to RGB. Score the whole image and four
   overlapping corner windows, each 60% of image width and height, with the
   checkpoint's image preprocessing. These windows have no measured camera pose
   or perspective rectification; the model's resize/centre-crop preprocessing can
   lose detail. This does not establish viewpoint invariance.
4. **Rank for inspection.** Compare each target's cosine similarity against the
   strongest comparison prompt in the same window. Comparisons include native
   clematis, toetoe, mānuka, broom, general vegetation, animals, open sky,
   water, shore and rock, plus the photo's own original-subject taxon (never a
   watchlist target, so references are not compared with themselves). Select the
   largest target-minus-comparison margin across windows and species. Save all
   window similarities, target results, dimensions and the selected window.
   A positive margin is not an established detection threshold. Every acquired
   animal photo remains reviewable, including low-ranked photos for missed-weed
   auditing. Whole-image scores are retained as the first direct-analysis comparison.
5. **Export and review.** Write a reproducible run manifest, then mark screening
   completed. Next.js exposes sources, windows, dates, location uncertainty,
   reference separation, filters and decisions. Confirm/reject/uncertain decisions
   and notes append local review history with the reviewer's name; activity
   retries preserve them. When reviewers' latest decisions differ, the photo is
   marked "Reviewers disagree" with each person's decision. Decisions saved before
   attribution existed show "Reviewer not recorded". The
   API export includes current decisions, while the completion manifest records
   the state at screening completion.

Acquisition, screening and export are separate Temporal activities, each with
timeouts, heartbeats and up to three attempts. Query snapshots and cached photos
resume interrupted acquisition; scored photos resume inference. A retry refuses
changed scoring configuration rather than mixing results from different methods.
Byte checksums are verified before inference. Inputs already cached for the first
time in a new run are checksummed as that run's input; this is not a publisher
signature or proof that a previously modified local cache matches the source.

No training, SAM segmentation, automatic augmentation, existing-occurrence
comparison, public posting or creation of new iNaturalist observations occurs.
Tiny/background-plant recall, skew tolerance and NZ field accuracy remain unmeasured.
The six requested references are source-labelled reference evidence, not six
independent expert-verified segmentation ground truths. Do not report classification
accuracy or discovery precision from these references alone.

## Files and evidence

Everything generated is ignored by Git:

| Path | Contents |
| --- | --- |
| `data/pilot/images/` | Downloaded large photo derivatives; source rights remain attached |
| `data/pilot/runs/<id>/*.json` | Raw source query snapshots and completion manifest |
| `data/pilot/discovery.sqlite3` | Runs, source records, raw scores, current decisions and review events |
| `data/pilot/temporal.sqlite3` | Persistent Temporal development-server history |
| `runs/nelson-tasman-review/` | Browser-check screenshots |

An observation coordinate describes the original observation, not a located weed.
Obscured/missing coordinates and positional accuracy remain explicit. Native
lookalikes, indistinct plants and locations with no nearby known weed record are
still reviewable. “Species visible” is a local reviewer decision about the suggested
species in a photo; it does not verify a new locality. Notes can record alternative
identifications; a structured corrected-species annotation is a subsequent step.
There is no gold dataset or measured discovery yield until independent reviews
and a low-ranked-photo audit are completed.

## Verification

```sh
uv run pytest -q
uv run ruff check
uv run ruff format --check
uv run pyright
uv run python scripts/check_file_length.py
pnpm --dir web check
pnpm --dir web build
```

Python tests use synthetic records and images and require no model or network.
They exercise source eligibility, uncertainty, separate reference labels,
comparison ranking, review persistence, retries and export failure handling.
The frontend regression check mocks delayed API responses to verify run switching.
The smoke check is read-only against a completed local pilot and verifies filters,
source-image loading, window toggling, export and mobile layout.

```sh
# One-time browser setup, if no compatible Chromium is available.
pnpm --dir web exec playwright install chromium
pnpm --dir web test
pnpm --dir web smoke
```

Set `PLAYWRIGHT_CHROMIUM_EXECUTABLE` to reuse an installed Chromium binary, or
`WEEDZ_WEB_URL` for a non-default frontend. Run builds with the dev frontend
stopped because both write Next.js build state. No screenshot step changes
botanical review decisions.
