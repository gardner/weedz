"""Offline blind packages using existing Label Studio task/config/publication contracts."""

import re
from io import BytesIO
from pathlib import Path

from PIL import Image

from weedz.annotation.credits import photo_credit
from weedz.annotation.label_studio import label_config, task
from weedz.contract import Media, Rights, Sample, revise_sample
from weedz.labelled.images import validate_rgb_png
from weedz.labelled.publication import digest, json_bytes, output_namespace, publish

ALLOWED = {"cc0", "cc-by", "cc0-1.0", "cc-by-4.0"}


def prepare(manifest: Path, output: Path, *, image_prefix: str) -> dict:
    output, source_raw, samples = _inputs(manifest, output, image_prefix)
    prepared = [_prepare(sample, manifest.parent, image_prefix) for sample in samples]
    prepared.sort(key=lambda row: row[0]["meta"]["external_id"])
    tasks = []
    records = []
    for imported, portable, encoded in prepared:
        publish(output / portable.media.uri, encoded)
        tasks.append(imported)
        records.append(
            {
                "external_id": imported["meta"]["external_id"],
                "sample": portable.model_dump(mode="json"),
            }
        )
    private = output / "private"
    private.mkdir(mode=0o700)
    publish(private / "source-samples.jsonl", source_raw)
    publish(output / "tasks.json", json_bytes(tasks))
    publish(output / "label-config.xml", label_config("blind").encode())
    publish(
        private / "provenance.json",
        json_bytes(
            {
                "schema_version": 1,
                "mode": "blind",
                "source_manifest_sha256": digest(source_raw),
                "samples": records,
                "prediction_count": 0,
                "human_annotation_count": 0,
                "order": "opaque external-ID sort, not source stratum order",
                "interpretation": "Unreviewed images prepared for later review; not expert NZ gold",
            }
        ),
    )
    files = {
        str(path.relative_to(output)): digest(path.read_bytes())
        for path in sorted(output.rglob("*"))
        if path.is_file()
    }
    receipt = {
        "schema_version": 1,
        "mode": "blind",
        "task_count": len(tasks),
        "source_manifest_sha256": digest(source_raw),
        "image_prefix": image_prefix,
        "files": files,
    }
    publish(output / "manifest.json", json_bytes(receipt))
    return receipt


def _inputs(manifest: Path, output: Path, image_prefix: str) -> tuple[Path, bytes, list[Sample]]:
    output = output_namespace(output, manifest.parent)
    if output.exists() or not re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", image_prefix):
        raise ValueError("Choose a new package directory and opaque relative image prefix")
    source_raw = manifest.read_bytes()
    samples = [Sample.model_validate_json(line) for line in source_raw.splitlines()]
    if not 1 <= len(samples) <= 120 or len({sample.id for sample in samples}) != len(samples):
        raise ValueError("Choose 1–120 distinct review-preparation samples")
    return output, source_raw, samples


def _prepare(sample: Sample, root: Path, prefix: str) -> tuple[dict, Sample, bytes]:
    _unreviewed(sample)
    path = (root / sample.media.uri).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Review image escapes its canonical source root")
    with path.open("rb") as stream:
        encoded = stream.read(160_000_001)
    if digest(encoded) != sample.media.sha256:
        raise ValueError("Review image checksum differs from source manifest")
    validate_rgb_png(encoded)
    with Image.open(BytesIO(encoded)) as image:
        if image.width * image.height > 40_000_000 or image.size != (
            sample.media.width,
            sample.media.height,
        ):
            raise ValueError("Review image dimensions differ from source manifest or exceed budget")
        image.load()
        size = image.size
    attribution = sample.rights.attribution
    observer = sample.context.get("source_observer_login")
    if sample.rights.metadata_license.lower() in {"cc-by", "cc-by-4.0"} and not observer:
        raise ValueError("CC BY observation metadata needs its actual source observer credit")
    if observer:
        attribution += f". Observation data credit: {observer}"
    rights = Rights.model_validate(dict(sample.rights.model_dump(), attribution=attribution))
    imported, _ = task(
        sample.source_id,
        str(sample.media.sha256),
        {},
        {},
        size,
        "blind",
        prefix,
    )
    imported["meta"]["image_sha256"] = sample.media.sha256
    imported["data"].update(
        source_dataset=sample.source,
        photo_credit=photo_credit(
            rights.attribution, rights.media_license, rights.metadata_license, rights.license_source
        ),
    )
    portable = revise_sample(
        sample,
        geography=None,
        rights=rights,
        media=Media(
            uri=f"images/{prefix}/{sample.media.sha256}.png",
            sha256=sample.media.sha256,
            width=sample.media.width,
            height=sample.media.height,
            format="PNG",
        ),
    )
    return imported, portable, encoded


def _unreviewed(sample: Sample) -> None:
    if sample.rights.consent is not None:
        raise ValueError(
            "Public source review preparation excludes consent-backed contributor media"
        )
    if sample.source != "inaturalist":
        raise ValueError("This blind preparation profile requires iNaturalist source identities")
    if sample.tasks != frozenset({"inference"}) or sample.annotations or sample.review_history:
        raise ValueError(
            "Blind preparation requires inference-only images without annotations/history"
        )
    if sample.completeness:
        raise ValueError("Blind preparation does not import completeness claims")
    if {sample.rights.media_license.lower(), sample.rights.metadata_license.lower()} - ALLOWED:
        raise ValueError("This blind preparation profile permits separate CC0/BY rights only")
