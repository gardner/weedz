# Source-labelled datasets and NZ review preparation

These adapters preserve publisher labels as `origin=source`, `review=unreviewed`.
They do not create expert NZ gold, model predictions, Label Studio tasks or human
submissions. Raw sources and converted batches belong outside every Git worktree.
A `ready.json` closes the manifest and provenance by SHA256. Identical partial
conversions resume; conflicting existing bytes are refused rather than replaced.

## Inventory and independent origins

| Source | Verified inventory | Actual supervision | Evaluation limits |
|---|---:|---|---|
| Leafy Spurge, already cached | 900 images, 800 train/100 test; 903 pinned files verified | Surveyed centre-point presence/absence of *Euphorbia esula* | Not boxes or masks; retain survey clusters and native split. Already used by this project's baseline. |
| DeepWeeds, already cached | 17,509 images | Original eight weed classes plus negative image class | Negative means no named target, not no plants. Weed-AI repackaging is not another independent dataset. Prior pipeline exposure. |
| CWFID, newly acquired | 60 unique images | Expert crop/weed plant/part polygons intersected with algorithmic vegetation mask | Functional classes, not scientific taxa; false-colour multispectral sensor. Partial labels and split overlap. |
| ImageWeeds v2, newly acquired | 81 soybean +94 maize images; 735 native boxes | Publisher manual species boxes, five taxa | Two mirror contexts are ONE dataset origin. One invalid maize image is quarantined, not clipped. No documented independent-site split. |
| NZ review cohort | Explicit maximum120 | No gold annotations or model predictions | Source subjects are context only; later human review remains necessary. |

