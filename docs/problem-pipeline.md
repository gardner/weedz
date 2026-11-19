# Problem statement 2: we can't yet turn a pile of photos into a short, trustworthy list of weed finds

Written 15 November 2026. Weedz has three problems to solve, in order:

1. **[Dataset](problem-dataset.md):** no dataset shows where weeds appear in real NZ photos.
2. **Pipeline** (this document): we can't yet turn a pile of photos into a short, trustworthy list of weed finds.
3. **Reach:** weeds that are found don't reach the people who deal with them.

The pipeline depends on the dataset: without human-checked labels it can't be tuned or measured. Problem 3 depends on the pipeline, because a find is only worth sending if a person can trust it.

The implementation status below is a 15 November snapshot. For the current
server/CVAT research scope and the 19 November run, see the
[Weedz problem statement](problem-statement.md). The
[prior-art investigation](background-plant-prior-art.md) evaluates segmentation
alongside existing multi-species recognition methods.

## The problem

Give Weedz thousands of photos of birds, insects and landscapes. It should hand back a short list:

- these photos probably show old man's beard, pampas or gorse;
- here is the part of each photo that shows it;
- here is how sure we are.

A person should then be able to confirm or reject each find in seconds.

That's harder than it sounds, for four reasons:

- **The weed is small and in the background.** It may fill a few percent of the frame, partly hidden, out of focus, or seen from far away. Classifiers trained on photos of the plant itself aren't built for this.
- **Other plants look like the weeds.** Native clematis looks like old man's beard, toetoe like pampas, and mānuka and kānuka like gorse. A false alarm on a native wastes reviewer time, and if it's acted on, it can harm the native plant. Broom also looks like gorse; it's a weed too, but not a target, so flagging it as gorse is still a wrong answer.
- **Reviewer time is the real budget.** Weeds are rare in incidental photos. A pipeline that flags 10% of photos, when only a fraction of 1% hold a weed, buries reviewers. What matters is real finds per hour of review, not accuracy on a balanced test set.
- **The phone has to run it.** People's photos live on their phones and should stay there unless they approve a report. So screening has to run on the device, within the phone's memory, battery and background-time limits.

## Where we are today

On the desktop, the steps run end to end, but nothing has been shown to work yet. The phone path is only partly built.

| Stage | What runs today | What we don't know |
| --- | --- | --- |
| **Collect** | Bounded, licensed iNaturalist collections for Nelson/Tasman, with provenance and checksums, run through Temporal | How well other sources would serve: trail cameras, roadside imagery (#9) |
| **Find the plant** | The whole photo plus overlapping tiles. Tiles are search windows, not plant outlines. They cover every pixel except in very wide or tall panoramas, where tiles are capped at 32 and thinned. The gaps are then seen only in the downscaled whole photo, where small weeds can be lost. SAM 2.1/SAM 3 segmentation runs as an optional experiment ([segmentation](segmentation-experiment.md), #122) | Whether segmenting first finds more weeds, or loses the small ones it misses |
| **Identify** | BioCLIP 2 compares each window with the target weeds, lookalikes and scene descriptions. The Aotearoa Species Classifier, PlantCLEF and WeedScan run as optional comparisons | Accuracy on background plants. Which model, or which combination |
| **Rank** | Photos are ordered by the best margin between a target weed and any comparison label. [Score meaning is versioned](../src/weedz/discovery/score_meaning.py) | Margins are uncalibrated; there's no agreed threshold (#16) |
| **Review** | The Next.js review desk, a blind audit sample, a lookalike queue, reviewer attribution, and Label Studio export | Reviewer effort per real find |
| **Run on a phone** | Not yet. The [Flutter app](mobile.md) has its scaffold, its domain layer and a library scanner, but no on-device model: only test fakes implement the screener. The server side exists: device intake, signed model bundles, and a parity harness (fp16 matches the desktop model, int8 doesn't; [parity](../benchmarks/optimised-model-parity.json)) | Phone speed, memory and battery; Core ML / LiteRT conversion (#51) |

What we've measured, on small samples of source-labelled photos:

- **The pilot run:** 30 photos screened, 0 expert-confirmed discoveries ([screening](../benchmarks/nelson-tasman-screening.json)). Nobody has reviewed them yet; this isn't a failure count.
- **Lookalikes:** toetoe photos scored a positive margin for pampas in 1 of 6, and native clematis for old man's beard in 2 of 15. A positive margin isn't a detection, because no threshold has been chosen, but it shows how close natives come to the weeds (#33, [model comparison](../benchmarks/model-comparison.json)).
- **Whole photo vs tiles:** the harness exists, but it has no verdict because there are no independent labels for background plants ([whole vs region](../benchmarks/whole-vs-region.json), #12).
- **Cost:** BioCLIP 2 is a 1.7 GB checkpoint and takes about 3 s per photo on a desktop CPU (about 7 windows per photo). That's far too slow and heavy for scanning a phone's whole library (#51).

## What a solved pipeline does

For each target weed, it can say the following, backed by a blind test set from problem 1:

1. **How many real finds per hour of review,** at a review budget the partner agrees to (#1).
2. **How many visible weeds it misses,** measured on randomly sampled photos, including ones it didn't flag.
3. **How often natives are flagged,** reported separately for each lookalike.
4. **Why it flagged a photo:** the region it looked at, the score and its meaning, and the model version. Reviewers judge the evidence, not a bare number.
5. **That it runs on a phone** within an agreed time and battery cost per photo, with results that match the desktop model inside the parity limits.
6. **That every result can be reproduced:** pinned models, preprocessing, prompts and inputs, so a result can be rerun and audited.

## What we'll try, in order

Each step is measured on the same frozen dataset before the next is adopted. A newer or bigger model isn't assumed to be better.

1. **Baseline first.** Measure today's whole-photo-plus-tiles BioCLIP 2 screen on the first gold release. Every later change must beat this.
2. **Segment, then identify.** Propose plant regions with SAM, then identify each region (#122). Count separately the weeds the segmenter misses, so a gain in precision can't hide a loss in recall.
3. **Compare identifiers.** BioCLIP 2, the Aotearoa Species Classifier, PlantCLEF and reference-photo matching, on the same regions (#152).
4. **Learn from labels.** Only if the failures call for it, add a small classifier on frozen embeddings, or fine-tune, using reviewed labels and hard negatives (#33).
5. **Calibrate.** Turn margins into scores with an agreed meaning and per-target thresholds, set by the review budget (#16).
6. **Shrink for phones.** Ship only the image tower, with text prompts precomputed on the server. Keep fp16 or a distilled model that passes the parity gate, then measure on real phones (#51, #128).

## Not in scope

- **Building the dataset.** That's problem 1. This document assumes its gold releases and blind test set.
- **Sending finds to agencies.** That's problem 3.
- **Aerial and satellite mapping.** These are a separate research path with their own benchmark. They aren't the incidental-photo pipeline.
- **Claiming first occurrences or calibrated probabilities** before they are measured.

## Open questions

- **Review budget:** how much review time can the partner give, and what share of false alarms is tolerable (#1)?
- **Target accuracy:** what miss rate is acceptable for each weed, given how costly a missed incursion is?
- **Where it runs:** should the phone run the whole pipeline, or only a fast first pass, with heavier models on the server for reports the person has approved?
- **Licences:** the Aotearoa classifier's weights are CC BY-NC 4.0. Is that compatible with how a shipped app bundles them (#62)?
- **More weeds:** when should the watchlist grow past three species, and how will each new target's lookalikes be chosen?
