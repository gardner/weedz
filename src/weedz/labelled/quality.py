"""Conservative source-annotation quality gate, independent of any model outcomes."""

from collections import defaultdict
from pathlib import Path

from weedz.contract import Media, Sample, revise_sample
from weedz.labelled.audit import verified_asset
from weedz.labelled.images import validate_rgb_png
from weedz.labelled.native_imageweeds import NativeImage, inventory
from weedz.labelled.publication import close_batch, digest, json_bytes, output_namespace, publish
from weedz.manifest import manifest_bytes


def annotation_identity(sample: Sample) -> str:
    labels = []
    for annotation in sample.annotations:
        if annotation.origin != "source" or annotation.supervision != "box":
            raise ValueError("Primary ImageWeeds selection requires publisher source boxes only")
        labels.append(
            annotation.model_dump(mode="json", include={"taxon", "category", "label", "box"})
        )
    labels.sort(key=lambda row: json_bytes(row))
    return digest(json_bytes({"boxes": labels}))


def select_primary(
    samples: list[Sample], *, invalid_pixels: set[str] | None = None
) -> tuple[set[str], list[dict]]:
    groups: dict[str, list[Sample]] = defaultdict(list)
    for sample in samples:
        groups[sample.context["decoded_pixel_sha256"]].append(sample)
    selected: set[str] = set()
    ledger = []
    for pixels, members in sorted(groups.items()):
        variants = {annotation_identity(sample) for sample in members}
        reason = _reason(pixels, members, variants, invalid_pixels or set())
        if reason is None:
            selected.add(members[0].id)
        else:
            ledger.append(
                {
                    "pixel_sha256": pixels,
                    "sample_ids": sorted(s.id for s in members),
                    "annotation_variants": len(variants),
                    "reason": reason,
                }
            )
    return selected, ledger


def _reason(
    pixels: str, members: list[Sample], variants: set[str], invalid: set[str]
) -> str | None:
    if pixels in invalid:
        return "invalid_source_annotation_alias"
    if len(members) == 1:
        return None
    return "divergent_annotation_aliases" if len(variants) > 1 else "redundant_identical_aliases"


def prepare(manifests: tuple[Path, ...], source_dir: Path, output: Path) -> str:
    output = output_namespace(output, source_dir)
    for path in manifests:
        output_namespace(output, path.parent)
    native = inventory(source_dir)
    samples, assets, pins = _verified(manifests, native)
    invalid = [record for record in native.values() if record.error is not None]
    selected, ledger = select_primary(samples, invalid_pixels={r.pixel_sha256 for r in invalid})
    updated = [_copy(sample, assets[sample.id], output, selected, ledger) for sample in samples]
    all_raw = manifest_bytes(updated)
    publish(output / "all-records.jsonl", all_raw)
    primary = [sample for sample in updated if sample.id in selected]
    provenance = _report(native, updated, primary, ledger, invalid, pins)
    provenance["all_records_manifest_sha256"] = digest(all_raw)
    quarantine_raw = json_bytes(
        {
            "alias_groups": ledger,
            "invalid_native_records": [_invalid_record(record) for record in invalid],
        }
    )
    provenance["quarantine_sha256"] = digest(quarantine_raw)
    provenance["sample_schema_versions"] = sorted({sample.schema_version for sample in updated})
    publish(output / "quarantine.json", quarantine_raw)
    return close_batch(output, primary, provenance)


def _verified(
    manifests: tuple[Path, ...], native: dict[str, NativeImage]
) -> tuple[list[Sample], dict[str, Path], list[dict]]:
    samples: list[Sample] = []
    assets: dict[str, Path] = {}
    pins = []
    for manifest in manifests:
        raw = manifest.read_bytes()
        pins.append({"file": str(manifest.resolve()), "sha256": digest(raw)})
        for line in raw.splitlines():
            sample = Sample.model_validate_json(line)
            if sample.id in assets:
                raise ValueError("Repeated source record in quality inputs")
            assets[sample.id] = _verify_record(sample, native, manifest.parent)
            samples.append(sample)
    _complete(assets, native)
    return samples, assets, pins


def _verify_record(sample: Sample, native: dict[str, NativeImage], root: Path) -> Path:
    expected = native.get(sample.id)
    if expected is None:
        raise ValueError("Unknown ImageWeeds source record")
    _check_source(sample, expected)
    _, pixels = verified_asset(sample, root)
    if pixels != expected.pixel_sha256:
        raise ValueError("Canonical pixels differ from pinned native image")
    return (root / sample.media.uri).resolve()


