"""Frozen releases split whole groups, protect holdouts and record test freshness."""

import json
from pathlib import Path
from typing import Any

import pytest

from weedz.contract import Annotation, Geography, Media, Rights, Sample
from weedz.release import (
    ExplicitSplit,
    HashSplit,
    ReleaseSpec,
    build_release,
    read_release,
    record_test_status,
    write_release,
)

RIGHTS = Rights(
    media_license="cc-by",
    metadata_license="cc0",
    attribution="(c) Ana",
    license_source="https://example.org",
)
WHEN = "2026-11-14T00:00:00+00:00"


def point(label: str = "present", **fields: Any) -> Annotation:
    return Annotation.model_validate(
        {
            "id": "survey",
            "supervision": "surveyed_point",
            "taxon": "Euphorbia esula",
            "label": label,
            "point": (1, 1),
            "origin": "source",
        }
        | fields
    )


def sample(
    number: int,
    site: str,
    *,
    label: str = "present",
    latitude: float | None = None,
    **fields: Any,
) -> Sample:
    geography = None if latitude is None else Geography(latitude=latitude, longitude=0.0)
    return Sample.model_validate(
        {
            "id": f"test:{number}",
            "source": "test",
            "source_id": str(number),
            "snapshot": "rev-1",
            "rights": RIGHTS,
            "media": Media(uri=f"https://example.org/{number}.png", width=3, height=3),
            "geography": geography,
            "groups": {"site": site},
            "tasks": ["point_classification"],
            "annotations": [point(label)],
        }
        | fields
    )


def sites(*names: str, per_site: int = 2) -> list[Sample]:
    """Each site has a present and an absent point; sites are 1 degree apart."""
    return [
        sample(
            index * 10 + offset,
            name,
            label=("present", "absent")[offset % 2],
            latitude=float(index),
        )
        for index, name in enumerate(names)
        for offset in range(per_site)
    ]


EXPLICIT = ExplicitSplit(
    group_key="site", assignment={"a": "fit", "b": "fit", "c": "validation", "d": "test"}
)


def spec(**fields: Any) -> ReleaseSpec:
    return ReleaseSpec.model_validate(
        {
            "name": "toy",
            "task": "point_classification",
            "protocol": "Fit on fit, select on validation, evaluate test once.",
            "split": EXPLICIT,
        }
        | fields
    )


def test_explicit_assignment_keeps_whole_groups_together() -> None:
    release, kept = build_release(sites("a", "b", "c", "d"), spec(), recorded_at=WHEN)
    assert release.splits["fit"].groups == ["a", "b"]
    assert release.splits["fit"].samples == ["test:0", "test:1", "test:10", "test:11"]
    assert release.splits["validation"].samples == ["test:20", "test:21"]
    assert release.splits["test"].samples == ["test:30", "test:31"]
    assert release.excluded == {}
    assert [sample.id for sample in kept] == sorted(sample.id for sample in kept)
    assert release.counts["fit"].labels == {"absent": 2, "present": 2}
    assert release.counts["test"].reviews == {"unreviewed": 2}
    assert release.counts["test"].taxa == {"Euphorbia esula": 2}
    assert release.contract_schema_version == 1
    assert release.source_snapshots == {"test": ["rev-1"]}
    assert release.licenses == ["cc-by"]


def test_an_unassigned_group_is_refused_rather_than_guessed() -> None:
    with pytest.raises(ValueError, match="no split for site 'e'"):
        build_release(sites("a", "c", "d", "e"), spec(), recorded_at=WHEN)


def test_hash_split_is_stable_and_depends_on_its_recorded_seed() -> None:
    names = [f"s{index}" for index in range(40)]
    rule = HashSplit(
        group_key="site", seed="7", fractions={"fit": 0.6, "validation": 0.2, "test": 0.2}
    )
    first, _ = build_release(sites(*names), spec(split=rule), recorded_at=WHEN)
    again, _ = build_release(list(reversed(sites(*names))), spec(split=rule), recorded_at=WHEN)
    reseeded, _ = build_release(
        sites(*names), spec(split=rule.model_copy(update={"seed": "8"})), recorded_at=WHEN
    )
    assert first.splits == again.splits and first.id == again.id
    assert first.splits != reseeded.splits
    assert all(first.splits[name].groups for name in ("fit", "validation", "test"))
    assert first.split.model_dump()["seed"] == "7"


def test_hash_fractions_must_sum_to_one() -> None:
    with pytest.raises(ValueError, match="sum to 1"):
        HashSplit(
            group_key="site", seed="1", fractions={"fit": 0.5, "validation": 0.2, "test": 0.2}
        )


