# Problem statement 1: no dataset shows where weeds appear in real NZ photos

Written 15 November 2026. Weedz has three problems to solve, in order:

1. **Dataset** (this document): no dataset shows where weeds appear in real NZ photos.
2. **Detection:** we can't yet find weeds reliably in photos that weren't taken of weeds.
3. **Reach:** weeds that are found don't reach the people who deal with them.

The dataset comes first. Without it we can't train a model for problem 2, and we can't measure whether one works.

## The problem

New Zealand already has millions of identified, located plant photos. But every one of them answers the question "what is this photo of?" None answers "is there a weed anywhere in this photo, and where?"

That second question is the one Weedz needs answered. Old man's beard behind a kererū, or gorse on the far hillside of a landscape shot, is real evidence of where a weed grows. Today nobody records it, because the photo is filed under the bird or the view. No collection shows:

- **Where in the frame** the weed is: a box or an outline, not just a label on the whole photo.
- **Weeds in the background** of photos taken for some other reason, which is the case Weedz is built for.
- **Real negatives:** photos a person checked and found no target weed in. Without these we can't count false alarms.
- **Native lookalikes** that a model is likely to mistake for a weed, checked by a person: native clematis, toetoe, mānuka, kānuka.

Because none of this exists, any claim about how well a model finds incidental NZ weeds is a guess. That includes our own BioCLIP screening, whose scores are still uncalibrated.

## Why existing sources don't solve it

