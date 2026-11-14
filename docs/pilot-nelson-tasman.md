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
