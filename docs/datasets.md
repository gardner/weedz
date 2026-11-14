# Datasets, curation, and detection methods

Reviewed 13 November 2026. Dataset facts below link to publisher documentation;
processing choices are our proposed design unless marked **implemented**.
See [the ideal pipeline flow](pipeline.md) for the end-to-end design, SAM's
proposed role, model training, and the runtime detection path.

## Current research direction

Weedz is an **open-source, non-commercial public-good project**. Dataset choices
and permitted uses should be assessed for that declared purpose.

The product target is **incidental weed discovery in photos taken for another
purpose**. The first product experiment is a bounded retrospective NZ collection,
with expert review of useful discoveries and their cost. Existing labelled weed
datasets support development; they do not establish performance on overlooked
background plants. Aerial mapping and broad model training are supporting paths.

Keep a discovery corpus separate from target-species reference photos. Preserve
the original subject label; a bird observation or an animal-empty camera frame
does not supply a background plant label. Detection/annotation work must establish
that separately. Do not select the entire discovery corpus using target-weed labels.

### Project purpose and source reuse

iNaturalist's [Terms of Use, section 7](https://www.inaturalist.org/pages/terms)
address commercial AI training. That restriction is not a reason to exclude our
declared non-commercial research. The earlier commercial-project framing in
this plan was incorrect and is superseded here.

