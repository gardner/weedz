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
resume workflow history and retain photos and decisions. By default (`--access
local`) the stack binds its services to this computer and asks no one to sign in.
Reviewers type their name, which is recorded with each decision as attribution, not
verified identity. For reviewers elsewhere, see [Remote reviewers](#remote-reviewers).

### Remote reviewers

Partner specialists and volunteers can review from their own browser without
running the stack. Each one gets a personal invite token. Under `--access tokens`,
every request needs a token, and every record (review, audit, finding,
judgement, referral, lead selection, study version and study link) is saved
under the name the token was issued to. The API refuses a record that names
anyone else, with 403.

Invite, list and revoke reviewers from the command line on the host:

```sh
uv run main.py reviewers add --name "Ana Smith"   # prints the token once
uv run main.py reviewers list                     # never shows tokens
uv run main.py reviewers revoke --id 3            # refused from the next request
```

Send each token privately, for example in a password manager share or an
end-to-end encrypted message, not in a shared channel. A token is
`weedz_<id>_<secret>`: 256 random bits. Only the SHA-256 of the secret is kept,
in `access.sqlite3` in the pilot folder (owner-only permissions). It is kept apart
from `discovery.sqlite3` so that copying or sharing the evidence store never
carries credentials. Tokens are compared in constant time. They are never logged,
returned by the API, or printed again after `add`. Revoke a token that has been
lost or shared, then send a new one. All `reviewers` commands take `--pilot-dir`.

Start the stack with sign-in required:

```sh
uv run main.py dev --access tokens
```

To queue runs from the command line on the host, set your own token in the
environment, never as an argument: `WEEDZ_REVIEWER_TOKEN=weedz_… uv run main.py
discover …`.

The API always listens on 127.0.0.1; only the review app talks to it. The review
app also listens on 127.0.0.1 unless `--web-host` is given. `dev` refuses a
non-loopback `--web-host` without `--access tokens`. Put an HTTPS reverse proxy in
front of the review app on the same machine, and leave everything else
unexposed. With [Caddy](https://caddyserver.com/), which obtains and renews the
certificate automatically, the whole configuration (`Caddyfile`) is:

```
review.example.org {
	reverse_proxy 127.0.0.1:3001
}
```

Reviewers open `https://review.example.org` and paste their token into the
sign-in form. The app exchanges it for an `HttpOnly`, `SameSite=Strict` session
cookie, so page scripts never hold it. The cookie is marked `Secure` on any
non-loopback host or when the proxy sends `X-Forwarded-Proto: https`. Plain HTTP
beyond this computer cannot sign in. The form will not send a token from a page
that is not a secure context, and the app refuses a sign-in that did not arrive
over HTTPS or from this computer. Keep the proxy's defaults of passing the
original `Host` header through and setting `X-Forwarded-Proto`. The app's proxy refuses writes, and sign-ins,
that a browser marks as started by another site. Sign out clears the cookie in
that browser only; to stop a token working everywhere, revoke it.

What this does not do yet: there are no roles, so any signed-in reviewer can
queue a regional run or edit a study, as anyone can locally. Tokens do not
expire until revoked, and sign-ins are not rate-limited (guessing a 256-bit
token is infeasible). The Temporal UI and the API docs are not served to remote
reviewers: the docs are switched off under `--access tokens`. `dev` still runs
`next dev`. A VPN or tailnet (WireGuard, Tailscale) can sit in front as an extra
network layer, but it identifies devices, not reviewers, so keep the tokens.
Hosting, the domain and any single sign-on provider are the project owner's
decisions; see issue #31. The sharing rules are unchanged: obscured coordinates
are never served in either mode, and nothing is published on anyone's behalf.

### Reports from devices

A future phone app (its platform is issue #50) sends only the reports a person
has approved on the phone. The server side of that (issue #57) is a separate
API, never mounted on the review API. Each device is a *submitter*, a different
principal from a reviewer: its token is `weedzsub_<id>_<secret>`, kept hashed in
`data/intake/submitters.sqlite3`. A reviewer token is never accepted for
intake, and a submitter token never works on the review API.

```sh
uv run main.py intake add --label "Pilot phone 1"   # prints the token once
uv run main.py intake list                          # never shows tokens
uv run main.py intake revoke --id 3                 # its reports are kept
uv run main.py intake withdraw --submitter 3 --report <uuid>  # at the person's request
uv run main.py intake serve --port 8300             # loopback; put HTTPS in front
```

The contract, with every request sending `Authorization: Bearer weedzsub_…`:

- `PUT /reports/{uuid}` takes a version-1 report as JSON
  (`src/weedz/intake/schema.py`). The device generates the UUID, so a retry
  returns the same receipt (200, or 201 the first time). Different content
  under a used id gets 409, and a withdrawn id gets 410. Unknown fields, NaN,
  a location without its accuracy, a capture time without a timezone, and
  anything but a declared target taxon are refused with 422. A body over 2 MB
  is refused with 413.
- An optional cropped `image` (base64 JPEG, PNG or WebP, at most 1 MB and
  4096×4096 pixels) is accepted only with `consent.image: true` and a licence
  the collection admits (`cc0`, `cc-by` or `cc-by-nc`). Otherwise the report is
  refused and nothing is stored. The server keeps only the pixels, re-encoded
  as a fresh JPEG, so EXIF (including GPS and camera serials), XMP, ICC
  profiles and comments never reach storage.
- `consent` records what the person agreed to, under a published wording
  (`wording_version`, from [the consent text](report-consent.md)). An unpublished
  version is refused with 422. With a photo, `consent.uses` lists what it may be
  used for. It must include `review`; `evidence`, `agencies`, `public` and
  `training` are separate opt-ins. A report without a photo lists no uses. An
  optional `credit` names the person in the attribution (#60).
- `GET /reports/{uuid}` returns the submitter's own receipt. `DELETE` withdraws
  the report: its image is deleted and its content erased (zeroed in the
  database file), leaving only ids, times, the consent wording and the uses
  that were permitted (never the credit name), so a retry can't bring it back
  and the history shows what was agreed and when it ended. Receipts show the
  wording and uses.
  `GET` for another submitter's report is a 404, the same as a missing one.
  Device `DELETE` records a tombstone even before an upload arrives, so a late
  `PUT` gets 410. Creating a new tombstone counts toward the daily report
  budget (429 means retry after `Retry-After`); withdrawing an existing
  report or repeating a withdrawal is always allowed. This is scoped to the authenticated submitter, even when
  another device uses the same report id. If a device
  token is lost or revoked, the operator can withdraw its reports with
  `intake withdraw`. An unknown id is an error. If the report may still be on
  its way, `--not-yet-received` records the withdrawal, so the report is
  refused (410) if it arrives.
- One submitter's uploads and withdrawals are handled one at a time. A body
  that stops arriving for 30 seconds gets 408, so a phone that drops off
  mid-upload doesn't hold up its own retries or withdrawals. A slow but steady
  upload is never cut off.
- Each submitter may send 100 reports and 50 MB of images per rolling 24 hours,
  including withdrawn reports and crops refused after decoding. Past that, the
  server answers 429 with `Retry-After`. Usage records (ids, times and stored
  crop sizes) are deleted once they leave the window.

Reports are kept in `data/intake/reports/` (owner-only), apart from the
discovery evidence. Nothing serves them to reviewers or publishes them yet:
`ReportStore.active()` is where specialist review would read them (issue #58).
Hosting, accounts and enrolment, the retention period, and whether images are
uploaded at all are the project owner's decisions; see issues #55 and #57.

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
   metadata and photo licences must be CC0, CC BY or CC BY-NC, and the store
   refuses any other ([sharing](#sharing-licences-and-location-privacy)).
   Preserve query/response snapshots, original subject, attribution and licence
   fields. Download the publisher's `large` image derivative, retain its bytes
   and SHA-256 checksum, and deduplicate source photo IDs within a run. Even
   stratified, this is a bounded sample, not a random regional survey: within
   each season the API still returns the newest 100 records.
3. **Screen.** Load the run's pinned model and record its key, revision and
   weights checksum. New runs use [BioCLIP 2](https://huggingface.co/imageomics/bioclip-2)
   at revision `2957b322090f9cb17ae72c71981c7218a28d81e0`. `--model bioclip` and
   runs saved earlier use [BioCLIP](https://huggingface.co/imageomics/bioclip) at
   `ce901ab3c6a913f9e9ef94ce6d27761069f4f01c`. The first BioCLIP 2 run downloads
   1.7 GB, and the worker heartbeats throughout so a slow download is not
   mistaken for a stalled activity.
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
   **What a score means** is declared per model, pinned checkpoint and ranking
   revision in `src/weedz/discovery/score_meaning.py`, and served as the run's
   `score_meaning` (run detail, export and completion manifest). A declaration
   such as `bioclip-2/ranking-4/meaning-1` states what the margin ranks, what it
   does not mean (not a probability; positive is not present and negative is not
   absent; not comparable across models or ranking revisions), that no threshold
   or abstention rule has been chosen, and the source-labelled evidence from
   `benchmarks/model-comparison.json` (a test keeps the numbers equal to the
   benchmark). An operating point may only be chosen on reviewed and
   blind-audited development runs, then fixed as a new meaning version before
   any final test. Screening pins each run to the declaration current when it
   started (the run's model metadata records its `score_meaning` id, and a retry
   keeps it), and declarations are never edited, so a new version never changes
   an earlier run's meaning. A run screened under a configuration with no
   declaration is pinned as undeclared (`null`), so a declaration added later
   cannot claim it. Runs screened before pinning keep their configuration's
   first declaration. Any other configuration, such as runs scored under ranking
   revisions 2 or 3, is served with "no declared meaning": compare its scores
   only within that run. The review desk shows each species' margin in words
   beside the suggestion, with the declaration behind "What this score means";
   the blind audit view shows neither.
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
   own audit, so any other earlier review, recorded finding, judgement, referral
   or referral answer (for example, one made before the audit sample existed)
   means the suggestion may have been seen. Other audits
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
6. **Record a different or missed plant.** In the evidence panel, *Record a
   different or missed plant* opens a form for a structured finding, kept apart
   from the reviewer's decision and from blind audits. A finding is a
   *correction* (the plant is a different species from the suggestion; only
   offered when there is a suggestion, and never the suggested species itself,
   whether picked or typed by its scientific or common name)
   or an *addition* (a plant the screening didn't suggest). It names one
   watchlist species or an other taxon typed as free text. Free text is stored
   verbatim and never mapped to a watchlist species, even when it reads "gorse".
   An optional box marks the plant's visible extent in original image pixels.
   Drag on the photo to draw it, or type its left, top, right and bottom edges,
   which works without a pointer. The box must fit the screened image, so it
   cannot be added before screening has measured the image. Findings are
   append-only, attributed and timed like decisions, and listed under the
   photo with their boxes drawn as solid outlines (the model's search window
   stays dashed). Each photo in the run detail and export carries its
   `findings`. Time spent before a finding is saved belongs to that finding:
   `review_effort` totals include it, and it is reported apart from decisions
   (`minutes_by_finding_kind`, `measured_findings`, `unmeasured_findings`,
   `unmeasured_incidental_findings`). An untimed incidental finding also
   withholds the per-photo rate.
   `GET` and `POST /runs/{run}/photos/{photo}/findings` read and append them.
   A box is a reviewer's outline, not a segmentation, and nothing can be edited
   or withdrawn yet.
7. **Judge identity, location, history and novelty separately.** Under the
   findings, *Separate judgements* has one row per dimension, each with its own
   value, note and save button. Saving one changes neither the others nor the
   suggestion decision. Each judgement is about one plant, chosen under *Plant
   being judged*: the suggested species, or a recorded plant by its finding id
   (`finding_id`, null for the suggestion). A photo with no suggestion can only
   have its recorded plants judged:

   | Dimension | Values |
   | --- | --- |
   | Identity | `confirmed`, `disputed`, `unresolved`, `unassessed` |
   | Location usefulness | `usable`, `too_imprecise`, `camera_point_only`, `unknown`, `unassessed` |
   | Historical relevance | `recent_evidence`, `historical_evidence`, `no_longer_present`, `date_unknown`, `unassessed` |
   | Novelty | `already_recorded`, `new_in_photo`, `absent_from_references`, `earlier_than_records`, `verified_new_locality`, `unassessed` |

   Novelty is graded so claims stay proportionate. *Newly noticed in this
   photo* says nothing about records. *Absent from the reference records* and
   *earlier than the available records* are relative to the loaded DOC
   snapshot. Only *independently verified new locality* claims a new locality.
   It needs a note giving the verification evidence (who checked, how and
   when). An unresolved identity needs a note saying what evidence would
   resolve it, and *reported no longer present* needs a note saying who reported
   it gone and when. Missing notes are rejected (422). Claims the photo cannot
   support are disabled in the app, with the reason, and refused by the API
   (409): a usable location needs a search area (public coordinates with a
   reported accuracy; see *Location and date limits* below); recent or historical
   evidence and "earlier than records" need a photo date; and novelty against
   records needs this photo to have been compared with the snapshot for the
   judged plant's own watchlist species. A free-text taxon, or a species the
   snapshot did not query, is never compared, so its novelty against records
   stays unassessed. The claim must also agree with that comparison:
   *absent from the reference records* needs no record of the species within
   5 km. *Earlier than the available records* needs at least one nearby record,
   every nearby record dated, and a photo year earlier than all of them. These
   are the same rules the outcomes report uses. Each judgement keeps the SHA-256
   of the snapshot loaded when it was saved (`reference_snapshot`, null when
   none was), so a later snapshot never changes what a claim was made against. Judgements are append-only, attributed and
   timed (`measured_judgements`, `unmeasured_judgements`,
   `minutes_by_judgement_dimension` and `unmeasured_incidental_judgements` in
   `review_effort`). Each reviewer's latest judgement stands. `unassessed`
   withdraws it, and no judgement means unassessed, never negative. In the run
   detail and export, each photo carries the suggestion's `judgements` (per
   dimension, each reviewer's standing value, note and time) and
   `judgement_disputes` (the dimensions where standing values differ, shown as
   "Reviewers disagree"). Each recorded plant in `findings` carries its own.
   The export's `review_history` carries every judgement event.
   `GET` and `POST /runs/{run}/photos/{photo}/judgements` read and append them.
8. **Refer what you can't resolve to a specialist.** Under the judgements,
   *Specialist referrals* lists each request for specialist assessment on the
   photo. *Refer for specialist assessment* opens a form. Choose the plant
   referred: the whole photo, or a recorded plant by its finding id. Then give:

   - a required reason: `lookalike`, `cultivated_or_wild`, `poor_view`,
     `location_or_date` or `other`;
   - the expertise needed, as free text (there is no list of specialists yet);
   - a required note saying what is unresolved and what would settle it.

   A referral starts *open*. Someone, usually the specialist under their own
   name, then *answers* it or *withdraws* it with a required note. That is a
   further append-only event, never an edit, and only an open referral can be
   closed: a second answer or withdrawal is refused (409).

   An answer never changes a reviewer's decision or judgement. A specialist who
   settles the identity records it as their own judgement first. The answer can
   then cite it (`judgement_ids`). Only the answerer's own judgements on the referred plant (any
   plant for a whole-photo referral) made since the referral can be cited, and
   other citations are refused (409).

   The **Needs specialist** queue view lists photos with open referrals, from
   every cohort and any review status, longest waiting first. It still holds
   back audit-sample photos you haven't audited, and the blind audit list never
   shows referrals. Photo rows elsewhere show "Needs specialist".

   Each photo in the run detail and export carries its `referrals`, each with a
   `status` and its `events`. The export's `review_history` holds the same
   history. Referral actions are timed like other review work
   (`measured_referral_actions`, `unmeasured_referral_actions`,
   `minutes_by_referral_action` and `unmeasured_incidental_referral_actions` in
   `review_effort`).

   The outcomes report's *Follow-up usefulness* measure counts referrals on
   incidental photos: open, answered and withdrawn, by reason, with median and
   longest hours from referral to answer (unknown until one is answered).

   API:

   - `GET` and `POST /runs/{run}/photos/{photo}/referrals` read and open
     referrals.
   - `POST /runs/{run}/photos/{photo}/referrals/{id}/events`, with `action`
     `answered` or `withdrawn`, closes one.

   Names are attribution on this unauthenticated stack (#31), not identity, so
   an answer is a named person's note, not a verified identification.

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
an absence, and neither point locates a plant. Known records never filter or
reorder the queue (PRD P11). Screening sees only the image and its original
subject, and the queue follows the margin. An unexpected location is a reason to
refer the photo to a specialist (step 8), not to reject it. The evidence panel
says so under *Known records*. The 14 November 2026 snapshot
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

### Define the study

A study records what the runs are for (PRD P01, Journey 1). It holds:

- the discovery question, the partner, and the responsible people by role
- the regions and historical period, each with its rationale
- the watchlist and lookalikes, each with its rationale
- the source collection and how original subjects were selected
- the review budget, in hours, photos or both
- the declared reference records
- an optional agreed limit for each outcome measure

A study only records decisions; it never makes them. Whatever is missing is listed
under *open decisions*. The study stays `provisional` until the lead marks it
`agreed`, which needs a question and a partner. The partner and question decision
itself is issue #1.

Open **Study definition** beside the run settings to view or edit the study. You
can also use the CLI:

```sh
uv run main.py study --run nelson-tasman-3e62ad801459                 # show it
uv run main.py study --run nelson-tasman-3e62ad801459 --file study.json \
  --author "Your name" --note "Budget agreed" --base-version 2         # record a version
```

The file is the definition as JSON, with the same fields the API takes; see
`StudyDefinition` in `src/weedz/discovery/study.py`. Once the run has a study,
`--base-version` must name the version your file edits. That is the `version` the
show command printed. If someone has recorded a newer version since, the edit is
refused.

- **Versions.** Each edit appends a whole new version with its author, time and
  note. Versions are never edited. An edit based on an older version is refused
  (409), so two people cannot overwrite each other unseen. This holds in the app,
  where the form saves against the version it opened, and in the CLI.
  Saving a form never drops what it cannot show:

  - names the screening no longer covers come back as not yet screened
  - limits for measures no longer offered are kept, and the server then refuses them by name
- **Runs.** A study can serve several runs. A run links to one study at a time,
  and the latest link stands.
- **Screening terms.** Regions, watchlist species and lookalikes are checked
  against the screening's code constants (`REGIONS`, `SPECIES`, `LOOKALIKES`).
  Any other name is refused unless it is marked `"screened": false`, meaning not
  yet screened. *Differs from the screening* lists every gap: screened species or
  regions the study leaves out, names not yet screened, declared lookalikes with
  no rationale, and a run period outside the study period.
- **Limits.** Each limit has a fixed unit and direction, for example *at least N
  % of incidental photos reviewed*. `GET /studies/terms` lists them. A limit left
  out is "not yet agreed", never zero.

The API endpoints are:

- `GET/POST /studies`. A new study may take `run_id` to link it in the same
  request. If that run already has a study, the request is refused (409).
- `GET /studies/{id}`: the current version and history.
- `POST /studies/{id}/versions`
- `GET/POST /runs/{id}/study`

The run detail and the run export (shareable by default) carry the study now linked,
at its latest version. Responsible people's names travel with it, as reviewer names
already do. The completion manifest is written once, when screening completes.
It records the study linked at that moment, which is usually none, because a
study is often defined after a run. Use the export for the current study.

### Check the source's suitability

Before reviewing a run, check what its photos can and cannot support (PRD P02,
P14, Journey 1):

```sh
uv run main.py suitability --run nelson-tasman-3e62ad801459 --json suitability.json
```

This prints a Markdown summary of the run's incidental photos. `--json` also
writes it as JSON. `GET /runs/{id}/suitability` serves the same JSON, the run
export and completion manifest carry it as `source_suitability`, and the
**Source suitability** panel in the review app shows it each time it is opened.
Nothing in it is computed afresh. It composes what the run already records: each
photo's limits and sharing decision, the site-visit groups, the corpus coverage,
the reference comparison and the linked study. It covers:

- **Scope:** photos per region against the requested number, and the run's status.
  A shortfall, an unfinished run or a missing reference snapshot is listed as
  affected coverage.
- **Dates:** earliest and latest photo, the query period and the study period.
  Also photos outside the study period, and those that cannot be placed in it
  because they are undated, or dated only to a month or year that crosses one of
  its ends. Gaps are looked for only in the part of the study period the run
  queried. Years, and seasons that part reaches, that no photo could fall in are
  listed as unassessed. A month- or year-only date covers every month it spans
  inside the period. Any part of the study period before or after the query
  period is stated as not sampled, and its years are never listed as gaps. Gaps
  are "unknown" when an undated photo could fill any of them, or when the study
  period lies wholly before or after the query period, so none of it was
  sampled. A recent (newest-first) run has an open start, so its earlier years
  are stated as not sampled.
- **Location quality:** photos with a search area, each reason the rest have none,
  and the reported accuracy (median and bands, with 20 m or better marked as
  precise enough for aerial site context).
- **Permitted uses:** the photo and observation licence mix, non-commercial-only
  photos, images that may be shared or only linked, and locations that may be
  shared or are withheld, with the reasons.
- **Missing information:** photos missing each field, zeros included.
- **Independence and screening:** site visits and ungrouped photos, and screened
  and unscreened photos. Also whether the tiles covered every pixel and photos
  with featureless windows, both "not recorded" for runs scored before these were
  recorded, plus the original subjects and reviewed and unassessed photos.
  Visible vegetation is stated as *not measured*.
- **Comparison with known records:** the snapshot, and photos not compared, with
  the reasons.
- **What these photos cannot support:** for each conclusion, the photos and site
  visits that cannot support it, and why. The conclusions are a field search
  lead, aerial site context, when a plant was there, the study period, novelty,
  an independent count, a shared image or location, and any screening
  suggestion. Without a study period, that check reads "not assessed", not zero.

A photo, area, period or year that was not collected, screened, compared or
reviewed is unassessed. It is never evidence that no weed is there.

### Report outcomes against the success measures

```sh
uv run main.py outcomes --run nelson-tasman-3e62ad801459 --json outcomes.json
```

This reads the run from `--pilot-dir` (default `data/pilot`) without Temporal or
the API, and prints a Markdown report of the PRD's eight success measures.
`--json` also writes the report as JSON, and `GET /runs/{id}/outcomes` serves the
same JSON. Each measure has a value, its denominator, the evidence behind it, and
a status: measured, partially measured or not yet measurable, with the reason.
Photo sets are counted as independent site visits, and ungrouped photos are kept
apart. "Unknown" means unmeasured, not zero. A confirmed review shows only that
the species is visible, not that the finding is useful (#18), and a reference
distance is not a novelty claim.

Each measure's `limit` compares it with the linked study's agreed limit:

| Verdict | When |
| --- | --- |
| `not agreed` | No study is linked, or it agrees no limit for the measure. No verdict is given. |
| `not comparable` | The measure gives no value in the limit's unit yet, or only a lower bound that does not settle the limit. The reason says which. |
| `met` / `not met` | Both a limit and a comparable value exist. |

Today only two measures give a comparable value: *evidence completeness* (% of
incidental photos with complete evidence) and *coverage* (% reviewed). Coverage
is a lower bound while photos wait for review, so a shortfall stays
`not comparable` until every photo is reviewed. Usefulness (#18), a detection
rule (#16) and follow-up judgements are not recorded yet, so the other measures
cannot be compared.

The report's `study` section gives:

- the study's version and status
- its open decisions and its differences from the screening
- **review-budget use**: measured review hours (decisions, findings, judgements,
  referral actions and blind audits) and photos with a decision or audit,
  against the budget

Untimed work makes the hours a lower bound. So a budget is reported as `spent`
for certain, but `within so far` only while some work is untimed.

The *Novel or earlier evidence* measure has two parts, reported side by side.
Both cover the same plants: confirmed suggestions and recorded watchlist plants.

- **Computed comparison.** Its value counts plants with no record within 5 km,
  or observed in an earlier year than every record within it. It needs a
  reference snapshot.
- **Judged novelty.** The evidence's `judged_novelty` tallies, as site visits,
  each plant's level from its reviewers' standing judgements (step 7):

  - When reviewers' values differ, the plant counts as `disputed`, never as a
    level.
  - A plant nobody judged counts as `unassessed`.
  - Only a `verified_new_locality` with its verification note counts as a new
    locality. `verified_new_localities` lists each claim's photo, finding id
    (none for the suggestion), reviewer and note.
  - `record_relative_judged_against_another_snapshot` counts plants whose
    *absent from the reference records* or *earlier than the available records*
    claim was made against a snapshot other than the one loaded now, so they
    can be rechecked.

  Judged levels are reported even without a snapshot.

The measure is partially measured once either part has something to report,
and not yet measurable when neither does. Judged levels are reviewer opinions,
never a first-occurrence claim.

### Review the reference collection

To see a run's reviewed examples as a reference collection (PRD P13, Journey 5), run:

```sh
uv run main.py reference --run nelson-tasman-3e62ad801459 --json reference.json
```

This prints a Markdown summary, and `--json` also writes every example. Nothing is
stored: the collection is re-derived from the review history each time, so it
cannot disagree with it. Each label on a photo is one example, built from the
contract samples (`pilot_samples`). An example keeps:

- the photo's original source label
- its rights and attribution
- who recorded it, and who reviewed it

It has a **standing**:

- **original:** the source's own label
- **accepted:** a reviewer's finding, or a screening suggestion, that reviewers accepted
- **unresolved:** reviewers disagree, or left it unresolved
- **unsuitable:** rejected on review
- **unreviewed:** nobody has judged it yet

Its eligibility is stated per use, with the reason whenever it is not eligible:

- **Training:** a present or absent label that was not rejected or left
  unresolved. This is the contract's `supervises()` rule, plus a suggestion that
  reviewers accepted.
- **Evaluation:** a source's original label, or a reviewer's label that someone
  *other than its author* accepted. An accepted suggestion never counts, because
  reviewers saw the suggestion.
- **Sharing:** an original or accepted label whose photo and observation licences
  the sharing policy admits. Non-commercial terms are flagged.
- **Contributor consent:** a photo its person sent from the app (`rights.consent`)
  is training- and evaluation-eligible only with their `training` permission,
  and sharing-eligible only with `agencies`. Once withdrawn it is eligible for
  nothing. Sourced photos have no consent record and are judged by licence alone.

Coordinates are never included. Each example says only whether its location could
be shared, or why it is withheld.

Coverage counts photos with an eligible example for each watchlist species and
each species seen. They are counted by source, label, view, season and region.

Gaps are listed:

- a use with no eligible example
- no absent (negative) example
- a source, region, view or season the collection holds with none for the species

A view or season that no eligible example records is listed as unknown, not as a
gap. Every iNaturalist photo's view is unknown. Growth stage and habitat are
recorded nowhere, and the report says so. A missing example is a gap in the
collection. It is never evidence that a weed is absent.

### Prepare a follow-up package

The team decides which leads are worth investigating, and records why (PRD
Journey 4). A lead is the suggested species, or a recorded plant, on an
incidental photo.

**Select a lead.** In the review app, the photo's **Follow-up** section selects
or deselects a lead. Both actions need your name and a reason.

- Selections are appended, never edited. The latest event for a lead stands,
  and a deselection is a later event, so the history stays visible.
- Repeating the current state is refused (409): selecting a lead that is
  already selected, or deselecting one that is not.
- Selection is not timed review work.
- A selection by someone who had not audited the photo unblinds later audits,
  like any other review action.
- The export's `lead_selections` lists every event.
- API: `POST /runs/{run}/photos/{photo}/leads`, with `action` (`selected` or
  `deselected`), `selector`, `reason` and an optional `finding_id`.

**Build the package.**

```sh
uv run main.py package --run nelson-tasman-3e62ad801459 --out follow-up/
```

This writes `package.json`, a readable `package.md`, and `photos/` to a new or
empty folder. With no selections, it says so plainly and writes nothing.

In the app, **Follow-up package ↓** downloads the same files as a zip
(`GET /runs/{id}/package/archive`). `GET /runs/{id}/package` returns the JSON.

**What each lead carries.** Only selected leads are packaged, never the whole
queue. Each lead carries:

- **Selection:** who selected it, when and why, and its selection history.
- **Candidate:** the candidate plant, kept apart from the photo's original
  subject.
- **Source:** the source link, observer, attribution, and photo and
  observation licences.
- **Review:** each reviewer's decision on the suggestion, and whether they
  disagree.
- **Judgements:** for each dimension, a level (the agreed value, `disputed` or
  `unassessed`), with every opinion and its note.
- **Limits:**
  - the search area: its centre is the observation point, never a plant point,
    and its radius is the reported accuracy plus the 100 m allowance. If there
    is no search area, the reason is given.
  - the photo, upload and screening dates
  - the presence statement: a photo is not current presence
- **Comparison basis:**
  - the reference snapshot's file, retrieval date and SHA-256
  - this plant's distance-only comparison, or why there is none (free-text
    taxa are never compared)
  - the judged novelty level
  - whether a record-relative claim was judged against another snapshot
- **Referrals** affecting the plant, with their answers.
- **Site visit:** its site-visit group.

**Location privacy.** Raw coordinates are never copied into a package. An
obscured or missing location appears only as "not searchable", with its reason.

**Photos.** A photo is included only when its licence is CC0, CC BY or CC BY-NC.
All three permit sharing with attribution; for CC BY-NC, the package says the
use must be non-commercial.

- The included file is the run's retained copy, and only while it still matches
  its recorded SHA-256. Otherwise the lead links to the source and says why.
- Any other licence gets a source link and the reason the photo was left out.
- The relevant detail is given as pixel boxes on the photo, not as new crops:
  the screening window for a suggestion, or the reviewer-drawn extent for a
  recorded plant.
- Nothing is published, and no observation is created on anyone's behalf.
- Each lead's source also carries the observation licence's conditions. The
  image decision comes from the shared policy
  ([sharing](#sharing-licences-and-location-privacy)).

**Real-data check.** On a copy of `data/pilot`, run
`nelson-tasman-3e62ad801459` had no selections, and the command printed "No
leads are selected for follow-up in this run" and wrote nothing.

After two suggestions were selected on that copy, it wrote two leads (one
CC BY-NC photo, one CC BY photo). Both had public locations:

- One had a 295 m search area (195 m accuracy), not precise enough for aerial
  context.
- The other had a 105 m area (5 m accuracy), precise enough for aerial context.

Neither had a DOC record within 5 km. Both remained unassessed on every
judgement dimension.

### Sharing, licences and location privacy

One policy, `src/weedz/discovery/sharing.py`, decides what may leave the
project (PRD P15, P17). Every outbound path uses it: the run export, the
follow-up package and the image endpoint. It knows two uses:

- `review`: the local review app, on the reviewer's own machine.
- `share`: anything that leaves that machine, such as the downloaded export
  or a package.

**Licences.** For each photo the policy states whether the image may be shown
(review), included (share) or only linked, and why.

| Licence | Review app | Export and package |
| --- | --- | --- |
| CC0, CC BY, CC BY-NC | shown | included, with attribution; CC BY-NC for non-commercial use only |
| ND (`cc-by-nd`, `cc-by-nc-nd`) | not admitted; link | link: only verbatim copies are allowed, and verbatim-only handling is not implemented |
| SA (`cc-by-sa`, `cc-by-nc-sa`) | not admitted; link | link: share-alike terms for derived material are not yet carried |
| none (all rights reserved) | not admitted; link | link: the observer's permission is not established |

- Acquisition asks iNaturalist only for the three admitted licences, and
  checks every photo and observation individually. `Store.save_photos`
  refuses any other licence, so a new source or cohort cannot add one
  silently. ND, SA and all-rights-reserved material cannot enter today.
- `GET /runs/{id}/photos/{photo}/image` serves only admitted photos. Anything
  else is refused with 403 and the reason, so reviewers still see every photo
  the collection holds.
- Attribution and both licences always travel. A photo's `sharing.terms` in
  the export gives the attribution, observer, source link, photo terms,
  observation terms (the observation data, such as taxon, date and location,
  has its own licence), and whether non-commercial use applies.
- Admitting ND or SA later means changing acquisition and this one table,
  with the handling the table names.
- A photo sent from the app also carries what its person permitted
  (`consent`, [consent text](report-consent.md)). The review app shows it only
  with `review`, and an export or package includes it only with `agencies`.
  Otherwise it is linked with the reason, and a withdrawn photo is used for
  nothing. Its `sharing.terms` add `contributor_permits`, so a recipient knows,
  for example, not to publish it, and its attribution is the credit the person
  chose.

**Locations.** Exact locations are the scientific value of a weed record. So
a public point is shared exactly, with its accuracy, in every output. It is
not generalised to a grid or withheld by audience (#61 records why that was
rejected). The limits below are hard constraints: they protect locations that
are not ours to reveal, or that would overstate what is known.
`tests/test_location_privacy.py` calls each review-API GET route that returns
photo data, and unpacks the package archive, for an obscured observation. It
finds the point in none of them. Each other GET route is listed with the
reason it carries no location, so a new route fails the test until someone
classifies it. Image bytes carry no location: iNaturalist strips metadata from
hosted photos, and device crops are re-encoded.

- An obscured point is never served, not even to the review app. iNaturalist
  displaces it on purpose, so passing it on would present an invented
  location. `coordinate_status` stays `obscured`.
- For `share`, a public point leaves only with its accuracy. A point of
  unknown accuracy is withheld, because it would overstate where the photo
  was taken. The review app still shows it, marked "accuracy not supplied".
- A point under an observation licence that is not admitted is withheld for
  `share`, and so is any search area centred on it: in the export and in a
  package, its `search_area.status` becomes `withheld`, with the reason.
- Each exported photo's `sharing.location` gives the status, the point that
  may leave, its accuracy, and the reason anything was withheld.

**The run export is shareable by default.** `GET /runs/{id}/export` (**Export
evidence ↓**) returns the shareable form. Coordinates follow the location
rule, each photo has a `sharing` block (`terms`, `image`, `location`), and
the top-level `sharing` lists the rules. No HTTP endpoint serves raw obscured
coordinates. The download button is the file people pass on, so the safe form
is the default. A raw-coordinate route is exactly what would leak once remote
access (#31) exists. The complete record stays local: the SQLite store and the
completion manifest in `data/pilot/runs/<id>/manifest.json`. The package, the
outcome report and the completion manifest compute from that full record, and
apply their own output rules.

**No publication on anyone's behalf.** Nothing in the project publishes
photos, observations or identifications to iNaturalist, GBIF or anywhere else.
The source clients only read. `tests/test_sharing_surface.py` proves that
every request the iNaturalist and GBIF clients make is a GET, and that no
module naming those hosts calls a write method. A reviewer who wants a plant
recorded publicly should ask the observer, or record their own observation.

**Real-data check.** On a copy of `data/pilot`, the shareable export of run
`nelson-tasman-3e62ad801459` held 30 photos, all public and all admitted:

- 13 CC BY photos under CC BY observations, and 12 CC BY-NC photos under
  CC BY-NC observations.
- Two CC BY photos under CC0 observations, two CC0 under CC0, and one CC BY
  under a CC BY-NC observation.

13 photos carry non-commercial terms. 26 points were given with their
accuracy. Four public points of unknown accuracy were withheld, though the
review app still shows them.

With one photo's record then marked obscured on the copy:

- The export and the run detail no longer contained its point.
- Its image still loaded for review.
- A package selecting it and a public photo included both CC BY photos, and
  gave the obscured one as "not searchable".

## Files and evidence

Everything generated is ignored by Git:

| Path | Contents |
| --- | --- |
| `data/pilot/images/` | Downloaded large photo derivatives; source rights remain attached |
| `data/pilot/runs/<id>/*.json` | Raw source query snapshots and completion manifest |
| `data/pilot/embeddings/` | Cached BioCLIP window embeddings, keyed by image bytes, pinned model, weights, library versions, preprocessing and window geometry; safe to delete |
| `data/pilot/references/` | Dated DOC weed-record snapshots from GBIF for comparison |
| `data/pilot/discovery.sqlite3` | Runs, source records, raw scores, current decisions, review events, audits, findings, judgements, specialist referrals and lead selections |
| `data/pilot/temporal.sqlite3` | Persistent Temporal development-server history |
| `runs/nelson-tasman-review/` | Browser-check screenshots |

An observation coordinate describes the original observation, not a located weed.
Obscured/missing coordinates and positional accuracy remain explicit. The store
keeps the source's point. The run detail and export pass on only what the
[sharing policy](#sharing-licences-and-location-privacy) allows.

### Location and date limits

For PRD P09, each photo in the run detail and export carries `limits`, computed in
`src/weedz/discovery/limits.py`. The evidence panel shows them as *Dates* and
*Search area*.

- **Search area** (`limits.search_area`):
  - The `centre` is the observation point, where the photographer was. It is
    never a plant point.
  - `radius_m` is the reported positional accuracy plus
    `CAMERA_TO_PLANT_ALLOWANCE_M` (100 m). iNaturalist records no camera bearing,
    pose or focal distance, and hosted photos have no EXIF, so the distance from
    the camera to a background plant is unknown. The 100 m is a declared planning
    allowance, not a measurement. A telephoto background can be farther, so the
    area is where to start looking, not a bound.
  - `site_context` is true when accuracy is 20 m or better. At that accuracy
    aerial imagery can show the site's context, but never the plant
    ([LINZ assessment](datasets.md)).
  - Obscured, missing and unknown-accuracy locations have `status` `obscured`,
    `missing` or `accuracy_unknown` and a `reason`, with no centre or radius.
    The obscured point is never shown or used.
- **Dates** (`limits.dates`):
  - `photographed`, `uploaded` and `screened` are kept distinct. `screened` is
    when the photo was last scored (the photo's `screened_at`). It is null before
    screening, and for photos scored before this was recorded.
  - `photographed` is kept as the source gave it, even a partial date such as
    `2024-06`.
  - `days_photo_to_upload` and `days_photo_to_screening` give the gaps. They are
    null unless both dates are full calendar days.
  - `current_presence` says that, if the plant is visible, the photo shows it
    was there on its capture date, not that it is there now. For an undated
    photo, it says the photo can show neither. It is conditional because a
    candidate is not a confirmed plant.

The outcomes report uses the same rule:

- *Evidence and review completeness* counts a location as complete only when it
  gives a search area, and lists `search_areas` by status.
- *Follow-up usefulness* lists `watchlist_finding_search_areas` for confirmed
  and recorded watchlist plants, counted per photo.

A reviewer's location and history judgements (step 7) remain separate opinions. Native
lookalikes, indistinct plants and locations with no nearby known weed record are
still reviewable. Photos by the same observer on the same observed date, with public coordinates
within 250 m once both accuracy radii are allowed for, form one site visit. The
queue and export show the group, and the stats count independent visits.
Obscured, missing or undated records, and photos with unknown positional
accuracy or accuracy over 250 m, never link, so groups can be too small but are never invented. These
photos show “Site visit unknown” and are counted as “could not be grouped”,
never as independent visits. “Species visible” is a local reviewer decision about the suggested
species in a photo; it does not verify a new locality. Corrected species and missed
plants are recorded as structured findings (see step 6), not inferred from notes.
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
The findings check records a corrected and a missed plant, drawing one box by
dragging on the photo and typing another by keyboard, and the accessibility
check audits the finding form open with a box error showing.
The judgements check saves identity and a noted verified new locality
separately, then judges a recorded plant apart from the suggestion. It checks
that per-dimension disagreement is shown and that a draft does not pass to
another reviewer. It also checks
that unsupported claims are disabled with a reason. The accessibility check
audits the judgements with a required-note hint showing.
The referrals check refers a recorded plant with a reason and expertise,
answers an open referral citing a judgement made since it, and withdraws
another. It checks that the Needs specialist view lists only open referrals,
holds back an unaudited sample photo until its reviewer has audited it, and
that the blind audit list never mentions a referral. The accessibility check
audits the referral form and an open referral's response form.
The sign-in check signs in with a reviewer token, checks that the name field is
fixed to the signed-in reviewer and sent with a decision, and signs out. The
session-cookie check covers the cookie flags and refuses malformed tokens. The
accessibility check audits the sign-in form with an error showing, at desktop
and phone widths, and the signed-in desk.
The limits check shows a searchable photo's radius, labelled observation point,
allowance and three dates. It also checks that an obscured photo shows no point
or radius, and that an unknown-accuracy photo shows no radius.
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
