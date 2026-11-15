"""Retries preserve completed model work and never convert outages to negative evidence."""

import hashlib
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image
from test_discovery import observation

from weedz.discovery.records import RunSpec
from weedz.discovery.source import photo_from_observation
from weedz.discovery.store import Store
from weedz.segmentation.artifacts import digest
from weedz.segmentation.stages import PipelineStages


@pytest.fixture
def store(tmp_path):
    result = Store(tmp_path)
    result.create_run("run", RunSpec(segmentation="sam2.1-tiny-v1"))
    (tmp_path / "images").mkdir()
    for index in range(2):
        photo = photo_from_observation(observation(), "Nelson", "incidental")
        assert photo
        photo = photo.model_copy(update={"id": str(index), "image_path": f"images/{index}.png"})
        image = tmp_path / photo.image_path
        Image.new("RGB", (8, 8), (index, 100, 50)).save(image)
        photo.sha256 = hashlib.sha256(image.read_bytes()).hexdigest()
        result.save_photos("run", [photo])
    return result


class Proposer:
    metadata = {"checkpoint": "pinned", "version": 1}
    calls = 0
    fail_second = True

    def generate(self, image):
        self.calls += 1
        if image.getpixel((0, 0))[0] == 1 and self.fail_second:
            raise RuntimeError("Interrupted GPU stage")
        return [
            {"segmentation": np.ones((8, 8), bool), "predicted_iou": 0.9, "stability_score": 0.99}
        ]


def runner(store, proposer):
    return PipelineStages(
        store,
        lambda: proposer,
        lambda _run: SimpleNamespace(metadata={"classifier": "pinned"}),
        lambda _detail: None,
    )


def test_retry_skips_completed_proposals_but_retries_failed_work(store):
    proposer = Proposer()
    assert runner(store, proposer).segment("run")["failed"] == 1
    assert proposer.calls == 4
    proposer.fail_second = False
    result = runner(store, proposer).segment("run")
    assert proposer.calls == 5
    assert result["cache_hits"] == 1
    assert result["completed"] == 2 and result["failed"] == 0
    assert runner(store, proposer).segment("run")["cache_hits"] == 2
    assert proposer.calls == 5


def test_changed_source_or_model_provenance_refuses_cache_reuse(store):
    proposer = Proposer()
    proposer.fail_second = False
    runner(store, proposer).segment("run")
    proposer.metadata = {"checkpoint": "changed", "version": 1}
    with pytest.raises(ValueError, match="provenance"):
        runner(store, proposer).segment("run")


def test_final_failed_photo_is_explicit_partial_fallback_not_negative(store, monkeypatch):
    stages = runner(store, Proposer())
    result = stages.segment("run")
    assert result["completed"] == 1 and result["failed"] == 1
    for photo in store.photos("run"):
        store.score("run", photo["id"], {"margin": 0.12, "best_species": "Ulex europaeus"})
    before = {p["id"]: (p["scores"].copy(), p["screened_at"]) for p in store.photos("run")}
    monkeypatch.setattr(
        "weedz.segmentation.stages.identify_views",
        lambda _model, views, _subject: {name: {"margin": -0.2} for name in views},
    )
    stages.score_regions("run")
    for photo in store.photos("run"):
        evidence = photo["scores"].pop("segmentation")
        assert photo["scores"] == before[photo["id"]][0]
        assert photo["screened_at"] == before[photo["id"]][1]
        assert evidence["baseline_retained"] is True
    summary = stages.summary("run")
    assert summary["outcome"] == "partial"
    assert summary["warnings"]


def test_model_startup_failure_is_not_committed_as_a_per_photo_negative(store):
    def missing_runtime():
        raise ValueError("Checkpoint mismatch")

    stages = PipelineStages(store, missing_runtime, lambda _run: None, lambda _detail: None)
    with pytest.raises(ValueError, match="Checkpoint"):
        stages.segment("run")
    assert not list((store.root / "runs/run/pipeline-v1").glob("*.json"))


def test_empty_proposals_are_valid_and_preserve_baseline_without_region_scoring(store, monkeypatch):
    class Empty(Proposer):
        def generate(self, image):
            return []

    stages = runner(store, Empty())
    assert stages.segment("run")["completed"] == 2
    for photo in store.photos("run"):
        store.score("run", photo["id"], {"margin": -0.04})

    def no_views(*_args):
        pytest.fail("An empty proposal set has no model views to score")

    monkeypatch.setattr("weedz.segmentation.stages.identify_views", no_views)
    stages.score_regions("run")
    assert stages.summary("run")["outcome"] == "completed"
    assert stages.summary("run")["proposals"]["empty"] == 2
    assert all(photo["scores"]["margin"] == -0.04 for photo in store.photos("run"))


