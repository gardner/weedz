"""A release is visible only when its manifest, history and pinned assets are complete."""

import hashlib
from pathlib import Path

import pytest
from PIL import Image
from test_gold_policy import WHEN
from test_gold_release import materialize, reviewed_samples, spec
from test_release import sites
from test_release import spec as legacy_spec

import weedz.release as releases
from weedz.contract import ReviewEvent, Sample


def test_gold_writer_requires_a_closed_asset_source(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="assets_root"):
        releases.write_release(tmp_path / "release", reviewed_samples(), spec())
    assert not (tmp_path / "release").exists()


def test_released_history_and_assets_survive_removing_the_source(tmp_path: Path) -> None:
    source, output = tmp_path / "source", tmp_path / "release"
    samples = materialize(source)
    mask = source / "masks" / "historical.png"
    mask.parent.mkdir()
    Image.new("L", (40, 30), 255).save(mask)
    mask_sha = hashlib.sha256(mask.read_bytes()).hexdigest()
    assert samples[0].media.sha256 is not None
    event = ReviewEvent(
        id="old:revision",
        sample_id=samples[0].id,
        media_sha256=samples[0].media.sha256,
        origin="reviewer",
        actor="reviewer:old",
        recorded_at=WHEN,
        action="completed_human_revision",
        dimension="annotation",
        payload={
            "annotations": (
                {"id": "old:mask", "mask_uri": "masks/historical.png", "mask_sha256": mask_sha},
            )
        },
    )
    value = samples[0].model_dump(mode="json")
    value["review_history"].append(event.model_dump(mode="json"))
    samples[0] = Sample.model_validate(value)
    record = releases.write_release(output, samples, spec(), assets_root=source, recorded_at=WHEN)
    expected = {sample.media.uri: sample.media.sha256 for sample in samples}
    expected["masks/historical.png"] = mask_sha
    assert record.assets == expected
    assert record.release_format == 2
    source.rename(tmp_path / "removed-source")
    frozen, loaded = releases.read_release(output)
    assert frozen == record
    assert loaded[0].review_history[-1] == event
    assert all(
        hashlib.sha256((output / uri).read_bytes()).hexdigest() == sha
        for uri, sha in expected.items()
    )


@pytest.mark.parametrize("empty_existing", [False, True])
def test_failure_before_record_write_does_not_publish_a_partial_release(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, empty_existing: bool
) -> None:
    output = tmp_path / "release"
    if empty_existing:
        output.mkdir()

    def interrupted(*_args: object) -> None:
        raise OSError("injected full disk")

    monkeypatch.setattr(releases, "_write_record", interrupted)
    with pytest.raises(OSError, match="full disk"):
        releases.write_release(output, sites("a", "c", "d"), legacy_spec())
    assert not output.exists() or list(output.iterdir()) == []
    assert not list(tmp_path.glob(".release-pending-*"))


def test_corrupt_asset_is_refused_before_publication_and_after_tampering(tmp_path: Path) -> None:
    source, output = tmp_path / "source", tmp_path / "release"
    samples = materialize(source)
    photo = source / samples[0].media.uri
    original = photo.read_bytes()
    photo.write_bytes(b"changed source")
    with pytest.raises(ValueError, match="checksum"):
        releases.write_release(output, samples, spec(), assets_root=source)
    assert not output.exists()
    photo.write_bytes(original)
    releases.write_release(output, samples, spec(), assets_root=source)
    (output / samples[0].media.uri).write_bytes(b"changed release")
    with pytest.raises(ValueError, match="checksum"):
        releases.read_release(output)


@pytest.mark.parametrize("uri", ["../private.png", "/private.png", "images/../../private.png"])
def test_asset_paths_cannot_escape_the_source_or_release(tmp_path: Path, uri: str) -> None:
    source = tmp_path / "source"
    samples = materialize(source)
    value = samples[0].model_dump(mode="json")
    value["media"]["uri"] = uri
    samples[0] = Sample.model_validate(value)
    with pytest.raises(ValueError, match="asset path"):
        releases.write_release(tmp_path / "release", samples, spec(), assets_root=source)
    assert not (tmp_path / "release").exists()


def test_symlink_escape_is_refused(tmp_path: Path) -> None:
    source = tmp_path / "source"
    samples = materialize(source)
    photo = source / samples[0].media.uri
    outside = tmp_path / "outside.png"
    photo.rename(outside)
    photo.symlink_to(outside)
    with pytest.raises(ValueError, match="asset path"):
        releases.write_release(tmp_path / "release", samples, spec(), assets_root=source)


