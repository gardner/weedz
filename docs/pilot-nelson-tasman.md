# First Nelson / Tasman screening run

Completed 13 November 2026, run `nelson-tasman-3e62ad801459`.
The workflow and review interface work on real photos. **The screening method
is not yet a reliable incidental-weed detector.** Expert review remains pending.

| Evidence | Result |
| --- | --- |
| Nelson animal-subject photos | 12 |
| Tasman animal-subject photos | 12 |
| Separate target-species references | 6: one per species per region |
| Photos screened | 30, with five windows each |
| Species watchlist | Old man's beard, pampas grass, gorse |
| Source photo licences | 16 CC BY, 12 CC BY-NC, 2 CC0 |
| Expert-verified incidental discoveries | 0 established; all 30 records await review |

The run used current iNaturalist council place IDs 40493 and 40494, source
research-grade observations, separately eligible observation/photo licences,
and a capture-date cutoff of 31 December 2024. Selection was recent-first from
the first 100 results per query. Some photos were uploaded later than their
capture date. This small convenience sample does not measure regional coverage,
camera-view diversity, or generalisation to other datasets.

Pinned BioCLIP on CPU produced raw image/text similarities for the whole frame
and four overlapping windows. It ranks target-minus-comparison margins with
native lookalikes and general scene/animal prompts. All three references in each
region ranked their source-labelled target highest among our target species.
That is a reference sanity check, not an accuracy estimate for background plants.

