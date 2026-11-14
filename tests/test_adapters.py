"""Adapters map existing records into the contract without changing their meaning."""

from pathlib import Path

import pytest
from test_discovery import observation
from test_findings import finding, store_with_photo

from weedz.adapters import leafy_spurge_samples, pilot_samples
from weedz.contract import UnsupportedTask, require_task
from weedz.dataset import LICENSE, REVISION, read_observations
from weedz.discovery.judgements import Judgement
from weedz.discovery.records import Finding
from weedz.discovery.source import photo_from_observation
from weedz.manifest import read_manifest, write_manifest
from weedz.provenance import checksum, record_dataset


def test_leafy_spurge_points_become_surveyed_point_supervision(dataset_dir: Path) -> None:
    record_dataset(dataset_dir)
    samples = leafy_spurge_samples(dataset_dir)
    observations = read_observations(dataset_dir)
    assert len(samples) == len(observations) == 48
    first, row = samples[0], observations[0]
    assert first.id == f"leafy-spurge:{row.sample_id}" and first.snapshot == REVISION
    assert first.rights.media_license == first.rights.metadata_license == LICENSE
    assert first.media.sha256 == checksum(row.image_path)
    assert (first.media.width, first.media.height) == (39, 39)
    assert (first.view, first.ground and first.ground.gsd_m) == ("nadir", 0.013)
    assert first.geography and first.geography.uncertainty_m is None
    assert first.groups == {"survey_cluster": "0", "source_split": "train"}
    assert first.tasks == {"point_classification"}
    (point,) = first.annotations
    assert (point.supervision, point.taxon, point.point) == (
        "surveyed_point",
        "Euphorbia esula",
        (19.5, 19.5),
    )
    assert (point.origin, point.review) == ("source", "unreviewed")
    labels = {sample.annotations[0].label for sample in samples}
    assert labels == {"present", "absent"}
    with pytest.raises(UnsupportedTask):
        require_task(first, "segmentation")


def test_leafy_spurge_adapter_refuses_altered_source_bytes(dataset_dir: Path) -> None:
    record_dataset(dataset_dir)
    image = read_observations(dataset_dir)[0].image_path
    image.write_bytes(image.read_bytes() + b"x")
    with pytest.raises(ValueError, match="checksum"):
        leafy_spurge_samples(dataset_dir)


def test_pilot_photos_become_image_samples_without_plant_supervision(tmp_path: Path) -> None:
    store, photo_id = store_with_photo(tmp_path)
    (sample,) = pilot_samples(store, "run")
    assert sample.id == f"inaturalist:{photo_id}" and sample.snapshot == "run"
    assert sample.tasks == {"inference"}
    assert sample.original_label == "Turdus merula"
    assert sample.context["cohort"] == "incidental"
    assert sample.rights.media_license == "cc-by-nc"
    assert sample.rights.license_source == "https://www.inaturalist.org/observations/100"
    assert sample.geography and sample.geography.privacy == "obscured"
    # iNaturalist displaces obscured points; the observer's GPS accuracy would look precise.
    assert sample.geography.uncertainty_m is None
    assert (sample.media.width, sample.media.height, sample.media.sha256) == (400, 300, None)
    assert sample.groups == {"observation": "100"}
    (suggestion,) = sample.annotations
    assert (suggestion.origin, suggestion.taxon, suggestion.review) == (
        "model",
        "Clematis vitalba",
        "unreviewed",
    )
    assert not suggestion.supervises()


