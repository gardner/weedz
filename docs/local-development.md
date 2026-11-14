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
uv run main.py discover --limit 12 --controls 1 --after 2010-01-01 --before 2024-12-31 --wait
```

`--limit` accepts 1–50 animal photos per region; `--controls` accepts 0–3 per
target species per region. The date is the observed/photo date cutoff, not an
upload cutoff. Photos uploaded later can belong to this historical-photo corpus.
Non-default connections use `discover --api-url` and `--temporal-address`.
New runs screen with BioCLIP 2 by default. It is much better at telling native
lookalikes from weeds, but about 4.6× slower on CPU and downloads 1.7 GB on first
use. `--model bioclip` selects the original model. Runs saved earlier keep the
model they were screened with; see
[the comparison](../benchmarks/model-comparison.json). `--lookalikes N` (0–3) also acquires N photos of each declared lookalike taxon per
region: native clematis, toetoe, broom, mānuka and kānuka. They are screened as
a separate `lookalike` cohort, and the export's `lookalikes` summary shows how
often each passes as the weed it resembles.

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
2. **Select and retain.** By default (`--sampling stratified`), each region's
   animal photos are queried once per southern-hemisphere season (DJF, MAM, JJA,
   SON) between `--after` (default 2010-01-01, no earlier than 2008-01-01, when
   iNaturalist began) and `--before` (no later than today). Up to 100 results per
   season are taken. The cap is filled round-robin across seasons and years:
   years are visited in bit-reversed order, so even a small cap reaches both
   ends and the middle of the period, with seasons rotated so consecutive picks
   change both. Within a season, photos follow a stable hash order, with at most
   one photo per observer per day across both regions. The same snapshots
   therefore always give the same sample, and no single walk or week
   dominates. `--sampling recent` reproduces the first pilot's single
   newest-first query, and runs saved before this option existed are reported
   as `recent`. The export's `corpus_coverage` counts photos by year, season,
   observer and observer-day. Take one eligible photo per observation. Both
   metadata and photo licences must be CC0, CC BY or CC BY-NC.
   Preserve query/response snapshots, original subject, attribution and licence
   fields. Download the publisher's `large` image derivative, retain its bytes
   and SHA-256 checksum, and deduplicate source photo IDs within a run. Even
   stratified, this is a bounded sample, not a random regional survey: within
   each season the API still returns the newest 100 records.
3. **Screen.** Load [BioCLIP](https://huggingface.co/imageomics/bioclip) at revision
   `ce901ab3c6a913f9e9ef94ce6d27761069f4f01c`; retain the weights checksum.
   Correct EXIF orientation and convert to RGB. Score the whole image, letterboxed
   to a square, and overlapping **square** tiles covering every pixel (photos that
   would need more than 32 tiles have their long axis thinned, and the result's
   `coverage_complete` is false). Each tile's
   side is 60% of the short side, with at least 25% overlap. Square inputs survive
   the checkpoint's resize/centre-crop intact, so no edge strip is discarded.
   Tiles with no visible structure (greyscale std below 8, such as a black night
   strip) keep their scores but cannot be the winning window. The windows have no
   measured camera pose or perspective rectification, and downscaling still loses
   fine detail. This does not establish viewpoint invariance.
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
   attribution existed show "Reviewer not recorded". Each decision also records
   active review time on that photo. Time is counted only while the tab is
   visible, and it stops counting after 10 minutes without input. The export's
   `review_effort` reports minutes by decision and reviewer, and incidental minutes
   per "Species visible" photo. Untimed earlier decisions are listed as unmeasured,
   never as zero, and any untimed incidental decision withholds the per-photo rate.
   Photos where reviewers disagree are not counted as "Species visible".
   Confirmation is not a useful-finding measure. The **Audit sample** view lists
   a fixed random quarter of incidental photos, chosen from run and photo ids so
   screening rank plays no part. It hides the suggestion, search window and
   scores, and asks "Is any watchlist weed visible?". Audits are stored apart
   from suggestion reviews, and each auditor's blind finding is kept. A photo
   counts as a found weed if any auditor's blind finding names a species, and
   photos where auditors' findings differ are counted as disputed. A sampled
   photo is held out of each reviewer's ranked Incidental queue until that
   reviewer has audited it (with no name entered, every sampled photo is held),
   and each view keeps its own open photo, so no auditor sees its suggestion
   first. This is a workflow guard on a local, unauthenticated stack, not access
   control: names are not verified and anyone with the API can still read the
   scores. An audit counts as blind only if it is that auditor's first answer
   for the photo, and nobody reviewed the photo before it without having audited
   it first. The app lets a sampled photo be reviewed only after the reviewer's
   own audit, so any other earlier review (for example, one made before the
   audit sample existed) means the suggestion may have been seen. Other audits
   are left out of the findings and reported as `not_blind`, and the audit view
   disables the answers once you have audited a photo. Simply opening a photo is
   not recorded, so viewing outside this workflow cannot be detected. The
   sample itself comes from run and photo ids, so it is fixed from the moment a
   run starts. The run detail gives audit counts and who
   audited each photo; only the export lists findings.
   There is no calibrated detection threshold yet, so neither gives a hit or
   miss verdict. For each found weed the export reports the photo's 1-based
   rank in the incidental queue (by margin, highest first) out of all incidental
   photos, and whether the found species was the top suggestion shown. With a
   small sample this bounds, rather than estimates, how often weeds are ranked
   low. The
   API export includes current decisions and site-visit groups, while the completion manifest records
   the state at screening completion.

Acquisition, screening and export are separate Temporal activities, each with
timeouts, heartbeats and up to three attempts. Query snapshots and cached photos
resume interrupted acquisition; scored photos resume inference. A retry refuses
changed scoring configuration rather than mixing results from different methods.
Byte checksums are verified before inference. Inputs already cached for the first
time in a new run are checksummed as that run's input; this is not a publisher
signature or proof that a previously modified local cache matches the source.

### Compare with known records

```sh
uv run main.py references
```

This writes a new, never-overwritten snapshot of the
[DOC Weeds Observation Data 1983–2023](https://www.gbif.org/dataset/d986e335-a2e3-44f0-9606-845e2eb6081d)
(CC BY 4.0) to `data/pilot/references/`. It covers each watchlist taxon inside a
declared Nelson/Tasman bounding box. The snapshot records its retrieval date,
query, taxon keys and limitations. For each species, the run detail and export
report the distance and year of the nearest record and the number of records
within 5 km. This applies only to photos with public coordinates and known
accuracy within 5 km; other photos are marked not compared, with a reason. The
evidence panel shows this for the suggested species.

This is a distance comparison, not a novelty verdict. A missing record is not
an absence, and neither point locates a plant. The 14 November 2026 snapshot
(51 old man's beard, 4 pampas, 147 gorse records) is sparse near the pilot
photos: nearest records are typically 7–70 km away and mostly from the late
1990s. "No nearby record" therefore says more about the reference set than about
the plant.

No training, SAM segmentation, automatic augmentation, novelty classification,
public posting or creation of new iNaturalist observations occurs.
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
| `data/pilot/embeddings/` | Cached BioCLIP window embeddings, keyed by image bytes, pinned model, weights, library versions, preprocessing and window geometry; safe to delete |
| `data/pilot/references/` | Dated DOC weed-record snapshots from GBIF for comparison |
| `data/pilot/discovery.sqlite3` | Runs, source records, raw scores, current decisions and review events |
| `data/pilot/temporal.sqlite3` | Persistent Temporal development-server history |
| `runs/nelson-tasman-review/` | Browser-check screenshots |

An observation coordinate describes the original observation, not a located weed.
Obscured/missing coordinates and positional accuracy remain explicit. Native
lookalikes, indistinct plants and locations with no nearby known weed record are
still reviewable. Photos by the same observer on the same observed date, with public coordinates
within 250 m once both accuracy radii are allowed for, form one site visit. The
queue and export show the group, and the stats count independent visits.
Obscured, missing or undated records, and photos with unknown positional
accuracy or accuracy over 250 m, never link, so groups can be too small but are never invented. These
photos show “Site visit unknown” and are counted as “could not be grouped”,
never as independent visits. “Species visible” is a local reviewer decision about the suggested
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
The accessibility check runs axe-core with the WCAG 2.0–2.2 A/AA rules at desktop
and phone widths, and fails on any violation. It also audits the empty-queue
state and computes WCAG contrast directly for every text node and placeholder,
because axe leaves very short text (such as a count) unresolved and never checks
placeholders. It also makes a review decision by
keyboard alone, checking that the focused control is visibly marked. Muted text
colours were darkened within their hue to at least 4.5:1 contrast after the
first audit found 42 failures.
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
