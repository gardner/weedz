# Pipeline validation before NZ review

This audit tracks what each existing labeled dataset can test and which results
should change reviewer intake. Use source labels at their documented scope.
Report every stage separately so a final miss can be traced to the source photo,
plant proposals, crop, classifier or decision rule.

| Stage | Labeled evidence and measured result | Review implication |
| --- | --- | --- |
| Acquisition, eligibility and split | The source receipts verify rights, mappings, dimensions and hashes. The ImageWeeds source audit quarantined bad geometry and conflicting duplicate records. The NZ intake sampled animal observations before model inference. | Check plant visibility as a separate intake question. Keep independent encounters and the original sampling records. |
| Generic plant presence | The first ADE20K reserve contains 24 photos with mapped vegetation. SAM3 called 12 on whole photos and 14 after adding tiles at 0.50. On a second scene-disjoint fixture, explicit `tree`, `grass` and `shrub` prompts increased mapped recovery from 11/24 to 18/24. Both experiments missed the 95% retention gate. | Keep these scores out of any rule that drops photos from review. |
| Region proposals | On 138 ImageWeeds images, SAM3 matched 348/645 labeled boxes at IoU ≥0.5. PhenoBench supplied 853 human instances for separate size, duplicate, merge and fragmentation diagnostics. | Keep the failed proposals in the denominator, particularly on small plants. |
| Crop geometry and identification | On the same 645 human ImageWeeds boxes, PlantCLEF top-one recovery was 74 for the legacy tight view, 60 for the square tight view and 42 for the square context view. SAM3-matched regions recovered the correct class in 48/348 matched cases. | Use tight crops as the measured baseline. Present the whole original when a crop lacks context. |
| Ranking, aggregation and final calls | At the same five-slot budget the ImageWeeds region aggregation replay improved from 5 to 23 recovered pairs out of 303. On the separate Danish reserve, PlantCLEF tiles recovered 16/21 as the top suggestion. Released XP4 cutoffs recovered 15/21 with a variable suggestion count. | Compare within each reported budget. These sources support labeled-positive recovery. General precision requires sufficiently complete labels. |
| Threshold and agreement choices | The grouped NZ source-subject replay recovered 69/150 with the frozen rule. A crop-local BioCLIP experiment recovered 105/150 with three comparison prompts. A fresh camera transfer yielded two unreviewed cues from 112 sites. | Keep crop-local cues exploratory. A photo's recorded subject provides no exhaustive background labels. |
| Reviewer UI and return path | Hosted CVAT originals and search crops were verified against the packages. Local tests cover manifest checks, geometry, aggregation and annotation intake. The hosted jobs await independent submissions. | Use one replica per reviewer and keep the blind and assisted jobs separate. Record actual timing and unresolved cases from the returned work. |

[Source and experiment details](benchmark-program.md) ·
[ADE20K intake results](../benchmarks/ade20k-sam3-intake-20261126.json) ·
[Prompt vocabulary follow-up](../benchmarks/ade20k-sam3-vocabulary-20261126.json) ·
[Hosted CVAT audit](../benchmarks/nz-cvat-review-pilot-20261126.json)

## What still needs stronger evidence

- **Visibility suitable for NZ species review.** Generic vegetation masks
  test whether foliage was found. They do not establish that enough detail
  is visible for an expert to identify a plant. Add scene-level labels for
  clear vegetation, small or obscured vegetation, and assessed plant-poor
  views from the relevant ground-level settings. Use separate source
  groups for development and testing.
- **False alarms and missed species on whole photos.** Retain a small blind
  audit of unfiltered or low-score frames. Put most species-review slots
  toward photos with usable detail, lookalikes and difficult candidates.
  Preserve the intake stratum to make those two denominators interpretable.
- **Reviewer effort and botanical decisions.** Technical checks verify that
  reviewers can get to the source evidence. Actual work in the independent
  jobs is needed to measure effort and assess the cues.
