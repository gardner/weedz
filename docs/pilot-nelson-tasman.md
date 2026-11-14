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

The highest-ranked incidental suggestion was pampas grass in an
[Australasian gannet photograph](https://www.inaturalist.org/observations/257459474).
The displayed search window shows bird and sky, an obvious false alarm. A
positive comparison margin does not establish plant presence. This concrete
failure argues against automatically accepting these rankings or scaling this
method as a validated detector.

### Lookalike photos: can screening tell the weed from its lookalike?

On 14 November 2026, 39 source-labelled iNaturalist photos of declared lookalikes
were screened with the same model and ranking
([#11](https://github.com/gardner/weedz/issues/11), [summary](../benchmarks/nelson-tasman-lookalikes.json)).
That was up to three per taxon per region.

Every photo has a top suggestion, which is the watchlist species with the largest
margin, and the review desk shows it whatever the margin's sign. A positive
margin means that weed also beat every comparison label.

| Lookalike | Resembles | Top suggestion is that weed | Also a positive margin | Median margin |
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

The next experiment should include original-subject taxon prompts as stronger
comparison labels, independently reviewed native lookalikes and genuine
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
