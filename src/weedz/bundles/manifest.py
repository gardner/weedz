"""What a bundle manifest says, the parity gate before it is built, and a device's checks.

The watchlist, lookalikes, prompts, window geometry and screening stamp come from the
code the server screens with, never from hand-written configuration, so a phone cannot be
told something the server does not do. Only the artefact files, the parity record that
admits the image tower, and the delivery fields (sequence, expiry, minimum app version)
come from the bundle spec.
"""

import json
import re
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

from weedz.bundles.parity_gate import validate_parity
from weedz.bundles.signing import PAYLOAD_TYPE, BundleRejected, verify
from weedz.bundles.text_table import preprocessing_sha256, table_parts
from weedz.bundles.windows import scoring, windows
from weedz.discovery.inference import COMPARISONS, MODELS, RANKING_REVISION, file_sha256
from weedz.discovery.lookalikes import LOOKALIKES
from weedz.discovery.parity import THRESHOLDS
from weedz.discovery.records import REGIONS, SPECIES

__all__ = ["PAYLOAD_TYPE", "BundleRejected", "BundleSpec", "ParityRefused"]

SCHEMA = 1
Version = Annotated[str, StringConstraints(pattern=r"^\d{1,4}\.\d{1,4}\.\d{1,4}$")]
# How a device feeds the tower and reads it, as the parity benchmark did (#52).
INPUT = (
    "Each window (see windows) cut from the photo and letterboxed to a square, then "
    "prepared per preprocessing (open_clip's config; decimals are strings): an RGB "
    "tensor of runtime.input_dtype shaped [batch, 3, height, width]."
)
OUTPUT = (
    "One embedding per window: L2-normalise it, then take its dot product with every "
    "text_table row (cosine similarity) and rank as ranking_revision says."
)
Token = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9._-]{0,39}$")]


class ParityRefused(ValueError):
    """An image tower without a passing parity record for exactly its bytes (#52)."""


class Spec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ParitySource(Spec):
    benchmark: str  # a parity benchmark JSON, e.g. benchmarks/optimised-model-parity.json
    variant: Token


class Runtime(Spec):
    """How a parity-tested tower ran, as the benchmark recorded it."""

    format: Token  # torch, onnx; later coreml, tflite
    precision: Literal["fp32", "fp16", "int8"]
    input_dtype: Literal["float32", "float16"]


class ImageModel(Spec):
    """The tower file and the parity record that admits it; how it runs (format, precision,
    input dtype) is read from that record, never declared here."""

    path: str
    parity: ParitySource


class BundleSpec(Spec):
    """The publisher's choices for one bundle; everything else comes from code."""

    model_key: Literal["bioclip", "bioclip-2"]
    image_model: ImageModel
    text_table: str
    min_app_version: Version
    # Strictly increasing per published tree; a device refuses anything not newer.
    sequence: int = Field(ge=1, le=2**53 - 1)
    # After this day a device stops trusting the bundle until it fetches a newer one.
    expires: date


def artefact(path: Path) -> dict[str, Any]:
    """A file's content address and size."""
    return {"sha256": file_sha256(path), "size": path.stat().st_size}


def check_artefact(path: Path, entry: Mapping[str, Any]) -> None:
    """Refuse a downloaded file unless it is exactly the one the manifest lists."""
    size = path.stat().st_size
    if size != entry["size"]:
        raise BundleRejected(f"{path.name}: size {size}, but the manifest lists {entry['size']}")
    if file_sha256(path) != entry["sha256"]:
        raise BundleRejected(f"{path.name}: SHA-256 differs from the manifest")


def parity_record(
    benchmark: Mapping[str, Any], variant: str, model_key: str, sha256: str, preprocessing_hash: str
) -> str:
    """The passing parity record admitting these image-tower bytes and transform."""
    record = benchmark.get("variants", {}).get(variant)
    if record is None:
        raise ParityRefused(f"There is no parity record for variant {variant!r}")
    model = MODELS[model_key]
    if (record.get("model"), record.get("revision")) != (model["repo"], model["revision"]):
        raise ParityRefused(f"{variant} measured another model than pinned {model_key}")
    # compare_optimised records the thresholds once for the whole benchmark.
    version = benchmark.get("thresholds", {}).get("version")
    if version != THRESHOLDS["version"]:
        raise ParityRefused(f"{variant} was measured against thresholds version {version}")
    if benchmark["thresholds"].get("limits") != THRESHOLDS["limits"]:
        raise ParityRefused(f"{variant} was judged against other limits than version {version}'s")
    try:
        validate_parity(record.get("parity"))
    except ValueError as error:
        raise ParityRefused(f"{variant} did not pass parity with the reference: {error}") from error
    _measured_these_bytes(record, variant, sha256)
    measured = record.get("preprocessing_sha256")
    if not isinstance(measured, str) or re.fullmatch(r"[0-9a-f]{64}", measured) is None:
        raise ParityRefused(f"{variant} records no valid preprocessing SHA-256; re-measure parity")
    if measured != preprocessing_hash:
        raise ParityRefused(f"{variant} measured other preprocessing; re-measure parity")
    return f"{variant}/thresholds-{version}"


