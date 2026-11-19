# Existing research for Weedz background-plant discovery

Investigated 19 November 2026, after writing the
[Weedz problem statement](problem-statement.md). Sources below are original papers,
author repositories, official challenge pages and publisher archives. This is a
research and availability audit, not a new model benchmark.

## Finding

**We should reuse substantial existing work.** Multi-species vegetation recognition
and invasive-species presence detection are established research tasks with public
implementations. The strongest immediate match is Pl@ntNet's Danish roadside
project: released code, model weights and annotated scene images. PlantCLEF is the
closest recurring benchmark. Neither establishes reliable discovery of small NZ
weeds behind arbitrary photographed subjects.

Our earlier assumption that a successful system must segment individual plants
before identifying them is too restrictive. Tiled botanical recognition is a
serious competing approach. Keep localisation evidence for review, but measure
whether strict segmentation helps rather than making it a mandatory gate.

## 1. Pl@ntNet roadside invasive-plant identification: first replication candidate

Espitalier et al., **Adapting a global plant identification model to detect invasive
alien plant species in high-resolution road side images**, Ecological Informatics
89, 103129 (2025): [paper DOI](https://doi.org/10.1016/j.ecoinf.2025.103129),
[author institution's abstract](https://pure.au.dk/portal/en/publications/adapting-a-global-plant-identification-model-to-detect-invasive-a/).
The repository and 2024 archives retain earlier manuscript titles; these are the
same research line, not separate results.

- [MIT code](https://github.com/plantnet/roadside-invasive-plant-identification)
  compares tiling with enlarged ViT input, called VaMIS, with and without
  task-specific fine-tuning. Its README recommends XP4, tiling without fine-tuning.
- [Released BEiT models](https://zenodo.org/records/13891416) include backbone and
  experiment-specific heads. The vocabulary is six target taxa/meta-species,
  including broom (*Cytisus scoparius*); it is not a ready-made NZ watchlist model.
- [Danish roadside dataset](https://zenodo.org/records/14013930): 14,838 images at
  4024×3036. The publisher separates 14,602 monolabel images and **206 multilabel
  images**, with a CSV for the latter. Quick-test folders duplicate 30 main images.
  The published scene annotations must not be described as plant-instance masks.
- The Zenodo APIs identify **CC BY 4.0** for both model and dataset archives.
  The data archive is 46.1 GB and uses JPEG quality 70; the record links to a
  separate original-quality archive. Preserve the supplied pixels when benchmarking.

**Why it matters:** it directly tests converting a botanical subject classifier
into invasive-species presence detection in large, cluttered scenes. The authors
report tiling benefits, including without fine-tuning. This is closer to Weedz
than another single-plant classifier comparison.

**Remaining work:** inspect actual CSV semantics, negative/completeness scope,
train/test grouping and duplicate images; reproduce the released experiment on
its own test split before adapting to NZ. Its limited vocabulary and roadside
camera geometry do not establish gorse/vine detection in incidental NZ photos.

## 2. PlantCLEF: recognise the species present without separating every plant

The official [2025 task](https://www.imageclef.org/PlantCLEF2025) and
[2026 task](https://www.imageclef.org/PlantCLEF2026) predict multiple species in
high-resolution vegetation quadrats. Training largely uses single-subject photos;
evaluation uses mixed vegetation. This explicitly addresses our classifier-to-scene
domain shift, although quadrats differ from distant, oblique background vegetation.
Species-list labels measure presence, not instance boundaries. The official pages
link training images, metadata, pretrained models and plot test images; access to
images alone does not establish access to every held-out evaluation label.

**DS@GT 2026** is a particularly relevant implementation:
[paper](https://arxiv.org/abs/2607.14509),
[MIT code](https://github.com/dsgt-arc/plantclef-2026).
It combines multi-scale DINOv2 classification with retrieval and contextual
aggregation. Its selected submission reports private F1 **0.43902**. This is the
challenge's multi-label metric, not 43.9% ordinary classification accuracy and not
comparable with our 79.7% single-subject recovery. The paper distinguishes its
selected submission from a higher-scoring unselected configuration.

The authors also tried **SAM3 plant/flower crops and found no consistent gain**
over the corresponding tiled runs. That supports testing context-preserving
recognition rather than assuming cleaner outlines improve taxonomic recognition.
This is evidence on their benchmark, not proof segmentation cannot help Weedz.

The experiment source is public. I did not verify a downloadable final trained
ViT-L checkpoint and matching retrieval index in the inspected release material;
full reproduction may require obtaining those assets or retraining. Its European
geographic filtering must not be copied unchanged into NZ surveillance: known
ranges can rank leads but must not erase credible new incursions.

Useful alternatives with public code:

- [DS@GT 2025](https://github.com/dsgt-arc/plantclef-2025), MIT:
  [4×4 tiled ViT, voting and visual-cluster priors](https://arxiv.org/abs/2507.06093),
  reported private F1 0.348. The
  [organiser pretrained model archive](https://zenodo.org/records/10848263)
  is downloadable and marked CC BY 4.0, making a simpler reproducible baseline
  possible without assuming the 2026 final assets are released.
- [Chlorophyll Crew](https://github.com/geranium12/plant-clef-2025), MIT:
  [species/genus/family heads with multi-scale inference](https://arxiv.org/abs/2508.10457).
  A useful alternative for hierarchical identification; trained final checkpoint
  availability was not established by this audit.

The [PlantCLEF 2025 overview](https://arxiv.org/abs/2509.17602) also reports mixed
results for vegetation filtering. The relevant lesson is to compare decisions on
multiple species, not to reinterpret a single-subject softmax top five as five
species present.

## 3. Pl@ntNet multi-species survey API: an existing service to compare

The official [survey API documentation](https://my.plantnet.org/doc/api/survey)
describes recognition of multiple species using tiled single-species inference.
It returns candidate species and matching tile positions, scores and coverage
estimates. Its documented applications include quadrats and roadside imagery.

This is **restricted beta access**, requested from Pl@ntNet, rather than verified
self-hosted survey-server source and weights. Published
[client and batch benchmark scripts](https://github.com/plantnet/my.plantnet)
are not the identification server. It is a useful potential external comparison
if access is obtained; no contact, account request, upload or API inference was
performed during this investigation. Tile coverage is not a plant-instance mask.

## 4. Segmentation research that addresses our specific weaknesses

| Project | What is actually demonstrated | Fit and limitation for Weedz |
| --- | --- | --- |
| [ADAM PlantCLEF2025](https://github.com/ADAM-UEFS/PlantCLEF2025), [paper](https://arxiv.org/abs/2512.19957) | Prototype-guided plant-relevant regions and contextual classification; reported private F1 0.33331 | Relevant plant-specific alternative to generic SAM proposals. Attention regions are not verified individual-plant masks. Public source, but no repository licence identified; a prototype tensor is present, not a verified complete inference release. |
| [ZeroPlantSeg](https://github.com/JunhaoXing/ZeroPlantSeg), [WACV 2026 paper](https://openaccess.thecvf.com/content/WACV2026/papers/Xing_Zero-shot_Hierarchical_Plant_Segmentation_via_Foundation_Segmentation_Models_and_Text-to-image_WACV_2026_paper.pdf) | Groups leaf instances into whole rosette-shaped plant individuals from top views; checkpoint download script provided | Directly addresses leaves-versus-plants. GPL-3.0 repository; underlying model terms are separate. Does not itself identify species or establish transfer to woody shrubs, tangled vines or grass clumps. |
| [Weeds Are Weird](https://github.com/PRBonn/WeedsAreWeird), [IROS 2025 paper](https://www.ipb.uni-bonn.de/pdfs/chong2025iros.pdf) | SAM vegetation proposals plus BioCLIP feature comparison to crop references, yielding crop/weed/soil semantics | MIT code and released crop references; already tried locally. In a crop field, unusual vegetation can be weed. In conservation, a native is not a weed simply because it differs from reference plants. This is not invasive-species identification. |
| [Flora_Mask](https://github.com/salimsoltani28/Flora_Mask), [2025 paper](https://bg.copernicus.org/articles/22/6545/2025/) | SAM plus classifier Grad-CAM turns citizen-science subject photos into training masks, then studies transfer to UAV tree mapping | Useful weak-label curation method. It helps locate an already-labelled subject, rather than proving identities of every background plant. Public code; no repository code licence identified in the inspected tree. |
| [PlantSAM, Petti et al.](https://uflbsail.net/wp-content/uploads/2026/03/Petti2025-PlantSAM_-Towards-Real-Time-Plant-Segmentation-with-Efficient-Vision-Language-Foundation-Models.pdf) | Species/clade-conditioned SAM using BioCLIP-generated training examples | Very relevant design, but the paper reports background/blur misses and species-recognition failures. A public author code/checkpoint release was not verified. Different projects also use the PlantSAM name; herbarium segmentation is a different task. |

These are more specific starting points than swapping generic detector backbones.
They still need validation on Weedz's scene types and species.

## 5. What iNaturalist does and does not supply

The original [iNaturalist detection paper](https://gvh.codes/assets/papers/inaturalist_dataset.pdf)
is important: **the 2017 bounding-box annotations explicitly exclude Plantae**,
as well as fungi, protozoa and chromista, because instances were difficult to box.
It also says no segmentation masks were collected. A dataset advertised as
“iNaturalist classification and detection” therefore does not automatically give
us labelled plant instances. See the [original release](https://github.com/visipedia/inat_comp/tree/master/2017).

Ordinary observation identifications remain valuable botanical training/reference
labels, with per-image rights and possible identification errors. They do not
exhaustively label everything visible in each image. Subject recovery is a useful
control, not a background-species precision or recall estimate.

## 6. What we have already reused, and why that has not solved it

This investigation does not reset our previous experiments:

- The native Aotearoa EfficientNet run and its 300-image subject-recovery results
  are recorded in the [problem statement](problem-statement.md). It is a locally
  useful single-subject identifier, not an existing multi-species scene system.
- The 18 November WaW experiment on 64 PhenoBench images obtained 91.28% plant
  foreground IoU but only 52.99% instance recovery at IoU ≥0.5, with 2,412 proposals.
  Good vegetation coverage can coexist with poor individual-plant recovery.
- Our 18 November reuse of PlantCLEF's 4×4 frequency-vote component on ImageWeeds
  recovered 0/303 labelled positive image–taxon pairs at a five-species output
  budget. The source-box control recovered 74/645 as top one and 297/645 as top
  five. That points to classifier/domain mismatch as well as aggregation failure.
  It was not a reproduction of the complete PlantCLEF competition submission,
  and does not evaluate DS@GT 2026 or the Danish roadside models.

Local evidence and adapters remain outside Git in
`/home/gardner/src/weedz-prior-work-artifacts/20261118/`; see its `README.md`,
`verification-summary.json`, source-box diagnostic and CVAT project 4. These are
source-labelled development diagnostics, not independent NZ performance claims.

## Recommended next experiment

1. **Replicate the Danish roadside baseline first.** Audit metadata and splits,
   then run released XP4 on a bounded, fixed source test selection and the
   separately declared multilabel scope. Compare the published implementation,
   our whole-photo baseline and our region pipeline on common evaluable taxa.
   Inspect the 206-scene CSV before claiming exhaustive labels or precision.
2. **Add an actual multi-species decision baseline.** Reuse released PlantCLEF
   weights and multi-scale tiles with a fixed species-list admission rule. Retain
   rare candidate evidence; do not assume frequency voting suits rare weeds.
   Compare against SAM crops under the same final species/review budget, not
   unbounded unions of top-five lists. Audit model vocabulary before comparison.
3. **Separate geometry from species.** Use source instance masks/boxes to measure
   proposal misses and oracle-region classification independently. Consider
   ZeroPlantSeg only on appropriate rosette/top-view examples, and investigate
   context-aware identification before more generic mask generation.
4. **Keep CVAT and provenance.** Show actual source-aligned evidence and suggested
   taxa, keep models/outputs separate, and record unknown/unreviewed regions.
   Avoid a new annotation UI or workflow engine solely to run these comparisons.
5. **Transfer to NZ after those controls.** Review a fixed incidental NZ cohort
   including unflagged scenes, native lookalikes and explicit negatives. Existing
   source-labelled plant portraits can support subject recovery, but cannot replace
   those labels. Geographic priors must not forbid unexpected occurrences.

**Decision:** reuse the roadside and PlantCLEF work as comparison branches; keep
SAM as a localisation/annotation option. Do not claim that the broad NZ discovery
problem is solved, or that a stronger subject classifier alone solves it. The
remaining contribution is measured transfer to incidental scenes, reliable extra
species findings, uncertainty handling and sustainable human review.

## Availability audit and evidence

Repository metadata, exact commits and complete file trees were captured under
`/home/gardner/src/weedz-research-artifacts/20261119/background-plant-prior-art/`.
The Zenodo record JSON confirms downloadable filenames and licence identifiers;
large archives and candidate models were not downloaded or run in this audit.
Original source/data rights and each dependency's terms still apply independently.
A missing identified code licence is not permission inferred from public access.

Key inspected commits:

| Repository | Commit |
| --- | --- |
| Pl@ntNet roadside | `043379010d0081eb23f58146bcdbf94f611b3f7f` |
| DS@GT PlantCLEF2026 | `1cf0ecb43a2ec32f17262544372e4a7ea9d37eb3` |
| DS@GT PlantCLEF2025 | `ccc1bce4be984854ac68957f1a4e01f62305fd2c` |
| ADAM PlantCLEF2025 | `8e7a6e929136f427fdd448ad3bf2e7d09194561d` |
| Weeds Are Weird | `21db2d3df5a730a8ea3a277561960b443ca47a69` |
| Flora_Mask | `791868dda0a5e0fc21f6205338811224c56c3ecf` |

No published F1, mask IoU, subject accuracy and candidate-recovery figures in this
report should be ranked as if they shared a dataset, task or denominator.
