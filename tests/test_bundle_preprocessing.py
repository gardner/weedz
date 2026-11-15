"""A signed transform must be the exact one the selected parity variant measured."""

import json
from pathlib import Path

import pytest
from bundle_helpers import VARIANT, spec

from weedz.bundles.manifest import ParityRefused, build_manifest
from weedz.bundles.text_table import provenance_path


@pytest.mark.parametrize(
    "field,value",
    [("mean", ["0.9", "0.4", "0.4"]), ("size", [512, 512]), ("interpolation", "nearest")],
)
def test_edited_sidecar_preprocessing_cannot_reuse_a_passing_gate(
    tmp_path: Path, field: str, value: object
) -> None:
    specification = spec(tmp_path)
    assert build_manifest(specification)["sequence"] == 1
    sidecar = provenance_path(Path(specification.text_table))
    recorded = json.loads(sidecar.read_text())
    recorded["preprocessing"][field] = value
    sidecar.write_text(json.dumps(recorded))
    with pytest.raises(ParityRefused, match="preprocessing"):
        build_manifest(specification)


@pytest.mark.parametrize("recorded", [None, True, [], "not-a-hash", "A" * 64, "0" * 64])
def test_missing_or_invalid_measured_transform_hash_refuses_publishing(
    tmp_path: Path, recorded: object
) -> None:
    specification = spec(tmp_path)
    source = Path(specification.image_model.parity.benchmark)
    benchmark = json.loads(source.read_text())
    variant = benchmark["variants"][VARIANT]
    if recorded is None:
        variant.pop("preprocessing_sha256", None)
    else:
        variant["preprocessing_sha256"] = recorded
    source.write_text(json.dumps(benchmark))
    with pytest.raises(ParityRefused, match="preprocessing"):
        build_manifest(specification)
