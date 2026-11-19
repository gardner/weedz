# Weedz problem statement

Written 19 November 2026, before the accompanying prior-art investigation.

## The problem

Existing photographs contain overlooked evidence of invasive plants. A photograph
filed as a bird observation may also show gorse behind the bird, or an invasive
vine among native vegetation. Identifying the photographed subject does not
record those additional plants.

Weedz should turn a collection of eligible photographs into a manageable queue of
**locatable, species-specific candidate findings for human verification**. Its
value is finding additional useful evidence, rather than reproducing the species
already named in the original record.

The first scope is ordinary ground-level New Zealand photographs: animal-subject
observations, landscapes and other cluttered scenes. Old man's beard
(*Clematis vitalba*), pampas (*Cortaderia selloana*) and gorse (*Ulex europaeus*)
are initial targets. Native clematis, toetoe, mānuka and kānuka are important
lookalikes; broom is another relevant alternative. Aerial crop surveys and
isolated plant portraits are supporting benchmarks, not substitutes for this task.

## What a useful result contains

For each candidate, retain:

- The original image and a source-aligned region showing the proposed plant.
  A box may be sufficient for review; a mask can make the visible extent clearer.
- Species alternatives, an explicit uncertain/unknown outcome, the model version,
  and what the scores mean. A high closed-set score is not verified identity.
- Enough original resolution and surrounding vegetation for a reviewer to assess
  botanical features. Tiny, blurred or occluded plants may be unidentifiable.
- Original subject labels, provenance, attribution, reuse permissions, dates and
  location uncertainty, kept separate from new machine-generated suggestions.
- A review decision and correction history. Only completed human checks create
  verified findings; accepted species and accepted geometry are separate claims.

The source observation remains intact. A bird observation must not become a weed
observation merely because a model found a candidate plant in its photograph.
Camera location is not necessarily the distant plant's location. Missing records
are not proof of a new locality, and related photographs are not independent finds.

## What makes this different from image classification

A scene may contain several species, several instances of one species, plant
fragments or overlapping clumps. A single-subject classifier's top-five answers
are competing identities, not five confirmed species in the scene. A general
segmenter may outline leaves or vegetation patches without separating individual
plants or establishing a species identity.

One plausible pipeline is high-resolution plant proposals, followed by species
identification of each region using tight, masked and contextual views. It must
retain the original coordinates and account for missed proposals and duplicates.
However, segmentation is a means, not a prerequisite: multi-label vegetation
recognition, tiled classification, species-conditioned detection, or exemplar
retrieval may solve parts of the problem more effectively. Whole-photo screening
is a required comparison and may remain a useful parallel branch.

## Immediate scope and constraints

- Focus on reproducible GPU/server experiments and CVAT review now. Mobile
  deployment is a later engineering constraint, not a reason to reject a useful
  desktop baseline at this stage.
- Reuse existing public implementations and pretrained models where their actual
  availability and licences permit this non-commercial open-source project.
  Open code, downloadable weights and permitted image reuse are separate facts.
- Preserve lossless source inputs for inference. WebP viewing copies must retain
  a documented mapping to source geometry and must not silently replace inputs.
- Cache expensive stages and preserve inputs, masks, raw rankings, preprocessing,
  model identities and workflow history. Changing a policy creates a new run.
- Allow unknown or insufficient visual evidence. Do not force every region to be
  a target weed or treat an empty proposal result as verified absence.

## What we have established so far

On 19 November 2026 the Temporal SAM3-to-native-Waikato-EfficientNet experiment
processed 300 NZ photographs through 1,500 image windows, yielding 3,930 candidate
masks and three classification views per mask. Actual masks and species
suggestions are available in [CVAT job 12](https://cvat.llm.nz/tasks/12/jobs/12).
Mask counts are not counts of distinct plants. Twenty-six photos had no retained
mask; all suggestions still require human verification.

The six-species cohort has one upstream iNaturalist subject identification per
photo, not exhaustive scene annotations. Whole-photo classification recovered
that subject as top one in 239/300 images and top five in 279/300. At least one
masked candidate recovered it as top one in 218/300 and top five in 239/300.
Context crops recovered it as top one in 246/300, but receive multiple chances per
image. Pooling crop views retrospectively is not a deployed decision rule or
proof of better accuracy. These results do not measure background discovery.

Only 898/3,930 proposals agree on their top species across all three crop views.
Agreement is not correctness. Apparent mask quality, subject recovery, accurate
region identification and useful additional discoveries are distinct outcomes.

Evidence is retained outside Git under
`/home/gardner/src/weedz-pipeline-artifacts/20261119/nz-sam3-efficientnet-v1/`:
`complete.json`, `verification.json`, `subject-recovery.json`, source-bound region
outputs, raw logits and Temporal history. These are exploratory development
results, not a representative held-out NZ benchmark or a gold dataset.

## How we will judge solutions

Evaluate methods on the same frozen images, vocabulary and declared review or
proposal budget. Use existing externally labelled datasets first, while preparing
NZ images for later specialist review. Keep foreground portraits, mixed
vegetation, genuine incidental scenes and aerial data as separate domains.

1. **Proposal coverage:** which labelled plant regions are found or missed, at a
   fixed candidate budget and documented localisation criterion?
2. **Region identification:** conditional on a valid region match, is the taxon
   correct, a lookalike, too coarse, unknown or unresolvable?
3. **End-to-end discovery:** how many additional target species and independent
   encounters are correctly found beyond the original subject identification?
4. **False-alarm workload:** how many wrong, duplicate or inconclusive suggestions
   must a person inspect per useful finding? Include randomly sampled unflagged
   photos when measuring misses.
5. **Practical cost:** throughput, GPU memory, repeatability, and measured reviewer
   time. Report these alongside accuracy rather than replacing it with mask count.

A single subject label cannot establish that another species suggestion is false.
Exhaustive labels within a declared target scope are needed for precision and
verified negatives. Mixed-scene image-level species lists can measure species
presence, but cannot establish individual mask accuracy. Numerical acceptance
thresholds must be agreed for a specific watchlist and review budget.

## Research question

Which existing datasets, models and open implementations already identify
multiple plant species in mixed scenes, localise fine-grained species, or combine
plant proposals with botanical identification? What evidence and engineering
would still be needed to use them for incidental NZ invasive-plant discovery?

The investigation should prioritise working released implementations and relevant
evaluation data over model release dates or generic benchmark claims. Any claim
that the full problem is solved needs evidence on this actual task.

See also the [product requirements](prd.md), [dataset problem](problem-dataset.md),
[pipeline problem](problem-pipeline.md) and [region evaluation protocol](region-evaluation.md).
