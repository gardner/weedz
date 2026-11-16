# Region evaluation protocol

This evaluator separates localisation from identification. Existing image-level
source labels, model proposals and Label Studio predictions are not independent
region ground truth. The mechanics tests contain constructed examples; they are
not benchmark observations.

## Inputs and eligible claims

An evaluation uses a frozen canonical sample manifest, explicit source or reviewed
annotations, and checksum-bound model outputs. Image, mask and output hashes must
refer to the same upright source pixels. Newly acquired ground-truth masks require
their own hashes. Functional categories and taxonomic names remain separate label
spaces; an explicit mapping is required before comparing species names.

Source annotations retain source origin and their actual review status. Published
source completeness can support a source-benchmark denominator when documentary
evidence names the task and target scope. It does not become independently accepted
human review. A later NZ gold release requires the separate review policy and actual
review history. Missing groups or unknown training overlap are reported as unknown.

## Localisation

Boxes use upright source-image coordinates with exclusive right/bottom edges.
Mask IoU and Dice compare actual foreground pixels on the same grid. Two empty
masks have undefined overlap, rather than a perfect localisation score. Boxes alone
cannot establish pixel overlap.

At each declared IoU threshold and proposal budget, matching maximises the number
of labelled regions recovered with a one-to-one assignment. Truth input order is
stable. Search edges prefer higher overlap, then earlier proposal order; augmenting
paths recover matches that a simple greedy assignment could strand. This is
**deterministic maximum-cardinality threshold matching**, not COCO average precision
or COCO's detection matching algorithm. Assignment never reads predicted species.

Report recovered and missed labelled regions separately from unmatched proposals.
Unmatched proposals are not automatically false positives: labels may be partial,
or proposals may cover plants outside the assessed label scope. Duplicate proposals
cannot increase recall. An exhaustive, eligible task/target scope is required before
counting false alarms or verified negatives.

Semantic foreground union overlap is a separate result. Connected components of a
semantic mask do not create independently labelled plant instances. Source polygons
count as labelled regions or patches unless the source documents an instance
interpretation. A crop/weed foreground comparison cannot measure species accuracy.

## Identification and end-to-end findings

Crop identification is conditional on a valid localisation match and an explicit,
supported taxonomic mapping. Unsupported labels remain excluded with a reason.
Wrong identification of a matched crop is distinct from a missed proposal. The
operating view and decision policy must be fixed before scoring; ground truth must
not choose the most favourable crop view or threshold.

Raw BioCLIP margins remain signed margins, not probabilities. Scores from different
model profiles do not share a ranking scale. Report image and proposal budgets as
such; human review time requires actual measured human work.

## External data and NZ preparation

CWFID provides functional crop/weed annotations and vegetation masks, under its
non-commercial research terms. Its images are false-colour R/NIR/R. The vegetation
mask comes from an NDVI/Otsu procedure; it is not a manually drawn plant boundary.
Human crop/weed regions leave heavily overlapping vegetation unassigned. Canonical
category masks therefore retain sparse supervision and explicit assessed support.
Their diagnostic is coverage of labelled positive pixels, not full-scene pixel
accuracy, foreground precision, instance recall or species correctness. Algorithmic
vegetation-mask agreement must remain separately named and attributed.

Its source split has 40 train and 21 test memberships
but only 60 unique images: image 28 occurs in both lists at source commit
`36290d0912a032f0bd1a5678ed55457ddafde217`. Preserve this defect and quarantine the
overlap for held-out claims. Neither these source labels nor later NZ review proves
that model pretraining excluded the images.

The existing NZ diagnostic cohort has already been inspected during development.
Preparing it for later review does not turn it into a fresh model-selection holdout.
No native-device feasibility or high-resolution pre-SAM tiling result is implied by
this evaluation protocol.

Protocol references: the official [COCO evaluator](https://github.com/cocodataset/cocoapi/blob/master/PythonAPI/pycocotools/cocoeval.py)
defines its own matching/AP convention; the official [LVIS evaluator](https://github.com/lvis-dataset/lvis-api/blob/master/lvis/eval.py)
handles explicitly negative and non-exhaustive category scopes. The
[CWFID source](https://github.com/cwfid/dataset) describes its annotations and use terms.

## Running a closed evaluation

Run `python -m weedz.region_evaluation.cli --help` from the installed environment.
The command requires SHA-pinned label manifest and proposal-ready receipt, the
asset root, proposer kind, and a new private output directory. `--mode boxes`
measures supplied boxes; the default sparse mode measures supplied positive mask
support. `--truth-origin source` is explicit by default; reviewer mode requires
accepted standing annotations and uses only reviewer completeness. These modes
never combine a publisher's old label with a later human correction.

Identification additionally requires all of `--classifier`, `--classifier-sha256`,
`--taxonomy-map`, `--taxonomy-map-sha256` and `--vocabulary`. The mapping names the
source namespace and exact checksum-pinned classifier vocabulary. The operating
view is the stored masked crop and top1 taxon; scoring cannot choose a crop using
its ground-truth answer. Unknown or contradictory target claims remain unassessed.

`--allow-source-subset` explicitly permits an independently frozen primary cohort
to reuse a larger original inference receipt by exact sample/pixel identity. Both
manifest hashes and all excluded inference records remain in the report. Duplicate
pixel records block a primary aggregate rather than silently choosing a label set.
An explicit `--max-source-bytes 160000000` supports large lossless canonical PNGs;
the default remains 20MB and the 40MP bound is unchanged. Explicit ingress is bound
to SAM2/SAM3 and crop-classifier provenance/cache identity; it never resizes truth.

## Initial source-bound development evidence

The closed ImageWeeds primary cohort contains 138 unique images and 645 manual
source boxes (57 soybean and 81 maize images). The raw source has 175 records but
157 unique pixel images. One invalid-geometry record and all 36 records from 18
ambiguous, divergent-label duplicate pairs are quarantined before primary scoring.
No labels were unioned, repaired or selected using model outcomes. Original MPO
primary-frame pixels are preserved in canonical lossless PNGs. Manual box/patch
units are not verified individual-plant instances, and completeness is partial.

The SAM2.1 tiny baseline (768px, 8×8 grid, at most 12 proposals) matched 8/645 source
regions at IoU≥0.5, retaining 267 proposals. Fixed masked PlantCLEF top1 was correct
for 1/8 matched regions; 637 labelled regions were not localised. Unmatched proposals
are unassessed, not verified false alarms. The single denser development experiment
was selected after this baseline's geometry diagnostic: 1024px, 16×16 grid,
batch16, at most 24 proposals, with unchanged weights and filter thresholds. It
matched 22/645 source regions and retained 838 proposals. Its fourfold grid and
twofold retention cap are unequal compute budgets, not a held-out winner claim.
All thresholds/budgets and exact child input/model receipts remain in private
reports; these figures do not establish NZ weed performance or pretraining exclusion.

The complete CWFID 60 diagnostic measures only manually coloured assessed positive
support. At all retained baseline proposals, weed coverage was 216,716/4,322,897
(5.01%) and crop coverage 6,155/1,212,423 (0.51%). These are sparse positive-pixel
coverage, not full-scene IoU/Dice, negatives, species accuracy or plant recall.
CWFID inputs and reports remain private under their actual research terms.

Current closed evidence is under the owner-private
`weedz-evaluation-artifacts/20261116` sibling directory; no source media or model
outputs belong in Git. A separately prepared 90-image NZ observer-separated cohort
awaits human review and contributes no independent NZ/background metric here.
