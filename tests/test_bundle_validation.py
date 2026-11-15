"""Publisher inputs must substantiate the parity and normalized-vector claims (#100)."""

import json
from pathlib import Path

import numpy as np
import pytest
from bundle_helpers import PREPROCESSING, VARIANT, parity_benchmark, write_artefacts

from weedz.bundles.manifest import ParityRefused, artefact, parity_record
from weedz.bundles.text_table import (
    preprocessing_sha256,
    prompts,
    provenance_path,
    save_table,
    table_parts,
)
from weedz.discovery.inference import file_sha256
from weedz.discovery.parity import THRESHOLDS


def checks() -> dict:
    return {
        name: {"value": 0, "limit": limit, "passed": True}
        for name, limit in THRESHOLDS["limits"].items()
    }


@pytest.mark.parametrize("invalid", ["missing", "failing", "nan", "negative", "bool", "limit"])
def test_summary_flag_cannot_override_invalid_measurements(tmp_path: Path, invalid: str) -> None:
    tower, _ = write_artefacts(tmp_path)
    benchmark = json.loads(parity_benchmark(tmp_path, tower).read_text())
    measured = checks()
    drift = measured["max_margin_drift"]
    if invalid == "missing":
        measured.pop("references_lost")
    elif invalid == "failing":
        drift["value"] = 1
    elif invalid == "nan":
        drift["value"] = float("nan")
    elif invalid == "negative":
        drift["value"] = -1
    elif invalid == "bool":
        drift["value"] = False
    else:
        drift["limit"] = 1
    benchmark["variants"][VARIANT]["parity"] = {"passed": True, "checks": measured}
    with pytest.raises(ParityRefused):
        parity_record(
            benchmark,
            VARIANT,
            "bioclip-2",
            artefact(tower)["sha256"],
            preprocessing_sha256(PREPROCESSING),
        )


@pytest.mark.parametrize(
    "rows", [np.empty((16, 0)), np.full((16, 4), 1.0), np.full((16, 4), np.nan)]
)
def test_writing_refuses_empty_nonunit_or_nonfinite_rows(tmp_path: Path, rows) -> None:
    assert len(rows) == len(prompts())
    with pytest.raises(ValueError):
        save_table(tmp_path / "text.f32", rows, "bioclip-2", "w" * 64, PREPROCESSING)
    assert not (tmp_path / "text.f32").exists()


@pytest.mark.parametrize("data", [b"", b"a", np.ones((16, 4), dtype="<f4").tobytes()])
def test_publishing_rechecks_rows_even_with_repaired_provenance(
    tmp_path: Path, data: bytes
) -> None:
    _, table = write_artefacts(tmp_path)
    table.write_bytes(data)
    provenance = json.loads(provenance_path(table).read_text())
    provenance["table_sha256"] = file_sha256(table)
    provenance_path(table).write_text(json.dumps(provenance))
    with pytest.raises(ValueError):
        table_parts(table, "bioclip-2")