Leafy Spurge is [mpg-ranch/leafy_spurge](https://huggingface.co/datasets/mpg-ranch/leafy_spurge),
pinned at `ede1689fa8d424bcaea2c02157e791d97e4eba04`, CC BY4, DOI
[10.57967/hf/2508](https://doi.org/10.57967/hf/2508). Existing
`leafy_spurge_samples` retains point granularity. `benchmarks/leafy-spurge-cpu.json`
is prior evaluation evidence, so these images are not a fresh held-out acquisition.

## CWFID

[Official source](https://github.com/cwfid/dataset), pinned commit
`36290d0912a032f0bd1a5678ed55457ddafde217`; archive SHA256
`5a5f178e7d87a55b5d03fbd6047f09114255e6bdec609f1b3bed920601a1f1e3`.
[Haug and Ostermann's paper](https://doi.org/10.1007/978-3-319-16220-1_8)
and its [official proceedings copy](https://projet.liris.cnrs.fr/imagine/pub/proceedings/ECCV-2014/workshops/w23/paper26.pdf)
describe manually labelled crop/weed plants and parts, unlabelled overlapping areas,
and NDVI/Otsu vegetation boundaries. The vegetation threshold was fitted using the
training images. It is an algorithm-derived source reference, not manually traced GT.
The field images contain Red/NIR/Red channels; storing them in an RGB PNG container
does not make them natural-colour photographs.

Exact publisher terms: **All data is subject to copyright and may only be used for
non-commercial research. In case of use please cite our publication.** These custom
terms are not CC BY-NC. This adapter prepares private noncommercial research data;
it does not admit CWFID to public/LS sharing profiles.

Red source pixels mean weed, green mean crop. Black contains both inferred soil and
unassigned vegetation. Derived binary `L` PNG category masks use0/255, with a
separate assessed mask containing only labelled crop/weed support. Soil inferred
from NDVI is not promoted to human-assessed negative background. Source vegetation,
RGB annotation and YAML polygons are preserved separately. Category supervision is
`sparse_mask`/`sparse_segmentation`; no connected components become human instances.
Mask paths are relative and individually SHA-pinned. Completeness remains partial.

Native split has40 training +21 testing memberships but60 unique images: **028 is in
both**. Both memberships are retained and028 is quarantined from held-out scoring.
All60 may support explicitly descriptive source-label diagnostics, not independent
held-out accuracy claims. Polygons are plants/parts/labelled regions; do not infer
an exhaustive individual-plant census.

```sh
aria2c -x4 -s4 -j4 --dir "$SOURCE" --out cwfid.tar.gz \
  https://codeload.github.com/cwfid/dataset/tar.gz/36290d0912a032f0bd1a5678ed55457ddafde217
uv run main.py labelled-batches cwfid --archive "$SOURCE/cwfid.tar.gz" \
  --output "$ARTIFACTS/cwfid-60" --limit 60
```

The archive is read in
place, never extracted, and is verified through the same descriptor before reading
and again before the batch closes. Unsafe/duplicate/link members are refused.

## ImageWeeds v2

Original [Mendeley release](https://data.mendeley.com/datasets/8kjcztbjz2/2), DOI
[10.17632/8kjcztbjz2.2](https://doi.org/10.17632/8kjcztbjz2.2), and
[authors' paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC10618417/).
Both media and annotation metadata are distributed under CC BY4. Credit Rai et al.
and the original DOI; the Weed-AI mirror is a distribution copy, not another source.

| Context | Official Weed-AI UUID, head version2 | ZIP SHA256 |
|---|---|---|
| Soybean | `cfe6e919-6ddd-4b4e-aa63-58483841a11f` | `3cb63ffdac4c8ece9e08a33389395585fcd4ea380ee3b933bdd549df55c1ecc2` |
| Maize | `1a9e04c8-80c3-41f1-a7af-a9d3f39d0feb` | `361f5adad959ca35f8cf4dc7769077eb1a75930d28c4c0a7247d937496bb6bbb` |

The five source species are *Erigeron canadensis*, *Bassia scoparia*, *Amaranthus
retroflexus*, *Ambrosia artemisiifolia* and *Amaranthus tuberculatus*. Category IDs
are local: soybeanID2 means *A.retroflexus*, maizeID2 means *A.tuberculatus*.
The adapter preserves native category text/IDs and uses explicit names, not inferred
synonym equivalence. Empty COCO segmentation arrays do not become masks.

Images are5472×3648. A measured8,466,536-byte JPEG becomes34,907,858 bytes as lossless
RGB PNG. Therefore this standalone external benchmark preserves exact upright
JPEG/MPO bytes privately, source metadata included, and records primary frame0.
It refuses rotated/ambiguous annotation frames and mismatched dimensions. It does
not resize, recompress, strip metadata destructively, or widen canonical public
PNG/20MB segmentation defaults. A future provenance-bound high-resolution ingress
profile can support lossless PNG without changing those defaults.

Maize `UASs_355.jpg`, annotation273, has x5366+width107=5473 beyond width5472. The
whole image is withheld from canonical labelled evaluation with its native record
and reason retained; no box is silently clipped. All175 source images remain
acquired. Completeness is unknown, so missing boxes are not assessed negatives.

```sh
aria2c -x4 -s4 -j4 --dir "$SOURCE" --out imageweeds-soybean.zip \
  https://weed-ai.sydney.edu.au/code/download/cfe6e919-6ddd-4b4e-aa63-58483841a11f.zip
uv run main.py labelled-batches imageweeds --crop soybean \
  --archive "$SOURCE/imageweeds-soybean.zip" --output "$ARTIFACTS/soybean" --limit 81
```

Reuse cached verified archives; fresh
large downloads use the requested aria2c four-connection/four-job settings.

## NZ review cohort

The bounded preparation command reuses the rate-limited
[iNaturalist API](https://api.inaturalist.org/v1/docs/) client and keeps six explicit
strata: gorse, broom, pampas, old man's beard, other plants and incidental animals.
Maximum20 per stratum,120 total; shortfalls remain visible rather than fabricated.
Image and observation licences must each be `cc0` or `cc-by`; actual codes are
retained without inventing a licence version. Observed/uploaded dates, observer and
observation groups, source locations/uncertainty/privacy and exact source responses
are preserved. No site or encounter independence is inferred from uncertain points.

Previously inventoried pilot observation IDs, observers and decoded RGB pixels are
excluded; duplicates within the new cohort are excluded too. This is an explicit
inventory scope, not a claim that every image on the internet was checked. Images
are EXIF-upright metadata-free RGB PNGs with original encoded and decoded hashes.
All annotations/predictions remain absent; source subject labels stay context.
Keep a later blind-review subset free of predictions and hide its source taxonomy
in the review presentation. Do not reuse old33/133 as a fresh blind cohort.

```sh
uv run main.py labelled-batches nz-review --prior-root "$PREVIOUS_PILOT" \
  --output "$ARTIFACTS/nz-review" --per-stratum 20
```

No command writes source stores,
review decisions, Label Studio project1 or any external account.