def test_changed_image_bytes_are_not_hidden_by_a_completed_artifact(store):
    proposer = Proposer()
    proposer.fail_second = False
    stages = runner(store, proposer)
    stages.segment("run")
    photo = store.photos("run")[0]
    Image.new("RGB", (8, 8), "blue").save(store.root / photo["image_path"])
    with pytest.raises(ValueError, match="provenance"):
        stages.segment("run")
    assert proposer.calls == 2


def test_region_runtime_failure_keeps_masks_and_is_retryable_before_final_fallback(
    store, monkeypatch
):
    proposer = Proposer()
    proposer.fail_second = False
    stages = runner(store, proposer)
    stages.segment("run")
    for photo in store.photos("run"):
        store.score("run", photo["id"], {"margin": -0.04})

    def interrupted(*_args):
        raise RuntimeError("Classifier interrupted")

    monkeypatch.setattr("weedz.segmentation.stages.identify_views", interrupted)
    assert stages.score_regions("run")["failed"] == 2
    assert all(
        photo["scores"]["segmentation"]["view_status"] == "failed" for photo in store.photos("run")
    )
    result = runner(store, proposer).score_regions("run")
    assert result["failed"] == 2 and result["cache_hits"] == 0
    assert all(
        photo["scores"]["segmentation"]["regions"][0]["views"] == {}
        for photo in store.photos("run")
    )


def test_completed_matching_proposals_win_even_if_late_local_work_fails(store):
    from dataclasses import asdict

    from weedz.segmentation.artifacts import StageArtifacts
    from weedz.segmentation.stages import CONFIG, PROFILE

    photo = store.photos("run")[0]

    class Racing(Proposer):
        fail_second = False

        def generate(self, image):
            if image.getpixel((0, 0))[0] == 0:
                inputs = {
                    "profile": PROFILE,
                    "image_sha256": photo["sha256"],
                    "config": asdict(CONFIG),
                    "proposer": self.metadata,
                }
                StageArtifacts(store.root, "run").write(
                    "proposals",
                    photo["id"],
                    inputs,
                    {"status": "empty", "regions": [], "elapsed_seconds": 1.0},
                )
                raise RuntimeError("Late attempt failed after another attempt committed")
            return super().generate(image)

    result = runner(store, Racing()).segment("run")
    assert result["completed"] == 2 and result["failed"] == 0


def test_canonical_region_result_is_attached_when_late_classifier_fails(store, monkeypatch):
    from weedz.segmentation.artifacts import StageArtifacts

    proposer = Proposer()
    proposer.fail_second = False
    stages = runner(store, proposer)
    stages.segment("run")
    for photo in store.photos("run"):
        store.score("run", photo["id"], {"margin": -0.04})
    first = store.photos("run")[0]
    artifacts = StageArtifacts(store.root, "run")
    calls = []

    def racing(model, views, _subject):
        calls.append(True)
        if len(calls) == 1:
            proposal = artifacts.entry("proposals", first["id"])
            assert proposal
            inputs = {
                "proposal_inputs_sha256": digest(proposal["inputs"]),
                "classifier": model.metadata,
                "version": 2,
            }
            canonical = {
                **proposal["result"],
                "proposal_status": "ok",
                "view_status": "ok",
                "baseline_retained": True,
            }
            canonical["regions"] = [
                {**row, "views": {name: {"margin": 0.123} for name in views}}
                for row in proposal["result"]["regions"]
            ]
            artifacts.write("views", first["id"], inputs, canonical)
            raise RuntimeError("Late classifier failed after another attempt completed")
        return {name: {"margin": -0.2} for name in views}

    monkeypatch.setattr("weedz.segmentation.stages.identify_views", racing)
    result = stages.score_regions("run")
    assert result["completed"] == 2 and result["failed"] == 0
    first = store.photos("run")[0]
    assert first["scores"]["segmentation"]["regions"][0]["views"]["tight"]["margin"] == 0.123
    assert first["scores"]["margin"] == -0.04


def test_late_baseline_attempt_cannot_erase_attached_region_evidence(store):
    store.score("run", "0", {"margin": -0.04, "model": "baseline"})
    stale = dict(store.photos("run")[0]["scores"])
    stages = runner(store, Proposer())
    evidence = {"status": "ok", "regions": [{"id": "durable-region"}]}
    stages._attach("run", "0", evidence)
    store.score("run", "0", stale)
    assert store.photos("run")[0]["scores"] == {**stale, "segmentation": evidence}


