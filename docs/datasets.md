# Datasets, curation, and detection methods

Reviewed 13 November 2026. Dataset facts below link to publisher documentation;
processing choices are our proposed design unless marked **implemented**.
See [the ideal pipeline flow](pipeline.md) for the end-to-end design, SAM's
proposed role, model training, and the runtime detection path.

## What works today

Only the **Leafy Spurge `crop` configuration** is downloaded and supported by the
executable pipeline. The other sources are candidates, not implemented adapters.
Changing `--data-dir` changes a filesystem location; it does not select another
dataset. No iNaturalist images have been imported.

```sh
uv run main.py
uv run main.py run --offline
```

The current path is:

| Step | Actual behavior | Code |
| --- | --- | --- |
| Acquire | Download 900 small crops, two CSVs, and the source README from a pinned Hugging Face revision; record SHA-256 checksums and attribution | [provenance.py](../src/weedz/provenance.py) |
| Read | Validate source labels, finite coordinates, unique sample IDs, and safe image paths | [dataset.py](../src/weedz/dataset.py) |
| Split | Preserve published test; reserve the highest training cluster for validation; apply a 2 m separation buffer | [partition.py](../src/weedz/partition.py) |
| Encode | Require opaque 39×39 RGB/RGBA crops; calculate 84 RGB/HSV histogram, colour-summary, and texture features | [features.py](../src/weedz/features.py) |
| Fit | Fit a scaler and class-balanced logistic regression on fitting observations only | [model.py](../src/weedz/model.py) |
| Decide | Choose the highest threshold meeting the requested validation recall; default target is 90% | [evaluation.py](../src/weedz/evaluation.py) |
| Evaluate | Evaluate the held-out test observations; save model, metrics, input/source checksums, and partition IDs | [pipeline.py](../src/weedz/pipeline.py) |
| Review | Export WGS84 points, CSV predictions, and an offline map with embedded crops and error filters | [report.py](../src/weedz/report.py) |

The [recorded baseline](../benchmarks/leafy-spurge-cpu.json) uses 700 fitting,
100 validation, and 100 test observations. Test recall is 82.4%, precision 63.6%,
and accuracy 67%, versus a 51% majority-class accuracy. It missed 9 positives
and produced 24 false alarms. The validation set had 5 misses and 21 false alarms.
These are measurements at one Montana site, not evidence of NZ generalisation.

There is currently no saved human-review workflow, general dataset schema,
perspective augmentation, learned image encoder, box detector, pixel segmenter,
or inference over arbitrary geographic rasters. The map's `truth` field means
the upstream survey label; it has not been independently adjudicated by us.

## Dataset shortlist

Priority is a suggested acquisition order, not a claim that sources can be pooled.
Only Leafy Spurge crop files have been downloaded and exercised locally. Other
entries describe published contents; verify actual archives and annotation
conventions when implementing their adapters. Pin the exact release at import.

