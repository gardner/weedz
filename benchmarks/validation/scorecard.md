# Validation scorecard

## Stage summary

| Stage | Checks | Gated passing | Gated failing | Gated unmeasured |
| --- | ---: | ---: | ---: | ---: |
| plant-presence | 2 | 6 | 28 | 6 |
| region-proposals | 5 | 0 | 0 | 0 |
| species-identification | 3 | 0 | 0 | 0 |
| target-false-alarms | 2 | 5 | 3 | 0 |
| whole-photo-species | 2 | 0 | 0 | 0 |

## Headline gates

Gated metrics in the `all` stratum. Counts above include gates in every stratum.

| Stage | Check | Metric | Count | Rate (95% CI) | Gate |
| --- | --- | --- | ---: | --- | --- |
| plant-presence | cocostuff-vegetation-presence | segformer_recall | 0/0 | unmeasured | unmeasured (≥ 95%) |
| plant-presence | cocostuff-vegetation-presence | segformer_false_alarm_rate | 0/0 | unmeasured | unmeasured (≤ 10%) |
| plant-presence | cocostuff-vegetation-presence | segformer_baseline_recall | 1045/1100 | 95.0% (93.5–96.1%) | fail (≥ 95%) |
| plant-presence | cocostuff-vegetation-presence | segformer_baseline_false_alarm_rate | 217/832 | 26.1% (23.2–29.2%) | fail (≤ 10%) |
| plant-presence | cocostuff-vegetation-presence | sam3_recall | 1026/1100 | 93.3% (91.6–94.6%) | fail (≥ 95%) |
| plant-presence | cocostuff-vegetation-presence | sam3_false_alarm_rate | 202/832 | 24.3% (21.5–27.3%) | fail (≤ 10%) |
| plant-presence | cocostuff-vegetation-presence | sam3_baseline_recall | 406/1100 | 36.9% (34.1–39.8%) | fail (≥ 95%) |
| plant-presence | cocostuff-vegetation-presence | sam3_baseline_false_alarm_rate | 46/832 | 5.5% (4.2–7.3%) | pass (≤ 10%) |
| plant-presence | openimages-plant-presence | segformer_false_alarm_rate | 580/1500 | 38.7% (36.2–41.2%) | fail (≤ 10%) |
| plant-presence | openimages-plant-presence | segformer_recall | 1433/1500 | 95.5% (94.4–96.5%) | fail (≥ 95%) |
| plant-presence | openimages-plant-presence | sam3_false_alarm_rate | 355/1500 | 23.7% (21.6–25.9%) | fail (≤ 10%) |
| plant-presence | openimages-plant-presence | sam3_recall | 1420/1500 | 94.7% (93.4–95.7%) | fail (≥ 95%) |
| target-false-alarms | inat2021-target-false-alarms | pilot_cue_wrong_subject | 15/42680 | 0.0% (0.0–0.1%) | pass (≤ 1%) |
| target-false-alarms | inat2021-target-false-alarms | local_cue_wrong_subject | 107/42680 | 0.3% (0.2–0.3%) | pass (≤ 1%) |
| target-false-alarms | plantclef2024-target-false-alarms | pilot_cue_wrong_subject | 49/20503 | 0.2% (0.2–0.3%) | pass (≤ 1%) |
| target-false-alarms | plantclef2024-target-false-alarms | local_cue_wrong_subject | 223/20503 | 1.1% (1.0–1.2%) | fail (≤ 1%) |

## Full results