def test_each_photo_gets_its_own_bounded_transient_retry_budget(store):
    class Flaky(Proposer):
        seen = {0: 0, 1: 0}

        def generate(self, image):
            index = image.getpixel((0, 0))[0]
            self.seen[index] += 1
            if self.seen[index] <= (2 if index == 0 else 1):
                raise RuntimeError("Transient per-photo failure")
            return super().generate(image)

    proposer = Flaky()
    proposer.fail_second = False
    result = runner(store, proposer).segment("run")
    assert result["completed"] == 2 and result["failed"] == 0
    assert proposer.seen == {0: 3, 1: 2}


def test_late_progress_cannot_regress_terminal_run_state(store):
    store.status("run", "completed", "Canonical export complete")
    store.status("run", "screening", "Late timed-out worker progress")
    run = store.runs()[0]
    assert run["status"] == "completed" and run["detail"] == "Canonical export complete"


def test_region_classification_retries_are_independent_for_later_photos(store, monkeypatch):
    proposer = Proposer()
    proposer.fail_second = False
    stages = runner(store, proposer)
    stages.segment("run")
    for photo in store.photos("run"):
        store.score("run", photo["id"], {"margin": -0.04})
    seen = {0: 0, 1: 0}

    def flaky(_model, views, _subject):
        index = views["tight"].getpixel((0, 0))[0]
        seen[index] += 1
        if seen[index] <= (2 if index == 0 else 1):
            raise RuntimeError("Transient classifier interruption")
        return {name: {"margin": -0.2} for name in views}

    monkeypatch.setattr("weedz.segmentation.stages.identify_views", flaky)
    result = stages.score_regions("run")
    assert result["completed"] == 2 and result["failed"] == 0
    assert seen == {0: 3, 1: 2}


@pytest.mark.parametrize("late_status", ["failed", "skipped_proposal_failure"])
def test_successful_attachment_dominates_stale_failed_attempt(store, late_status):
    stages = runner(store, Proposer())
    baseline = {"margin": -0.04, "model": "unchanged-baseline"}
    store.score("run", "0", baseline)
    good = {"status": "ok", "view_status": "ok", "regions": [{"id": "canonical-success"}]}
    failed = {"status": "failed", "view_status": late_status, "regions": []}
    stages._attach("run", "0", failed)
    stages._attach("run", "0", good)
    stages._attach("run", "0", failed)
    assert store.photos("run")[0]["scores"] == {**baseline, "segmentation": good}


def test_failed_proposal_recovery_does_not_poison_existing_fallback_views(store, monkeypatch):
    proposer = Proposer()
    stages = runner(store, proposer)
    assert stages.segment("run")["failed"] == 1
    for photo in store.photos("run"):
        store.score("run", photo["id"], {"margin": -0.04})
    monkeypatch.setattr(
        "weedz.segmentation.stages.identify_views",
        lambda _model, views, _subject: {name: {"margin": -0.2} for name in views},
    )
    assert stages.score_regions("run")["failed"] == 1
    proposer.fail_second = False
    assert stages.segment("run")["completed"] == 2
    result = stages.score_regions("run")
    assert result["completed"] == 2 and result["cache_hits"] == 1
    recovered = store.photos("run")[1]["scores"]
    assert recovered["margin"] == -0.04
    assert recovered["segmentation"]["view_status"] == "ok"
    assert recovered["segmentation"]["regions"]
    from weedz.segmentation.artifacts import StageArtifacts

    canonical = StageArtifacts(store.root, "run").entry("proposals", "1")
    assert canonical
    assert (
        recovered["segmentation"]["provenance"]["proposal_artifact_sha256"] == canonical["sha256"]
    )


def test_late_skipped_attachment_keeps_masks_when_classifier_failed(store):
    stages = runner(store, Proposer())
    store.score("run", "0", {"margin": -0.04})
    retained = {
        "status": "failed",
        "proposal_status": "ok",
        "view_status": "failed",
        "regions": [{"id": "real-proposal"}],
    }
    skipped = {
        "status": "failed",
        "proposal_status": "failed",
        "view_status": "skipped_proposal_failure",
        "regions": [],
    }
    stages._attach("run", "0", retained)
    stages._attach("run", "0", skipped)
    assert store.photos("run")[0]["scores"]["segmentation"] == retained
