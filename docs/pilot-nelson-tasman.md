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
at +0.009. The cost is about 4.6× the CPU time and a 1.7 GB checkpoint. The
default stays `bioclip` until the project lead decides; runs can opt in with
`RunSpec.model = "bioclip-2"`. These are small, source-labelled samples, not
reviewed accuracy.

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
