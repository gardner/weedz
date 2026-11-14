"""The fixed prompts' text embeddings, computed once on the server for every device.

A phone runs only the image tower. It scores each window against this table, whose rows
follow `prompts()`: the watchlist targets first, then the comparison labels. The file is
raw little-endian float32, row-major, so any platform reads it without a parser.

Beside it, `<table>.json` records which pinned model wrote it and that model's image
pre-processing, so a bundle cannot label one model's embeddings as another's, and a phone
is told how to prepare each window for the tower.
"""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np

from weedz.discovery.inference import LABELS, MODELS, file_sha256, prompt
from weedz.discovery.records import SPECIES

DTYPE = "float32-le"


def prompts() -> list[str]:
    """The table's rows, in order."""
    return [prompt(label) for label in LABELS]


def portable(value: Any) -> Any:
    """JSON every language reads alike: tuples become lists, floats decimal strings."""
    if isinstance(value, Mapping):
        return {str(key): portable(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [portable(item) for item in value]
    if isinstance(value, float):
        return repr(value)
    return value


def provenance_path(table: Path) -> Path:
    return table.with_name(f"{table.name}.json")


# Float32 normalization accumulates rounding error across the embedding dimensions.
# Accept that noise, but never silently change the vectors that were measured.
UNIT_TOLERANCE = 1e-5


def _check_rows(rows: np.ndarray) -> None:
    if rows.ndim != 2 or rows.shape[0] != len(prompts()) or rows.shape[1] == 0:
        raise ValueError(f"Expected nonempty rows for {len(prompts())} prompts, got {rows.shape}")
    norms = np.linalg.norm(rows.astype(np.float64), axis=1)
    if not np.isfinite(rows).all() or not np.allclose(norms, 1, rtol=0, atol=UNIT_TOLERANCE):
        raise ValueError("Text table rows must be finite unit vectors")


def save_table(
    out: Path,
    embeddings: Any,
    model_key: str,
    weights_sha256: str,
    preprocessing: Mapping[str, Any],
) -> None:
    """Write one float32 row per fixed prompt, and the provenance a bundle checks."""
    rows = np.asarray(embeddings, dtype="<f4")
    _check_rows(rows)
    out.write_bytes(rows.tobytes(order="C"))
    provenance = {
        "model_key": model_key,
        "revision": MODELS[model_key]["revision"],
        "weights_sha256": weights_sha256,
        "table_sha256": file_sha256(out),
        "prompts": prompts(),
        "preprocessing": portable(preprocessing),
    }
    provenance_path(out).write_text(json.dumps(provenance, indent=2, ensure_ascii=False))


def _provenance(path: Path, model_key: str) -> dict[str, Any]:
    """The table's recorded provenance, refused unless it is this model's and these bytes'."""
    recorded = json.loads(provenance_path(path).read_text())
    expected = (model_key, MODELS[model_key]["revision"])
    if (recorded["model_key"], recorded["revision"]) != expected:
        raise ValueError(
            f"{path} was written by {recorded['model_key']} {recorded['revision']}, "
            f"not the bundle's {model_key} {expected[1]}"
        )
    if recorded["table_sha256"] != file_sha256(path):
        raise ValueError(f"{path} SHA-256 differs from the one its provenance recorded")
    if recorded["prompts"] != prompts():
        raise ValueError(f"{path} was written for other prompts than the bundle's")
    return recorded


def table_parts(path: Path, model_key: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """How the manifest describes the table, and the model's image pre-processing."""
    recorded = _provenance(path, model_key)
    size = path.stat().st_size
    rows = len(prompts())
    if size == 0 or size % (4 * rows):
        raise ValueError("Text table size must contain complete nonempty float32 rows")
    _check_rows(np.fromfile(path, dtype="<f4").reshape(rows, -1))
    entry = {
        "sha256": recorded["table_sha256"],
        "size": size,
        "dtype": DTYPE,
        "shape": [rows, size // (4 * rows)],
        "prompts": prompts(),
        "target_count": len(SPECIES),
        "model_key": model_key,
        "model_revision": recorded["revision"],
        "weights_sha256": recorded["weights_sha256"],
        "normalised": True,
    }
    return entry, recorded["preprocessing"]


def write_text_table(model_key: str, out: Path) -> None:  # pragma: no cover - loads a model
    """Embed the fixed prompts with the pinned model's text tower and write the table."""
    import open_clip

    from weedz.discovery.inference import Screener

    screener = Screener.load(model=model_key)
    if screener.prompts != prompts():
        raise ValueError("The screener's prompts differ from the bundle's")
    preprocessing = open_clip.get_model_preprocess_cfg(screener.model)
    rows = screener.text.cpu().numpy()
    save_table(out, rows, model_key, screener.weights_sha256, preprocessing)
