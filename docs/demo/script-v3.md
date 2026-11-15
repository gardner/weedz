# Weedz: value-first website video

Target: three minutes. Native Breeze narration; no voice post-processing. Mobile appears only in the closing next steps. Recorded model outputs must be labelled honestly; do not imply that playback timing is live inference.

## 0–20 seconds

Help protect the places you love, using photographs that already exist. Weedz looks for overlooked plants in everyday images, turning a background detail into a lead someone can investigate. The goal is simple: help people find useful evidence without searching every photograph by hand.

Visual: Ordinary licensed photograph, then the real review site's original photo and suggested flower region

## 20–41 seconds

A useful lead needs more than a plant name. It needs the photograph, the suggested region, and a clear way for a person to assess the evidence. Here is that path, running through the real screening pipeline and the review website.

Visual: Photo to region proposals to species comparisons to human review; connect each stage to saved real outputs

## 41–65 seconds

First, a segmentation model proposes regions in the image. These coloured masks are actual outputs from SAM two point one, showing two flower regions in this photograph. A mask describes a shape. It does not identify a weed, and some proposed regions will be irrelevant.

Visual: Actual SAM2.1 inference record, followed by original, first flower mask and second flower mask; label recorded output

## 65–91 seconds

Next, BioCLIP compares image views with a watchlist and lookalikes. Whole-image and smaller views provide different evidence; segmentation adds another view rather than replacing the original. The original screening scores order the queue; region scores stay separate for review. They are model comparisons, not a calibrated percentage chance that the plant is a weed.

Visual: Real BioCLIP comparisons for the original and mask crops, with watchlist and lookalikes visible

## 91–118 seconds

The website brings that evidence together. A reviewer can inspect the original, compare suggested regions, and see where the image came from. They can record what the photograph supports, or leave it uncertain. Keeping the source and the original alongside the suggestion makes the lead easier to check and discuss.

Visual: Actual review website: original, mask toggle, evidence, source attribution and review controls

## 118–140 seconds

The aim is a focused review queue: possible sightings worth a second look, with the evidence close at hand. A lookalike or an unclear photograph is a useful outcome too. Human review keeps an interesting model suggestion from becoming an unsupported claim.

Visual: Real contrasting cases and review queue; do not stage a positive judgement or invent a discovery

## 140–162 seconds

Weedz is open source, and this is a working pipeline. We still need to measure whether segmentation produces more useful findings for the time people spend reviewing. The next proof comes from checked sightings and real conservation work, not from a convincing looking score.

Visual: Small pilot evidence, open repository and actual website; no unmeasured improvement chart

## 162–180 seconds

Start with the evidence. Explore the review site, help test the suggestions, and help turn ordinary photographs into useful conservation leads. Next, we will bring that path to the mobile app, making it easier to contribute from a camera roll.

Visual: Website and project URL; one closing next-step line about mobile, then source and audio credits
