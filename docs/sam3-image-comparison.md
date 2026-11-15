# Optional SAM3 still-image comparison

This is an opt-in comparison stage, not a change to default discovery, SAM2.1, or human labels. It uses the official SAM3 **image** builder, not SAM3.1 video. A text concept match is neither calibrated species confidence nor a verified plant boundary. Generic `plant`, `flower`, and `leaves` predictions do not acquire a Latin taxon.

## Reproduce

SAM3 has a separate uv environment because its pinned official source requires NumPy below 2, while the main application requires NumPy 2.5+. Install the official source at `eef6839bcfc3458dd52ea80535dc6bd62aea86b1`, with its dependencies, in an external uv project. The tested environment uses Python 3.12, PyTorch 2.15.0+cu132, NumPy 1.26.4, Pillow 13, timm 1.0.31, pycocotools 2.0.11, and setuptools 80.10.2. The last constraint preserves `pkg_resources`, imported by that official builder. No system packages were installed.

Obtain authorized access through [the official model page](https://huggingface.co/facebook/sam3), read its SAM License, and download `sam3.pt` from revision `3c879f39826c281e95690f02c7821c4de09afae7`. The loader verifies SHA-256 `9999e2341ceef5e136daa386eecb55cb414446a00ac2b55eb2dfd2f7c3cf8c9e` and the installed source revision. Do not put tokens, weights or generated evidence in Git. Access terms require the operator's own authorization; the tool does not accept terms.

From the repository, using the isolated runtime's Python and its CUDA dependencies:

```sh
PYTHONPATH="$PWD/src" /path/to/sam3-runtime/.venv/bin/python main.py sam3-image \
  /absolute/public-image.png --checkpoint /external/checkpoints/sam3.pt \
  --cache /external/sam3-cache --output /external/new-result.json \
  --prompt 'yellow flowers' --prompt leaves --threshold 0.2 --max-regions 64
```

`uv run main.py sam3-image --help` works without installing SAM3. Actual inference requires the isolated CUDA runtime. The loader explicitly moves weights to logical `cuda:0`, uses FP32 weights with BF16 CUDA autocast and inference mode, and bounds CPU threads. The official builder does not move weights for the string `cuda:0` by itself. `CUDA_VISIBLE_DEVICES` can assign each independently scheduled worker a physical GPU.

Inputs are bounded to 20 MB/40 MP, EXIF-upright RGB, then a longest side of at most 1024 pixels. One to eight distinct prompts are allowed. Each prompt has an explicit retained-region cap and an 8 MB default serialized-region retention budget (configurable downward with `--max-prompt-bytes`); both are recorded in the profile identity. It reports count/byte truncation separately and reserves space below the 32 MB per-prompt artifact cap. If no otherwise eligible mask fits its byte budget, the prompt records `OutputBudgetExceeded` failure rather than an empty result. The official processor returns all proposals at threshold zero; the configured retention cutoff is applied separately, with the top 20 scores before retention retained for diagnosis. Scores are sigmoid concept logits multiplied by sigmoid presence, not mask IoU. Results retain original-frame boxes, mask transforms, exact source hash, checkpoint/code/runtime/config and prompt-specific identities. Successful per-prompt artifacts resume without repeating inference; failed prompts remain failed and retryable. Startup/checkpoint errors fail before producing a negative result.

`restore_concept_regions(encoded_bytes, records, config, expected_sha256=source_envelope_sha)` verifies the exact source bytes, decodes once per photo, and reconstructs tight, masked and context crops without inventing SAM2 IoU/stability values. Its `Region.quality` is empty. Use the envelope's original SHA, rather than a hash guessed from a supplied replacement image. The singular convenience wrapper requires the same encoded bytes and expected SHA. Callers retain the original concept record and score kind alongside separately versioned crop-classifier output.

## Actual exploratory results

The public broom source is [iNaturalist observation 250532538](https://www.inaturalist.org/observations/250532538). Its original subject label is context, not new human verification. On this crowded image, `flower` at 0.5 retained zero masks (largest pre-retention score 0.3535); `yellow flowers` at 0.5 retained nine. At 0.2, these retained 23 and 84 respectively. The latter includes broad overlapping shrub regions, so the count is not a count of correctly outlined flowers. At 0.1, `yellow flowers` reached the 128-region experiment cap. These original zero-result variants are retained.

On a licensed DeepWeeds leaf control, `leaves` at 0.5 retained 18 regions aligned with visible leaves. Both the broom and leaf example also returned a `gorse` concept candidate despite their source labels differing. Species-prompt matches therefore remain tentative predictions requiring verification.

A separate real run processed the original 33 public photos plus the first 100 canonical DeepWeeds photos using four concepts (`plant`, `flower`, `yellow flowers`, `leaves`), separate 0.5/0.2 retention and a 64-region cap per prompt. It took 33.80 seconds after startup and peaked at 6,599,766,016 allocated CUDA bytes on the tested GPU. These are selected exploratory examples, not held-out accuracy, weed recall, comparative model sufficiency, or complete flower coverage. Machine outputs must remain separate from human annotations.

External experiment roots on the execution host:

- `/home/gardner/src/weedz-sam3-artifacts/task9-concept-v3/` (original six prompts, including zero results)
- `/home/gardner/src/weedz-sam3-artifacts/task9-thresholds-v1/` (raw-score threshold comparison and inspected overlays)
- `/home/gardner/src/weedz-sam3-artifacts/corpus133-concepts-v1/` (closed 133-image run and source identities)

The [official repository](https://github.com/facebookresearch/sam3/tree/eef6839bcfc3458dd52ea80535dc6bd62aea86b1) and its [license](https://github.com/facebookresearch/sam3/blob/eef6839bcfc3458dd52ea80535dc6bd62aea86b1/LICENSE) remain the primary model references. Weights and model code have their own SAM License; repository package classifiers are not a substitute for reading it.

The subsequent bounded two-GPU standalone run completed all 17,509 DeepWeeds photographs across 176 source batches. It computed 17,409 new photos and adopted the first 100 already-completed results without recomputation. The two workers processed 8,709/8,700 new photos in 1,524.98/1,688.94 seconds after startup, with 4,150,398,976 peak allocated CUDA bytes each. The aggregate receipt is `/home/gardner/src/weedz-sam3-artifacts/deepweeds17509-concepts-v1/complete.json`; each source batch manifest hash was verified. This is standalone comparison execution, not evidence that these earlier jobs have Temporal history. Actual future activity integration belongs to #148. Human annotations remained unchanged.