def test_a_sample_without_the_split_group_is_ineligible() -> None:
    samples = [*sites("a", "c", "d"), sample(99, "a", groups={})]
    with pytest.raises(ValueError, match="test:99 has no 'site' group"):
        build_release(samples, spec(), recorded_at=WHEN)


def test_a_sample_that_did_not_declare_the_task_is_ineligible() -> None:
    samples = [*sites("a", "c", "d"), sample(99, "a", tasks=["inference"], annotations=[])]
    with pytest.raises(ValueError, match="test:99 does not support point_classification"):
        build_release(samples, spec(), recorded_at=WHEN)


def test_a_declared_group_spanning_splits_is_refused() -> None:
    samples = sites("a", "c", "d")
    samples[0] = samples[0].model_copy(update={"groups": {"site": "a", "visit": "v1"}})
    samples[-1] = samples[-1].model_copy(update={"groups": {"site": "d", "visit": "v1"}})
    with pytest.raises(ValueError, match="visit 'v1' spans fit and test"):
        build_release(samples, spec(separate=["site", "visit"]), recorded_at=WHEN)


def test_derivatives_of_one_parent_cannot_span_splits() -> None:
    samples = sites("a", "c", "d")
    samples[0] = samples[0].model_copy(update={"parent_id": "test:raster"})
    samples[-1] = samples[-1].model_copy(update={"parent_id": "test:raster"})
    with pytest.raises(ValueError, match="parent 'test:raster' spans fit and test"):
        build_release(samples, spec(), recorded_at=WHEN)


def test_a_split_without_both_labels_lacks_point_classification_evidence() -> None:
    samples = [*sites("a", "c"), sample(30, "d", label="present", latitude=3.0)]
    with pytest.raises(ValueError, match="test lacks absent surveyed_point evidence"):
        build_release(samples, spec(), recorded_at=WHEN)


def test_predictions_and_uncertain_labels_are_not_split_evidence() -> None:
    samples = sites("a", "c", "d")
    uncertain = point("absent", review="uncertain")
    model = point("absent", origin="model", model="m")
    # The sample keeps its declared task through its present point; the extra
    # annotations must not count as the split's absent evidence.
    samples[-1] = samples[-1].model_copy(
        update={"annotations": (point("present"),), "groups": {"site": "d"}}
    )
    samples[-2] = samples[-2].model_copy(
        update={
            "annotations": (
                point("present"),
                uncertain.model_copy(update={"id": "u"}),
                model.model_copy(update={"id": "m"}),
            )
        }
    )
    with pytest.raises(ValueError, match="test lacks absent surveyed_point evidence"):
        build_release(samples, spec(), recorded_at=WHEN)


def test_an_empty_split_is_refused() -> None:
    with pytest.raises(ValueError, match="validation is empty"):
        build_release(sites("a", "d"), spec(), recorded_at=WHEN)


def close_sites() -> list[Sample]:
    """Fit site 'a' and validation site 'c' each have one point 1 m from the next split."""
    metre = 1 / 111_195  # degrees of latitude per metre on the release's sphere
    return [
        sample(0, "a", label="present", latitude=-1.0),
        sample(1, "a", label="absent", latitude=-1.0),
        sample(2, "a", label="present", latitude=1.0 - metre),  # 1 m from validation
        sample(20, "c", label="present", latitude=1.0),
        sample(21, "c", label="absent", latitude=1.0),
        sample(22, "c", label="absent", latitude=2.0 - metre),  # 1 m from test
        sample(30, "d", label="present", latitude=2.0),
        sample(31, "d", label="absent", latitude=2.0),
    ]


def test_buffer_protects_test_then_validation_and_records_exclusions() -> None:
    release, kept = build_release(close_sites(), spec(buffer_m=2.0), recorded_at=WHEN)
    assert release.excluded == {
        "test:22": "within 2.0 m of test",
        "test:2": "within 2.0 m of validation",
    }
    assert "test:22" not in {sample.id for sample in kept}
    assert release.splits["test"].samples == ["test:30", "test:31"]
    assert release.buffer is not None and release.buffer.unbuffered == []


def test_a_smaller_buffer_excludes_nothing() -> None:
    release, _ = build_release(close_sites(), spec(buffer_m=0.5), recorded_at=WHEN)
    assert release.excluded == {}


def test_known_coordinate_uncertainty_widens_the_buffer() -> None:
    samples = close_sites()
    samples[2] = samples[2].model_copy(
        update={"geography": Geography(latitude=0.0, longitude=0.0, uncertainty_m=200_000)}
    )
    release, _ = build_release(samples, spec(buffer_m=0.5), recorded_at=WHEN)
    assert release.excluded == {"test:2": "within 0.5 m of validation"}