def _measured_these_bytes(record: Mapping[str, Any], variant: str, sha256: str) -> None:
    if record.get("artefact_sha256") is None:
        raise ParityRefused(f"{variant} records no artefact SHA-256; re-measure its parity")
    if record["artefact_sha256"] != sha256:
        raise ParityRefused(f"{variant} measured other bytes than the file being published")
    try:
        Runtime.model_validate(record.get("runtime"))
    except ValidationError as error:
        raise ParityRefused(f"{variant} records no valid runtime: {error}") from error


def screening_stamp(model_key: str) -> dict[str, Any]:
    """Device model identity, without borrowing server-population score meaning."""
    model = MODELS[model_key]
    return {
        "model_key": model_key,
        "revision": model["revision"],
        "ranking_revision": RANKING_REVISION,
    }


def build_manifest(spec: BundleSpec) -> dict[str, Any]:
    """The manifest for `spec`, refused unless its image tower passed parity."""
    tower = artefact(Path(spec.image_model.path))
    source = spec.image_model.parity
    benchmark = json.loads(Path(source.benchmark).read_text())
    table, preprocessing = table_parts(Path(spec.text_table), spec.model_key)
    parity = parity_record(
        benchmark,
        source.variant,
        spec.model_key,
        tower["sha256"],
        preprocessing_sha256(preprocessing),
    )
    runtime = Runtime.model_validate(benchmark["variants"][source.variant]["runtime"])
    return {
        "schema": SCHEMA,
        "sequence": spec.sequence,
        "expires": spec.expires.isoformat(),
        "min_app_version": spec.min_app_version,
        "region": {"inaturalist_place_ids": dict(REGIONS)},
        "watchlist": [{"taxon": name, "common_name": common} for name, common in SPECIES.items()],
        "lookalikes": [
            {"inaturalist_taxon_id": taxon} | entry for taxon, entry in sorted(LOOKALIKES.items())
        ],
        "comparisons": list(COMPARISONS),
        "windows": windows(),
        "scoring": scoring(),
        "screening": screening_stamp(spec.model_key),
        "image_model": tower
        | {
            "runtime": runtime.model_dump(),
            "model_key": spec.model_key,
            "model_revision": MODELS[spec.model_key]["revision"],
            "parity": parity,
            "input": INPUT,
            "preprocessing": preprocessing,
            "output": OUTPUT,
        },
        "text_table": table,
    }


def _version(text: str) -> tuple[int, ...]:
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)", text)
    if match is None:
        raise BundleRejected(f"{text!r} is not a version like 1.2.3")
    return tuple(int(part) for part in match.groups())


def read_manifest(
    envelope: Mapping[str, Any],
    trusted: Sequence[str],
    *,
    today: date,
    installed: int,
    app_version: str,
) -> dict[str, Any]:
    """What a device does before using a bundle: verify, then refuse anything unsafe.

    `installed` is the sequence of the bundle it already has (0 for none): an older or
    replayed bundle is refused, as is one past its expiry or needing a newer app.
    """
    payload = verify(envelope, trusted)
    try:
        manifest = json.loads(payload)
    except ValueError as error:
        raise BundleRejected("The manifest is not UTF-8 JSON") from error
    if not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA:
        raise BundleRejected(f"Unknown manifest schema; this reader knows schema {SCHEMA}")
    if manifest["sequence"] <= installed:
        raise BundleRejected(
            f"Bundle {manifest['sequence']} is older than or the same as installed {installed}"
        )
    if _version(app_version) < _version(manifest["min_app_version"]):
        raise BundleRejected(f"This bundle needs app version {manifest['min_app_version']}")
    if today > date.fromisoformat(manifest["expires"]):
        raise BundleRejected(f"The bundle expired on {manifest['expires']}")
    return manifest
