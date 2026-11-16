"""Frozen gold releases include policy, scoped negatives and their original review history."""

import hashlib
import json
from pathlib import Path

import pytest
from PIL import Image
from test_gold_policy import WHEN, policy, specimen

from weedz.contract import Sample
from weedz.release import ReleaseSpec, build_release, read_release, write_release


def reviewed_samples() -> list[Sample]:
    result = []
    for number, site in enumerate(("a", "b", "c"), start=1):
        value = specimen(negative=number == 2).model_dump(mode="json")
        identifier, sha = f"test:{number}", str(number) * 64
        value.update(
            id=identifier,
            source_id=str(number),
            media=value["media"] | {"sha256": sha, "uri": f"images/{number}.png"},
            groups={"site": site, "observer": f"observer:{number}"},
        )
        for coverage in value["completeness"]:
            coverage["media_sha256"] = sha
        for event in value["review_history"]:
            event.update(sample_id=identifier, media_sha256=sha)
            if event["dimension"] == "completeness":
                event["payload"]["claim"]["media_sha256"] = sha
        result.append(Sample.model_validate(value))
    return result


def materialize(root: Path) -> list[Sample]:
    root.mkdir()
    samples = []
    for number, sample in enumerate(reviewed_samples(), start=1):
        path = root / sample.media.uri
        path.parent.mkdir(exist_ok=True)
        Image.new("RGB", (40, 30), (number, 40, 60)).save(path)
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        value = sample.model_dump(mode="json")
        value["media"]["sha256"] = sha
        for claim in value["completeness"]:
            claim["media_sha256"] = sha
        for event in value["review_history"]:
            event["media_sha256"] = sha
            if event["dimension"] == "completeness":
                event["payload"]["claim"]["media_sha256"] = sha
        samples.append(Sample.model_validate(value))
    return samples


def spec(**fields: object) -> ReleaseSpec:
    return ReleaseSpec.model_validate(
        {
            "name": "checked-fixture",
            "task": "detection",
            "protocol": "Synthetic gold workflow test, not actual NZ verification.",
            "split": {
                "kind": "explicit",
                "group_key": "site",
                "assignment": {"a": "fit", "b": "validation", "c": "test"},
            },
            "review_policy": policy().model_dump(mode="json"),
            "rights_profile": "public-cc0-by",
            **fields,
        }
    )


def test_policy_promotes_samples_and_keeps_the_explicit_negative_in_a_release(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    samples = materialize(source)
    release = write_release(
        tmp_path / "release", samples, spec(), assets_root=source, recorded_at=WHEN
    )
    verified, frozen = read_release(tmp_path / "release")
    assert verified.id == release.id
    assert all("detection" in sample.tasks for sample in frozen)
    assert all(sample.tasks == frozenset({"inference"}) for sample in samples)
    assert verified.review_policy == policy()
    assert verified.rights_profile == "public-cc0-by"
    assert verified.metadata_licenses == ["cc-by-4.0"]
    assert verified.counts["validation"].checked_negatives == {"taxon:Ulex europaeus": 1}
    assert frozen[1].annotations == ()
    assert frozen[1].review_history == samples[1].review_history


def test_explicit_noncommercial_scope_preserves_both_source_licences() -> None:
    samples = reviewed_samples()
    value = samples[0].model_dump(mode="json")
    value["rights"]["metadata_license"] = "cc-by-nc-4.0"
    samples[0] = Sample.model_validate(value)
    with pytest.raises(ValueError, match="licence"):
        build_release(samples, spec(), recorded_at=WHEN)
    record, kept = build_release(
        samples, spec(rights_profile="noncommercial-cc0-by-nc"), recorded_at=WHEN
    )
    assert record.metadata_licenses == ["cc-by-4.0", "cc-by-nc-4.0"]
    assert kept[0].rights.metadata_license == "cc-by-nc-4.0"


def test_a_gold_policy_cannot_be_applied_to_a_non_detection_task() -> None:
    with pytest.raises(ValueError, match="detection"):
        build_release(reviewed_samples(), spec(task="inference"), recorded_at=WHEN)


def test_required_gold_groups_must_be_separated_even_if_not_in_legacy_separate() -> None:
    samples = reviewed_samples()
    value = samples[1].model_dump(mode="json")
    value["groups"]["observer"] = "observer:1"
    samples[1] = Sample.model_validate(value)
    with pytest.raises(ValueError, match="observer.*spans"):
        build_release(samples, spec(), recorded_at=WHEN)


def test_changing_only_the_review_policy_changes_the_frozen_release_id() -> None:
    samples = reviewed_samples()
    first, _ = build_release(samples, spec(), recorded_at=WHEN)
    second, _ = build_release(
        samples, spec(review_policy=policy(independent=False).model_dump()), recorded_at=WHEN
    )
    assert first.id != second.id


def test_policy_and_history_tampering_are_detected_on_read(tmp_path: Path) -> None:
    directory = tmp_path / "release"
    source = tmp_path / "source"
    write_release(directory, materialize(source), spec(), assets_root=source, recorded_at=WHEN)
    value = json.loads((directory / "release.json").read_text())
    value["review_policy"]["independent"] = False
    (directory / "release.json").write_text(json.dumps(value))
    with pytest.raises(ValueError, match="content"):
        read_release(directory)


def test_reading_rechecks_evidence_against_even_a_self_consistent_policy_record(
    tmp_path: Path,
) -> None:
    from weedz.release import Release

    source, directory = tmp_path / "source", tmp_path / "release"
    original = write_release(directory, materialize(source), spec(), assets_root=source)
    changed = Release.model_validate(
        original.model_dump(mode="json")
        | {"review_policy": policy(min_reviewers=2).model_dump(mode="json")}
    )
    changed = changed.model_copy(update={"id": changed.content_id()})
    (directory / "release.json").write_text(changed.model_dump_json())
    with pytest.raises(ValueError, match="reviewer"):
        read_release(directory)