Assess analysis, non-commercial training, and sharing against the actual source
conditions. Include CC0, CC BY, and CC BY-NC material where their respective terms
fit this work, rather than limiting the project to photos permitting commercial
reuse. iNaturalist [licenses images and observation data separately](https://help.inaturalist.org/en/support/solutions/articles/151000175695).
Preserve attribution and any applicable non-commercial or share-alike conditions;
open-source code does not change upstream asset licences. Consider other licence
types according to the intended use; exclude all-rights-reserved material unless
permission is established. A bounded Nelson/Tasman iNaturalist collection is now
downloaded alongside the Leafy Spurge baseline; see [local operation](local-development.md).

## What works today

Two paths are implemented: the **Leafy Spurge `crop` baseline** below, and the
**Nelson/Tasman iNaturalist screening pilot**. `uv run main.py dev` starts the
regional review stack; `uv run main.py discover --wait` queues up to 24 licensed
animal-subject photos and six separately labelled references through Temporal.
BioCLIP screens the letterboxed whole photo plus overlapping square tiles that
cover every pixel. The Next.js
review app retains source subjects, attribution, dates, coordinate uncertainty
and human review history. These windows are not masks; no NZ accuracy or
incidental discovery count has been established. Other adapters remain proposed.
Changing the baseline's `--data-dir` only changes its filesystem location.

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
Leafy Spurge and a bounded iNaturalist pilot have been exercised locally. Other
entries describe published contents; verify actual archives and annotation
conventions when implementing their adapters. Pin the exact release at import.

| Source | Contents and viewpoint | Rights/access | Intended role and status |
| --- | --- | --- | --- |
| [Leafy Spurge](https://huggingface.co/datasets/mpg-ranch/leafy_spurge) | Montana drone imagery; 39×39 crops, larger context images, survey presence/absence, coordinates, and unlabelled orthomosaic | CC BY 4.0; Hugging Face | **Implemented: crops only.** Retain as the reproducible point-classification baseline; context is a later extension |
| [DOC/LILA NZ trail cameras](https://lila.science/datasets/nz-trailcams) | Approximately 2.5 million wildlife camera images in the public subset; animal categories and unique location identifiers | Community Data License Agreement, permissive variant; confirm the selected snapshot and location availability | **Priority candidate:** sample daytime vegetation views for an incidental-discovery pilot; no supplied weed labels |
| [Wellington camera traps](https://datasets.cms.waikato.ac.nz/taiao/wellington_camera_traps/) | 270,450 images from 187 camera locations; animal/empty/unclassifiable labels and triggered sequences | Community Data License Agreement, permissive variant; published image archive is about 185 GB | **Bounded benchmark candidate:** evaluate usable vegetation and overlap with other camera collections before acquisition |
| [iNaturalist](https://www.inaturalist.org/pages/developers) | Photos of observed organisms with dates and locations of varying precision; original subjects may be animals or other plants | Image and observation licences plus platform terms; include suitable non-commercially licensed material for this project's purpose | **Implemented: bounded Nelson/Tasman pilot.** Animal-subject photos and separate weed references; BioCLIP window screening and human review; accuracy unmeasured |
| [Mapillary](https://help.mapillary.com/hc/en-us/articles/115001770409-CC-BY-SA-license-for-open-data) | Street/roadside imagery, often successive views; local NZ coverage still to measure | Publisher states CC BY-SA for images; platform terms, acquisition, and intended reuse need review | **Roadside candidate:** bounded NZ corridor sample after eligibility and coverage checks |
| [KartaView](https://kartaview.org/doc) | Street-level imagery; NZ coverage, accessible metadata, and image quality still to inspect | Exact source terms and selected image eligibility not verified here | **Investigate:** alternative roadside corpus; no bulk import assumed |
| [MAVSD](https://doi.org/10.6084/m9.figshare.28428707.v1) | Chinese UAV RGB images at several angles; 13 semantic categories including invasive goldenrod; pixel masks/polygons | CC BY 4.0; Figshare archive is approximately 15.3 GB | **Supporting:** multi-angle segmentation experiment; acquire only when it answers a measured pilot need |
| [LINZ imagery](https://github.com/linz/imagery) plus our own field labels | NZ orthorectified geographic imagery; rural surveys typically 20–30 cm; NIR products exist for some surveys; no supplied weed labels | Open imagery; retain the selected collection's actual licence, owner, and attribution | **Assessed ([#34](https://github.com/gardner/weedz/issues/34)): site context only.** 8 of 24 pilot photos fall within a contemporary 0.25 m season, and dates are seasons, not days; it cannot confirm species or place a plant; later patch mapping needs independently reviewed labels |
| [DOC weed observations](https://www.gbif.org/dataset/d986e335-a2e3-44f0-9606-845e2eb6081d) | NZ occurrence records from 1983–2023; locations may be approximate to 100 m | CC BY 4.0; GBIF/Darwin Core archive | **Supporting:** select survey areas and check taxonomy; no direct image supervision |
| [DeepWeeds](https://github.com/AlexOlsen/DeepWeeds) | 17,509 field photos from Queensland; eight weed species plus a negative class; image-level labels | Dataset images/annotations: CC BY 4.0; repository code licence is separate | **Optional:** ground-photo classification and transfer experiments |
| [ImageWeeds v2](https://data.mendeley.com/datasets/8kjcztbjz2/2) | North Dakota aerial and greenhouse/handheld imagery with bounding-box annotations in several formats | CC BY 4.0; Mendeley | **Optional:** box detection, scale variation, and agricultural transfer experiments |
| [OpenWeeds](https://openweeds.linkoping-ri.se/) | Swedish agricultural images, including tractor views, with detection boxes and some sparse segmentation annotations | Publisher describes permissive commercial use; confirm the exact licence and accessible release before admission | **Investigate:** detection/sparse-label transfer; ingestion is blocked on source verification |
| [Sentinel-2 Level-2A](https://dataspace.copernicus.eu/data-collections/copernicus-sentinel-missions/sentinel-2) | Repeated multispectral satellite observations; bands have different native resolutions; no supplied weed labels | Copernicus open data terms; preserve product metadata and attribution | **Later:** regional screening and change detection with independent reference labels |
| [WeedMap](https://www.research-collection.ethz.ch/entities/researchdata/0a5dcd76-cc44-4fbe-9f48-d8a717c90a30) | Agricultural UAV multispectral imagery and semantic mapping labels | Repository states non-commercial use permitted; retain the exact release conditions | **Optional research comparison:** non-commercial status fits the project; prioritise according to relevance to the incidental-discovery study |

ImageWeeds' [data paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC10618417/)
describes its annotations as bounding boxes. Multiple export formats do not
imply that pixel masks are available. OpenWeeds' [project page](https://openweeds.linkoping-ri.se/about.html)
and [documentation](https://github.com/edl78/obdb_docs) describe acquisition and
training workflows, but the website still has placeholder sections and the
exact dataset licence has not been confirmed here. Its entry remains a candidate
rather than a verified acquisition recommendation.

The [LILA publisher page](https://lila.science/datasets/nz-trailcams) also describes
an expanded DOC collection of 3.3 million animal and 6.8 million empty images.
It is a different acquisition scope from the public subset. Verify licence scope,
overlap, metadata, and usable locations for the exact collection rather than
merging counts. Neither animal presence nor an "empty" category describes plants.

Other leads from the research brief include Flickr, Wikimedia Commons, DigitalNZ,
GNS landscape archives, National Library collections, GBIF-linked media,
Macaulay Library, and vegetation-survey photographs. Treat them as discovery leads
until image-level rights, access, NZ coverage, dates, and location quality are checked.
Metadata catalogue size is not a count of usable photographs. NZTA road-survey
video is a later negotiated-access possibility, not an open source assumed by
the pilot or a reason to delay work on accessible collections.

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

### iNaturalist: incidental plants and reference evidence

After the source-use check above, acquire a bounded place/date/subject query using
the official API, or the
[licensed image dataset](https://github.com/inaturalist/inaturalist-open-data)
for bulk work, following the [API practices](https://www.inaturalist.org/pages/api%2Brecommended%2Bpractices).
Archive the response/query, observation and photo IDs, taxon, observer/photographer,
licences, retrieval date, and checksums. Check each photo individually even when
the observation passes the licence filter; keep API credentials out of manifests.

For discovery, include photos whose original subject is not the target weed;
animal and landscape views may be useful. Inspect the whole scene and candidate
regions. Keep the original observation's identity separate from every proposed
plant identity. [Research Grade](https://help.inaturalist.org/en/support/solutions/articles/151000169936-what-is-the-data-quality-assessment-and-how-do-observations-qualify-to-become-research-grade-)
describes the original subject, not the incidental plant. Species-labelled target
photos are a separate reference/control collection, not evidence of discovery.
Review whether each candidate actually contains diagnostic features; preserve
close-up, whole-plant, habitat, and original-subject context.

Preserve aspect ratio and parent coordinates when analysing whole images and
local regions with existing eligible models. Return candidate taxon, evidence
crop, full-photo context, and abstention/review state. Compare direct image analysis
with candidate-region identification using independently reviewed background
labels. Boxes and masks require their own evidence. Another species' observation
is not a confirmed weed-free scene. Non-commercial fine-tuning is an option where
the source conditions permit and independently reviewed labels are available.
Begin with inference to test discovery value; that experimental order does not
imply that non-commercial training is excluded.

Keep all photos of an observation, duplicate photos, and known encounters with
the same plant in one partition. Test additional observer/site holdouts. Export
an observation location only with its uncertainty and privacy status; it is not
a plant boundary or a camera-to-ground projection. Respect
[obscured/private coordinates](https://help.inaturalist.org/en/support/solutions/articles/151000233080-how-does-inaturalist-protect-the-locations-of-sensitive-species-).
Hosted photos have metadata removed, so camera pose must not be assumed available
from [downloaded image EXIF](https://help.inaturalist.org/en/support/solutions/articles/151000233085-how-to-download-a-photo-from-inaturalist).

### NZ trail cameras: vegetation behind animals and in empty frames

Read source image IDs, camera/location IDs, dates, and sequences from the published
annotations. Animal categories are contextual metadata, not weed supervision;
the Wellington source notes that a sequence label can apply even when an animal
is absent from an individual frame. Audit source overlap before combining collections.

Sample a bounded set of daytime views across independent cameras and periods;
record night/infrared exclusions and the conditions the experiment actually tests.
Analyse background vegetation and retain the full scene for review. Create new
plant labels through expert review, including genuinely negative and unidentifiable
regions. Hold out whole camera sites and keep triggered/repeated sequences together.
Count distinct encounters/sites as well as frames. A location identifier alone
does not provide plant coordinates; obtain permitted location context before
claiming an actionable occurrence. Keep precise locations private where required.

**Assessed 14 November 2026 ([#8](https://github.com/gardner/weedz/issues/8)).**
The facts below come from LILA metadata v1.00 and are recorded in
[the assessment summary](../benchmarks/nz-trailcams-assessment.json). Reproduce
them with `uv run python scripts/assess_trailcams.py <metadata.json>`; no images
are downloaded.

- **Size and labels:** 2,453,840 images, all labelled with an animal. Half are
  mice, and the public subset has no empty frames.
- **Sites:** 57 projects and 3,113 known camera sites. Each site repeats one fixed
  view (median 77 frames, p90 1,176, max 27,563). Another 84,091 images sit in
  per-project `unknown` buckets that pool unrelated cameras, so they are not
  counted as sites.
- **Timing:** there are no sequence IDs. 93% of frames are timestamped, mostly
  2019–2020 with only 2,709 before 2015. Only 33% are between 07:00 and 19:00;
  442,567 frames are between 09:00 and 16:00, 1,784 known sites among them.
- **Vegetation:** in the script's `daytime_sample` (the first 12 projects by name hash,
  with one mid-day frame from each; the frame ids are listed in the summary), 11 show substantial
  forest-floor, fern, tussock or grassland vegetation, and one is a low-light
  infrared frame. That is far more visible vegetation than the pilot's
  iNaturalist bird photos.
- **Location:** no coordinates or regions are published. DOC's bucket README offers
  coordinates on request, rounded to the nearest 10 km.

**Recommendation.** Use this as a detection-development corpus. Sample about one
frame per site per season, so repetition doesn't dominate, and never bulk-download.
Do not use it as a source of Nelson/Tasman leads until DOC supplies site locations.
Even then, 10 km rounding supports neither a field search nor a regional filter.
Requesting finer site locations is a partner decision.

### Mapillary/KartaView: incidental roadside vegetation

Verify local coverage and intended-use eligibility first. Preserve capture date,
sequence/image IDs, photographer attribution, public camera locations and any
supplied pose. Sample independent road segments rather than every adjacent frame.
Search full scenes and local plant regions with consistent transforms back to the
source image. Link repeated views of the same probable plant and separate them
from independent detections; hold out corridors/encounters for evaluation.

Review candidate identity, cultivated/wild context, source-date relevance, and
actionability. The camera point is not the plant point. Export an uncertain search
area when geometry does not support a plant location. Keep existing reference
records and the basis of any novelty claim with each reviewed lead. Do not infer
that platform availability alone permits unrestricted bulk analysis or training.

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

**Assessed 14 November 2026 ([#34](https://github.com/gardner/weedz/issues/34)).**
Can LINZ imagery corroborate or locate the pilot's 24 incidental leads? The
facts below come from the public `nz-imagery` STAC catalogue and the run
`nelson-tasman-3e62ad801459`. They are recorded in
[the assessment summary](../benchmarks/linz-nelson-tasman-assessment.json), which
lists photo IDs but no coordinates. Reproduce them with
`uv run python scripts/assess_linz.py`. The script reads collection JSON and
simplified capture areas only, never rasters. The catalogue is live, so each
collection's entry records the catalogue's checksums of its collection JSON and
capture area. A rerun can then show which inputs have changed. The photo
records come from the local, gitignored pilot store in `data/pilot/`, which the
screening run creates ([local operation](local-development.md); its source
manifest checksum is in
[the screening summary](../benchmarks/nelson-tasman-screening.json)). Without
that store the script stops with an error rather than reporting zero photos.

- **Coverage:** 43 of the 61 candidate collections cover at least one photo.
  They run from 1980 to 2025, with GSDs from 0.075 to 1 m plus six national 10 m
  satellite mosaics. Seven are RGBN near-infrared products. All are
  CC BY 4.0, but licensors vary:
  - Most aerial surveys name one of the two councils.
  - The 2022 Top of the South flood survey adds Waka Kotahi.
  - The 2016–17 Tasman surveys add AAM NZ.
  - Scanned historical surveys name LINZ and/or MPI.
  - The satellite mosaics name Planet or Sinergise.

  Take each collection's own licensors and producers from the benchmark, and
  keep both in any attribution.
- **Dates are seasons, not days:** collections and tiles carry one flying-season
  window, encoded as New Zealand midnights. The day a given tile was flown is
  not published in STAC. Only **8 of 24** photos fall inside a contemporary
  aerial window: Tasman 0.25 m (RGB and RGBN), 6 December 2024 to
  27 March 2025. That window is 16 weeks long, so the flight could be up to
  86 days after the photo.
- **Four Tasman riverbed photos** lie outside that survey's capture area.
  Their nearest aerial capture is the 0.1 m Tasman River Valleys Flood survey,
  198 days later and after the July 2025 floods.
- **Eleven of the 12 Nelson photos have no contemporary capture.** The only
  exception falls on the Tasman survey's edge. For ten of the eleven, the
  nearest capture is 0.1 m in May 2025, 140–141 days later, and the finest is
  0.075 m in December 2025, 335–336 days later. The eleventh, with 1,634 m
  accuracy, has its nearest sub-metre capture in December 2022, 732 days earlier.
  Two photos, one per region, have no sub-metre capture within a year. Both
  have about 1.6 km accuracy. Across all photos, the
  nearest sub-metre capture has a median gap of 141 days.
- **Resolution:** at 0.25 m a 1 m clump is 4 pixels across and a 3 m clump
  12 pixels. At 0.075–0.1 m they are 10–40 pixels. A clump can be seen as a
  shrub-sized blob, but RGB at these scales gives no species identity. Gorse,
  broom, native shrubs and garden plants look alike from above. Old man's beard
  is seen only as canopy texture, if at all. Sentinel-scale (10 m) mosaics
  cannot show a single clump.
- **An observation point is not a plant point:** positional accuracy is 3 to
  1,634 m (median 18.5 m). Four photos report none and 9 report more than 20 m.
  iNaturalist records no camera heading, so the background plant can lie
  anywhere in that circle or beyond it. Only **11 of 24** photos have an
  accuracy of 20 m or better. At 0.25 m that is a search circle of up to
  80 pixels radius, about 180 times the area of a 3 m clump. The imagery's own
  horizontal error is not in STAC. LDS layer notes give figures such as
  [±1.2 m at 90% for Tasman 2015–16](https://catalogue.data.govt.nz/dataset/tasman-0-3m-rural-aerial-photos-2015-20164).
  That is negligible beside the photos' uncertainty.
- **Two windows were read to check this by eye:**
  - An 80 m window of Tasman 0.25 m around the Tanguru chafer photo (17 m
    accuracy, inside the season). The point falls on a house roof with solar
    panels. The 17 m circle holds a lawn, a farm track, scattered 2–5 m shrubs
    and native bush edges. Any of those shrubs could be the "background
    plant", and none can be named.
  - A 50 m window of the 0.1 m flood survey around the pied stilt photo (6 m
    accuracy), from the same riverbed visit as the oystercatcher candidate. It
    shows the channel, bare gravel bars and flood-deposited logs, with no live
    vegetation in the circle. The flood reworked the riverbed after the photo,
    so this image can neither confirm nor rule out the vegetation the photo
    showed.

**Recommendation.** Do not use LINZ imagery to corroborate a lead's species or
to place a plant point. Its dates are seasonal, its pixels cannot separate
the watchlist from lookalikes, and most pilot photos are too imprecise to say
where in the image to look. It is still useful as **site context** for leads
with public coordinates accurate to about 20 m or better. A reviewer can see
whether the site is a garden, riverbed, roadside or bush edge, which helps
judge cultivated or wild status, access and actionability. Pair it with the
nearest capture's slug and signed day gap from this script. Treat
captures outside the photo's season as "the site at another time". Do not
build an aerial lead viewer until a reviewed lead shows that context would have
changed a decision. Patch mapping still needs field-reviewed polygons with dates
compatible with the capture, as described above. Exact flight days would have
to be requested from LINZ or the producer.

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
shared image-classification interface, with a dataset-specific label map and
aspect-preserving preprocessing. Score per-class precision/recall,
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

### WeedMap: optional multispectral research comparison

For a research comparison under the source's non-commercial conditions, align
multispectral tiles and source semantic labels, preserve band order/scale and valid pixels, and fit a matching
segmentation head. Split at field/flight level before generating derivatives.
Evaluate field-level segmentation with the source's crop/weed label definitions;
those labels do not establish NZ invasive-species identity. Its non-commercial
conditions fit the project's stated purpose; the reason to defer this experiment
would be relevance or effort, not an assumption that Weedz is commercial.
Preserve the source's actual reuse and redistribution terms with the results.

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
| Learn representations | Compare a pretrained RGB image encoder with a frozen-embedding classifier on source-eligible curated classification data | Better grouped validation and source/site transfer at a recorded compute cost |
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
2. **Bounded incidental-photo collection:** inspect metadata and eligibility for
   an accessible NZ trail-camera, community-photo, or roadside source. Keep original
   subjects, duplicate/encounter groups, capture dates, and location limitations.
   Start with manageable daytime or otherwise supported views; do not download
   whole multi-million-image archives as the first step.
3. **Inference-first comparison:** compare direct whole-photo analysis with region
   proposals plus specialist identification using existing eligible models. Obtain
   independent incidental-plant labels; measure review effort, false alarms,
   missed visible targets, and deduplicated useful discoveries. Do not require
   supervised segmentation before testing the product hypothesis.
4. **Local retrospective benchmark:** define the weed watchlist and reference
   occurrence records with specialists. Preserve as-of dates and distinguish an
   unlabelled photo, a finding missing from the reference set, earlier available
   evidence, and a verified new locality. Geographic expectations prioritise review
   but do not veto credible unusual candidates.
5. **Targeted extensions:** add source-eligible supervised training or a MAVSD
   segmentation comparison only if it addresses observed failure modes. Use LINZ
   for supporting evidence where useful; defer restricted footage and a continuous
   monitoring service until the pilot's yield and review economics are demonstrated.

Use failing tests first for these behavior changes. Consequential acceptance
checks include stable IDs without cross-source collisions; checksum failure on
alteration; image/metadata rights admission; point/box/mask validation; joint
geometry transforms; ignored pixels excluded from loss and metrics; duplicates
and parent derivatives kept together; non-geographic photos processed without
fake locations; raster windows round-tripping through CRS/affine transforms; and
all statistics/thresholds fitted without held-out-label leakage. Every release
should reproduce its sample list, model configuration, and reported metrics.