def test_source_and_review_mask_references_need_pinned_digests(tmp_path: Path) -> None:
    source = tmp_path / "source"
    samples = materialize(source)
    value = samples[0].model_dump(mode="json")
    value["context"]["assessed_mask_uri"] = "masks/assessed.png"
    samples[0] = Sample.model_validate(value)
    with pytest.raises(ValueError, match="SHA-256"):
        releases.write_release(tmp_path / "release", samples, spec(), assets_root=source)
    assert not (tmp_path / "release").exists()


def test_a_destination_populated_during_staging_is_preserved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "release"
    write_record = releases._write_record

    def another_writer(directory: Path, release: releases.Release) -> None:
        write_record(directory, release)
        output.mkdir()
        (output / "other.txt").write_text("preserve concurrent output")

    monkeypatch.setattr(releases, "_write_record", another_writer)
    with pytest.raises(ValueError, match="empty"):
        releases.write_release(output, sites("a", "c", "d"), legacy_spec())
    assert [path.name for path in output.iterdir()] == ["other.txt"]
    assert not list(tmp_path.glob(".release-pending-*"))


def test_asset_size_budget_failure_cleans_staging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import weedz.release_assets as assets

    source = tmp_path / "source"
    samples = materialize(source)
    monkeypatch.setattr(assets, "MAX_ASSET_BYTES", 1)
    with pytest.raises(ValueError, match="byte budget"):
        releases.write_release(tmp_path / "release", samples, spec(), assets_root=source)
    assert not (tmp_path / "release").exists()
    assert not list(tmp_path.glob(".release-pending-*"))


def test_materialized_release_assets_stay_outside_git(tmp_path: Path) -> None:
    source = tmp_path / "source"
    samples = materialize(source)
    repository = tmp_path / "repository"
    (repository / ".git").mkdir(parents=True)
    with pytest.raises(ValueError, match="outside Git"):
        releases.write_release(repository / "release", samples, spec(), assets_root=source)
    assert not (repository / "release").exists()


def claim_only_history(source: Path, samples: list[Sample]):
    from weedz.contract import Annotation, revise_sample

    assert samples[0].media.sha256 is not None
    mask = source / "masks" / "old-targeted-claim.png"
    mask.parent.mkdir(exist_ok=True)
    Image.new("L", (40, 30), 255).save(mask)
    sha = hashlib.sha256(mask.read_bytes()).hexdigest()
    note = Annotation(
        id="old:targeted-mask",
        supervision="dense_mask",
        taxon="Ulex europaeus",
        label="present",
        origin="reviewer",
        review="accepted",
        author="reviewer:old",
        mask_uri="masks/old-targeted-claim.png",
        mask_sha256=sha,
    )
    event = ReviewEvent(
        id="old:targeted-acceptance",
        sample_id=samples[0].id,
        media_sha256=samples[0].media.sha256,
        origin="reviewer",
        actor="reviewer:old",
        recorded_at=WHEN,
        action="accepted",
        dimension="identity",
        annotation_id=note.id,
        payload={"claim": note.model_dump(mode="json")},
    )
    samples[0] = revise_sample(samples[0], review_history=[*samples[0].review_history, event])
    assert all(annotation.id != note.id for annotation in samples[0].annotations)
    return mask, event, sha


def test_removed_mask_referenced_only_by_targeted_claim_is_closed(tmp_path: Path):
    source, output = tmp_path / "source", tmp_path / "release"
    samples = materialize(source)
    _, event, sha = claim_only_history(source, samples)
    record = releases.write_release(output, samples, spec(), assets_root=source, recorded_at=WHEN)
    assert record.assets is not None
    assert record.assets["masks/old-targeted-claim.png"] == sha
    assert hashlib.sha256((output / "masks/old-targeted-claim.png").read_bytes()).hexdigest() == sha
    source.rename(tmp_path / "removed-source")
    loaded, frozen = releases.read_release(output)
    assert loaded == record and frozen[0].review_history[-1] == event


@pytest.mark.parametrize("failure", ["missing", "corrupt"])
def test_invalid_targeted_historical_mask_refuses_atomic_release(tmp_path: Path, failure: str):
    source, output = tmp_path / "source", tmp_path / "release"
    samples = materialize(source)
    mask, _, _ = claim_only_history(source, samples)
    if failure == "missing":
        mask.unlink()
    else:
        mask.write_bytes(b"corrupt historical mask")
    error = FileNotFoundError if failure == "missing" else ValueError
    with pytest.raises(error):
        releases.write_release(output, samples, spec(), assets_root=source, recorded_at=WHEN)
    assert not output.exists()
    assert not list(tmp_path.glob(".release-pending-*"))