def test_unlocated_and_obscured_samples_are_recorded_as_unbuffered() -> None:
    samples = close_sites()
    samples[0] = samples[0].model_copy(update={"geography": None})
    obscured = Geography(latitude=-1.0, longitude=0.0, privacy="obscured")
    samples[1] = samples[1].model_copy(update={"geography": obscured})
    release, _ = build_release(samples, spec(buffer_m=0.5), recorded_at=WHEN)
    assert release.buffer is not None
    assert release.buffer.unbuffered == ["test:0", "test:1"]
    assert "unknown" in release.buffer.basis


def test_a_release_without_a_buffer_says_so() -> None:
    release, _ = build_release(close_sites(), spec(), recorded_at=WHEN)
    assert release.buffer is None and release.excluded == {}


def test_a_written_release_reads_back_and_rebuilds_identically(tmp_path: Path) -> None:
    first = write_release(tmp_path / "one", sites("a", "b", "c", "d"), spec(), recorded_at=WHEN)
    shuffled = list(reversed(sites("a", "b", "c", "d")))
    second = write_release(tmp_path / "two", shuffled, spec(), recorded_at=WHEN)
    assert first.id == second.id and first.id.startswith("toy-")
    assert (tmp_path / "one" / "samples.jsonl").read_bytes() == (
        tmp_path / "two" / "samples.jsonl"
    ).read_bytes()
    release, samples = read_release(tmp_path / "one")
    assert release == first and len(samples) == 8
    assert release.manifest_sha256 == first.manifest_sha256
    assert release.test_status == "fresh"
    assert release.test_history[0].recorded_at == WHEN


def test_writing_refuses_a_non_empty_directory(tmp_path: Path) -> None:
    (tmp_path / "old.txt").write_text("keep")
    with pytest.raises(ValueError, match="must be empty"):
        write_release(tmp_path, sites("a", "c", "d"), spec(), recorded_at=WHEN)


def test_reading_detects_an_altered_manifest(tmp_path: Path) -> None:
    write_release(tmp_path, sites("a", "c", "d"), spec(), recorded_at=WHEN)
    manifest = tmp_path / "samples.jsonl"
    manifest.write_bytes(manifest.read_bytes().replace(b'"present"', b'"absent"', 1))
    with pytest.raises(ValueError, match="checksum"):
        read_release(tmp_path)


def test_reading_detects_an_edited_split(tmp_path: Path) -> None:
    write_release(tmp_path, sites("a", "c", "d"), spec(), recorded_at=WHEN)
    path = tmp_path / "release.json"
    payload = json.loads(path.read_text())
    payload["splits"]["test"]["samples"].append("test:0")
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="does not match its content"):
        read_release(tmp_path)


def test_test_status_only_advances_and_keeps_its_history(tmp_path: Path) -> None:
    write_release(tmp_path, sites("a", "c", "d"), spec(), recorded_at=WHEN)
    later = "2026-11-15T00:00:00+00:00"
    release = record_test_status(tmp_path, "inspected", note="reported", recorded_at=later)
    assert release.test_status == "inspected"
    assert [entry.status for entry in release.test_history] == ["fresh", "inspected"]
    with pytest.raises(ValueError, match="cannot return from inspected to fresh"):
        record_test_status(tmp_path, "fresh", note="oops", recorded_at=later)
    assert read_release(tmp_path)[0].test_status == "inspected"


def test_test_status_changes_do_not_change_the_release_id(tmp_path: Path) -> None:
    created = write_release(tmp_path, sites("a", "c", "d"), spec(), recorded_at=WHEN)
    used = record_test_status(tmp_path, "used_for_selection", note="tuned", recorded_at=WHEN)
    assert used.id == created.id


def test_a_hand_edited_history_that_regresses_is_refused(tmp_path: Path) -> None:
    write_release(tmp_path, sites("a", "c", "d"), spec(test_status="inspected"), recorded_at=WHEN)
    path = tmp_path / "release.json"
    payload = json.loads(path.read_text())
    payload["test_history"].append({"status": "fresh", "recorded_at": WHEN, "note": "reset"})
    payload["test_status"] = "fresh"
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="cannot return"):
        read_release(tmp_path)


def test_a_release_manifest_cannot_point_outside_its_directory(tmp_path: Path) -> None:
    write_release(tmp_path / "release", sites("a", "c", "d"), spec(), recorded_at=WHEN)
    path = tmp_path / "release" / "release.json"
    payload = json.loads(path.read_text())
    payload["manifest"] = "../elsewhere.jsonl"
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="samples.jsonl"):
        read_release(tmp_path / "release")