| Source | Contents and viewpoint | Rights/access | Intended role and status |
| --- | --- | --- | --- |
| [Leafy Spurge](https://huggingface.co/datasets/mpg-ranch/leafy_spurge) | Montana drone imagery; 39×39 crops, larger context images, survey presence/absence, coordinates, and unlabelled orthomosaic | CC BY 4.0; Hugging Face | **Implemented: crops only.** Retain as the reproducible point-classification baseline; context is a later extension |
| [iNaturalist](https://www.inaturalist.org/pages/developers) | Species observations with one or more photos, often ground/oblique views and close-ups; viewing angle needs curation | Photo and observation licences are independent; initially admit CC0/CC BY for both | **Next:** curated species-identification collection, starting with NZ gorse, broom, and reviewed lookalikes |
| [MAVSD](https://doi.org/10.6084/m9.figshare.28428707.v1) | Chinese UAV RGB images at several angles; 13 semantic categories including invasive goldenrod; pixel masks/polygons | CC BY 4.0; Figshare archive is approximately 15.3 GB | **Next:** multi-angle segmentation benchmark; acquire the archive, then extract a bounded working subset before broad training |
| [LINZ imagery](https://github.com/linz/imagery) plus our own field labels | NZ orthorectified geographic imagery; rural surveys typically 20–30 cm; NIR products exist for some surveys; no supplied weed labels | Open imagery; retain the selected collection's actual licence, owner, and attribution | **Early local validation:** independently label one target species at several sites using suitable capture dates and resolution |
| [DOC weed observations](https://www.gbif.org/dataset/d986e335-a2e3-44f0-9606-845e2eb6081d) | NZ occurrence records from 1983–2023; locations may be approximate to 100 m | CC BY 4.0; GBIF/Darwin Core archive | **Supporting:** select survey areas and check taxonomy; no direct image supervision |
| [DeepWeeds](https://github.com/AlexOlsen/DeepWeeds) | 17,509 field photos from Queensland; eight weed species plus a negative class; image-level labels | Dataset images/annotations: CC BY 4.0; repository code licence is separate | **Optional:** ground-photo classification and transfer experiments |
| [ImageWeeds v2](https://data.mendeley.com/datasets/8kjcztbjz2/2) | North Dakota aerial and greenhouse/handheld imagery with bounding-box annotations in several formats | CC BY 4.0; Mendeley | **Optional:** box detection, scale variation, and agricultural transfer experiments |
| [OpenWeeds](https://openweeds.linkoping-ri.se/) | Swedish agricultural images, including tractor views, with detection boxes and some sparse segmentation annotations | Publisher describes permissive commercial use; confirm the exact licence and accessible release before admission | **Investigate:** detection/sparse-label transfer; ingestion is blocked on source verification |
| [Sentinel-2 Level-2A](https://dataspace.copernicus.eu/data-collections/copernicus-sentinel-missions/sentinel-2) | Repeated multispectral satellite observations; bands have different native resolutions; no supplied weed labels | Copernicus open data terms; preserve product metadata and attribution | **Later:** regional screening and change detection with independent reference labels |
| [WeedMap](https://www.research-collection.ethz.ch/entities/researchdata/0a5dcd76-cc44-4fbe-9f48-d8a717c90a30) | Agricultural UAV multispectral imagery and semantic mapping labels | Repository states non-commercial use permitted | **Deferred:** research comparison only unless intended-use rights are resolved; exclude from the initial product dataset |

ImageWeeds' [data paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC10618417/)
describes its annotations as bounding boxes. Multiple export formats do not
imply that pixel masks are available. OpenWeeds' [project page](https://openweeds.linkoping-ri.se/about.html)
and [documentation](https://github.com/edl78/obdb_docs) describe acquisition and
training workflows, but the website still has placeholder sections and the
exact dataset licence has not been confirmed here. Its entry remains a candidate
rather than a verified acquisition recommendation.

## Processing each source according to its contents

All routes below except Leafy Spurge crops are **planned**. Sharing acquisition,
provenance, review, and reporting does not mean using the same label, model head,
image size, threshold, or metric for every source.

### Leafy Spurge: surveyed points

Use the implemented route above. Keep its `present`/`absent` meaning attached to
the survey location and the small crop around it. The label does not describe
every pixel, or prove absence throughout a larger surrounding image.

For a context extension, join larger images to the same observations and retain
the original group IDs. Use the point's aligned local crop, or an explicitly
specified weak-supervision method. Do not assign a positive point label to all
pixels in a 1024×1024 context image. Larger footprints require larger spatial
separation; the current 2 m guard is specific to the tiny crops. The unlabelled
orthomosaic can support inference and candidate review after geographic alignment
is verified, but cannot independently score segmentation or area estimates.

### iNaturalist: species observations and photos

Acquire a bounded taxon/place query using the official API, or the
[licensed image dataset](https://github.com/inaturalist/inaturalist-open-data)
for bulk work, following the [API practices](https://www.inaturalist.org/pages/api%2Brecommended%2Bpractices).
Archive the response/query, observation and photo IDs, taxon, observer/photographer,
licences, retrieval date, and checksums. Check each photo individually even when
the observation passes the licence filter; keep API credentials out of manifests.

Start with species-level, Research Grade observations, then review image
suitability. [Research Grade](https://help.inaturalist.org/en/support/solutions/articles/151000169936-what-is-the-data-quality-assessment-and-how-do-observations-qualify-to-become-research-grade-)
is an observation assessment, not a guarantee that every associated photo shows
diagnostic features. Select target-visible images or curate observation-level
photo sets. Record close-up, whole-plant, and habitat views separately.

Preserve aspect ratio; use controlled resize/padding or reviewed crops for a
pretrained image encoder and species-classification head. Train and score
image-level classification, or declare observation-level aggregation in advance.
Return taxon scores and an abstain/review decision. Boxes and masks require new
annotations. Another species' observation is not a confirmed weed-free scene.

Keep all photos of an observation, duplicate photos, and known encounters with
the same plant in one partition. Test additional observer/site holdouts. Export
an observation location only with its uncertainty and privacy status; it is not
a plant boundary or a camera-to-ground projection. Respect
[obscured/private coordinates](https://help.inaturalist.org/en/support/solutions/articles/151000233080-how-does-inaturalist-protect-the-locations-of-sensitive-species-).
Hosted photos have metadata removed, so camera pose must not be assumed available
from [downloaded image EXIF](https://help.inaturalist.org/en/support/solutions/articles/151000233085-how-to-download-a-photo-from-inaturalist).

### MAVSD: pixel masks across viewing angles

The [publisher's release](https://api.figshare.com/v2/articles/28428707)
describes RGB views at 30°, 45°, 60°, and 90°, semantic masks, polygons, and
angle-specific split lists. Retain the publisher's angle convention in metadata;
do not silently equate it with a different camera-pitch convention.

Decode the mask palette/class map and inspect image/mask alignment. Preserve all
13 source categories; goldenrod is the target species, while other vegetation
classes are not automatically invasive weeds. Fit a segmentation head with
joint image/mask transforms and ignored-pixel handling. Evaluate target IoU,
Dice, pixel precision/recall, and patch-level misses by angle and scene.

Keep frames and multi-angle views of the same scene together. Published split
lists alone do not establish scene independence; reconstruct groups from release
metadata and near-duplicate inspection. If reliable grouping cannot be recovered,
report that limitation and use an independently captured holdout. Image-space
masks are valid outputs without georeferencing. Ground polygons and hectares
require valid camera/terrain geometry, especially for oblique views.

### LINZ plus field review: geographic raster segmentation

Choose specific STAC collections/items by target area, capture date, ground
sampling distance, bands, and licence. Read geographic rasters in windows;
retain CRS, pixel-to-ground transform, valid-data mask, and parent raster ID.
Use RGB first. Admit NIR only through an explicit band configuration and a model
that supports it. The [LINZ catalogue](https://github.com/linz/imagery)
documents access through STAC/S3 and separates RGB and NIR products.

Create human-reviewed target polygons and confirmed negative areas, with dates
compatible with imagery capture. Mark ambiguous/unreviewed pixels as unknown.
Field observations made years later do not automatically label historical imagery.
Split whole sites/surveys before tiling. Train on aligned image/mask windows at
an explicit physical scale. At inference, blend overlapping tile predictions,
mask nodata, and reconcile edges before producing final geometry.

Export georeferenced score rasters and review polygons with model/release IDs.
Calculate area in a suitable metric CRS. Measure segmentation and patch recall
on reviewed sites. False alarms per hectare require a representative, exhaustively
reviewed area; they cannot be inferred from a handful of sampled points.

### DOC observations: site selection without a vision head

Parse occurrence records, normalise taxonomy, retain observation dates,
uncertainty, and source IDs, and deduplicate reused records. Use them to propose
survey areas and rank imagery for review. A historical record with approximate
coordinates does not label a present-day image pixel. Missing records are not
absences. No detector is trained directly from this table; promote a record to
visual supervision only through a documented imagery/field verification step.

### DeepWeeds: ground-photo classification

Import the photos and label CSV without collapsing eight species into a single
universal "weed" category. Retain the source negative-class meaning. Use the
same proposed classification interface as iNaturalist, with a dataset-specific
label map and aspect-preserving preprocessing. Score per-class precision/recall,
macro F1, and confusion with the negative class. Audit time/location/camera groups
and duplicate images before accepting published or newly generated splits.
Use overlapping taxa for transfer comparisons; NZ relevance is a separate test.

### ImageWeeds: bounding-box detection

Parse one canonical annotation export, then verify class IDs, coordinate origin,
normalised versus absolute box units, bounds, and image dimensions. Other exports
of the same image are not additional independent samples. Train a box detector
with joint box/image augmentation. Keep derived crops and parent images in the
same partition; hold out capture sessions/sites and report greenhouse and aerial
performance separately. Return species boxes and scores; evaluate per-class AP,
recall, and small-object misses. A box does not define a plant silhouette.

### OpenWeeds: detection and sparse segmentation

Once the source and rights are verified, route boxes through the detection
interface. For sparse masks, train/evaluate only annotated pixels and preserve
an explicit ignore mask elsewhere. Unlabelled pixels are not background. Keep
paired-camera views and acquisition sequences together where those identifiers
are available. Confirm annotation completeness before treating an unboxed plant
as a detector false positive. Report sparse-label scores separately from dense
segmentation benchmarks. Do not claim measured patch area from sparse labels.

### Sentinel-2: spectral and temporal regional screening

Use Level-2A reflectance, product metadata, and quality/cloud masks; retain the
declared bands and native resolutions. [Copernicus documentation](https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Data/S2L2A.html)
describes band resolutions and scene classification products. Resample to an
explicit analysis grid and record transforms; categorical masks use nearest
neighbour interpolation. Verify reflectance scales/offsets per product baseline.

Combine seasonally appropriate observations with independently reviewed labels
whose spatial extent is large enough for the pixels. Fit a spectral/temporal
classifier or segmenter, with geographic and temporal holdouts. Output regional
candidate areas or change scores for follow-up. Upsampling does not recover
individual small plants; do not reuse the crop baseline's species claims or
threshold. The [open data terms](https://dataspace.copernicus.eu/data-collections/copernicus-sentinel-missions/sentinel-2)
apply independently of any imagery access service.

### WeedMap: deferred multispectral segmentation

If permitted for a specific research use, align multispectral tiles and source
semantic labels, preserve band order/scale and valid pixels, and fit a matching
segmentation head. Split at field/flight level before generating derivatives.
Evaluate field-level segmentation with the source's crop/weed label definitions;
those labels do not establish NZ invasive-species identity. Keep this experiment
separate from product training while its stated non-commercial restriction
applies. Availability for download does not change the intended-use restriction.

## Generalising the pipeline

Build reusable ingestion, curation, split, and reporting stages, with task-specific
models. A new source should supply an adapter and an explicit capability record,
not force image-level labels, boxes, masks, and occurrence points into one binary
training table. This is a proposed interface, not an existing API.

### A common sample and annotation contract

Use a small versioned manifest and sidecar annotation/review files first. No
warehouse or dataset service is needed to support the initial collections.

| Concern | Required information |
| --- | --- |
| Identity/lineage | Dataset and release IDs; stable source/sample/asset IDs; parent image/observation; original URI; SHA-256; acquisition query/date |
| Rights | Image and metadata licences separately; creator; attribution; intended-use eligibility; source record of the licence |
| Media | Width/height; format; colour space; dtype; ordered band names/units; valid-data mask |
| Taxonomy | Original source label and taxon ID; reviewed accepted taxon/synonym mapping; separate regional invasive-status policy |
| Supervision | Typed annotation: surveyed point, image/observation class, box, dense mask, sparse mask, occurrence only, or unlabelled |
| Label extent | The actual point/region/pixels supported by evidence; explicit negative, unknown, ignored, and unreviewed states |
| View/scale | Nadir/oblique/ground/unknown; source angle convention and measured pose when available; detail/plant/patch; GSD and footprint when known |
| Geography/time | CRS, transform and footprint when real; coordinate uncertainty/privacy; capture and survey dates; site, flight/session, sensor |
| Grouping | Observation, parent raster, scene/encounter, survey/session, and duplicate-group IDs; final split assignment |
| Review | Reviewer, timestamp, evidence, decision, reason, superseded decision, and independently reviewed status |
| Prediction | Task, taxon, model/release/preprocessing version, score type, threshold, uncertainty/abstention, and geometry only when supported |

An adapter must declare supported tasks and required metadata. Validation should
reject unsupported combinations: for example, image labels cannot silently
become segmentation masks, sparse labels cannot become dense background, and
unknown ground geometry cannot produce ground-area measurements. Non-geographic
photos should still work for classification without invented coordinates.

Keep original labels alongside reviewed labels. "Not leafy spurge" does not mean
"no invasive plants"; "another observed species" does not mean "no gorse in the
frame". Taxon identity and weed status in a jurisdiction are separate concepts.

### Bronze, silver, and gold releases

| Layer | Contents | Promotion rule |
| --- | --- | --- |
| Bronze | Original downloaded media/metadata, licence evidence, source revision/query, checksums | Preserve source bytes; create a new snapshot when the source changes |
| Silver | Normalised inventory, typed annotations, quality/duplicate groups, append-only review decisions | Trace every correction or exclusion to evidence; keep unknowns explicit |
| Gold | Frozen eligible samples/labels, task configuration, partition manifest, and evaluation protocol | Resolve required reviews, demonstrate split separation, and pin all inputs before training |

`data/leafy-spurge` currently acts as a bronze source subset. Checksums detect
changes; they do not make local storage physically immutable. Gold is a dataset
release with explicit training/validation/test assignments, not a synonym for
the test set. Versioned correction files produce new releases without rewriting
the upstream originals. The saved map supports visual inspection but does not
persist review decisions; editable review and dataset promotion are still to build.

### Improve coverage and annotation quality

1. Measure coverage by species, source, geography, season/growth stage, viewpoint,
   GSD/subject size, sensor, habitat, and supervision type. Count independent
   sites/encounters as well as images; many near-identical frames add little
   evidence of generalisation.
2. Acquire missing combinations, particularly the same target species across
   ground, oblique, and aerial views. A comparison of ground gorse with aerial
   leafy spurge changes species and viewpoint together and cannot isolate either.
3. Review fit/validation disagreements and a random sample of agreements. Record
   whether a sample was selected diagnostically or randomly so a targeted queue
   is not mistaken for an unbiased label-quality audit. Do not curate new training
   labels from the test set and then report that same test as independent.
4. Include reviewed lookalikes, verified target-absent scenes, non-flowering
   plants, partial occlusion, variable illumination, and difficult habitats.
   Inspect held-out evaluation labels independently of model predictions.
5. For model-assisted masks or pseudo-labels, retain model/version/score and human
   review state. They remain predictions until accepted through the annotation
   process; they are not independent gold test evidence.

### Improve models without losing an honest baseline

| Stage | Experiment | Evidence needed before adopting it |
| --- | --- | --- |
| Preserve | Retain the current colour/texture model as a cheap regression baseline | Reproduce its frozen protocol and recorded results |
| Learn representations | Compare a pretrained RGB image encoder with a frozen-embedding classifier on curated classification data | Better grouped validation and source/site transfer at a recorded compute cost |
| Match supervision | Fine-tune classification, box detection, or segmentation heads only for compatible labels | Better task-specific validation; no conversion of weak labels into unjustified dense truth |
| Improve robustness | Train with rotations, scale/crop changes, illumination variation, and modest perspective changes | Better measured performance on actual views and resolutions expected in deployment |
| Control domain mixtures | Balance batches/loss contributions across sources, species, and label quality; use separate modality heads where needed | Improvement on each critical domain; large sources must not hide regression on a smaller target domain |
| Support review | Calibrate scores on held-out development data where justified and set abstention/threshold rules | Precision/recall and review workload on held-out deployment-like data, including unfamiliar taxa/scenes |

Perspective augmentation does not create the hidden surfaces of a 3D plant.
Preserve camera metadata when provided; use unknown when absent. For raw aerial
surveys, camera calibration and orthorectification belong before geographic
mapping. For already orthorectified imagery, retain the supplied geometry. See
[OpenCV's homography explanation](https://docs.opencv.org/5.0/tutorials/features/homography/homography.html)
for the planar assumptions behind a perspective transform.

Choose physical footprints for aerial training windows rather than treating
every 256-pixel image as the same scale. Preserve photo aspect ratios. For
images with masks/boxes, apply exactly matching geometric transforms to labels;
use appropriate categorical interpolation and preserve ignored regions.
RGB-only and multispectral inputs need declared band handling. Normalisation,
sampling, augmentation, and calibration must be versioned and fitted using
permitted development data, without leaking held-out data into selection.

### Evaluate the intended task and deployment

Split parent scenes/sites/observations before making tiles, crops, augmentations,
or pseudo-labels. Link exact and near duplicates across sources, including a
single iNaturalist photo reused through another biodiversity portal. Maintain
published benchmark scores separately when a stricter grouping changes the split.

| Evaluation | What it establishes |
| --- | --- |
| Grouped within-source holdout | Performance on unseen encounters/scenes within a collection |
| Leave-one-source/site/season out | Whether performance transfers beyond the source or collection conditions |
| Viewpoint/resolution slices | Which views/scales work; use overlapping taxa to avoid species confounding |
| Independent NZ field holdout | Whether the intended local species, habitat, and capture conditions are supported |
| Open-set and hard-negative review | Whether unknown taxa/lookalikes cause confident false alarms or useful abstentions |

Use class precision/recall, macro F1, and appropriate imbalance-aware summaries
for image labels; AP/recall by object size for boxes; IoU/Dice and patch recall
for dense masks; annotated-pixel metrics for sparse masks. Occurrence-only tables
do not supply vision accuracy. Include independent-group counts and uncertainty
on reported metrics. Report per-domain and worst relevant slice results alongside
overall scores. Sampled point errors cannot establish false alarms per hectare.

Select models, thresholds, calibration, and postprocessing on development data,
then freeze them for the final holdout. Our current test has been reported and
inspected; repeated optimisation against it would turn it into development data.
Acquire a new independent holdout for future generalisation claims. The current
binary score is not calibrated confidence and is not a universal weed threshold.

## Implementation order and acceptance checks

This is proposed follow-up work. The only available CLI remains the Leafy Spurge
`fetch`/`run` interface documented at the top.

1. **Shared inventory and curation:** introduce source-independent IDs, typed
   supervision, review decisions, and frozen release/split manifests. Preserve
   the legacy baseline adapter and its recorded experiment.
2. **Second classification source:** add a bounded iNaturalist import for selected
   taxa with per-photo rights checks and observation grouping. Compare a learned
   image representation with the baseline using appropriate new training data.
3. **Second task:** add a bounded MAVSD segmentation experiment, verify palette/
   geometry and scene groups, and report angle-specific results. Demonstrate that
   the shared pipeline can support a different label type without fabricating it.
4. **Local benchmark:** gather reviewed NZ labels with LINZ or permitted drone
   imagery, dates, and ground truth at the intended scale. Begin this collection
   early; unrelated international data cannot substitute for its independent test.
5. **Optional extensions:** admit DeepWeeds/ImageWeeds where they fill measured
   coverage gaps. Investigate OpenWeeds rights/access; defer satellite and
   restricted-data experiments until their task and eligibility are explicit.

Use failing tests first for these behavior changes. Consequential acceptance
checks include stable IDs without cross-source collisions; checksum failure on
alteration; image/metadata rights admission; point/box/mask validation; joint
geometry transforms; ignored pixels excluded from loss and metrics; duplicates
and parent derivatives kept together; non-geographic photos processed without
fake locations; raster windows round-tripping through CRS/affine transforms; and
all statistics/thresholds fitted without held-out-label leakage. Every release
should reproduce its sample list, model configuration, and reported metrics.
