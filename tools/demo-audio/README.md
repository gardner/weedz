# Breeze demo narration

This isolated uv environment keeps the desktop screening environment unchanged.
The user confirmed that the demonstration is non-commercial and selected Breeze.
No Kokoro dependency or audio is used in the production path.

Breeze model revision: `3e28c5151381a722f1d8661b4118c298caa77aa4`.
Inference source: https://github.com/breezeblue-ai/breeze-tts at
`daa6cb2efe5471f09369229f322d20bb956cb3c3`.
Read the model's [research/non-commercial license](https://huggingface.co/BreezeBlue/Breeze-TTS-2/blob/main/LICENSE).
The generic voice description does not clone a real person.

Download the pinned checkpoint (including its bundled audio tokenizer) with
Hugging Face Hub, clone/check out the source revision, and keep both outside Git.
The runner records the expected checkpoint revision without local checkpoint paths.
Optional reference audio is identified by its basename and SHA-256; runtime commands
still resolve its actual local path.
It verifies the inference-source Git revision, but does not verify that arbitrary
checkpoint contents match the expected model revision. Preserve download provenance
when supplying the checkpoint.

Then, from the Weedz repository root:

```sh
uv sync --project tools/demo-audio --locked
uv run --project tools/demo-audio python tools/demo-audio/main.py \
  --source /path/to/breeze-tts \
  --model /path/to/breeze-checkpoint \
  --text-file /path/to/narration.txt \
  --output /path/to/artifacts/narration-v1.wav
```

The runner uses GPU 0 by default (`--gpu 1` selects the second GPU), an
eager-compatible path, a fixed seed and a documented
female voice instruction. It records text, model/source revisions, settings and
package versions beside each WAV. Existing outputs or metadata sidecars are never
overwritten, and resolved output paths inside Git are refused.
Large model files and generated audio/video must remain outside the repository.

The upstream `qwen-tts` dependency currently requires Transformers 4.57.3 and
Hugging Face Hub below 1. The lockfile records those compatible transitive
requirements; dependencies were resolved with `uv add` rather than changing the
main project's newer libraries. PyTorch/CUDA availability was checked on the
local RTX 5090 before generating the first intro sample.

New generation receipts include `wav_sha256`, binding the exact untouched native WAV
bytes to the declared model/source revisions and passage. Video rendering checks this
receipt before accepting an utterance and rechecks the same bytes during PCM assembly.
The selected file hash is retained in the portable timeline. A same-format replacement
or different passage cannot inherit another recording's Breeze provenance.

Historical receipts without this hash are not silently upgraded or presented as original
checksummed generation evidence. Keep historical delivered media unchanged; a future new
render must use recordings with the documented generation receipt. These checks do not
normalize, trim, resample, adjust gain or otherwise process the native narration.
The source checkout must also be clean, including nonignored untracked files;
modified inference code cannot inherit the pinned source revision. Ignored runtime
caches and the separately recorded installed dependencies remain a trusted local
runtime boundary, not an attestation of every dependency on the host.