| Stage | Check | Dataset | Split | Metric | Stratum | Count | Rate (95% CI) | Gate |
| --- | --- | --- | --- | --- | --- | ---: | --- | --- |
| plant-presence | cocostuff-vegetation-presence | COCO-Stuff val2017 | held-out | segformer_recall | all | 0/0 | unmeasured | unmeasured (≥ 95%) |
| plant-presence | cocostuff-vegetation-presence | COCO-Stuff val2017 | held-out | segformer_recall | tiny | 0/0 | unmeasured | unmeasured (≥ 95%) |
| plant-presence | cocostuff-vegetation-presence | COCO-Stuff val2017 | held-out | segformer_recall | small | 0/0 | unmeasured | unmeasured (≥ 95%) |
| plant-presence | cocostuff-vegetation-presence | COCO-Stuff val2017 | held-out | segformer_recall | medium | 0/0 | unmeasured | unmeasured (≥ 95%) |
| plant-presence | cocostuff-vegetation-presence | COCO-Stuff val2017 | held-out | segformer_recall | large | 0/0 | unmeasured | unmeasured (≥ 95%) |
| plant-presence | cocostuff-vegetation-presence | COCO-Stuff val2017 | held-out | segformer_false_alarm_rate | all | 0/0 | unmeasured | unmeasured (≤ 10%) |
| plant-presence | cocostuff-vegetation-presence | COCO-Stuff val2017 | held-out | segformer_baseline_recall | all | 1045/1100 | 95.0% (93.5–96.1%) | fail (≥ 95%) |
| plant-presence | cocostuff-vegetation-presence | COCO-Stuff val2017 | held-out | segformer_baseline_recall | tiny | 25/44 | 56.8% (42.2–70.3%) | fail (≥ 95%) |
| plant-presence | cocostuff-vegetation-presence | COCO-Stuff val2017 | held-out | segformer_baseline_recall | small | 82/99 | 82.8% (74.2–89.0%) | fail (≥ 95%) |
| plant-presence | cocostuff-vegetation-presence | COCO-Stuff val2017 | held-out | segformer_baseline_recall | medium | 241/255 | 94.5% (91.0–96.7%) | fail (≥ 95%) |
| plant-presence | cocostuff-vegetation-presence | COCO-Stuff val2017 | held-out | segformer_baseline_recall | large | 697/702 | 99.3% (98.3–99.7%) | pass (≥ 95%) |
| plant-presence | cocostuff-vegetation-presence | COCO-Stuff val2017 | held-out | segformer_baseline_false_alarm_rate | all | 217/832 | 26.1% (23.2–29.2%) | fail (≤ 10%) |
| plant-presence | cocostuff-vegetation-presence | COCO-Stuff val2017 | held-out | sam3_recall | all | 1026/1100 | 93.3% (91.6–94.6%) | fail (≥ 95%) |
| plant-presence | cocostuff-vegetation-presence | COCO-Stuff val2017 | held-out | sam3_recall | tiny | 41/44 | 93.2% (81.8–97.7%) | fail (≥ 95%) |
| plant-presence | cocostuff-vegetation-presence | COCO-Stuff val2017 | held-out | sam3_recall | small | 90/99 | 90.9% (83.6–95.1%) | fail (≥ 95%) |
| plant-presence | cocostuff-vegetation-presence | COCO-Stuff val2017 | held-out | sam3_recall | medium | 231/255 | 90.6% (86.4–93.6%) | fail (≥ 95%) |
| plant-presence | cocostuff-vegetation-presence | COCO-Stuff val2017 | held-out | sam3_recall | large | 664/702 | 94.6% (92.7–96.0%) | fail (≥ 95%) |
| plant-presence | cocostuff-vegetation-presence | COCO-Stuff val2017 | held-out | sam3_false_alarm_rate | all | 202/832 | 24.3% (21.5–27.3%) | fail (≤ 10%) |
| plant-presence | cocostuff-vegetation-presence | COCO-Stuff val2017 | held-out | sam3_baseline_recall | all | 406/1100 | 36.9% (34.1–39.8%) | fail (≥ 95%) |
| plant-presence | cocostuff-vegetation-presence | COCO-Stuff val2017 | held-out | sam3_baseline_recall | tiny | 22/44 | 50.0% (35.8–64.2%) | fail (≥ 95%) |
| plant-presence | cocostuff-vegetation-presence | COCO-Stuff val2017 | held-out | sam3_baseline_recall | small | 37/99 | 37.4% (28.5–47.2%) | fail (≥ 95%) |
| plant-presence | cocostuff-vegetation-presence | COCO-Stuff val2017 | held-out | sam3_baseline_recall | medium | 93/255 | 36.5% (30.8–42.5%) | fail (≥ 95%) |
| plant-presence | cocostuff-vegetation-presence | COCO-Stuff val2017 | held-out | sam3_baseline_recall | large | 254/702 | 36.2% (32.7–39.8%) | fail (≥ 95%) |
| plant-presence | cocostuff-vegetation-presence | COCO-Stuff val2017 | held-out | sam3_baseline_false_alarm_rate | all | 46/832 | 5.5% (4.2–7.3%) | pass (≤ 10%) |
| plant-presence | openimages-plant-presence | Open Images V7 validation | held-out | segformer_false_alarm_rate | all | 580/1500 | 38.7% (36.2–41.2%) | fail (≤ 10%) |
| plant-presence | openimages-plant-presence | Open Images V7 validation | held-out | segformer_recall | all | 1433/1500 | 95.5% (94.4–96.5%) | fail (≥ 95%) |
| plant-presence | openimages-plant-presence | Open Images V7 validation | held-out | segformer_recall | group-of only | 467/477 | 97.9% (96.2–98.9%) | pass (≥ 95%) |
| plant-presence | openimages-plant-presence | Open Images V7 validation | held-out | segformer_recall | large | 502/507 | 99.0% (97.7–99.6%) | pass (≥ 95%) |
| plant-presence | openimages-plant-presence | Open Images V7 validation | held-out | segformer_recall | medium | 169/175 | 96.6% (92.7–98.4%) | fail (≥ 95%) |
| plant-presence | openimages-plant-presence | Open Images V7 validation | held-out | segformer_recall | no-box | 118/139 | 84.9% (78.0–89.9%) | fail (≥ 95%) |
| plant-presence | openimages-plant-presence | Open Images V7 validation | held-out | segformer_recall | small | 177/202 | 87.6% (82.4–91.5%) | fail (≥ 95%) |
| plant-presence | openimages-plant-presence | Open Images V7 validation | held-out | segformer_false_alarm_rate | verified-absent | 580/1500 | 38.7% (36.2–41.2%) | fail (≤ 10%) |
| plant-presence | openimages-plant-presence | Open Images V7 validation | held-out | sam3_false_alarm_rate | all | 355/1500 | 23.7% (21.6–25.9%) | fail (≤ 10%) |
| plant-presence | openimages-plant-presence | Open Images V7 validation | held-out | sam3_recall | all | 1420/1500 | 94.7% (93.4–95.7%) | fail (≥ 95%) |
| plant-presence | openimages-plant-presence | Open Images V7 validation | held-out | sam3_recall | group-of only | 441/477 | 92.5% (89.7–94.5%) | fail (≥ 95%) |
| plant-presence | openimages-plant-presence | Open Images V7 validation | held-out | sam3_recall | large | 480/507 | 94.7% (92.4–96.3%) | fail (≥ 95%) |
| plant-presence | openimages-plant-presence | Open Images V7 validation | held-out | sam3_recall | medium | 174/175 | 99.4% (96.8–99.9%) | pass (≥ 95%) |
| plant-presence | openimages-plant-presence | Open Images V7 validation | held-out | sam3_recall | no-box | 126/139 | 90.6% (84.7–94.5%) | fail (≥ 95%) |
| plant-presence | openimages-plant-presence | Open Images V7 validation | held-out | sam3_recall | small | 199/202 | 98.5% (95.7–99.5%) | pass (≥ 95%) |
| plant-presence | openimages-plant-presence | Open Images V7 validation | held-out | sam3_false_alarm_rate | verified-absent | 355/1500 | 23.7% (21.6–25.9%) | fail (≤ 10%) |
| region-proposals | cocostuff-vegetation-proposals | COCO-Stuff val2017 | held-out | half_covered_images | all | 135/1100 | 12.3% (10.5–14.3%) | — |
| region-proposals | cocostuff-vegetation-proposals | COCO-Stuff val2017 | held-out | half_covered_images | tiny | 16/44 | 36.4% (23.8–51.1%) | — |
| region-proposals | cocostuff-vegetation-proposals | COCO-Stuff val2017 | held-out | half_covered_images | small | 29/99 | 29.3% (21.2–38.9%) | — |
| region-proposals | cocostuff-vegetation-proposals | COCO-Stuff val2017 | held-out | half_covered_images | medium | 45/255 | 17.6% (13.5–22.8%) | — |
| region-proposals | cocostuff-vegetation-proposals | COCO-Stuff val2017 | held-out | half_covered_images | large | 45/702 | 6.4% (4.8–8.5%) | — |
| region-proposals | cocostuff-vegetation-proposals | COCO-Stuff val2017 | held-out | component_iou_recall | all | 280/4638 | 6.0% (5.4–6.8%) | — |
| region-proposals | cocostuff-vegetation-proposals | COCO-Stuff val2017 | held-out | component_iou_recall | tiny | 74/2545 | 2.9% (2.3–3.6%) | — |
| region-proposals | cocostuff-vegetation-proposals | COCO-Stuff val2017 | held-out | component_iou_recall | small | 96/741 | 13.0% (10.7–15.6%) | — |
| region-proposals | cocostuff-vegetation-proposals | COCO-Stuff val2017 | held-out | component_iou_recall | medium | 73/659 | 11.1% (8.9–13.7%) | — |
| region-proposals | cocostuff-vegetation-proposals | COCO-Stuff val2017 | held-out | component_iou_recall | large | 37/693 | 5.3% (3.9–7.3%) | — |
| region-proposals | cocostuff-vegetation-proposals | COCO-Stuff val2017 | held-out | component_coverage_recall | all | 372/4638 | 8.0% (7.3–8.8%) | — |
| region-proposals | cocostuff-vegetation-proposals | COCO-Stuff val2017 | held-out | component_coverage_recall | tiny | 133/2545 | 5.2% (4.4–6.2%) | — |
| region-proposals | cocostuff-vegetation-proposals | COCO-Stuff val2017 | held-out | component_coverage_recall | small | 113/741 | 15.2% (12.8–18.0%) | — |
| region-proposals | cocostuff-vegetation-proposals | COCO-Stuff val2017 | held-out | component_coverage_recall | medium | 88/659 | 13.4% (11.0–16.2%) | — |
| region-proposals | cocostuff-vegetation-proposals | COCO-Stuff val2017 | held-out | component_coverage_recall | large | 38/693 | 5.5% (4.0–7.4%) | — |
| region-proposals | cocostuff-vegetation-proposals | COCO-Stuff val2017 | held-out | potted_plant_iou_recall | all | 63/111 | 56.8% (47.5–65.6%) | — |
| region-proposals | cocostuff-vegetation-proposals | COCO-Stuff val2017 | held-out | potted_plant_iou_recall | tiny | 17/37 | 45.9% (31.0–61.6%) | — |
| region-proposals | cocostuff-vegetation-proposals | COCO-Stuff val2017 | held-out | potted_plant_iou_recall | small | 30/45 | 66.7% (52.1–78.6%) | — |
| region-proposals | cocostuff-vegetation-proposals | COCO-Stuff val2017 | held-out | potted_plant_iou_recall | medium | 12/23 | 52.2% (33.0–70.8%) | — |
| region-proposals | cocostuff-vegetation-proposals | COCO-Stuff val2017 | held-out | potted_plant_iou_recall | large | 4/6 | 66.7% (30.0–90.3%) | — |
| region-proposals | cocostuff-vegetation-proposals | COCO-Stuff val2017 | held-out | potted_plant_coverage_recall | all | 69/111 | 62.2% (52.9–70.6%) | — |
| region-proposals | cocostuff-vegetation-proposals | COCO-Stuff val2017 | held-out | potted_plant_coverage_recall | tiny | 21/37 | 56.8% (40.9–71.3%) | — |
| region-proposals | cocostuff-vegetation-proposals | COCO-Stuff val2017 | held-out | potted_plant_coverage_recall | small | 32/45 | 71.1% (56.6–82.3%) | — |
| region-proposals | cocostuff-vegetation-proposals | COCO-Stuff val2017 | held-out | potted_plant_coverage_recall | medium | 12/23 | 52.2% (33.0–70.8%) | — |
| region-proposals | cocostuff-vegetation-proposals | COCO-Stuff val2017 | held-out | potted_plant_coverage_recall | large | 4/6 | 66.7% (30.0–90.3%) | — |
| region-proposals | cocostuff-vegetation-proposals | COCO-Stuff val2017 | held-out | nonvegetation_proposal_share | all | 466/1681 | 27.7% (25.6–29.9%) | — |
| region-proposals | cocostuff-vegetation-proposals | COCO-Stuff val2017 | held-out | nonvegetation_proposal_share | tiny | 18/46 | 39.1% (26.4–53.5%) | — |
| region-proposals | cocostuff-vegetation-proposals | COCO-Stuff val2017 | held-out | nonvegetation_proposal_share | small | 15/100 | 15.0% (9.3–23.3%) | — |
| region-proposals | cocostuff-vegetation-proposals | COCO-Stuff val2017 | held-out | nonvegetation_proposal_share | medium | 80/298 | 26.8% (22.1–32.1%) | — |
| region-proposals | cocostuff-vegetation-proposals | COCO-Stuff val2017 | held-out | nonvegetation_proposal_share | large | 99/947 | 10.5% (8.7–12.6%) | — |
| region-proposals | cocostuff-vegetation-proposals | COCO-Stuff val2017 | held-out | nonvegetation_proposal_share | negative | 194/198 | 98.0% (94.9–99.2%) | — |
| region-proposals | cocostuff-vegetation-proposals | COCO-Stuff val2017 | held-out | nonvegetation_proposal_share | unassessable | 60/92 | 65.2% (55.1–74.2%) | — |
| region-proposals | cwfid-mask-coverage | CWFID publisher test, no overlap | test | foreground_90pct_covered | all | 20/20 | 100.0% (83.9–100.0%) | — |
| region-proposals | cwfid-mask-coverage | CWFID publisher test, no overlap | test | foreground_90pct_covered | crop | 17/20 | 85.0% (64.0–94.8%) | — |
| region-proposals | cwfid-mask-coverage | CWFID publisher test, no overlap | test | foreground_90pct_covered | weed | 20/20 | 100.0% (83.9–100.0%) | — |
| region-proposals | cwfid-mask-coverage | CWFID publisher test, no overlap | test | foreground_half_covered | all | 20/20 | 100.0% (83.9–100.0%) | — |
| region-proposals | cwfid-mask-coverage | CWFID publisher test, no overlap | test | foreground_half_covered | crop | 20/20 | 100.0% (83.9–100.0%) | — |
| region-proposals | cwfid-mask-coverage | CWFID publisher test, no overlap | test | foreground_half_covered | weed | 20/20 | 100.0% (83.9–100.0%) | — |
| region-proposals | imageweeds-region-recovery | ImageWeeds v2 primary138 | validation | box_recall | all | 348/645 | 54.0% (50.1–57.8%) | — |
| region-proposals | imageweeds-region-recovery | ImageWeeds v2 primary138 | validation | box_recall | crop:maize | 222/417 | 53.2% (48.4–58.0%) | — |
| region-proposals | imageweeds-region-recovery | ImageWeeds v2 primary138 | validation | box_recall | crop:soybean | 126/228 | 55.3% (48.8–61.6%) | — |
| region-proposals | imageweeds-region-recovery | ImageWeeds v2 primary138 | validation | box_recall | taxon:Amaranthus retroflexus | 54/101 | 53.5% (43.8–62.9%) | — |
| region-proposals | imageweeds-region-recovery | ImageWeeds v2 primary138 | validation | box_recall | taxon:Amaranthus tuberculatus | 50/118 | 42.4% (33.8–51.4%) | — |
| region-proposals | imageweeds-region-recovery | ImageWeeds v2 primary138 | validation | box_recall | taxon:Ambrosia artemisiifolia | 107/176 | 60.8% (53.4–67.7%) | — |
| region-proposals | imageweeds-region-recovery | ImageWeeds v2 primary138 | validation | box_recall | taxon:Bassia scoparia | 72/142 | 50.7% (42.6–58.8%) | — |
| region-proposals | imageweeds-region-recovery | ImageWeeds v2 primary138 | validation | box_recall | taxon:Erigeron canadensis | 65/108 | 60.2% (50.8–68.9%) | — |
| region-proposals | openimages-plant-boxes | Open Images V7 validation | held-out | sam3_box_recall | all | 1155/2949 | 39.2% (37.4–40.9%) | — |
| region-proposals | openimages-plant-boxes | Open Images V7 validation | held-out | sam3_box_recall | small | 500/1468 | 34.1% (31.7–36.5%) | — |
| region-proposals | openimages-plant-boxes | Open Images V7 validation | held-out | sam3_box_recall | medium | 374/824 | 45.4% (42.0–48.8%) | — |
| region-proposals | openimages-plant-boxes | Open Images V7 validation | held-out | sam3_box_recall | large | 281/657 | 42.8% (39.0–46.6%) | — |
| region-proposals | phenobench-instance-recovery | PhenoBench v1.1.0 development64 | validation | foreground_90pct_covered | all | 59/64 | 92.2% (83.0–96.6%) | — |
| region-proposals | phenobench-instance-recovery | PhenoBench v1.1.0 development64 | validation | foreground_90pct_covered | crop | 62/64 | 96.9% (89.3–99.1%) | — |
| region-proposals | phenobench-instance-recovery | PhenoBench v1.1.0 development64 | validation | foreground_90pct_covered | date:05-15 | 28/33 | 84.8% (69.1–93.3%) | — |
| region-proposals | phenobench-instance-recovery | PhenoBench v1.1.0 development64 | validation | foreground_90pct_covered | date:05-26 | 14/14 | 100.0% (78.5–100.0%) | — |
| region-proposals | phenobench-instance-recovery | PhenoBench v1.1.0 development64 | validation | foreground_90pct_covered | date:06-05 | 17/17 | 100.0% (81.6–100.0%) | — |
| region-proposals | phenobench-instance-recovery | PhenoBench v1.1.0 development64 | validation | foreground_90pct_covered | weed | 29/61 | 47.5% (35.5–59.8%) | — |
| region-proposals | phenobench-instance-recovery | PhenoBench v1.1.0 development64 | validation | foreground_half_covered | all | 64/64 | 100.0% (94.3–100.0%) | — |
| region-proposals | phenobench-instance-recovery | PhenoBench v1.1.0 development64 | validation | foreground_half_covered | crop | 64/64 | 100.0% (94.3–100.0%) | — |
| region-proposals | phenobench-instance-recovery | PhenoBench v1.1.0 development64 | validation | foreground_half_covered | date:05-15 | 33/33 | 100.0% (89.6–100.0%) | — |
| region-proposals | phenobench-instance-recovery | PhenoBench v1.1.0 development64 | validation | foreground_half_covered | date:05-26 | 14/14 | 100.0% (78.5–100.0%) | — |
| region-proposals | phenobench-instance-recovery | PhenoBench v1.1.0 development64 | validation | foreground_half_covered | date:06-05 | 17/17 | 100.0% (81.6–100.0%) | — |
| region-proposals | phenobench-instance-recovery | PhenoBench v1.1.0 development64 | validation | foreground_half_covered | weed | 56/61 | 91.8% (82.2–96.4%) | — |
| region-proposals | phenobench-instance-recovery | PhenoBench v1.1.0 development64 | validation | instance_recall | all | 535/853 | 62.7% (59.4–65.9%) | — |
| region-proposals | phenobench-instance-recovery | PhenoBench v1.1.0 development64 | validation | instance_recall | complete | 446/697 | 64.0% (60.4–67.5%) | — |
| region-proposals | phenobench-instance-recovery | PhenoBench v1.1.0 development64 | validation | instance_recall | crop | 364/519 | 70.1% (66.1–73.9%) | — |
| region-proposals | phenobench-instance-recovery | PhenoBench v1.1.0 development64 | validation | instance_recall | date:05-15 | 207/348 | 59.5% (54.2–64.5%) | — |
| region-proposals | phenobench-instance-recovery | PhenoBench v1.1.0 development64 | validation | instance_recall | date:05-26 | 130/221 | 58.8% (52.2–65.1%) | — |
| region-proposals | phenobench-instance-recovery | PhenoBench v1.1.0 development64 | validation | instance_recall | date:06-05 | 198/284 | 69.7% (64.1–74.8%) | — |
| region-proposals | phenobench-instance-recovery | PhenoBench v1.1.0 development64 | validation | instance_recall | partial | 89/156 | 57.1% (49.2–64.6%) | — |
| region-proposals | phenobench-instance-recovery | PhenoBench v1.1.0 development64 | validation | instance_recall | size:2048plus | 277/337 | 82.2% (77.8–85.9%) | — |
| region-proposals | phenobench-instance-recovery | PhenoBench v1.1.0 development64 | validation | instance_recall | size:512to2047 | 131/172 | 76.2% (69.3–81.9%) | — |
| region-proposals | phenobench-instance-recovery | PhenoBench v1.1.0 development64 | validation | instance_recall | size:under512 | 127/344 | 36.9% (32.0–42.1%) | — |
| region-proposals | phenobench-instance-recovery | PhenoBench v1.1.0 development64 | validation | instance_recall | weed | 171/334 | 51.2% (45.9–56.5%) | — |
| species-identification | imageweeds-species | ImageWeeds v2 primary138 | validation | conditional_top1 | all | 48/348 | 13.8% (10.6–17.8%) | — |
| species-identification | imageweeds-species | ImageWeeds v2 primary138 | validation | conditional_top1 | crop:maize | 27/222 | 12.2% (8.5–17.1%) | — |
| species-identification | imageweeds-species | ImageWeeds v2 primary138 | validation | conditional_top1 | crop:soybean | 21/126 | 16.7% (11.2–24.1%) | — |
| species-identification | imageweeds-species | ImageWeeds v2 primary138 | validation | conditional_top1 | taxon:Amaranthus retroflexus | 16/54 | 29.6% (19.1–42.8%) | — |
| species-identification | imageweeds-species | ImageWeeds v2 primary138 | validation | conditional_top1 | taxon:Amaranthus tuberculatus | 0/50 | 0.0% (0.0–7.1%) | — |
| species-identification | imageweeds-species | ImageWeeds v2 primary138 | validation | conditional_top1 | taxon:Ambrosia artemisiifolia | 20/107 | 18.7% (12.4–27.1%) | — |
| species-identification | imageweeds-species | ImageWeeds v2 primary138 | validation | conditional_top1 | taxon:Bassia scoparia | 6/72 | 8.3% (3.9–17.0%) | — |
| species-identification | imageweeds-species | ImageWeeds v2 primary138 | validation | conditional_top1 | taxon:Erigeron canadensis | 6/65 | 9.2% (4.3–18.7%) | — |
| species-identification | imageweeds-species | ImageWeeds v2 primary138 | validation | conditional_top5 | all | 179/348 | 51.4% (46.2–56.6%) | — |
| species-identification | imageweeds-species | ImageWeeds v2 primary138 | validation | conditional_top5 | crop:maize | 110/222 | 49.5% (43.0–56.1%) | — |
| species-identification | imageweeds-species | ImageWeeds v2 primary138 | validation | conditional_top5 | crop:soybean | 69/126 | 54.8% (46.1–63.2%) | — |
| species-identification | imageweeds-species | ImageWeeds v2 primary138 | validation | conditional_top5 | taxon:Amaranthus retroflexus | 43/54 | 79.6% (67.1–88.2%) | — |
| species-identification | imageweeds-species | ImageWeeds v2 primary138 | validation | conditional_top5 | taxon:Amaranthus tuberculatus | 22/50 | 44.0% (31.2–57.7%) | — |
| species-identification | imageweeds-species | ImageWeeds v2 primary138 | validation | conditional_top5 | taxon:Ambrosia artemisiifolia | 66/107 | 61.7% (52.2–70.3%) | — |
| species-identification | imageweeds-species | ImageWeeds v2 primary138 | validation | conditional_top5 | taxon:Bassia scoparia | 23/72 | 31.9% (22.3–43.4%) | — |
| species-identification | imageweeds-species | ImageWeeds v2 primary138 | validation | conditional_top5 | taxon:Erigeron canadensis | 25/65 | 38.5% (27.6–50.6%) | — |
| species-identification | imageweeds-species | ImageWeeds v2 primary138 | validation | image_species_frequency_at5 | all | 5/303 | 1.7% (0.7–3.8%) | — |
| species-identification | imageweeds-species | ImageWeeds v2 primary138 | validation | image_species_frequency_at5 | crop:maize | 3/194 | 1.5% (0.5–4.4%) | — |
| species-identification | imageweeds-species | ImageWeeds v2 primary138 | validation | image_species_frequency_at5 | crop:soybean | 2/109 | 1.8% (0.5–6.4%) | — |
| species-identification | imageweeds-species | ImageWeeds v2 primary138 | validation | image_species_frequency_at5 | taxon:Amaranthus retroflexus | 0/48 | 0.0% (0.0–7.4%) | — |
| species-identification | imageweeds-species | ImageWeeds v2 primary138 | validation | image_species_frequency_at5 | taxon:Amaranthus tuberculatus | 0/50 | 0.0% (0.0–7.1%) | — |
| species-identification | imageweeds-species | ImageWeeds v2 primary138 | validation | image_species_frequency_at5 | taxon:Ambrosia artemisiifolia | 3/72 | 4.2% (1.4–11.5%) | — |
| species-identification | imageweeds-species | ImageWeeds v2 primary138 | validation | image_species_frequency_at5 | taxon:Bassia scoparia | 2/68 | 2.9% (0.8–10.1%) | — |
| species-identification | imageweeds-species | ImageWeeds v2 primary138 | validation | image_species_frequency_at5 | taxon:Erigeron canadensis | 0/65 | 0.0% (0.0–5.6%) | — |
| species-identification | imageweeds-species | ImageWeeds v2 primary138 | validation | image_species_max_score_at5 | all | 23/303 | 7.6% (5.1–11.1%) | — |
| species-identification | imageweeds-species | ImageWeeds v2 primary138 | validation | image_species_max_score_at5 | crop:maize | 14/194 | 7.2% (4.3–11.7%) | — |
| species-identification | imageweeds-species | ImageWeeds v2 primary138 | validation | image_species_max_score_at5 | crop:soybean | 9/109 | 8.3% (4.4–15.0%) | — |
| species-identification | imageweeds-species | ImageWeeds v2 primary138 | validation | image_species_max_score_at5 | taxon:Amaranthus retroflexus | 6/48 | 12.5% (5.9–24.7%) | — |
| species-identification | imageweeds-species | ImageWeeds v2 primary138 | validation | image_species_max_score_at5 | taxon:Amaranthus tuberculatus | 0/50 | 0.0% (0.0–7.1%) | — |
| species-identification | imageweeds-species | ImageWeeds v2 primary138 | validation | image_species_max_score_at5 | taxon:Ambrosia artemisiifolia | 9/72 | 12.5% (6.7–22.1%) | — |
| species-identification | imageweeds-species | ImageWeeds v2 primary138 | validation | image_species_max_score_at5 | taxon:Bassia scoparia | 6/68 | 8.8% (4.1–17.9%) | — |
| species-identification | imageweeds-species | ImageWeeds v2 primary138 | validation | image_species_max_score_at5 | taxon:Erigeron canadensis | 2/65 | 3.1% (0.8–10.5%) | — |
| species-identification | imageweeds-species | ImageWeeds v2 primary138 | validation | localized_and_identified | all | 48/645 | 7.4% (5.7–9.7%) | — |
| species-identification | imageweeds-species | ImageWeeds v2 primary138 | validation | localized_and_identified | crop:maize | 27/417 | 6.5% (4.5–9.3%) | — |
| species-identification | imageweeds-species | ImageWeeds v2 primary138 | validation | localized_and_identified | crop:soybean | 21/228 | 9.2% (6.1–13.7%) | — |
| species-identification | imageweeds-species | ImageWeeds v2 primary138 | validation | localized_and_identified | taxon:Amaranthus retroflexus | 16/101 | 15.8% (10.0–24.2%) | — |
| species-identification | imageweeds-species | ImageWeeds v2 primary138 | validation | localized_and_identified | taxon:Amaranthus tuberculatus | 0/118 | 0.0% (0.0–3.2%) | — |
| species-identification | imageweeds-species | ImageWeeds v2 primary138 | validation | localized_and_identified | taxon:Ambrosia artemisiifolia | 20/176 | 11.4% (7.5–16.9%) | — |
| species-identification | imageweeds-species | ImageWeeds v2 primary138 | validation | localized_and_identified | taxon:Bassia scoparia | 6/142 | 4.2% (2.0–8.9%) | — |
| species-identification | imageweeds-species | ImageWeeds v2 primary138 | validation | localized_and_identified | taxon:Erigeron canadensis | 6/108 | 5.6% (2.6–11.6%) | — |
| species-identification | imageweeds-species | ImageWeeds v2 primary138 | validation | source_box_top1 | all | 74/645 | 11.5% (9.2–14.2%) | — |
| species-identification | imageweeds-species | ImageWeeds v2 primary138 | validation | source_box_top1 | crop:maize | 37/417 | 8.9% (6.5–12.0%) | — |
| species-identification | imageweeds-species | ImageWeeds v2 primary138 | validation | source_box_top1 | crop:soybean | 37/228 | 16.2% (12.0–21.6%) | — |
| species-identification | imageweeds-species | ImageWeeds v2 primary138 | validation | source_box_top1 | taxon:Amaranthus retroflexus | 17/101 | 16.8% (10.8–25.3%) | — |
| species-identification | imageweeds-species | ImageWeeds v2 primary138 | validation | source_box_top1 | taxon:Amaranthus tuberculatus | 2/118 | 1.7% (0.5–6.0%) | — |
| species-identification | imageweeds-species | ImageWeeds v2 primary138 | validation | source_box_top1 | taxon:Ambrosia artemisiifolia | 39/176 | 22.2% (16.7–28.9%) | — |
| species-identification | imageweeds-species | ImageWeeds v2 primary138 | validation | source_box_top1 | taxon:Bassia scoparia | 7/142 | 4.9% (2.4–9.8%) | — |
| species-identification | imageweeds-species | ImageWeeds v2 primary138 | validation | source_box_top1 | taxon:Erigeron canadensis | 9/108 | 8.3% (4.4–15.1%) | — |
| species-identification | imageweeds-species | ImageWeeds v2 primary138 | validation | source_box_top5 | all | 297/645 | 46.0% (42.2–49.9%) | — |
| species-identification | imageweeds-species | ImageWeeds v2 primary138 | validation | source_box_top5 | crop:maize | 177/417 | 42.4% (37.8–47.2%) | — |
| species-identification | imageweeds-species | ImageWeeds v2 primary138 | validation | source_box_top5 | crop:soybean | 120/228 | 52.6% (46.2–59.0%) | — |
| species-identification | imageweeds-species | ImageWeeds v2 primary138 | validation | source_box_top5 | taxon:Amaranthus retroflexus | 65/101 | 64.4% (54.6–73.0%) | — |
| species-identification | imageweeds-species | ImageWeeds v2 primary138 | validation | source_box_top5 | taxon:Amaranthus tuberculatus | 63/118 | 53.4% (44.4–62.1%) | — |
| species-identification | imageweeds-species | ImageWeeds v2 primary138 | validation | source_box_top5 | taxon:Ambrosia artemisiifolia | 111/176 | 63.1% (55.7–69.8%) | — |
| species-identification | imageweeds-species | ImageWeeds v2 primary138 | validation | source_box_top5 | taxon:Bassia scoparia | 33/142 | 23.2% (17.1–30.8%) | — |
| species-identification | imageweeds-species | ImageWeeds v2 primary138 | validation | source_box_top5 | taxon:Erigeron canadensis | 25/108 | 23.1% (16.2–31.9%) | — |
| species-identification | inat2021-target-species | iNat2021 validation | validation | plantclef_top1_recall | all | 16/30 | 53.3% (36.1–69.8%) | — |
| species-identification | inat2021-target-species | iNat2021 validation | validation | plantclef_top5_recall | all | 26/30 | 86.7% (70.3–94.7%) | — |
| species-identification | inat2021-target-species | iNat2021 validation | validation | bioclip_top1_recall | all | 28/30 | 93.3% (78.7–98.2%) | — |
| species-identification | inat2021-target-species | iNat2021 validation | validation | bioclip_top5_recall | all | 30/30 | 100.0% (88.6–100.0%) | — |
| species-identification | inat2021-target-species | iNat2021 validation | validation | pilot_cue_recall | all | 21/30 | 70.0% (52.1–83.3%) | — |
| species-identification | inat2021-target-species | iNat2021 validation | validation | local_cue_recall | all | 20/30 | 66.7% (48.8–80.8%) | — |
| species-identification | inat2021-target-species | iNat2021 validation | validation | plantclef_top1_recall | Clematis vitalba | 6/10 | 60.0% (31.3–83.2%) | — |
| species-identification | inat2021-target-species | iNat2021 validation | validation | plantclef_top5_recall | Clematis vitalba | 8/10 | 80.0% (49.0–94.3%) | — |
| species-identification | inat2021-target-species | iNat2021 validation | validation | bioclip_top1_recall | Clematis vitalba | 8/10 | 80.0% (49.0–94.3%) | — |
| species-identification | inat2021-target-species | iNat2021 validation | validation | bioclip_top5_recall | Clematis vitalba | 10/10 | 100.0% (72.2–100.0%) | — |
| species-identification | inat2021-target-species | iNat2021 validation | validation | pilot_cue_recall | Clematis vitalba | 7/10 | 70.0% (39.7–89.2%) | — |
| species-identification | inat2021-target-species | iNat2021 validation | validation | local_cue_recall | Clematis vitalba | 8/10 | 80.0% (49.0–94.3%) | — |
| species-identification | inat2021-target-species | iNat2021 validation | validation | plantclef_top1_recall | Cortaderia selloana | 6/10 | 60.0% (31.3–83.2%) | — |
| species-identification | inat2021-target-species | iNat2021 validation | validation | plantclef_top5_recall | Cortaderia selloana | 9/10 | 90.0% (59.6–98.2%) | — |
| species-identification | inat2021-target-species | iNat2021 validation | validation | bioclip_top1_recall | Cortaderia selloana | 10/10 | 100.0% (72.2–100.0%) | — |
| species-identification | inat2021-target-species | iNat2021 validation | validation | bioclip_top5_recall | Cortaderia selloana | 10/10 | 100.0% (72.2–100.0%) | — |
| species-identification | inat2021-target-species | iNat2021 validation | validation | pilot_cue_recall | Cortaderia selloana | 8/10 | 80.0% (49.0–94.3%) | — |
| species-identification | inat2021-target-species | iNat2021 validation | validation | local_cue_recall | Cortaderia selloana | 5/10 | 50.0% (23.7–76.3%) | — |
| species-identification | inat2021-target-species | iNat2021 validation | validation | plantclef_top1_recall | Ulex europaeus | 4/10 | 40.0% (16.8–68.7%) | — |
| species-identification | inat2021-target-species | iNat2021 validation | validation | plantclef_top5_recall | Ulex europaeus | 9/10 | 90.0% (59.6–98.2%) | — |
| species-identification | inat2021-target-species | iNat2021 validation | validation | bioclip_top1_recall | Ulex europaeus | 10/10 | 100.0% (72.2–100.0%) | — |
| species-identification | inat2021-target-species | iNat2021 validation | validation | bioclip_top5_recall | Ulex europaeus | 10/10 | 100.0% (72.2–100.0%) | — |
| species-identification | inat2021-target-species | iNat2021 validation | validation | pilot_cue_recall | Ulex europaeus | 6/10 | 60.0% (31.3–83.2%) | — |
| species-identification | inat2021-target-species | iNat2021 validation | validation | local_cue_recall | Ulex europaeus | 7/10 | 70.0% (39.7–89.2%) | — |
| species-identification | inat2021-target-species | iNat2021 validation | validation | plantclef_top1_confusion | all | 3/40 | 7.5% (2.6–19.9%) | — |
| species-identification | inat2021-target-species | iNat2021 validation | validation | plantclef_top1_confusion | Austroderia richardii | 3/10 | 30.0% (10.8–60.3%) | — |
| species-identification | inat2021-target-species | iNat2021 validation | validation | plantclef_top1_confusion | Clematis paniculata | 0/10 | 0.0% (0.0–27.8%) | — |
| species-identification | inat2021-target-species | iNat2021 validation | validation | plantclef_top1_confusion | Cytisus scoparius | 0/10 | 0.0% (0.0–27.8%) | — |
| species-identification | inat2021-target-species | iNat2021 validation | validation | plantclef_top1_confusion | Leptospermum scoparium | 0/10 | 0.0% (0.0–27.8%) | — |
| species-identification | inat2021-target-species | iNat2021 validation | validation | bioclip_top1_confusion | all | 0/40 | 0.0% (0.0–8.8%) | — |
| species-identification | inat2021-target-species | iNat2021 validation | validation | bioclip_top1_confusion | Austroderia richardii | 0/10 | 0.0% (0.0–27.8%) | — |
| species-identification | inat2021-target-species | iNat2021 validation | validation | bioclip_top1_confusion | Clematis paniculata | 0/10 | 0.0% (0.0–27.8%) | — |
| species-identification | inat2021-target-species | iNat2021 validation | validation | bioclip_top1_confusion | Cytisus scoparius | 0/10 | 0.0% (0.0–27.8%) | — |
| species-identification | inat2021-target-species | iNat2021 validation | validation | bioclip_top1_confusion | Leptospermum scoparium | 0/10 | 0.0% (0.0–27.8%) | — |
| species-identification | inat2021-target-species | iNat2021 validation | validation | pilot_cue_confusion | all | 0/40 | 0.0% (0.0–8.8%) | — |
| species-identification | inat2021-target-species | iNat2021 validation | validation | pilot_cue_confusion | Austroderia richardii | 0/10 | 0.0% (0.0–27.8%) | — |
| species-identification | inat2021-target-species | iNat2021 validation | validation | pilot_cue_confusion | Clematis paniculata | 0/10 | 0.0% (0.0–27.8%) | — |
| species-identification | inat2021-target-species | iNat2021 validation | validation | pilot_cue_confusion | Cytisus scoparius | 0/10 | 0.0% (0.0–27.8%) | — |
| species-identification | inat2021-target-species | iNat2021 validation | validation | pilot_cue_confusion | Leptospermum scoparium | 0/10 | 0.0% (0.0–27.8%) | — |
| species-identification | inat2021-target-species | iNat2021 validation | validation | local_cue_confusion | all | 0/40 | 0.0% (0.0–8.8%) | — |
| species-identification | inat2021-target-species | iNat2021 validation | validation | local_cue_confusion | Austroderia richardii | 0/10 | 0.0% (0.0–27.8%) | — |
| species-identification | inat2021-target-species | iNat2021 validation | validation | local_cue_confusion | Clematis paniculata | 0/10 | 0.0% (0.0–27.8%) | — |
| species-identification | inat2021-target-species | iNat2021 validation | validation | local_cue_confusion | Cytisus scoparius | 0/10 | 0.0% (0.0–27.8%) | — |
| species-identification | inat2021-target-species | iNat2021 validation | validation | local_cue_confusion | Leptospermum scoparium | 0/10 | 0.0% (0.0–27.8%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top1_recall | all | 47/60 | 78.3% (66.4–86.9%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top5_recall | all | 55/60 | 91.7% (81.9–96.4%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_recall | all | 51/60 | 85.0% (73.9–91.9%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top5_recall | all | 60/60 | 100.0% (94.0–100.0%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_recall | all | 34/60 | 56.7% (44.1–68.4%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_recall | all | 25/60 | 41.7% (30.1–54.3%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top1_recall | Clematis vitalba | 18/20 | 90.0% (69.9–97.2%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top5_recall | Clematis vitalba | 19/20 | 95.0% (76.4–99.1%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_recall | Clematis vitalba | 19/20 | 95.0% (76.4–99.1%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top5_recall | Clematis vitalba | 20/20 | 100.0% (83.9–100.0%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_recall | Clematis vitalba | 13/20 | 65.0% (43.3–81.9%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_recall | Clematis vitalba | 11/20 | 55.0% (34.2–74.2%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top1_recall | Cortaderia selloana | 13/20 | 65.0% (43.3–81.9%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top5_recall | Cortaderia selloana | 17/20 | 85.0% (64.0–94.8%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_recall | Cortaderia selloana | 15/20 | 75.0% (53.1–88.8%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top5_recall | Cortaderia selloana | 20/20 | 100.0% (83.9–100.0%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_recall | Cortaderia selloana | 9/20 | 45.0% (25.8–65.8%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_recall | Cortaderia selloana | 5/20 | 25.0% (11.2–46.9%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top1_recall | Ulex europaeus | 16/20 | 80.0% (58.4–91.9%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top5_recall | Ulex europaeus | 19/20 | 95.0% (76.4–99.1%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_recall | Ulex europaeus | 17/20 | 85.0% (64.0–94.8%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top5_recall | Ulex europaeus | 20/20 | 100.0% (83.9–100.0%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_recall | Ulex europaeus | 12/20 | 60.0% (38.7–78.1%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_recall | Ulex europaeus | 9/20 | 45.0% (25.8–65.8%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top1_confusion | all | 0/20 | 0.0% (0.0–16.1%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top1_confusion | Cytisus scoparius | 0/20 | 0.0% (0.0–16.1%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_confusion | all | 0/20 | 0.0% (0.0–16.1%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_confusion | Cytisus scoparius | 0/20 | 0.0% (0.0–16.1%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_confusion | all | 0/20 | 0.0% (0.0–16.1%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_confusion | Cytisus scoparius | 0/20 | 0.0% (0.0–16.1%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_confusion | all | 1/20 | 5.0% (0.9–23.6%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_confusion | Cytisus scoparius | 1/20 | 5.0% (0.9–23.6%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top1_recall | val | 22/30 | 73.3% (55.6–85.8%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top5_recall | val | 28/30 | 93.3% (78.7–98.2%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_recall | val | 26/30 | 86.7% (70.3–94.7%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top5_recall | val | 30/30 | 100.0% (88.6–100.0%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_recall | val | 18/30 | 60.0% (42.3–75.4%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_recall | val | 14/30 | 46.7% (30.2–63.9%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top1_recall | val/Clematis vitalba | 8/10 | 80.0% (49.0–94.3%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top5_recall | val/Clematis vitalba | 9/10 | 90.0% (59.6–98.2%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_recall | val/Clematis vitalba | 10/10 | 100.0% (72.2–100.0%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top5_recall | val/Clematis vitalba | 10/10 | 100.0% (72.2–100.0%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_recall | val/Clematis vitalba | 7/10 | 70.0% (39.7–89.2%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_recall | val/Clematis vitalba | 5/10 | 50.0% (23.7–76.3%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top1_recall | val/Cortaderia selloana | 6/10 | 60.0% (31.3–83.2%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top5_recall | val/Cortaderia selloana | 9/10 | 90.0% (59.6–98.2%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_recall | val/Cortaderia selloana | 8/10 | 80.0% (49.0–94.3%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top5_recall | val/Cortaderia selloana | 10/10 | 100.0% (72.2–100.0%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_recall | val/Cortaderia selloana | 5/10 | 50.0% (23.7–76.3%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_recall | val/Cortaderia selloana | 4/10 | 40.0% (16.8–68.7%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top1_recall | val/Ulex europaeus | 8/10 | 80.0% (49.0–94.3%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top5_recall | val/Ulex europaeus | 10/10 | 100.0% (72.2–100.0%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_recall | val/Ulex europaeus | 8/10 | 80.0% (49.0–94.3%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top5_recall | val/Ulex europaeus | 10/10 | 100.0% (72.2–100.0%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_recall | val/Ulex europaeus | 6/10 | 60.0% (31.3–83.2%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_recall | val/Ulex europaeus | 5/10 | 50.0% (23.7–76.3%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top1_confusion | val | 0/10 | 0.0% (0.0–27.8%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top1_confusion | val/Cytisus scoparius | 0/10 | 0.0% (0.0–27.8%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_confusion | val | 0/10 | 0.0% (0.0–27.8%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_confusion | val/Cytisus scoparius | 0/10 | 0.0% (0.0–27.8%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_confusion | val | 0/10 | 0.0% (0.0–27.8%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_confusion | val/Cytisus scoparius | 0/10 | 0.0% (0.0–27.8%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_confusion | val | 0/10 | 0.0% (0.0–27.8%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_confusion | val/Cytisus scoparius | 0/10 | 0.0% (0.0–27.8%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top1_recall | test | 25/30 | 83.3% (66.4–92.7%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top5_recall | test | 27/30 | 90.0% (74.4–96.5%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_recall | test | 25/30 | 83.3% (66.4–92.7%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top5_recall | test | 30/30 | 100.0% (88.6–100.0%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_recall | test | 16/30 | 53.3% (36.1–69.8%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_recall | test | 11/30 | 36.7% (21.9–54.5%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top1_recall | test/Clematis vitalba | 10/10 | 100.0% (72.2–100.0%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top5_recall | test/Clematis vitalba | 10/10 | 100.0% (72.2–100.0%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_recall | test/Clematis vitalba | 9/10 | 90.0% (59.6–98.2%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top5_recall | test/Clematis vitalba | 10/10 | 100.0% (72.2–100.0%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_recall | test/Clematis vitalba | 6/10 | 60.0% (31.3–83.2%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_recall | test/Clematis vitalba | 6/10 | 60.0% (31.3–83.2%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top1_recall | test/Cortaderia selloana | 7/10 | 70.0% (39.7–89.2%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top5_recall | test/Cortaderia selloana | 8/10 | 80.0% (49.0–94.3%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_recall | test/Cortaderia selloana | 7/10 | 70.0% (39.7–89.2%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top5_recall | test/Cortaderia selloana | 10/10 | 100.0% (72.2–100.0%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_recall | test/Cortaderia selloana | 4/10 | 40.0% (16.8–68.7%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_recall | test/Cortaderia selloana | 1/10 | 10.0% (1.8–40.4%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top1_recall | test/Ulex europaeus | 8/10 | 80.0% (49.0–94.3%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top5_recall | test/Ulex europaeus | 9/10 | 90.0% (59.6–98.2%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_recall | test/Ulex europaeus | 9/10 | 90.0% (59.6–98.2%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top5_recall | test/Ulex europaeus | 10/10 | 100.0% (72.2–100.0%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_recall | test/Ulex europaeus | 6/10 | 60.0% (31.3–83.2%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_recall | test/Ulex europaeus | 4/10 | 40.0% (16.8–68.7%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top1_confusion | test | 0/10 | 0.0% (0.0–27.8%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top1_confusion | test/Cytisus scoparius | 0/10 | 0.0% (0.0–27.8%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_confusion | test | 0/10 | 0.0% (0.0–27.8%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_confusion | test/Cytisus scoparius | 0/10 | 0.0% (0.0–27.8%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_confusion | test | 0/10 | 0.0% (0.0–27.8%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_confusion | test/Cytisus scoparius | 0/10 | 0.0% (0.0–27.8%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_confusion | test | 1/10 | 10.0% (1.8–40.4%) | — |
| species-identification | plantclef2024-target-species | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_confusion | test/Cytisus scoparius | 1/10 | 10.0% (1.8–40.4%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | plantclef_top1_wrong_subject | all | 19/42680 | 0.0% (0.0–0.1%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | plantclef_top1_wrong_subject | lookalike | 3/40 | 7.5% (2.6–19.9%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | plantclef_top1_wrong_subject | same_genus | 11/110 | 10.0% (5.7–17.0%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | plantclef_top1_wrong_subject | same_family | 0/4390 | 0.0% (0.0–0.1%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | plantclef_top1_wrong_subject | other_plants | 5/38140 | 0.0% (0.0–0.0%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | plantclef_top1_worst_species | Clematis lasiantha | 4/10 | 40.0% (16.8–68.7%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | plantclef_top1_worst_species | Clematis virginiana | 4/10 | 40.0% (16.8–68.7%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | plantclef_top1_worst_species | Austroderia richardii | 3/10 | 30.0% (10.8–60.3%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | plantclef_top1_worst_species | Cortaderia jubata | 2/10 | 20.0% (5.7–51.0%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | plantclef_top1_worst_species | Smilax pumila | 2/10 | 20.0% (5.7–51.0%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | plantclef_top1_worst_species | Clematis drummondii | 1/10 | 10.0% (1.8–40.4%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | plantclef_top1_worst_species | Smilax glauca | 1/10 | 10.0% (1.8–40.4%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | plantclef_top1_worst_species | Smilax tamnoides | 1/10 | 10.0% (1.8–40.4%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | plantclef_top1_worst_species | Tillandsia usneoides | 1/10 | 10.0% (1.8–40.4%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | bioclip_top1_wrong_subject | all | 16515/42680 | 38.7% (38.2–39.2%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | bioclip_top1_wrong_subject | lookalike | 0/40 | 0.0% (0.0–8.8%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | bioclip_top1_wrong_subject | same_genus | 79/110 | 71.8% (62.8–79.4%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | bioclip_top1_wrong_subject | same_family | 1247/4390 | 28.4% (27.1–29.8%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | bioclip_top1_wrong_subject | other_plants | 15189/38140 | 39.8% (39.3–40.3%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | bioclip_top1_worst_species | Acer ginnala | 10/10 | 100.0% (72.2–100.0%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | bioclip_top1_worst_species | Acer negundo | 10/10 | 100.0% (72.2–100.0%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | bioclip_top1_worst_species | Acmella repens | 10/10 | 100.0% (72.2–100.0%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | bioclip_top1_worst_species | Aconitum septentrionale | 10/10 | 100.0% (72.2–100.0%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | bioclip_top1_worst_species | Actaea pachypoda | 10/10 | 100.0% (72.2–100.0%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | bioclip_top1_worst_species | Actaea rubra | 10/10 | 100.0% (72.2–100.0%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | bioclip_top1_worst_species | Actaea spicata | 10/10 | 100.0% (72.2–100.0%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | bioclip_top1_worst_species | Adenocaulon bicolor | 10/10 | 100.0% (72.2–100.0%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | bioclip_top1_worst_species | Adonis vernalis | 10/10 | 100.0% (72.2–100.0%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | bioclip_top1_worst_species | Aegopodium podagraria | 10/10 | 100.0% (72.2–100.0%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | bioclip_top1_worst_species | Aesculus hippocastanum | 10/10 | 100.0% (72.2–100.0%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | bioclip_top1_worst_species | Agave deserti | 10/10 | 100.0% (72.2–100.0%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | bioclip_top1_worst_species | Agave shawii | 10/10 | 100.0% (72.2–100.0%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | bioclip_top1_worst_species | Ageratina altissima | 10/10 | 100.0% (72.2–100.0%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | bioclip_top1_worst_species | Ageratina havanensis | 10/10 | 100.0% (72.2–100.0%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | pilot_cue_wrong_subject | all | 15/42680 | 0.0% (0.0–0.1%) | pass (≤ 1%) |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | pilot_cue_wrong_subject | lookalike | 0/40 | 0.0% (0.0–8.8%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | pilot_cue_wrong_subject | same_genus | 14/110 | 12.7% (7.7–20.2%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | pilot_cue_wrong_subject | same_family | 1/4390 | 0.0% (0.0–0.1%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | pilot_cue_wrong_subject | other_plants | 0/38140 | 0.0% (0.0–0.0%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | pilot_cue_worst_species | Clematis virginiana | 5/10 | 50.0% (23.7–76.3%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | pilot_cue_worst_species | Clematis lasiantha | 4/10 | 40.0% (16.8–68.7%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | pilot_cue_worst_species | Clematis ligusticifolia | 2/10 | 20.0% (5.7–51.0%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | pilot_cue_worst_species | Cortaderia jubata | 2/10 | 20.0% (5.7–51.0%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | pilot_cue_worst_species | Clematis drummondii | 1/10 | 10.0% (1.8–40.4%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | pilot_cue_worst_species | Miscanthus sinensis | 1/10 | 10.0% (1.8–40.4%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | local_cue_wrong_subject | all | 107/42680 | 0.3% (0.2–0.3%) | pass (≤ 1%) |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | local_cue_wrong_subject | lookalike | 0/40 | 0.0% (0.0–8.8%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | local_cue_wrong_subject | same_genus | 37/110 | 33.6% (25.5–42.9%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | local_cue_wrong_subject | same_family | 5/4390 | 0.1% (0.0–0.3%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | local_cue_wrong_subject | other_plants | 65/38140 | 0.2% (0.1–0.2%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | local_cue_worst_species | Clematis virginiana | 8/10 | 80.0% (49.0–94.3%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | local_cue_worst_species | Clematis drummondii | 6/10 | 60.0% (31.3–83.2%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | local_cue_worst_species | Cortaderia jubata | 6/10 | 60.0% (31.3–83.2%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | local_cue_worst_species | Clematis ligusticifolia | 5/10 | 50.0% (23.7–76.3%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | local_cue_worst_species | Clematis lasiantha | 4/10 | 40.0% (16.8–68.7%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | local_cue_worst_species | Clematis terniflora | 3/10 | 30.0% (10.8–60.3%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | local_cue_worst_species | Scutellaria lateriflora | 3/10 | 30.0% (10.8–60.3%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | local_cue_worst_species | Smilax tamnoides | 3/10 | 30.0% (10.8–60.3%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | local_cue_worst_species | Acer negundo | 2/10 | 20.0% (5.7–51.0%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | local_cue_worst_species | Chionanthus virginicus | 2/10 | 20.0% (5.7–51.0%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | local_cue_worst_species | Clematis occidentalis | 2/10 | 20.0% (5.7–51.0%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | local_cue_worst_species | Endodeca serpentaria | 2/10 | 20.0% (5.7–51.0%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | local_cue_worst_species | Galinsoga parviflora | 2/10 | 20.0% (5.7–51.0%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | local_cue_worst_species | Thalictrum pubescens | 2/10 | 20.0% (5.7–51.0%) | — |
| target-false-alarms | inat2021-target-false-alarms | iNat2021 validation | validation | local_cue_worst_species | Actaea rubra | 1/10 | 10.0% (1.8–40.4%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top1_wrong_subject | all | 11/20503 | 0.1% (0.0–0.1%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top1_wrong_subject | lookalike | 0/20 | 0.0% (0.0–16.1%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top1_wrong_subject | same_genus | 8/214 | 3.7% (1.9–7.2%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top1_wrong_subject | same_family | 3/15269 | 0.0% (0.0–0.1%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top1_wrong_subject | other_plants | 0/5000 | 0.0% (0.0–0.1%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top1_worst_species | Ulex minor | 3/20 | 15.0% (5.2–36.0%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top1_worst_species | Clematis cirrhosa | 2/20 | 10.0% (2.8–30.1%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top1_worst_species | Bothriochloa barbinodis | 1/20 | 5.0% (0.9–23.6%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top1_worst_species | Clematis flammula | 1/20 | 5.0% (0.9–23.6%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top1_worst_species | Clematis orientalis | 1/20 | 5.0% (0.9–23.6%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top1_worst_species | Genista lobelii | 1/20 | 5.0% (0.9–23.6%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top1_worst_species | Thinopyrum acutum | 1/9 | 11.1% (2.0–43.5%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top1_worst_species | Ulex gallii | 1/20 | 5.0% (0.9–23.6%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_wrong_subject | all | 7568/20503 | 36.9% (36.3–37.6%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_wrong_subject | lookalike | 0/20 | 0.0% (0.0–16.1%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_wrong_subject | same_genus | 153/214 | 71.5% (65.1–77.1%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_wrong_subject | same_family | 4811/15269 | 31.5% (30.8–32.2%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_wrong_subject | other_plants | 2604/5000 | 52.1% (50.7–53.5%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_worst_species | Lamarckia aurea | 20/20 | 100.0% (83.9–100.0%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_worst_species | Pulsatilla vulgaris | 20/20 | 100.0% (83.9–100.0%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_worst_species | Actaea spicata | 19/20 | 95.0% (76.4–99.1%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_worst_species | Cenchrus longisetus | 19/20 | 95.0% (76.4–99.1%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_worst_species | Echinaria capitata | 19/20 | 95.0% (76.4–99.1%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_worst_species | Pulsatilla rubra | 19/20 | 95.0% (76.4–99.1%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_worst_species | Ranunculus ficaria | 19/20 | 95.0% (76.4–99.1%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_worst_species | Ranunculus macrophyllus | 19/20 | 95.0% (76.4–99.1%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_worst_species | Ulex gallii | 19/20 | 95.0% (76.4–99.1%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_worst_species | Ulex minor | 19/20 | 95.0% (76.4–99.1%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_worst_species | Adonis aestivalis | 18/20 | 90.0% (69.9–97.2%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_worst_species | Anemonoides nemorosa | 18/20 | 90.0% (69.9–97.2%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_worst_species | Avena sterilis | 18/20 | 90.0% (69.9–97.2%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_worst_species | Clematis alpina | 18/20 | 90.0% (69.9–97.2%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_worst_species | Lagurus ovatus | 18/20 | 90.0% (69.9–97.2%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_wrong_subject | all | 49/20503 | 0.2% (0.2–0.3%) | pass (≤ 1%) |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_wrong_subject | lookalike | 0/20 | 0.0% (0.0–16.1%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_wrong_subject | same_genus | 36/214 | 16.8% (12.4–22.4%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_wrong_subject | same_family | 13/15269 | 0.1% (0.0–0.1%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_wrong_subject | other_plants | 0/5000 | 0.0% (0.0–0.1%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_worst_species | Ulex minor | 11/20 | 55.0% (34.2–74.2%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_worst_species | Ulex parviflorus | 10/20 | 50.0% (29.9–70.1%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_worst_species | Ulex gallii | 9/20 | 45.0% (25.8–65.8%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_worst_species | Ampelodesmos mauritanicus | 2/20 | 10.0% (2.8–30.1%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_worst_species | Clematis flammula | 2/20 | 10.0% (2.8–30.1%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_worst_species | Clematis viticella | 2/20 | 10.0% (2.8–30.1%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_worst_species | Adenocarpus decorticans | 1/20 | 5.0% (0.9–23.6%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_worst_species | Bothriochloa barbinodis | 1/20 | 5.0% (0.9–23.6%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_worst_species | Clematis cirrhosa | 1/20 | 5.0% (0.9–23.6%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_worst_species | Clematis recta | 1/20 | 5.0% (0.9–23.6%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_worst_species | Cytisus fontanesii | 1/6 | 16.7% (3.0–56.4%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_worst_species | Echinospartum horridum | 1/20 | 5.0% (0.9–23.6%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_worst_species | Elymus caninus | 1/20 | 5.0% (0.9–23.6%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_worst_species | Genista hirsuta | 1/20 | 5.0% (0.9–23.6%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_worst_species | Genista hispanica | 1/20 | 5.0% (0.9–23.6%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_wrong_subject | all | 223/20503 | 1.1% (1.0–1.2%) | fail (≤ 1%) |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_wrong_subject | lookalike | 1/20 | 5.0% (0.9–23.6%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_wrong_subject | same_genus | 76/214 | 35.5% (29.4–42.1%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_wrong_subject | same_family | 112/15269 | 0.7% (0.6–0.9%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_wrong_subject | other_plants | 34/5000 | 0.7% (0.5–0.9%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_worst_species | Ulex gallii | 17/20 | 85.0% (64.0–94.8%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_worst_species | Ulex minor | 14/20 | 70.0% (48.1–85.5%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_worst_species | Ulex parviflorus | 13/20 | 65.0% (43.3–81.9%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_worst_species | Clematis recta | 10/20 | 50.0% (29.9–70.1%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_worst_species | Clematis alpina | 6/20 | 30.0% (14.5–51.9%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_worst_species | Echinospartum horridum | 6/20 | 30.0% (14.5–51.9%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_worst_species | Genista hispanica | 6/20 | 30.0% (14.5–51.9%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_worst_species | Cenchrus longisetus | 5/20 | 25.0% (11.2–46.9%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_worst_species | Clematis viticella | 5/20 | 25.0% (11.2–46.9%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_worst_species | Clematis orientalis | 4/20 | 20.0% (8.1–41.6%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_worst_species | Actaea spicata | 3/20 | 15.0% (5.2–36.0%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_worst_species | Cenchrus orientalis | 3/7 | 42.9% (15.8–75.0%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_worst_species | Cytisus balansae | 3/16 | 18.8% (6.6–43.0%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_worst_species | Genista scorpius | 3/20 | 15.0% (5.2–36.0%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_worst_species | Saccharum spontaneum | 3/20 | 15.0% (5.2–36.0%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top1_wrong_subject | val | 4/10624 | 0.0% (0.0–0.1%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top1_wrong_subject | val/lookalike | 0/10 | 0.0% (0.0–27.8%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top1_wrong_subject | val/same_genus | 3/114 | 2.6% (0.9–7.5%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top1_wrong_subject | val/same_family | 1/7916 | 0.0% (0.0–0.1%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top1_wrong_subject | val/other_plants | 0/2584 | 0.0% (0.0–0.1%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top1_worst_species | val/Clematis cirrhosa | 1/10 | 10.0% (1.8–40.4%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top1_worst_species | val/Clematis orientalis | 1/10 | 10.0% (1.8–40.4%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top1_worst_species | val/Genista lobelii | 1/10 | 10.0% (1.8–40.4%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top1_worst_species | val/Ulex gallii | 1/10 | 10.0% (1.8–40.4%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_wrong_subject | val | 3980/10624 | 37.5% (36.5–38.4%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_wrong_subject | val/lookalike | 0/10 | 0.0% (0.0–27.8%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_wrong_subject | val/same_genus | 85/114 | 74.6% (65.9–81.7%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_wrong_subject | val/same_family | 2553/7916 | 32.3% (31.2–33.3%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_wrong_subject | val/other_plants | 1342/2584 | 51.9% (50.0–53.9%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_worst_species | val/Actaea spicata | 10/10 | 100.0% (72.2–100.0%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_worst_species | val/Adonis aestivalis | 10/10 | 100.0% (72.2–100.0%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_worst_species | val/Adonis vernalis | 10/10 | 100.0% (72.2–100.0%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_worst_species | val/Avena sterilis | 10/10 | 100.0% (72.2–100.0%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_worst_species | val/Cenchrus clandestinus | 10/10 | 100.0% (72.2–100.0%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_worst_species | val/Cenchrus longisetus | 10/10 | 100.0% (72.2–100.0%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_worst_species | val/Clematis alpina | 10/10 | 100.0% (72.2–100.0%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_worst_species | val/Echinaria capitata | 10/10 | 100.0% (72.2–100.0%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_worst_species | val/Lamarckia aurea | 10/10 | 100.0% (72.2–100.0%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_worst_species | val/Pulsatilla montana | 10/10 | 100.0% (72.2–100.0%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_worst_species | val/Pulsatilla vulgaris | 10/10 | 100.0% (72.2–100.0%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_worst_species | val/Ulex gallii | 10/10 | 100.0% (72.2–100.0%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_worst_species | val/Ulex minor | 10/10 | 100.0% (72.2–100.0%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_worst_species | val/Ulex parviflorus | 10/10 | 100.0% (72.2–100.0%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_worst_species | val/Anemonoides nemorosa | 9/10 | 90.0% (59.6–98.2%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_wrong_subject | val | 24/10624 | 0.2% (0.2–0.3%) | pass (≤ 1%) |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_wrong_subject | val/lookalike | 0/10 | 0.0% (0.0–27.8%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_wrong_subject | val/same_genus | 18/114 | 15.8% (10.2–23.6%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_wrong_subject | val/same_family | 6/7916 | 0.1% (0.0–0.2%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_wrong_subject | val/other_plants | 0/2584 | 0.0% (0.0–0.1%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_worst_species | val/Ulex minor | 7/10 | 70.0% (39.7–89.2%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_worst_species | val/Ulex gallii | 5/10 | 50.0% (23.7–76.3%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_worst_species | val/Ulex parviflorus | 3/10 | 30.0% (10.8–60.3%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_worst_species | val/Ampelodesmos mauritanicus | 1/10 | 10.0% (1.8–40.4%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_worst_species | val/Clematis cirrhosa | 1/10 | 10.0% (1.8–40.4%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_worst_species | val/Clematis recta | 1/10 | 10.0% (1.8–40.4%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_worst_species | val/Clematis viticella | 1/10 | 10.0% (1.8–40.4%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_worst_species | val/Elymus caninus | 1/10 | 10.0% (1.8–40.4%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_worst_species | val/Genista hirsuta | 1/10 | 10.0% (1.8–40.4%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_worst_species | val/Genista hispanica | 1/10 | 10.0% (1.8–40.4%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_worst_species | val/Genista lobelii | 1/10 | 10.0% (1.8–40.4%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_worst_species | val/Genista provincialis | 1/1 | 100.0% (20.7–100.0%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_wrong_subject | val | 109/10624 | 1.0% (0.9–1.2%) | fail (≤ 1%) |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_wrong_subject | val/lookalike | 0/10 | 0.0% (0.0–27.8%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_wrong_subject | val/same_genus | 37/114 | 32.5% (24.6–41.5%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_wrong_subject | val/same_family | 56/7916 | 0.7% (0.5–0.9%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_wrong_subject | val/other_plants | 16/2584 | 0.6% (0.4–1.0%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_worst_species | val/Ulex gallii | 9/10 | 90.0% (59.6–98.2%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_worst_species | val/Ulex minor | 7/10 | 70.0% (39.7–89.2%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_worst_species | val/Ulex parviflorus | 7/10 | 70.0% (39.7–89.2%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_worst_species | val/Clematis recta | 6/10 | 60.0% (31.3–83.2%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_worst_species | val/Clematis viticella | 3/10 | 30.0% (10.8–60.3%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_worst_species | val/Genista hispanica | 3/10 | 30.0% (10.8–60.3%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_worst_species | val/Thalictrum aquilegiifolium | 3/10 | 30.0% (10.8–60.3%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_worst_species | val/Aconitum anthora | 2/10 | 20.0% (5.7–51.0%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_worst_species | val/Cenchrus longisetus | 2/10 | 20.0% (5.7–51.0%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_worst_species | val/Cenchrus orientalis | 2/4 | 50.0% (15.0–85.0%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_worst_species | val/Echinospartum horridum | 2/10 | 20.0% (5.7–51.0%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_worst_species | val/Eragrostis curvula | 2/10 | 20.0% (5.7–51.0%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_worst_species | val/Genista triacanthos | 2/10 | 20.0% (5.7–51.0%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_worst_species | val/Ulex argenteus | 2/5 | 40.0% (11.8–76.9%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_worst_species | val/Acacia retinodes | 1/10 | 10.0% (1.8–40.4%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top1_wrong_subject | test | 7/9879 | 0.1% (0.0–0.1%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top1_wrong_subject | test/lookalike | 0/10 | 0.0% (0.0–27.8%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top1_wrong_subject | test/same_genus | 5/100 | 5.0% (2.2–11.2%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top1_wrong_subject | test/same_family | 2/7353 | 0.0% (0.0–0.1%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top1_wrong_subject | test/other_plants | 0/2416 | 0.0% (0.0–0.2%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top1_worst_species | test/Ulex minor | 3/10 | 30.0% (10.8–60.3%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top1_worst_species | test/Bothriochloa barbinodis | 1/10 | 10.0% (1.8–40.4%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top1_worst_species | test/Clematis cirrhosa | 1/10 | 10.0% (1.8–40.4%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top1_worst_species | test/Clematis flammula | 1/10 | 10.0% (1.8–40.4%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | plantclef_top1_worst_species | test/Thinopyrum acutum | 1/4 | 25.0% (4.6–69.9%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_wrong_subject | test | 3588/9879 | 36.3% (35.4–37.3%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_wrong_subject | test/lookalike | 0/10 | 0.0% (0.0–27.8%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_wrong_subject | test/same_genus | 68/100 | 68.0% (58.3–76.3%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_wrong_subject | test/same_family | 2258/7353 | 30.7% (29.7–31.8%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_wrong_subject | test/other_plants | 1262/2416 | 52.2% (50.2–54.2%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_worst_species | test/Aquilegia vulgaris | 10/10 | 100.0% (72.2–100.0%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_worst_species | test/Lamarckia aurea | 10/10 | 100.0% (72.2–100.0%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_worst_species | test/Poa annua | 10/10 | 100.0% (72.2–100.0%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_worst_species | test/Pulsatilla rubra | 10/10 | 100.0% (72.2–100.0%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_worst_species | test/Pulsatilla vulgaris | 10/10 | 100.0% (72.2–100.0%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_worst_species | test/Ranunculus ficaria | 10/10 | 100.0% (72.2–100.0%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_worst_species | test/Ranunculus macrophyllus | 10/10 | 100.0% (72.2–100.0%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_worst_species | test/Ranunculus montanus | 10/10 | 100.0% (72.2–100.0%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_worst_species | test/Actaea spicata | 9/10 | 90.0% (59.6–98.2%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_worst_species | test/Anemonoides nemorosa | 9/10 | 90.0% (59.6–98.2%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_worst_species | test/Aquilegia atrata | 9/10 | 90.0% (59.6–98.2%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_worst_species | test/Bothriochloa barbinodis | 9/10 | 90.0% (59.6–98.2%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_worst_species | test/Cenchrus longisetus | 9/10 | 90.0% (59.6–98.2%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_worst_species | test/Cynosurus echinatus | 9/10 | 90.0% (59.6–98.2%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | bioclip_top1_worst_species | test/Echinaria capitata | 9/10 | 90.0% (59.6–98.2%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_wrong_subject | test | 25/9879 | 0.3% (0.2–0.4%) | pass (≤ 1%) |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_wrong_subject | test/lookalike | 0/10 | 0.0% (0.0–27.8%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_wrong_subject | test/same_genus | 18/100 | 18.0% (11.7–26.7%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_wrong_subject | test/same_family | 7/7353 | 0.1% (0.0–0.2%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_wrong_subject | test/other_plants | 0/2416 | 0.0% (0.0–0.2%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_worst_species | test/Ulex parviflorus | 7/10 | 70.0% (39.7–89.2%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_worst_species | test/Ulex gallii | 4/10 | 40.0% (16.8–68.7%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_worst_species | test/Ulex minor | 4/10 | 40.0% (16.8–68.7%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_worst_species | test/Clematis flammula | 2/10 | 20.0% (5.7–51.0%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_worst_species | test/Adenocarpus decorticans | 1/10 | 10.0% (1.8–40.4%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_worst_species | test/Ampelodesmos mauritanicus | 1/10 | 10.0% (1.8–40.4%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_worst_species | test/Bothriochloa barbinodis | 1/10 | 10.0% (1.8–40.4%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_worst_species | test/Clematis viticella | 1/10 | 10.0% (1.8–40.4%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_worst_species | test/Cytisus fontanesii | 1/2 | 50.0% (9.5–90.5%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_worst_species | test/Echinospartum horridum | 1/10 | 10.0% (1.8–40.4%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_worst_species | test/Saccharum spontaneum | 1/10 | 10.0% (1.8–40.4%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | pilot_cue_worst_species | test/Thinopyrum acutum | 1/4 | 25.0% (4.6–69.9%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_wrong_subject | test | 114/9879 | 1.2% (1.0–1.4%) | fail (≤ 1%) |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_wrong_subject | test/lookalike | 1/10 | 10.0% (1.8–40.4%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_wrong_subject | test/same_genus | 39/100 | 39.0% (30.0–48.8%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_wrong_subject | test/same_family | 56/7353 | 0.8% (0.6–1.0%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_wrong_subject | test/other_plants | 18/2416 | 0.7% (0.5–1.2%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_worst_species | test/Ulex gallii | 8/10 | 80.0% (49.0–94.3%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_worst_species | test/Ulex minor | 7/10 | 70.0% (39.7–89.2%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_worst_species | test/Ulex parviflorus | 6/10 | 60.0% (31.3–83.2%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_worst_species | test/Clematis alpina | 5/10 | 50.0% (23.7–76.3%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_worst_species | test/Clematis recta | 4/10 | 40.0% (16.8–68.7%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_worst_species | test/Echinospartum horridum | 4/10 | 40.0% (16.8–68.7%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_worst_species | test/Cenchrus longisetus | 3/10 | 30.0% (10.8–60.3%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_worst_species | test/Clematis orientalis | 3/10 | 30.0% (10.8–60.3%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_worst_species | test/Cytisus balansae | 3/8 | 37.5% (13.7–69.4%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_worst_species | test/Genista hispanica | 3/10 | 30.0% (10.8–60.3%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_worst_species | test/Actaea spicata | 2/10 | 20.0% (5.7–51.0%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_worst_species | test/Clematis flammula | 2/10 | 20.0% (5.7–51.0%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_worst_species | test/Clematis viticella | 2/10 | 20.0% (5.7–51.0%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_worst_species | test/Genista scorpius | 2/10 | 20.0% (5.7–51.0%) | — |
| target-false-alarms | plantclef2024-target-false-alarms | PlantCLEF 2024 single-plant publisher val/test | validation | local_cue_worst_species | test/Saccharum spontaneum | 2/10 | 20.0% (5.7–51.0%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | released_cutoffs_recall | all | 642/778 | 82.5% (79.7–85.0%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | released_cutoffs_recall | all/Solidago | 192/238 | 80.7% (75.2–85.2%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | released_cutoffs_recall | all/Cytisus scoparius | 114/125 | 91.2% (84.9–95.0%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | released_cutoffs_recall | all/Rosa rugosa | 159/171 | 93.0% (88.1–95.9%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | released_cutoffs_recall | all/Lupinus polyphyllus | 60/83 | 72.3% (61.8–80.8%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | released_cutoffs_recall | all/Pastinaca sativa | 60/97 | 61.9% (51.9–70.9%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | released_cutoffs_recall | all/Reynoutria | 57/64 | 89.1% (79.1–94.6%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | released_cutoffs_recall | all/watchlist | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | released_cutoffs_recall | all/lookalikes | 114/125 | 91.2% (84.9–95.0%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | released_cutoffs_recall | test/all | 475/577 | 82.3% (79.0–85.2%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | released_cutoffs_recall | test/Solidago | 180/223 | 80.7% (75.0–85.4%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | released_cutoffs_recall | test/Cytisus scoparius | 73/79 | 92.4% (84.4–96.5%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | released_cutoffs_recall | test/Rosa rugosa | 121/127 | 95.3% (90.1–97.8%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | released_cutoffs_recall | test/Lupinus polyphyllus | 21/32 | 65.6% (48.3–79.6%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | released_cutoffs_recall | test/Pastinaca sativa | 29/59 | 49.2% (36.8–61.6%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | released_cutoffs_recall | test/Reynoutria | 51/57 | 89.5% (78.9–95.1%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | released_cutoffs_recall | test/watchlist | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | released_cutoffs_recall | test/lookalikes | 73/79 | 92.4% (84.4–96.5%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | released_cutoffs_recall | test/distance-filtered/all | 386/468 | 82.5% (78.8–85.7%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | released_cutoffs_recall | test/distance-filtered/Solidago | 140/182 | 76.9% (70.3–82.4%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | released_cutoffs_recall | test/distance-filtered/Cytisus scoparius | 61/67 | 91.0% (81.8–95.8%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | released_cutoffs_recall | test/distance-filtered/Rosa rugosa | 96/101 | 95.0% (88.9–97.9%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | released_cutoffs_recall | test/distance-filtered/Lupinus polyphyllus | 19/25 | 76.0% (56.6–88.5%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | released_cutoffs_recall | test/distance-filtered/Pastinaca sativa | 22/41 | 53.7% (38.7–67.9%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | released_cutoffs_recall | test/distance-filtered/Reynoutria | 48/52 | 92.3% (81.8–97.0%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | released_cutoffs_recall | test/distance-filtered/watchlist | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | released_cutoffs_recall | test/distance-filtered/lookalikes | 61/67 | 91.0% (81.8–95.8%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | released_cutoffs_recall | multilabel/all | 167/201 | 83.1% (77.3–87.6%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | released_cutoffs_recall | multilabel/Solidago | 12/15 | 80.0% (54.8–93.0%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | released_cutoffs_recall | multilabel/Cytisus scoparius | 41/46 | 89.1% (77.0–95.3%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | released_cutoffs_recall | multilabel/Rosa rugosa | 38/44 | 86.4% (73.3–93.6%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | released_cutoffs_recall | multilabel/Lupinus polyphyllus | 39/51 | 76.5% (63.2–86.0%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | released_cutoffs_recall | multilabel/Pastinaca sativa | 31/38 | 81.6% (66.6–90.8%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | released_cutoffs_recall | multilabel/Reynoutria | 6/7 | 85.7% (48.7–97.4%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | released_cutoffs_recall | multilabel/watchlist | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | released_cutoffs_recall | multilabel/lookalikes | 41/46 | 89.1% (77.0–95.3%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | released_cutoffs_recall | multilabel/distance-filtered/all | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | released_cutoffs_recall | multilabel/distance-filtered/Solidago | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | released_cutoffs_recall | multilabel/distance-filtered/Cytisus scoparius | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | released_cutoffs_recall | multilabel/distance-filtered/Rosa rugosa | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | released_cutoffs_recall | multilabel/distance-filtered/Lupinus polyphyllus | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | released_cutoffs_recall | multilabel/distance-filtered/Pastinaca sativa | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | released_cutoffs_recall | multilabel/distance-filtered/Reynoutria | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | released_cutoffs_recall | multilabel/distance-filtered/watchlist | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | released_cutoffs_recall | multilabel/distance-filtered/lookalikes | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top1_recall | all | 189/778 | 24.3% (21.4–27.4%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top1_recall | all/Solidago | 122/238 | 51.3% (44.9–57.5%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top1_recall | all/Cytisus scoparius | 0/125 | 0.0% (0.0–3.0%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top1_recall | all/Rosa rugosa | 3/171 | 1.8% (0.6–5.0%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top1_recall | all/Lupinus polyphyllus | 0/83 | 0.0% (0.0–4.4%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top1_recall | all/Pastinaca sativa | 0/97 | 0.0% (0.0–3.8%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top1_recall | all/Reynoutria | 64/64 | 100.0% (94.3–100.0%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top1_recall | all/watchlist | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top1_recall | all/lookalikes | 0/125 | 0.0% (0.0–3.0%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top1_recall | test/all | 180/577 | 31.2% (27.6–35.1%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top1_recall | test/Solidago | 121/223 | 54.3% (47.7–60.7%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top1_recall | test/Cytisus scoparius | 0/79 | 0.0% (0.0–4.6%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top1_recall | test/Rosa rugosa | 2/127 | 1.6% (0.4–5.6%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top1_recall | test/Lupinus polyphyllus | 0/32 | 0.0% (0.0–10.7%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top1_recall | test/Pastinaca sativa | 0/59 | 0.0% (0.0–6.1%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top1_recall | test/Reynoutria | 57/57 | 100.0% (93.7–100.0%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top1_recall | test/watchlist | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top1_recall | test/lookalikes | 0/79 | 0.0% (0.0–4.6%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top1_recall | test/distance-filtered/all | 145/468 | 31.0% (27.0–35.3%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top1_recall | test/distance-filtered/Solidago | 92/182 | 50.5% (43.3–57.7%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top1_recall | test/distance-filtered/Cytisus scoparius | 0/67 | 0.0% (0.0–5.4%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top1_recall | test/distance-filtered/Rosa rugosa | 1/101 | 1.0% (0.2–5.4%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top1_recall | test/distance-filtered/Lupinus polyphyllus | 0/25 | 0.0% (0.0–13.3%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top1_recall | test/distance-filtered/Pastinaca sativa | 0/41 | 0.0% (0.0–8.6%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top1_recall | test/distance-filtered/Reynoutria | 52/52 | 100.0% (93.1–100.0%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top1_recall | test/distance-filtered/watchlist | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top1_recall | test/distance-filtered/lookalikes | 0/67 | 0.0% (0.0–5.4%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top1_recall | multilabel/all | 9/201 | 4.5% (2.4–8.3%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top1_recall | multilabel/Solidago | 1/15 | 6.7% (1.2–29.8%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top1_recall | multilabel/Cytisus scoparius | 0/46 | 0.0% (0.0–7.7%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top1_recall | multilabel/Rosa rugosa | 1/44 | 2.3% (0.4–11.8%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top1_recall | multilabel/Lupinus polyphyllus | 0/51 | 0.0% (0.0–7.0%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top1_recall | multilabel/Pastinaca sativa | 0/38 | 0.0% (0.0–9.2%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top1_recall | multilabel/Reynoutria | 7/7 | 100.0% (64.6–100.0%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top1_recall | multilabel/watchlist | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top1_recall | multilabel/lookalikes | 0/46 | 0.0% (0.0–7.7%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top1_recall | multilabel/distance-filtered/all | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top1_recall | multilabel/distance-filtered/Solidago | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top1_recall | multilabel/distance-filtered/Cytisus scoparius | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top1_recall | multilabel/distance-filtered/Rosa rugosa | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top1_recall | multilabel/distance-filtered/Lupinus polyphyllus | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top1_recall | multilabel/distance-filtered/Pastinaca sativa | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top1_recall | multilabel/distance-filtered/Reynoutria | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top1_recall | multilabel/distance-filtered/watchlist | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top1_recall | multilabel/distance-filtered/lookalikes | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top3_recall | all | 656/778 | 84.3% (81.6–86.7%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top3_recall | all/Solidago | 238/238 | 100.0% (98.4–100.0%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top3_recall | all/Cytisus scoparius | 85/125 | 68.0% (59.4–75.5%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top3_recall | all/Rosa rugosa | 154/171 | 90.1% (84.7–93.7%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top3_recall | all/Lupinus polyphyllus | 40/83 | 48.2% (37.8–58.8%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top3_recall | all/Pastinaca sativa | 75/97 | 77.3% (68.0–84.5%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top3_recall | all/Reynoutria | 64/64 | 100.0% (94.3–100.0%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top3_recall | all/watchlist | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top3_recall | all/lookalikes | 85/125 | 68.0% (59.4–75.5%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top3_recall | test/all | 543/577 | 94.1% (91.9–95.8%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top3_recall | test/Solidago | 223/223 | 100.0% (98.3–100.0%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top3_recall | test/Cytisus scoparius | 70/79 | 88.6% (79.7–93.9%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top3_recall | test/Rosa rugosa | 123/127 | 96.9% (92.2–98.8%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top3_recall | test/Lupinus polyphyllus | 20/32 | 62.5% (45.3–77.1%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top3_recall | test/Pastinaca sativa | 50/59 | 84.7% (73.5–91.8%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top3_recall | test/Reynoutria | 57/57 | 100.0% (93.7–100.0%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top3_recall | test/watchlist | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top3_recall | test/lookalikes | 70/79 | 88.6% (79.7–93.9%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top3_recall | test/distance-filtered/all | 443/468 | 94.7% (92.2–96.4%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top3_recall | test/distance-filtered/Solidago | 182/182 | 100.0% (97.9–100.0%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top3_recall | test/distance-filtered/Cytisus scoparius | 58/67 | 86.6% (76.4–92.8%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top3_recall | test/distance-filtered/Rosa rugosa | 97/101 | 96.0% (90.3–98.4%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top3_recall | test/distance-filtered/Lupinus polyphyllus | 19/25 | 76.0% (56.6–88.5%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top3_recall | test/distance-filtered/Pastinaca sativa | 35/41 | 85.4% (71.6–93.1%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top3_recall | test/distance-filtered/Reynoutria | 52/52 | 100.0% (93.1–100.0%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top3_recall | test/distance-filtered/watchlist | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top3_recall | test/distance-filtered/lookalikes | 58/67 | 86.6% (76.4–92.8%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top3_recall | multilabel/all | 113/201 | 56.2% (49.3–62.9%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top3_recall | multilabel/Solidago | 15/15 | 100.0% (79.6–100.0%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top3_recall | multilabel/Cytisus scoparius | 15/46 | 32.6% (20.9–47.0%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top3_recall | multilabel/Rosa rugosa | 31/44 | 70.5% (55.8–81.8%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top3_recall | multilabel/Lupinus polyphyllus | 20/51 | 39.2% (27.0–52.9%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top3_recall | multilabel/Pastinaca sativa | 25/38 | 65.8% (49.9–78.8%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top3_recall | multilabel/Reynoutria | 7/7 | 100.0% (64.6–100.0%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top3_recall | multilabel/watchlist | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top3_recall | multilabel/lookalikes | 15/46 | 32.6% (20.9–47.0%) | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top3_recall | multilabel/distance-filtered/all | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top3_recall | multilabel/distance-filtered/Solidago | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top3_recall | multilabel/distance-filtered/Cytisus scoparius | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top3_recall | multilabel/distance-filtered/Rosa rugosa | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top3_recall | multilabel/distance-filtered/Lupinus polyphyllus | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top3_recall | multilabel/distance-filtered/Pastinaca sativa | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top3_recall | multilabel/distance-filtered/Reynoutria | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top3_recall | multilabel/distance-filtered/watchlist | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-publisher-baseline | danish-roadside | held-out | six_group_top3_recall | multilabel/distance-filtered/lookalikes | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | frame_top5_recall | all | 48/778 | 6.2% (4.7–8.1%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | frame_top5_recall | all/Solidago | 1/238 | 0.4% (0.1–2.3%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | frame_top5_recall | all/Cytisus scoparius | 0/125 | 0.0% (0.0–3.0%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | frame_top5_recall | all/Rosa rugosa | 20/171 | 11.7% (7.7–17.4%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | frame_top5_recall | all/Lupinus polyphyllus | 1/83 | 1.2% (0.2–6.5%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | frame_top5_recall | all/Pastinaca sativa | 0/97 | 0.0% (0.0–3.8%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | frame_top5_recall | all/Reynoutria | 26/64 | 40.6% (29.5–52.9%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | frame_top5_recall | all/watchlist | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | frame_top5_recall | all/lookalikes | 0/125 | 0.0% (0.0–3.0%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | frame_top5_recall | test/all | 45/577 | 7.8% (5.9–10.3%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | frame_top5_recall | test/Solidago | 0/223 | 0.0% (0.0–1.7%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | frame_top5_recall | test/Cytisus scoparius | 0/79 | 0.0% (0.0–4.6%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | frame_top5_recall | test/Rosa rugosa | 19/127 | 15.0% (9.8–22.2%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | frame_top5_recall | test/Lupinus polyphyllus | 0/32 | 0.0% (0.0–10.7%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | frame_top5_recall | test/Pastinaca sativa | 0/59 | 0.0% (0.0–6.1%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | frame_top5_recall | test/Reynoutria | 26/57 | 45.6% (33.4–58.4%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | frame_top5_recall | test/watchlist | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | frame_top5_recall | test/lookalikes | 0/79 | 0.0% (0.0–4.6%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | frame_top5_recall | test/distance-filtered/all | 44/468 | 9.4% (7.1–12.4%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | frame_top5_recall | test/distance-filtered/Solidago | 0/182 | 0.0% (0.0–2.1%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | frame_top5_recall | test/distance-filtered/Cytisus scoparius | 0/67 | 0.0% (0.0–5.4%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | frame_top5_recall | test/distance-filtered/Rosa rugosa | 18/101 | 17.8% (11.6–26.4%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | frame_top5_recall | test/distance-filtered/Lupinus polyphyllus | 0/25 | 0.0% (0.0–13.3%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | frame_top5_recall | test/distance-filtered/Pastinaca sativa | 0/41 | 0.0% (0.0–8.6%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | frame_top5_recall | test/distance-filtered/Reynoutria | 26/52 | 50.0% (36.9–63.1%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | frame_top5_recall | test/distance-filtered/watchlist | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | frame_top5_recall | test/distance-filtered/lookalikes | 0/67 | 0.0% (0.0–5.4%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | frame_top5_recall | multilabel/all | 3/201 | 1.5% (0.5–4.3%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | frame_top5_recall | multilabel/Solidago | 1/15 | 6.7% (1.2–29.8%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | frame_top5_recall | multilabel/Cytisus scoparius | 0/46 | 0.0% (0.0–7.7%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | frame_top5_recall | multilabel/Rosa rugosa | 1/44 | 2.3% (0.4–11.8%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | frame_top5_recall | multilabel/Lupinus polyphyllus | 1/51 | 2.0% (0.3–10.3%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | frame_top5_recall | multilabel/Pastinaca sativa | 0/38 | 0.0% (0.0–9.2%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | frame_top5_recall | multilabel/Reynoutria | 0/7 | 0.0% (0.0–35.4%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | frame_top5_recall | multilabel/watchlist | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | frame_top5_recall | multilabel/lookalikes | 0/46 | 0.0% (0.0–7.7%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | frame_top5_recall | multilabel/distance-filtered/all | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | frame_top5_recall | multilabel/distance-filtered/Solidago | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | frame_top5_recall | multilabel/distance-filtered/Cytisus scoparius | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | frame_top5_recall | multilabel/distance-filtered/Rosa rugosa | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | frame_top5_recall | multilabel/distance-filtered/Lupinus polyphyllus | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | frame_top5_recall | multilabel/distance-filtered/Pastinaca sativa | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | frame_top5_recall | multilabel/distance-filtered/Reynoutria | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | frame_top5_recall | multilabel/distance-filtered/watchlist | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | frame_top5_recall | multilabel/distance-filtered/lookalikes | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | tiles_top5_recall | all | 82/778 | 10.5% (8.6–12.9%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | tiles_top5_recall | all/Solidago | 0/238 | 0.0% (0.0–1.6%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | tiles_top5_recall | all/Cytisus scoparius | 1/125 | 0.8% (0.1–4.4%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | tiles_top5_recall | all/Rosa rugosa | 43/171 | 25.1% (19.2–32.1%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | tiles_top5_recall | all/Lupinus polyphyllus | 2/83 | 2.4% (0.7–8.4%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | tiles_top5_recall | all/Pastinaca sativa | 2/97 | 2.1% (0.6–7.2%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | tiles_top5_recall | all/Reynoutria | 34/64 | 53.1% (41.1–64.8%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | tiles_top5_recall | all/watchlist | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | tiles_top5_recall | all/lookalikes | 1/125 | 0.8% (0.1–4.4%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | tiles_top5_recall | test/all | 76/577 | 13.2% (10.7–16.2%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | tiles_top5_recall | test/Solidago | 0/223 | 0.0% (0.0–1.7%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | tiles_top5_recall | test/Cytisus scoparius | 1/79 | 1.3% (0.2–6.8%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | tiles_top5_recall | test/Rosa rugosa | 40/127 | 31.5% (24.1–40.0%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | tiles_top5_recall | test/Lupinus polyphyllus | 0/32 | 0.0% (0.0–10.7%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | tiles_top5_recall | test/Pastinaca sativa | 1/59 | 1.7% (0.3–9.0%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | tiles_top5_recall | test/Reynoutria | 34/57 | 59.6% (46.7–71.4%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | tiles_top5_recall | test/watchlist | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | tiles_top5_recall | test/lookalikes | 1/79 | 1.3% (0.2–6.8%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | tiles_top5_recall | test/distance-filtered/all | 74/468 | 15.8% (12.8–19.4%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | tiles_top5_recall | test/distance-filtered/Solidago | 0/182 | 0.0% (0.0–2.1%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | tiles_top5_recall | test/distance-filtered/Cytisus scoparius | 1/67 | 1.5% (0.3–8.0%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | tiles_top5_recall | test/distance-filtered/Rosa rugosa | 38/101 | 37.6% (28.8–47.4%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | tiles_top5_recall | test/distance-filtered/Lupinus polyphyllus | 0/25 | 0.0% (0.0–13.3%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | tiles_top5_recall | test/distance-filtered/Pastinaca sativa | 1/41 | 2.4% (0.4–12.6%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | tiles_top5_recall | test/distance-filtered/Reynoutria | 34/52 | 65.4% (51.8–76.8%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | tiles_top5_recall | test/distance-filtered/watchlist | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | tiles_top5_recall | test/distance-filtered/lookalikes | 1/67 | 1.5% (0.3–8.0%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | tiles_top5_recall | multilabel/all | 6/201 | 3.0% (1.4–6.4%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | tiles_top5_recall | multilabel/Solidago | 0/15 | 0.0% (0.0–20.4%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | tiles_top5_recall | multilabel/Cytisus scoparius | 0/46 | 0.0% (0.0–7.7%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | tiles_top5_recall | multilabel/Rosa rugosa | 3/44 | 6.8% (2.3–18.2%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | tiles_top5_recall | multilabel/Lupinus polyphyllus | 2/51 | 3.9% (1.1–13.2%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | tiles_top5_recall | multilabel/Pastinaca sativa | 1/38 | 2.6% (0.5–13.5%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | tiles_top5_recall | multilabel/Reynoutria | 0/7 | 0.0% (0.0–35.4%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | tiles_top5_recall | multilabel/watchlist | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | tiles_top5_recall | multilabel/lookalikes | 0/46 | 0.0% (0.0–7.7%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | tiles_top5_recall | multilabel/distance-filtered/all | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | tiles_top5_recall | multilabel/distance-filtered/Solidago | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | tiles_top5_recall | multilabel/distance-filtered/Cytisus scoparius | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | tiles_top5_recall | multilabel/distance-filtered/Rosa rugosa | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | tiles_top5_recall | multilabel/distance-filtered/Lupinus polyphyllus | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | tiles_top5_recall | multilabel/distance-filtered/Pastinaca sativa | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | tiles_top5_recall | multilabel/distance-filtered/Reynoutria | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | tiles_top5_recall | multilabel/distance-filtered/watchlist | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | tiles_top5_recall | multilabel/distance-filtered/lookalikes | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | grid_top5_recall | all | 122/778 | 15.7% (13.3–18.4%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | grid_top5_recall | all/Solidago | 4/238 | 1.7% (0.7–4.2%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | grid_top5_recall | all/Cytisus scoparius | 2/125 | 1.6% (0.4–5.6%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | grid_top5_recall | all/Rosa rugosa | 74/171 | 43.3% (36.1–50.8%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | grid_top5_recall | all/Lupinus polyphyllus | 2/83 | 2.4% (0.7–8.4%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | grid_top5_recall | all/Pastinaca sativa | 1/97 | 1.0% (0.2–5.6%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | grid_top5_recall | all/Reynoutria | 39/64 | 60.9% (48.7–71.9%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | grid_top5_recall | all/watchlist | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | grid_top5_recall | all/lookalikes | 2/125 | 1.6% (0.4–5.6%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | grid_top5_recall | test/all | 111/577 | 19.2% (16.2–22.7%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | grid_top5_recall | test/Solidago | 4/223 | 1.8% (0.7–4.5%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | grid_top5_recall | test/Cytisus scoparius | 2/79 | 2.5% (0.7–8.8%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | grid_top5_recall | test/Rosa rugosa | 65/127 | 51.2% (42.6–59.7%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | grid_top5_recall | test/Lupinus polyphyllus | 0/32 | 0.0% (0.0–10.7%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | grid_top5_recall | test/Pastinaca sativa | 1/59 | 1.7% (0.3–9.0%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | grid_top5_recall | test/Reynoutria | 39/57 | 68.4% (55.5–79.0%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | grid_top5_recall | test/watchlist | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | grid_top5_recall | test/lookalikes | 2/79 | 2.5% (0.7–8.8%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | grid_top5_recall | test/distance-filtered/all | 92/468 | 19.7% (16.3–23.5%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | grid_top5_recall | test/distance-filtered/Solidago | 1/182 | 0.5% (0.1–3.0%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | grid_top5_recall | test/distance-filtered/Cytisus scoparius | 1/67 | 1.5% (0.3–8.0%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | grid_top5_recall | test/distance-filtered/Rosa rugosa | 53/101 | 52.5% (42.8–61.9%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | grid_top5_recall | test/distance-filtered/Lupinus polyphyllus | 0/25 | 0.0% (0.0–13.3%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | grid_top5_recall | test/distance-filtered/Pastinaca sativa | 1/41 | 2.4% (0.4–12.6%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | grid_top5_recall | test/distance-filtered/Reynoutria | 36/52 | 69.2% (55.7–80.1%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | grid_top5_recall | test/distance-filtered/watchlist | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | grid_top5_recall | test/distance-filtered/lookalikes | 1/67 | 1.5% (0.3–8.0%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | grid_top5_recall | multilabel/all | 11/201 | 5.5% (3.1–9.5%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | grid_top5_recall | multilabel/Solidago | 0/15 | 0.0% (0.0–20.4%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | grid_top5_recall | multilabel/Cytisus scoparius | 0/46 | 0.0% (0.0–7.7%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | grid_top5_recall | multilabel/Rosa rugosa | 9/44 | 20.5% (11.2–34.5%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | grid_top5_recall | multilabel/Lupinus polyphyllus | 2/51 | 3.9% (1.1–13.2%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | grid_top5_recall | multilabel/Pastinaca sativa | 0/38 | 0.0% (0.0–9.2%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | grid_top5_recall | multilabel/Reynoutria | 0/7 | 0.0% (0.0–35.4%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | grid_top5_recall | multilabel/watchlist | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | grid_top5_recall | multilabel/lookalikes | 0/46 | 0.0% (0.0–7.7%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | grid_top5_recall | multilabel/distance-filtered/all | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | grid_top5_recall | multilabel/distance-filtered/Solidago | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | grid_top5_recall | multilabel/distance-filtered/Cytisus scoparius | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | grid_top5_recall | multilabel/distance-filtered/Rosa rugosa | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | grid_top5_recall | multilabel/distance-filtered/Lupinus polyphyllus | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | grid_top5_recall | multilabel/distance-filtered/Pastinaca sativa | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | grid_top5_recall | multilabel/distance-filtered/Reynoutria | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | grid_top5_recall | multilabel/distance-filtered/watchlist | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | grid_top5_recall | multilabel/distance-filtered/lookalikes | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top1_recall | all | 398/778 | 51.2% (47.6–54.7%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top1_recall | all/Solidago | 160/238 | 67.2% (61.0–72.9%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top1_recall | all/Cytisus scoparius | 27/125 | 21.6% (15.3–29.6%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top1_recall | all/Rosa rugosa | 74/171 | 43.3% (36.1–50.8%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top1_recall | all/Lupinus polyphyllus | 38/83 | 45.8% (35.5–56.4%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top1_recall | all/Pastinaca sativa | 46/97 | 47.4% (37.8–57.3%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top1_recall | all/Reynoutria | 53/64 | 82.8% (71.8–90.1%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top1_recall | all/watchlist | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top1_recall | all/lookalikes | 27/125 | 21.6% (15.3–29.6%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top1_recall | test/all | 334/577 | 57.9% (53.8–61.8%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top1_recall | test/Solidago | 153/223 | 68.6% (62.2–74.3%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top1_recall | test/Cytisus scoparius | 19/79 | 24.1% (16.0–34.5%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top1_recall | test/Rosa rugosa | 65/127 | 51.2% (42.6–59.7%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top1_recall | test/Lupinus polyphyllus | 13/32 | 40.6% (25.5–57.7%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top1_recall | test/Pastinaca sativa | 33/59 | 55.9% (43.3–67.8%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top1_recall | test/Reynoutria | 51/57 | 89.5% (78.9–95.1%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top1_recall | test/watchlist | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top1_recall | test/lookalikes | 19/79 | 24.1% (16.0–34.5%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top1_recall | test/distance-filtered/all | 269/468 | 57.5% (53.0–61.9%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top1_recall | test/distance-filtered/Solidago | 127/182 | 69.8% (62.8–76.0%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top1_recall | test/distance-filtered/Cytisus scoparius | 17/67 | 25.4% (16.5–36.9%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top1_recall | test/distance-filtered/Rosa rugosa | 51/101 | 50.5% (40.9–60.0%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top1_recall | test/distance-filtered/Lupinus polyphyllus | 7/25 | 28.0% (14.3–47.6%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top1_recall | test/distance-filtered/Pastinaca sativa | 21/41 | 51.2% (36.5–65.7%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top1_recall | test/distance-filtered/Reynoutria | 46/52 | 88.5% (77.0–94.6%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top1_recall | test/distance-filtered/watchlist | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top1_recall | test/distance-filtered/lookalikes | 17/67 | 25.4% (16.5–36.9%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top1_recall | multilabel/all | 64/201 | 31.8% (25.8–38.6%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top1_recall | multilabel/Solidago | 7/15 | 46.7% (24.8–69.9%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top1_recall | multilabel/Cytisus scoparius | 8/46 | 17.4% (9.1–30.7%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top1_recall | multilabel/Rosa rugosa | 9/44 | 20.5% (11.2–34.5%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top1_recall | multilabel/Lupinus polyphyllus | 25/51 | 49.0% (35.9–62.3%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top1_recall | multilabel/Pastinaca sativa | 13/38 | 34.2% (21.2–50.1%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top1_recall | multilabel/Reynoutria | 2/7 | 28.6% (8.2–64.1%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top1_recall | multilabel/watchlist | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top1_recall | multilabel/lookalikes | 8/46 | 17.4% (9.1–30.7%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top1_recall | multilabel/distance-filtered/all | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top1_recall | multilabel/distance-filtered/Solidago | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top1_recall | multilabel/distance-filtered/Cytisus scoparius | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top1_recall | multilabel/distance-filtered/Rosa rugosa | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top1_recall | multilabel/distance-filtered/Lupinus polyphyllus | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top1_recall | multilabel/distance-filtered/Pastinaca sativa | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top1_recall | multilabel/distance-filtered/Reynoutria | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top1_recall | multilabel/distance-filtered/watchlist | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top1_recall | multilabel/distance-filtered/lookalikes | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top3_recall | all | 599/778 | 77.0% (73.9–79.8%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top3_recall | all/Solidago | 232/238 | 97.5% (94.6–98.8%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top3_recall | all/Cytisus scoparius | 61/125 | 48.8% (40.2–57.5%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top3_recall | all/Rosa rugosa | 102/171 | 59.6% (52.2–66.7%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top3_recall | all/Lupinus polyphyllus | 61/83 | 73.5% (63.1–81.8%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top3_recall | all/Pastinaca sativa | 80/97 | 82.5% (73.7–88.8%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top3_recall | all/Reynoutria | 63/64 | 98.4% (91.7–99.7%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top3_recall | all/watchlist | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top3_recall | all/lookalikes | 61/125 | 48.8% (40.2–57.5%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top3_recall | test/all | 475/577 | 82.3% (79.0–85.2%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top3_recall | test/Solidago | 220/223 | 98.7% (96.1–99.5%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top3_recall | test/Cytisus scoparius | 41/79 | 51.9% (41.1–62.6%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top3_recall | test/Rosa rugosa | 83/127 | 65.4% (56.7–73.1%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top3_recall | test/Lupinus polyphyllus | 24/32 | 75.0% (57.9–86.7%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top3_recall | test/Pastinaca sativa | 50/59 | 84.7% (73.5–91.8%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top3_recall | test/Reynoutria | 57/57 | 100.0% (93.7–100.0%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top3_recall | test/watchlist | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top3_recall | test/lookalikes | 41/79 | 51.9% (41.1–62.6%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top3_recall | test/distance-filtered/all | 381/468 | 81.4% (77.6–84.7%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top3_recall | test/distance-filtered/Solidago | 179/182 | 98.4% (95.3–99.4%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top3_recall | test/distance-filtered/Cytisus scoparius | 35/67 | 52.2% (40.5–63.7%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top3_recall | test/distance-filtered/Rosa rugosa | 66/101 | 65.3% (55.7–73.9%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top3_recall | test/distance-filtered/Lupinus polyphyllus | 17/25 | 68.0% (48.4–82.8%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top3_recall | test/distance-filtered/Pastinaca sativa | 32/41 | 78.0% (63.3–88.0%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top3_recall | test/distance-filtered/Reynoutria | 52/52 | 100.0% (93.1–100.0%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top3_recall | test/distance-filtered/watchlist | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top3_recall | test/distance-filtered/lookalikes | 35/67 | 52.2% (40.5–63.7%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top3_recall | multilabel/all | 124/201 | 61.7% (54.8–68.1%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top3_recall | multilabel/Solidago | 12/15 | 80.0% (54.8–93.0%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top3_recall | multilabel/Cytisus scoparius | 20/46 | 43.5% (30.2–57.8%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top3_recall | multilabel/Rosa rugosa | 19/44 | 43.2% (29.7–57.8%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top3_recall | multilabel/Lupinus polyphyllus | 37/51 | 72.5% (59.1–82.9%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top3_recall | multilabel/Pastinaca sativa | 30/38 | 78.9% (63.7–88.9%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top3_recall | multilabel/Reynoutria | 6/7 | 85.7% (48.7–97.4%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top3_recall | multilabel/watchlist | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top3_recall | multilabel/lookalikes | 20/46 | 43.5% (30.2–57.8%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top3_recall | multilabel/distance-filtered/all | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top3_recall | multilabel/distance-filtered/Solidago | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top3_recall | multilabel/distance-filtered/Cytisus scoparius | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top3_recall | multilabel/distance-filtered/Rosa rugosa | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top3_recall | multilabel/distance-filtered/Lupinus polyphyllus | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top3_recall | multilabel/distance-filtered/Pastinaca sativa | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top3_recall | multilabel/distance-filtered/Reynoutria | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top3_recall | multilabel/distance-filtered/watchlist | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_whole_top3_recall | multilabel/distance-filtered/lookalikes | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top1_recall | all | 562/778 | 72.2% (69.0–75.3%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top1_recall | all/Solidago | 192/238 | 80.7% (75.2–85.2%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top1_recall | all/Cytisus scoparius | 77/125 | 61.6% (52.8–69.7%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top1_recall | all/Rosa rugosa | 145/171 | 84.8% (78.7–89.4%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top1_recall | all/Lupinus polyphyllus | 45/83 | 54.2% (43.6–64.5%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top1_recall | all/Pastinaca sativa | 50/97 | 51.5% (41.7–61.2%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top1_recall | all/Reynoutria | 53/64 | 82.8% (71.8–90.1%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top1_recall | all/watchlist | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top1_recall | all/lookalikes | 77/125 | 61.6% (52.8–69.7%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top1_recall | test/all | 471/577 | 81.6% (78.3–84.6%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top1_recall | test/Solidago | 188/223 | 84.3% (79.0–88.5%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top1_recall | test/Cytisus scoparius | 61/79 | 77.2% (66.8–85.1%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top1_recall | test/Rosa rugosa | 114/127 | 89.8% (83.3–93.9%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top1_recall | test/Lupinus polyphyllus | 20/32 | 62.5% (45.3–77.1%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top1_recall | test/Pastinaca sativa | 38/59 | 64.4% (51.7–75.4%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top1_recall | test/Reynoutria | 50/57 | 87.7% (76.8–93.9%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top1_recall | test/watchlist | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top1_recall | test/lookalikes | 61/79 | 77.2% (66.8–85.1%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top1_recall | test/distance-filtered/all | 388/468 | 82.9% (79.2–86.0%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top1_recall | test/distance-filtered/Solidago | 152/182 | 83.5% (77.4–88.2%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top1_recall | test/distance-filtered/Cytisus scoparius | 51/67 | 76.1% (64.7–84.7%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top1_recall | test/distance-filtered/Rosa rugosa | 91/101 | 90.1% (82.7–94.5%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top1_recall | test/distance-filtered/Lupinus polyphyllus | 18/25 | 72.0% (52.4–85.7%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top1_recall | test/distance-filtered/Pastinaca sativa | 30/41 | 73.2% (58.1–84.3%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top1_recall | test/distance-filtered/Reynoutria | 46/52 | 88.5% (77.0–94.6%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top1_recall | test/distance-filtered/watchlist | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top1_recall | test/distance-filtered/lookalikes | 51/67 | 76.1% (64.7–84.7%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top1_recall | multilabel/all | 91/201 | 45.3% (38.5–52.2%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top1_recall | multilabel/Solidago | 4/15 | 26.7% (10.9–52.0%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top1_recall | multilabel/Cytisus scoparius | 16/46 | 34.8% (22.7–49.2%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top1_recall | multilabel/Rosa rugosa | 31/44 | 70.5% (55.8–81.8%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top1_recall | multilabel/Lupinus polyphyllus | 25/51 | 49.0% (35.9–62.3%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top1_recall | multilabel/Pastinaca sativa | 12/38 | 31.6% (19.1–47.5%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top1_recall | multilabel/Reynoutria | 3/7 | 42.9% (15.8–75.0%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top1_recall | multilabel/watchlist | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top1_recall | multilabel/lookalikes | 16/46 | 34.8% (22.7–49.2%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top1_recall | multilabel/distance-filtered/all | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top1_recall | multilabel/distance-filtered/Solidago | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top1_recall | multilabel/distance-filtered/Cytisus scoparius | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top1_recall | multilabel/distance-filtered/Rosa rugosa | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top1_recall | multilabel/distance-filtered/Lupinus polyphyllus | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top1_recall | multilabel/distance-filtered/Pastinaca sativa | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top1_recall | multilabel/distance-filtered/Reynoutria | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top1_recall | multilabel/distance-filtered/watchlist | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top1_recall | multilabel/distance-filtered/lookalikes | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top3_recall | all | 731/778 | 94.0% (92.1–95.4%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top3_recall | all/Solidago | 235/238 | 98.7% (96.4–99.6%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top3_recall | all/Cytisus scoparius | 115/125 | 92.0% (85.9–95.6%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top3_recall | all/Rosa rugosa | 162/171 | 94.7% (90.3–97.2%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top3_recall | all/Lupinus polyphyllus | 71/83 | 85.5% (76.4–91.5%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top3_recall | all/Pastinaca sativa | 89/97 | 91.8% (84.6–95.8%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top3_recall | all/Reynoutria | 59/64 | 92.2% (83.0–96.6%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top3_recall | all/watchlist | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top3_recall | all/lookalikes | 115/125 | 92.0% (85.9–95.6%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top3_recall | test/all | 544/577 | 94.3% (92.1–95.9%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top3_recall | test/Solidago | 220/223 | 98.7% (96.1–99.5%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top3_recall | test/Cytisus scoparius | 69/79 | 87.3% (78.2–93.0%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top3_recall | test/Rosa rugosa | 121/127 | 95.3% (90.1–97.8%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top3_recall | test/Lupinus polyphyllus | 26/32 | 81.2% (64.7–91.1%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top3_recall | test/Pastinaca sativa | 54/59 | 91.5% (81.6–96.3%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top3_recall | test/Reynoutria | 54/57 | 94.7% (85.6–98.2%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top3_recall | test/watchlist | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top3_recall | test/lookalikes | 69/79 | 87.3% (78.2–93.0%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top3_recall | test/distance-filtered/all | 445/468 | 95.1% (92.7–96.7%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top3_recall | test/distance-filtered/Solidago | 181/182 | 99.5% (97.0–99.9%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top3_recall | test/distance-filtered/Cytisus scoparius | 57/67 | 85.1% (74.7–91.7%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top3_recall | test/distance-filtered/Rosa rugosa | 96/101 | 95.0% (88.9–97.9%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top3_recall | test/distance-filtered/Lupinus polyphyllus | 23/25 | 92.0% (75.0–97.8%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top3_recall | test/distance-filtered/Pastinaca sativa | 39/41 | 95.1% (83.9–98.7%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top3_recall | test/distance-filtered/Reynoutria | 49/52 | 94.2% (84.4–98.0%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top3_recall | test/distance-filtered/watchlist | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top3_recall | test/distance-filtered/lookalikes | 57/67 | 85.1% (74.7–91.7%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top3_recall | multilabel/all | 187/201 | 93.0% (88.6–95.8%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top3_recall | multilabel/Solidago | 15/15 | 100.0% (79.6–100.0%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top3_recall | multilabel/Cytisus scoparius | 46/46 | 100.0% (92.3–100.0%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top3_recall | multilabel/Rosa rugosa | 41/44 | 93.2% (81.8–97.7%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top3_recall | multilabel/Lupinus polyphyllus | 45/51 | 88.2% (76.6–94.5%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top3_recall | multilabel/Pastinaca sativa | 35/38 | 92.1% (79.2–97.3%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top3_recall | multilabel/Reynoutria | 5/7 | 71.4% (35.9–91.8%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top3_recall | multilabel/watchlist | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top3_recall | multilabel/lookalikes | 46/46 | 100.0% (92.3–100.0%) | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top3_recall | multilabel/distance-filtered/all | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top3_recall | multilabel/distance-filtered/Solidago | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top3_recall | multilabel/distance-filtered/Cytisus scoparius | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top3_recall | multilabel/distance-filtered/Rosa rugosa | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top3_recall | multilabel/distance-filtered/Lupinus polyphyllus | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top3_recall | multilabel/distance-filtered/Pastinaca sativa | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top3_recall | multilabel/distance-filtered/Reynoutria | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top3_recall | multilabel/distance-filtered/watchlist | 0/0 | unmeasured | — |
| whole-photo-species | danish-roadside-species | danish-roadside | held-out | six_group_grid_top3_recall | multilabel/distance-filtered/lookalikes | 0/0 | unmeasured | — |