| Source | What it gives us | What it lacks |
| --- | --- | --- |
| [iNaturalist NZ](https://www.inaturalist.org/pages/developers) / [GBIF](https://www.gbif.org/) | Species-labelled, dated, located photos under per-photo licences | The label covers the photo's subject only. Nothing says where the plant is, or what else is in the frame |
| [Aotearoa Species Classifier](https://github.com/Waikato/aotearoa-species-classifier) (Waikato / TAIAO) | An NZ-trained classifier with 14,991 classes, about 6,172 of them plants; weights under CC BY-NC 4.0. We already run it as an [optional baseline](aotearoa-baseline.md) | A whole-photo classifier trained on subject photos. No locations in the frame, and no published accuracy on background plants |
| [DOC Smart Weed Alert Tool](https://weeds.doc.govt.nz/) ([launched October 2026](https://www.doc.govt.nz/news/media-releases/2026-media-releases/new-warning-system-to-whack-weeds/)) | Alerts (currently batched weekly) on new weed records it pulls from GBIF daily | Works only on records someone has already identified, and holds no images to learn from. It's where Weedz finds should end up (problem 3), not a training source |
| Manaaki Whenua Central Plateau survey ([Peterson et al. 2024](https://doi.org/10.3390/rs16132503)) | Aerial photos from 2012–2023 of gorse, broom and tree lupin over 23,000 ha, with density layers by grid square. The paper says the data are on [LRIS](https://lris.scinfo.org.nz/data/?q=legumes) | Aerial, not ground photos. Labelled by grid square (about 6,000 squares), not by plant. An AI trial there was dropped after "several thousand false positives", including the native snow tōtara, kāretu and muddy puddles |
| [Weed-AI](https://github.com/Weed-AI/Weed-AI) (University of Sydney) | An open repository of annotated weed images with boxes and segmentation, in WeedCOCO format | Mostly Australian crop weeds in crop rows; no NZ conservation weeds |
| DeepWeeds, ImageWeeds, OpenWeeds, MAVSD ([shortlist](datasets.md#dataset-shortlist)) | Labelled weed photos: by photo, by box, or by pixel | Overseas species and settings. Useful for transfer experiments, not for measuring NZ performance |
| NZ trail cameras ([LILA](https://lila.science/datasets/nz-trailcams), Wellington) | Millions of NZ frames with real vegetation in the background | Labelled by animal or "empty"; nothing says what plants are in the frame |

What NZ lacks isn't photos. It's a dataset where a person has confirmed, inside real cluttered photos, **which target weed is there and where it is in the frame, or that none is there**.

## What the dataset needs to contain

Each sample follows the [common sample contract](datasets.md#a-common-sample-and-annotation-contract), which is already built in `src/weedz/contract.py`. For this dataset that means:

- **The photo and its rights:** source, creator, attribution, and image and metadata licences recorded separately. We admit CC0, CC BY and CC BY-NC where the terms fit this non-commercial project.
- **The original subject label**, kept as it was. A bird observation stays a bird observation; the plant labels sit alongside it.
- **Target weeds in the frame,** each with a box or mask, a species, and a review state: confirmed, rejected, unsure or not yet reviewed.
- **Explicit negatives:** "checked, no target weed in this photo", which is different from "not checked". Schema version 1 can't record this yet: a detection sample must contain at least one box. The contract needs an annotation-completeness field (for example "all targets marked") before negatives can enter a detection release.
- **The lookalikes checked,** so lookalike photos can be measured as a separate group (`src/weedz/discovery/lookalikes.py`).
- **Exact location and date,** with coordinate accuracy. Points that a source or contributor obscured stay obscured, and we never try to sharpen them.
- **Review history:** who decided, when, on what evidence, and anything they changed. Model suggestions stay marked as suggestions, never as labels.
- **Grouping,** by observation, place and observer, so splits keep photos of the same plant together and repeat photos can't inflate results.

## How we'll make it

Most of the plumbing exists. What's missing is human-checked labels, plus the schema change for explicit negatives described above.

1. **Collect.** Bounded, licensed NZ collections: iNaturalist photos where the subject is an animal or a landscape, plus labelled reference photos of each target weed and its lookalikes. Trail-camera frames come later.
2. **Propose.** BioCLIP screening (whole photo and tiles) and the optional segmentation step suggest where a weed might be in each photo. Proposals are only starting points.
3. **Check.** People confirm, correct or reject each proposal, in the review app and the [Label Studio package](label-studio.md). They also mark photos with no target weed as negatives.
4. **Measure without bias.** A random sample, including photos the model didn't flag, is checked blind in a separate project. This is the only way to count misses as well as false alarms.
5. **Release.** Confirmed samples move from silver to a frozen, versioned gold release ([`release.py`](datasets.md#what-a-release-implements)), split by location group with a spatial buffer. Each release records its licences and how it was checked.

## First release scope

- **Region:** Nelson/Tasman, matching the [pilot](pilot-nelson-tasman.md).
- **Targets:** old man's beard (*Clematis vitalba*), pampas (*Cortaderia selloana*) and gorse (*Ulex europaeus*).
- **Lookalikes:** native clematis (*C. paniculata*, *C. forsteri*, *C. foetida*), toetoe (*Austroderia*), broom, mānuka and kānuka.
- **Photo types:** incidental ground-level photos first. Aerial imagery (LINZ, the Manaaki Whenua survey) is a separate benchmark, not mixed in.
- **Size:** set with the review partner (#1) based on how much review time they have. A few hundred carefully checked photos, with real negatives and a blind test set, are worth more than thousands of unchecked ones.

## How we'll know it's solved

- Someone outside the project can download a gold release and train or benchmark a model on it, without asking us anything.
- Every image's licence and attribution travels with it, and withdrawn images are left out of later releases.
- The blind test set reports misses and false alarms for each target, and separately for lookalikes.
- A first model result on it (problem 2) can be compared fairly with BioCLIP and the Aotearoa Species Classifier.

## Not in scope

- **Claiming first occurrences.** A weed missing from one collection isn't proof it's new to the area.
- **Training models.** That's problem 2. This document covers only the data those models will be built and judged on.
- **Turning photo labels into outlines automatically.** A photo-level label never silently becomes a box or mask.
- **Pooling overseas datasets into the NZ test set.** They can help training; they don't tell us how well NZ detection works.

## Open questions

- **Who checks species?** Which partner experts, and how many independent checks does a sample need (#1)?
- **Licence of the release:** one licence for the whole release, or each image under its own (CC BY-NC images make the whole set non-commercial)?
- **Phone reports:** should reports people send from the phone app, with training use allowed under the [report consent](report-consent.md), feed this dataset, and from which release?
- **The Manaaki Whenua data:** are the LRIS layers still downloadable, and under what licence? Is the Central Plateau survey worth adding as an aerial benchmark?
- **Collaboration:** is it worth contacting Weed-AI, TAIAO and DOC SWAT about shared formats? For example, publishing in WeedCOCO, or sending confirmed finds to SWAT as GBIF records.