def test_pilot_findings_become_reviewed_annotations_with_provenance(tmp_path: Path) -> None:
    store, photo_id = store_with_photo(tmp_path)
    store.review("run", photo_id, "rejected", "not clematis", "Ana")
    box = Finding.model_validate(finding(box=[10, 20, 110, 220], note="flowering"))
    store.finding("run", photo_id, box)
    store.finding("run", photo_id, Finding.model_validate(finding(species=None, other_taxon="x")))
    gorse = store.findings("run", photo_id)[0]["id"]
    for reviewer in ("Ana", "Ben"):
        judgement = {"finding_id": gorse, "dimension": "identity", "value": "confirmed"}
        store.judgement(
            "run", photo_id, Judgement.model_validate(judgement | {"reviewer": reviewer})
        )
    (sample,) = pilot_samples(store, "run")
    suggestion, boxed, unboxed = sample.annotations
    assert (suggestion.review, suggestion.reviewer) == ("rejected", "Ana")
    assert (boxed.supervision, boxed.box, boxed.taxon) == (
        "box",
        (10, 20, 110, 220),
        "Ulex europaeus",
    )
    assert (boxed.origin, boxed.reviewer, boxed.note, boxed.review) == (
        "reviewer",
        "Ana",
        "flowering",
        "accepted",
    )
    assert boxed.recorded_at and boxed.id == f"addition-{gorse}"
    assert (unboxed.supervision, unboxed.taxon, unboxed.review) == (
        "image_class",
        "x",
        "unreviewed",
    )
    assert sample.tasks == {"inference"}


def test_disagreeing_identity_judgements_leave_a_finding_uncertain(tmp_path: Path) -> None:
    store, photo_id = store_with_photo(tmp_path)
    store.finding("run", photo_id, Finding.model_validate(finding()))
    plant = store.findings("run", photo_id)[0]["id"]
    for reviewer, value in (("Ana", "confirmed"), ("Ben", "disputed")):
        judgement = {"finding_id": plant, "dimension": "identity", "value": value}
        store.judgement(
            "run", photo_id, Judgement.model_validate(judgement | {"reviewer": reviewer})
        )
    (sample,) = pilot_samples(store, "run")
    assert sample.annotations[-1].review == "uncertain"


def test_an_unscreened_pilot_photo_has_unknown_size_and_no_suggestion(tmp_path: Path) -> None:
    store, _ = store_with_photo(tmp_path, scores=None)
    (sample,) = pilot_samples(store, "run")
    assert (sample.media.width, sample.media.height) == (None, None)
    assert sample.annotations == ()


def test_a_photo_without_coordinates_gets_no_invented_location(tmp_path: Path) -> None:
    store, _ = store_with_photo(tmp_path)
    photo = photo_from_observation(observation() | {"location": None}, "Nelson", "incidental")
    assert photo is not None and photo.coordinate_status == "missing"
    store.save_photos("run", [photo])
    (sample,) = pilot_samples(store, "run")
    assert sample.geography is None


def test_adapter_samples_round_trip_through_a_manifest(tmp_path: Path, dataset_dir: Path) -> None:
    record_dataset(dataset_dir)
    store, photo_id = store_with_photo(tmp_path / "pilot")
    store.finding("run", photo_id, Finding.model_validate(finding(box=[1, 2, 3, 4])))
    samples = leafy_spurge_samples(dataset_dir) + pilot_samples(store, "run")
    digest = write_manifest(tmp_path / "samples.jsonl", samples)
    assert read_manifest(tmp_path / "samples.jsonl", digest) == samples


def test_a_reopen_does_not_hide_another_reviewer_s_standing_decision(tmp_path: Path) -> None:
    store, photo_id = store_with_photo(tmp_path)
    store.score("run", photo_id, {"best_species": "Ulex europaeus", "margin": 0.1})
    store.review("run", photo_id, "confirmed", "", "Ana")
    store.review("run", photo_id, "unreviewed", "Second look", "Ben")
    (sample,) = pilot_samples(store, "run")
    suggestion = next(a for a in sample.annotations if a.id == "suggestion")
    assert (suggestion.review, suggestion.reviewer) == ("accepted", "Ana")


def test_disagreeing_reviewers_leave_the_suggestion_uncertain_and_name_both(tmp_path: Path) -> None:
    store, photo_id = store_with_photo(tmp_path)
    store.score("run", photo_id, {"best_species": "Ulex europaeus", "margin": 0.1})
    store.review("run", photo_id, "confirmed", "", "Ana")
    store.review("run", photo_id, "rejected", "Native", "Ben")
    (sample,) = pilot_samples(store, "run")
    suggestion = next(a for a in sample.annotations if a.id == "suggestion")
    assert (suggestion.review, suggestion.reviewer) == ("uncertain", "Ana; Ben")
