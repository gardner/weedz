"""Generate a synthetic signed bundle for Dart interoperability tests; never a real tower.

The deterministic private seed below is public test data, not a publisher key. Neither
these fake model bytes nor this public key may be used by an app's production pins.
Run with `uv run python scripts/build_mobile_bundle_conformance.py`.
"""

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from weedz.bundles.canonical import canonical
from weedz.bundles.manifest import BundleSpec, build_manifest
from weedz.bundles.signing import public_key_text, sign
from weedz.bundles.text_table import preprocessing_sha256, prompts, save_table
from weedz.discovery.inference import MODELS
from weedz.discovery.parity import THRESHOLDS

OUTPUT = Path("mobile/test/fixtures/model_bundle")


def build(output: Path = OUTPUT) -> None:
    output.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory() as temporary:
        folder = Path(temporary)
        model = folder / "model.onnx"
        model.write_bytes(b"SYNTHETIC TEST DATA, NOT AN INFERENCE MODEL")
        table = folder / "text.f32"
        preprocessing = {
            "size": [224, 224],
            "mode": "RGB",
            "mean": [0.48145466, 0.4578275, 0.40821073],
            "std": [0.26862954, 0.26130258, 0.27577711],
            "interpolation": "bicubic",
            "resize_mode": "shortest",
            "fill_color": 0,
        }
        save_table(table, [[0.5] * 4 for _ in prompts()], "bioclip-2", "a" * 64, preprocessing)
        benchmark = folder / "parity.json"
        benchmark.write_text(
            json.dumps(
                {
                    "thresholds": THRESHOLDS,
                    "variants": {
                        "onnx-fp16": {
                            "model": MODELS["bioclip-2"]["repo"],
                            "revision": MODELS["bioclip-2"]["revision"],
                            "artefact_sha256": hashlib.sha256(model.read_bytes()).hexdigest(),
                            "preprocessing_sha256": preprocessing_sha256(preprocessing),
                            "runtime": {
                                "format": "onnx",
                                "precision": "fp16",
                                "input_dtype": "float16",
                            },
                            "parity": {
                                "passed": True,
                                "checks": {
                                    name: {"value": 0, "limit": limit, "passed": True}
                                    for name, limit in THRESHOLDS["limits"].items()
                                },
                            },
                        }
                    },
                }
            )
        )
        spec = BundleSpec.model_validate(
            {
                "model_key": "bioclip-2",
                "image_model": {
                    "path": str(model),
                    "parity": {"benchmark": str(benchmark), "variant": "onnx-fp16"},
                },
                "text_table": str(table),
                "min_app_version": "0.1.0",
                "sequence": 7,
                "expires": "2027-02-14",
            }
        )
        key = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
        (output / "envelope.json").write_text(
            json.dumps(sign(canonical(build_manifest(spec)), key))
        )
        (output / "public-key.txt").write_text(public_key_text(key) + "\n")
        (output / "model.onnx").write_bytes(model.read_bytes())
        (output / "text.f32").write_bytes(table.read_bytes())


if __name__ == "__main__":
    build()