The 24 incidental photos are not 24 independent pieces of evidence. Several
are the same observer's photos from one beach or estuary visit, so they show
the same background vegetation. Grouping by observer, observed date and public
coordinates within 250 m (after both accuracy radii) gives **7 independent
site visits** among the 16 photos that could be checked: three single photos,
two pairs, one visit of four and one of five
([#4](https://github.com/gardner/weedz/issues/4)). The other **8 photos could
not be grouped**: four report no positional accuracy, and four report accuracy
(282–1,634 m) wider than the 250 m rule. They are reported as unknown, not as independent visits. The
review app and export show these groups. A group means one visit, not
necessarily the same plant.

The highest-ranked incidental suggestion was pampas grass in an
[Australasian gannet photograph](https://www.inaturalist.org/observations/257459474).
The displayed search window shows bird and sky, an obvious false alarm. A
positive comparison margin does not establish plant presence. This concrete
failure argues against automatically accepting these rankings or scaling this
method as a validated detector.

### Lookalike photos: can screening tell the weed from its lookalike?

On 14 November 2026, 39 source-labelled iNaturalist photos of declared lookalikes
were screened with the pinned BioCLIP and **ranking revision 2**: the whole frame
plus four corner windows, with no original-subject comparison
([#11](https://github.com/gardner/weedz/issues/11), [summary](../benchmarks/nelson-tasman-lookalikes.json)).
That was up to three per taxon per region. The same photos under revision 4 are
reported in the revision 4 section below. Lookalike confusion rises there.

Every photo has a top suggestion, which is the watchlist species with the largest
margin, and the review desk shows it whatever the margin's sign. The positive
margin column is counted independently: that weed beat every comparison label,
whichever weed was on top.

| Lookalike | Resembles | Top suggestion is that weed | Positive margin for that weed | Median margin |
| --- | --- | --- | --- | --- |
| Toetoe (*Austroderia*) | Pampas | 6 of 6 | **5 of 6** | +0.044 |
| *Clematis foetida* | Old man's beard | 3 of 3 | 2 of 3 | +0.006 |
| *Clematis forsteri* | Old man's beard | 6 of 6 | 3 of 6 | −0.002 |
| Puawhānanga (*C. paniculata*) | Old man's beard | 6 of 6 | 1 of 6 | −0.013 |
| Broom | Gorse | 5 of 6 | 0 of 6 | −0.091 |
| Mānuka | Gorse | 4 of 6 | 0 of 6 | −0.050 |
| Kānuka | Gorse | 4 of 6 | 0 of 6 | −0.049 |

The review desk would present most lookalike photos as their look-alike weed:
34 of 39 have it as the top suggestion. A suggestion is therefore not an
identification. Margins separate the groups further. Native toetoe beats every
comparison as pampas in 5 of 6 photos, even though toetoe is a comparison
prompt, and native clematis does so as old man's beard in 6 of 15. Broom, mānuka
and kānuka never beat the comparisons as gorse (0 of 18). Pampas and old man's
beard suggestions in particular need botanical review of diagnostic features,
such as flowering time, plume colour and leaf form, before they count as leads.
These are small, source-labelled samples, not reviewed false-positive rates.

### Ranking revision 3: re-screen of the same photos

The gannet failure was not a one-off. In 10 of 24 incidental photos a target
beat every comparison prompt, and the top four all chose a top-row window,
mostly as pampas grass. Pale sky, sea and shore textures had no better
explanation on offer. The comparisons also ignored the photo's own subject.
Ranking revision 3 ([#10](https://github.com/gardner/weedz/issues/10)) adds
the original-subject taxon as a per-photo comparison (never for a watchlist
target) and fixed sky, water, shore and rock prompts.

The same 30 photos and checksums were re-screened with the same weights. The
results are recorded in the [re-screen summary](../benchmarks/nelson-tasman-rescreen-r3.json).

| Check | Revision 2 | Revision 3 |
| --- | --- | --- |
| Incidental photos with a positive margin | 10 of 24 | 2 of 24 |
| Gannet margin (pampas) | +0.041, sky window | −0.102 |
| References ranking their source-labelled target first | 6 of 6 | 6 of 6, margins unchanged |

Two positives remain. The Tanguru chafer window is a pink fibrous non-plant
surface, so it is probably a false alarm. The South Island pied oystercatcher
window shows riverbed vegetation, which is reviewable but unverified. Fewer
positives is not higher recall: nothing here measures missed weeds, and 30
unreviewed photos give no accuracy estimate.

### Ranking revision 4: look at the whole photo

Revision 3 never showed the model a median 14.9% of each photo, and up to 31.5%
of tall photos ([#13](https://github.com/gardner/weedz/issues/13)). The four 60%
corner windows and the full frame were centre-cropped, losing their edges.
Revision 4 scores a letterboxed whole frame plus square tiles covering every
pixel, and ignores featureless tiles as winners. The 30 photos were re-screened
with the same weights ([summary](../benchmarks/nelson-tasman-rescreen-r4.json)).

| Check | Revision 3 | Revision 4 |
| --- | --- | --- |
| Incidental photos with a positive margin | 2 of 24 | 5 of 24 |
| References ranking their own target first | 6 of 6 | 6 of 6 |
| Featureless tiles excluded | n/a | 5 |

Looking at more of each photo surfaces more candidates. The extra three are a
grassy skink window, which is plausible vegetation, and two near-zero margins
(+0.005) on sky and on blurred water. A black night strip that briefly ranked
as pampas is now excluded as featureless. Lookalike confusion rises with
coverage too. Without the subject prompt, toetoe passes as pampas in 6 of 6
photos (previously 5), puawhānanga as old man's beard in 4 of 6 (previously 1),
and kānuka as gorse in 2 of 6 (previously 0). Seeing the whole photo is
necessary to find edge weeds, but it does not make the ranking more selective.
Calibrated thresholds and lookalike discrimination (#16, #14) remain the
limiting problems.

### BioCLIP 2: a model that tells natives from weeds

The same 30 pilot photos and 39 lookalike photos were screened with revision 4
by the original BioCLIP and by
[BioCLIP 2](https://huggingface.co/imageomics/bioclip-2) (MIT, ViT-L/14, pinned
at `2957b322`; [#14](https://github.com/gardner/weedz/issues/14),
[comparison](../benchmarks/model-comparison.json)).

| Check | BioCLIP | BioCLIP 2 |
| --- | --- | --- |
| Incidental photos with a positive margin | 5 of 24 | **1 of 24** |
| References with their own target on top (margin range) | 6 of 6 (0.032–0.165) | 6 of 6 (0.051–0.097) |
| Toetoe beating every comparison as pampas | 6 of 6 | **1 of 6** |
| Native clematis beating every comparison as old man's beard | 9 of 15 | **2 of 15** |
| Kānuka, broom or mānuka beating every comparison as gorse | 2 of 18 | **0 of 18** |
| CPU seconds per photo (about 7–11 windows) | 0.67 | 3.1 |

BioCLIP 2 keeps every reference clearly positive while rejecting most lookalikes
and the false alarms. The chafer's pink fibres and the sky tiles no longer
rank; its single incidental candidate is the oystercatcher's riverbed vegetation
at +0.009. The cost is about 4.6× the CPU time and a 1.7 GB checkpoint. On that
basis the project lead chose BioCLIP 2 as the default for new runs. Runs saved
earlier keep the original BioCLIP, and `--model bioclip` still selects it. These
are small, source-labelled samples, not reviewed accuracy.

### Whole frame or tiles: what a reviewer would see

Issue [#12](https://github.com/gardner/weedz/issues/12) asks whether whole-photo
or region-based screening puts more useful weeds in front of a reviewer at a fixed
budget. Revision 4 already scores both: a letterboxed whole frame and its square
tiles. `scripts/compare_framing.py` screens each photo once with BioCLIP 2, then
reads the same window similarities three ways:

- the whole frame only;
- the tiles only, with featureless tiles excluded;
- either, which is what runs use.

Each readout ranks photos by best margin. A budget K is the top K photos. The
same 30 pilot photos and 39 lookalike photos were measured on 14 November 2026
([summary](../benchmarks/whole-vs-region.json)).

**No verdict is possible yet.** The pilot has no reviews, blind audits or
findings. Its reference collection therefore has no example eligible for
evaluation, so recall and precision on the incidental review queue are "not
measurable" at every budget. The only labels are source subject labels: six
reference photos whose subject is a weed, and 39 photos whose subject is a
lookalike. They describe the subject, not background plants. A lookalike photo
is not a verified absence of the weed.

| Check | Whole frame | Tiles | Both (revision 4) |
| --- | --- | --- | --- |
| Windows encoded per photo (median) | 1 | 6 | 7 |
| References with their weed as suggestion in the top 5 / top 10 of the pooled 69 | 5 / 6 of 6 | 5 / 6 of 6 | 5 / 6 of 6 |
| Reference margins | 0.030–0.082 | 0.051–0.097 | 0.051–0.097 |
| Lookalikes in the pooled top 20, suggested as the weed they resemble | 12 | 9 | 9 |
| Incidental photos with a positive margin | 0 of 24 | 1 of 24 | 1 of 24 |
| Lookalike photos with a positive margin | 1 of 39 | 4 of 39 | 4 of 39 |

| Incidental review queue | Top 5 | Top 10 | Top 20 |
| --- | --- | --- | --- |
| Photos shared by the whole-frame and tile queues | 3 | 5 | 17 |
| Photos shared by the tile and revision 4 queues | 5 | 10 | 20 |

What this shows:

- **In practice, revision 4 ranks by its tiles.** The whole frame won only 4 of 69
  photos. It never changed the incidental queue at any budget, while costing one
  window in seven.
- **The choice changes what a reviewer sees.** The whole-frame and tile queues
  share only 3 of the top 5 and 5 of the top 10 incidental photos. The suggested
  species differs for 12 of 24 incidental photos. Independent labels will decide
  which choice is better.
- **Subject photos cannot separate the arms.** Every readout reaches the same
  references at the same budgets. Tiles widen the reference margins, but they also
  lift more lookalikes above zero (4 against 1). The whole frame puts more
  lookalikes in the top 20 (12 against 9), but all except one of its lookalike
  margins are negative. Neither difference measures background-plant
  performance.

What it cannot show: which readout finds more useful background weeds, its
missed weeds, or its false-alarm rate. Ranking 69 source-labelled photos is a
sanity check, not accuracy. The tiles are search windows from the same model,
not plant-region proposals followed by a specialist identifier, which this
repository does not have.

The harness already reads independent labels when they exist. It uses only the
blind audit sample, a quarter of incidental photos chosen from their ids
regardless of rank. Ranked review meets photos in revision 4 margin order, so
findings from it would favour the tile readout that ordered the queue. On the
sample, it reads:

- reference-collection examples eligible for evaluation;
- agreeing first answers from the blind audit, where "none" means no watchlist
  weed was visible. Disputed or unsure answers are skipped.

A species labelled both present and absent on one photo is left out as
unresolved. Re-run the command in the summary once the sample has been audited. The incidental rows then report recall, known false alarms and precision
over labelled photos per budget. Unlabelled photos are counted separately, never
as false alarms.

### Optimised models: does a smaller model still find the same weeds?

A phone cannot run BioCLIP 2 as the server does
([#51](https://github.com/gardner/weedz/issues/51)), and any model small
enough to fit changes the scores
([#52](https://github.com/gardner/weedz/issues/52)). Only the image tower needs
to be on the phone. The prompts are fixed, so the server can embed them once
and ship a table of 16 vectors.

`scripts/compare_optimised.py` checks each candidate image tower against the
BioCLIP 2 fp32 reference. It uses the same photos and the same revision 4
windows. Each photo's windows are pre-processed once, and every candidate
encodes them in its own process. The candidate's window similarities are then
scored against the reference's text embeddings and read the way a run reads
them. `weedz.discovery.parity` reports where the candidate disagrees with the
reference and applies fixed, versioned thresholds (version 1). Each threshold
has a reason written next to it, and the limits were set before the first run:

| Check | Limit | Why |
| --- | --- | --- |
| Largest change in any photo's margin for any weed | 0.01 | BioCLIP 2's only incidental candidate is at +0.009; its weakest reference at +0.051 |
| Top-suggestion changes that are not near-ties | 0 | With every margin within 0.01, only margins within 0.02 of each other can swap |
| Reference photos no longer found as their weed | 0 | Every pilot reference is found by both pinned models |
| Lookalikes newly beating every comparison as their weed | 0 | Rejecting lookalikes is why BioCLIP 2 became the default (#14) |
| Photos swapped in the incidental review queue, per budget (5, 10, 20) | 1 | Most incidental margins are negative and close together |

Size, memory and time are reported, not gated. What a phone can afford depends
on the platform (#50).

On 14 November 2026 the 30 pilot photos and 39 lookalike photos were measured
on an AMD Ryzen 9 9950X with 4 threads
([summary](../benchmarks/optimised-model-parity.json)). The table shows median
encoding time per photo (about 7 windows):

| Image tower | Size | Peak memory | Seconds per photo | Parity |
| --- | --- | --- | --- | --- |
| BioCLIP 2, PyTorch fp32 (reference, what runs use) | 1216 MB | 1856 MB | 2.88 | — |
| BioCLIP 2, ONNX fp32 | 1216 MB | 2217 MB | 1.12 | **Kept**: margins within 0.000002 |
| BioCLIP 2, fp16 | 608 MB | 1110 MB | 8.07 | **Kept**: margins within 0.0006 |
| BioCLIP 2, ONNX dynamic int8 (per tensor) | 306 MB | 897 MB | 0.46 | Failed |
| BioCLIP 2, ONNX dynamic int8 (per channel) | 308 MB | 836 MB | 0.47 | Failed |
| BioCLIP ViT-B/16, fp32 (smaller tower) | 345 MB | 877 MB | 0.62 | Failed |
| BioCLIP ViT-B/16, ONNX dynamic int8 | 87 MB | 438 MB | 0.10 | Failed |

What this shows:

- **fp16 keeps BioCLIP 2's behaviour at half the size.** Every top suggestion,
  queue and lookalike outcome is unchanged. It is slow here only because this
  desktop CPU has no fast fp16 arithmetic. Phone neural engines and GPUs are
  built for fp16, but that speed has to be measured on a phone.
- **ONNX export on its own is exact**, and on this CPU onnxruntime encodes 2.6×
  faster than PyTorch. It saves no space, though.
- **Dynamic int8 is 4× smaller and about 6× faster here, but it changes what
  the screen says.** Margins move by up to 0.08 (median 0.007). Two native
  lookalikes (a *Clematis forsteri* and an *Austroderia* toetoe) newly beat
  every comparison as the weed they resemble, and the top 20 of the incidental
  queue swaps two photos (one per budget with per-channel weights). All 9–11
  changed top suggestions were near-ties, and no reference was lost. Plain
  dynamic int8 of the whole tower is not safe to ship. Gentler int8 schemes are
  untested here.
- **The smaller BioCLIP tower is a different model, not an optimisation.** It
  lets 17 of 39 lookalikes beat every comparison as their weed, against 3 for
  BioCLIP 2, and reorders the queue, as #14 found.
  The harness fails it on every check except references, which shows it catches
  a real regression.

What it cannot show: phone latency, memory, battery or heat. Desktop CPU numbers
are not phone numbers, and conversion to Core ML, TFLite or ExecuTorch is
deferred to the platform choice (#50). Parity means agreeing with the reference
on 69 source-labelled photos. It is not accuracy, and a candidate that agrees
here can still diverge on other photos. On a phone, the per-photo
original-subject comparison is also absent, because a phone photo has no source
taxon. That changes the ranking itself and needs its own check.

### Source suitability

`uv run main.py suitability --run nelson-tasman-3e62ad801459`
([#6](https://github.com/gardner/weedz/issues/6)) states what the run's
photos can support before anyone reviews them. On 14 November 2026 it showed
the following:

- **Scope.** There are 24 incidental photos: 7 independent site visits plus 8
  ungrouped photos. Each region returned all 12 photos requested.
- **Dates.** All 24 are from 30 and 31 December 2024. The run sampled newest
  first, so every earlier date, and the autumn, winter and spring seasons, is
  unassessed.
- **Locations.** Twenty photos have a search area. Four report no accuracy, so
  they have none. Reported accuracy runs from 3 m to 1,634 m (median 18.5 m),
  and 11 photos are within 20 m.
- **Permitted uses.** All 24 images may be shared. Ten photos are for
  non-commercial use only. Four locations are withheld because their accuracy
  is unknown.
- **Screening.** All 24 photos are screened. The run predates the record of
  pixel coverage and featureless windows, so both are "not recorded". Visible
  vegetation is not measured.
- **Comparison.** Twenty photos were compared with the DOC snapshot. The four
  photos without an accuracy were not.
- **What the photos cannot support:**
  - a field search lead: 4 photos
  - aerial site context: 13 photos (3 site visits + 8 ungrouped)
  - novelty: 4 photos
  - an independent count: 8 ungrouped photos
  - a shared location: 4 photos
  - a study-period conclusion: not assessed, because no study is linked

This is a two-day summer sample. It can support findings about those days,
but not about other seasons or years.

### Outcomes against the success measures

On 14 November 2026 the run was read against the PRD's eight success measures
with `uv run main.py outcomes --run nelson-tasman-3e62ad801459`
([#29](https://github.com/gardner/weedz/issues/29),
[report](../benchmarks/nelson-tasman-outcomes.json)). The base is 24 incidental
photos: 7 independent site visits, plus 8 photos that could not be grouped.
Those 8 are counted apart, not as visits.

| Measure | Status | Result |
| --- | --- | --- |
| Useful incidental yield | Not yet measurable | No incidental photo reviewed; usefulness is not judged separately yet (#18) |
| Reviewer effort per useful finding | Not yet measurable | No useful finding to divide by; no review time recorded |
| Missed visible targets | Not yet measurable | The 6-photo blind audit sample is not yet audited. Even once audited, calling a found weed a miss needs an agreed detection rule (#16) |
| Novel or earlier evidence | Not yet measurable | No confirmed finding to compare with the DOC snapshot of 14 November 2026, and no novelty judged |
| False-alarm workload | Not yet measurable | No incidental photo reviewed. Even then, counting false alarms needs a rule for which suggestions are proposed leads (#16) |
| Follow-up usefulness | Not yet measurable | Intended users' judgements are not recorded (#18, #27) |
| Evidence and review completeness | Partially measured | 20 of 24 photos carry source, attribution, licences, date, location accuracy and checksum (4 report no positional accuracy). None has a review decision yet |
| Coverage and review usability | Partially measured | 0 of 24 photos and 0 of 7 visits assessed; nothing yet records users completing the study |

The honest result is that the pilot has not yet produced any outcome. Six of the
eight measures cannot be answered until people review the queue, audit the blind
sample and judge usefulness separately from visibility. "Unknown" in the report
means unmeasured, not zero: it does not show that the run found nothing, nor that
it missed nothing. Even once reviews exist, a confirmed review is not a useful
finding, and "no DOC record within 5 km" describes a sparse reference set, not
novelty. No success limits have been agreed (#1), so the report gives values
and statuses, not pass or fail verdicts.

The product can now record the study itself: question, partner, people, bounds,
budget, reference records and agreed limits (#2). This run has no study linked,
because the partner and question decision (#1) is still open. On a copy of the
pilot data, a *sample* study shows how the report reads once limits exist. It
records 24 photos and 10 hours, and limits of at least 80 % complete evidence,
50 % coverage and 2 useful site visits. The report then gives:

- **Evidence completeness: met.** 83.3 % of incidental photos have complete
  evidence.
- **Coverage: not comparable.** It is 0 %, a lower bound while all 24 photos
  wait for review.
- **Useful yield: not comparable.** Usefulness is not judged yet (#18).

Every other measure says "not agreed", and the budget shows 0 of 10 hours and
0 of 24 photos used. These limits were invented for the check and are not
agreed limits.

The next experiment should include independently reviewed native lookalikes and genuine
no-vegetation negatives, and a broader sample of habitat-visible animal photos.
Retain low-ranked photos for missed-weed review. Compare whole-frame and regional
analysis at a fixed reviewer budget before deciding whether a stronger model or
SAM proposals improve the outcome. An acquisition filter based on visible
vegetation must be audited for missed plants; it cannot establish weed absence.

The run completed through a real persistent Temporal development server and
resumed after interruption. Its completed history replayed successfully. All
30 input hashes were checked, and all rankings were independently recomputed
from saved window similarities. Browser checks verified the actual queue,
region/reference filters, source-image loading, window toggling, JSON export,
and mobile layout without changing review decisions. Python tests cover the
review audit trail and failure/retry behavior; a browser regression test covers
late responses during run switching.

The [tracked summary](../benchmarks/nelson-tasman-screening.json) records the
source selection, model revision, weights hash, counts and manifest checksum.
Detailed source records, attributed photos and the manifest remain in
`data/pilot/`; screenshots and Temporal history are in
`runs/nelson-tasman-review/`. An earlier development run was terminated and marked
superseded when a window-ranking regression was found; it is excluded from these
results. [Local operation](local-development.md) explains how to reopen the run
and continue review.