def _complete(assets: dict[str, Path], native: dict[str, NativeImage]) -> None:
    expected_ids = {key for key, row in native.items() if row.error is None}
    if set(assets) != expected_ids:
        raise ValueError("Quality gate requires all geometry-eligible native records")


def _check_source(sample: Sample, expected: NativeImage) -> None:
    if (sample.media.format, sample.context.get("format_profile")) != ("PNG", "lossless-rgb-png"):
        raise ValueError("Primary source quality requires the lossless RGB PNG profile")
    actual = (
        sample.snapshot,
        sample.rights,
        sample.annotations,
        sample.context.get("original_encoded_sha256"),
        sample.context.get("native_annotations_sha256"),
        sample.context.get("decoded_pixel_sha256"),
    )
    reference = (
        expected.snapshot,
        expected.rights,
        expected.annotations,
        expected.encoded_sha256,
        expected.annotation_source_sha256,
        expected.pixel_sha256,
    )
    if actual != reference:
        raise ValueError("Source labels, rights or identity differ from pinned publisher evidence")
    if sample.review_history or any(
        (c.status, c.origin, c.review, c.author, c.reviewers)
        != ("unknown", "source", "unreviewed", None, ())
        for c in sample.completeness
    ):
        raise ValueError("Source quality gate does not admit new gold or completeness claims")


def _copy(
    sample: Sample, source: Path, output: Path, selected: set[str], ledger: list[dict]
) -> Sample:
    uri = _copy_asset(sample, source, output)
    context = dict(sample.context)
    group = next((row for row in ledger if sample.id in row["sample_ids"]), None)
    if sample.id not in selected and group is None:
        raise ValueError("Missing source quarantine reason")
    status = "eligible" if group is None else group["reason"]
    context.update(
        primary_quality=status,
        primary_quality_policy="source-alias-quarantine-v1",
        alias_count=str(len(group["sample_ids"])) if group else "1",
    )
    groups = dict(sample.groups, decoded_asset="sha256:" + context["decoded_pixel_sha256"])
    return revise_sample(
        sample,
        media=Media(
            uri=uri,
            sha256=sample.media.sha256,
            width=sample.media.width,
            height=sample.media.height,
            format="PNG",
        ),
        groups=groups,
        context=context,
    )


def _copy_asset(sample: Sample, source: Path, output: Path) -> str:
    with source.open("rb") as stream:
        raw = stream.read(160_000_001)
    if len(raw) > 160_000_000 or digest(raw) != sample.media.sha256:
        raise ValueError("Verified canonical bytes changed before publication")
    validate_rgb_png(raw)
    uri = f"images/{sample.media.sha256}.png"
    publish(output / uri, raw)
    return uri


def _invalid_record(record: NativeImage) -> dict:
    return {
        "sample_id": record.sample_id,
        "encoded_sha256": record.encoded_sha256,
        "pixel_sha256": record.pixel_sha256,
        "annotation_count": record.annotation_count,
        "reason": record.error,
    }


def _report(
    native: dict[str, NativeImage],
    samples: list[Sample],
    primary: list[Sample],
    ledger: list[dict],
    invalid: list[NativeImage],
    pins: list[dict],
) -> dict:
    return {
        "policy": "source-alias-quarantine-v1",
        "input_manifests": pins,
        "raw_source_records": len(native),
        "raw_unique_pixels": len({r.pixel_sha256 for r in native.values()}),
        "geometry_eligible_records": len(samples),
        "geometry_eligible_unique_pixels": len(
            {s.context["decoded_pixel_sha256"] for s in samples}
        ),
        "invalid_source_records": len(invalid),
        "quarantined_alias_groups": len(ledger),
        "quarantined_alias_records": sum(len(row["sample_ids"]) for row in ledger),
        "primary_records": len(primary),
        "primary_boxes": sum(len(s.annotations) for s in primary),
        "primary_unique_pixels": len({s.context["decoded_pixel_sha256"] for s in primary}),
        "annotation_policy": "No annotation union or representative selection; "
        "all alias groups withheld",
        "interpretation": "Publisher source labels, unreviewed; "
        "not expert NZ gold or exhaustive negatives",
    }
