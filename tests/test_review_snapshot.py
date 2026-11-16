"""Export one read-only review snapshot without collapsing history or inventing groups."""

import hashlib
from pathlib import Path

import pytest
from test_findings import finding, store_with_photo

from weedz.discovery.judgements import Judgement
from weedz.discovery.records import Finding, Photo


def pinned_store(root: Path):
    store, photo_id = store_with_photo(root)
    photo = Photo.model_validate(store.photos("run")[0])
    store.save_photos("run", [photo.model_copy(update={"sha256": "a" * 64})])
    return store, photo_id


def test_snapshot_keeps_withdrawn_identity_votes_and_separate_model_reviews(tmp_path: Path):
    from weedz.review_snapshot import reviewed_pilot_samples

    store, photo_id = pinned_store(tmp_path)
    store.finding("run", photo_id, Finding.model_validate(finding(box=[1, 2, 3, 4])))
    found = store.findings("run", photo_id)[0]["id"]
    for value in ("confirmed", "unassessed"):
        store.judgement(
            "run",
            photo_id,
            Judgement(finding_id=found, dimension="identity", value=value, reviewer="Ana"),
        )
    store.review("run", photo_id, "confirmed", "Only accepts a model suggestion", "Ben")
    before = hashlib.sha256(store.database.read_bytes()).hexdigest()
    (sample,) = reviewed_pilot_samples(store, "run", namespace="fixture")
    assert hashlib.sha256(store.database.read_bytes()).hexdigest() == before
    assert sample.schema_version == 2 and sample.tasks == {"inference"}
    assert sample.annotations[-1].review == "unreviewed"
    assert sample.annotations[-1].author == "discovery:fixture:reviewer:Ana"
    identity = [event for event in sample.review_history if event.dimension == "identity"]
    assert [event.action for event in identity] == ["confirmed", "unassessed"]
    assert identity[1].supersedes == identity[0].id
    assert identity[0].annotation_id == sample.annotations[-1].id
    assert any(event.dimension == "model_suggestion" for event in sample.review_history)
    assert all(event.media_sha256 == sample.media.sha256 for event in sample.review_history)
    assert len({event.evidence["snapshot_sha256"] for event in sample.review_history}) == 1
    assert sample.completeness == ()


def test_snapshot_records_observer_login_without_inventing_site_or_encounter(tmp_path: Path):
    from weedz.review_snapshot import reviewed_pilot_samples

    store, _photo_id = pinned_store(tmp_path)
    original = store.photos("run")[0]
    (sample,) = reviewed_pilot_samples(store, "run", namespace="fixture")
    assert sample.groups == {
        "observation": str(original["observation_id"]),
        "observer": f"inaturalist:login:{original['observer']}",
    }
    assert sample.context["source_observer_login"] == original["observer"]
    assert sample.geography and sample.geography.privacy == "obscured"
    assert sample.geography.uncertainty_m is None


def test_snapshot_uses_one_transaction_when_another_review_arrives(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from weedz.review_snapshot import reviewed_pilot_samples

    store, photo_id = pinned_store(tmp_path)
    store.review("run", photo_id, "confirmed", "before snapshot", "Ana")
    original = store._photos

    def arriving_review(db, run_id):
        rows = original(db, run_id)
        store.review("run", photo_id, "unreviewed", "arrives during snapshot", "Ana")
        return rows

    monkeypatch.setattr(store, "_photos", arriving_review)
    (sample,) = reviewed_pilot_samples(store, "run", namespace="fixture")
    history = [event for event in sample.review_history if event.dimension == "model_suggestion"]
    assert [event.action for event in history] == ["confirmed"]
    assert sample.annotations[0].review == "accepted"
    assert len(store.reviews("run", photo_id)) == 2


def test_missing_media_digest_cannot_bind_human_history(tmp_path: Path):
    from weedz.review_snapshot import reviewed_pilot_samples

    store, _photo_id = store_with_photo(tmp_path)
    with pytest.raises(ValueError, match="media SHA"):
        reviewed_pilot_samples(store, "run", namespace="fixture")


@pytest.mark.parametrize(
    "namespace", ["team:reviewer:alice", "team/reviews", "", " team", "team ", "a" * 101]
)
def test_ambiguous_namespace_refuses_before_capture_or_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, namespace: str
):
    from weedz import review_snapshot

    def no_capture(*_args):
        pytest.fail("Invalid namespaces must refuse before reading the source database")

    monkeypatch.setattr(review_snapshot, "_capture", no_capture)
    output = tmp_path / "snapshot"
    with pytest.raises(ValueError, match="namespace"):
        review_snapshot.write_review_snapshot(
            tmp_path / "missing-source", "run", output, namespace=namespace
        )
    assert not output.exists()


@pytest.mark.parametrize("actual", ["alice:reviewer:bob", "Māia:reviewer:李"])
def test_valid_namespaces_keep_actual_reviewer_names_and_separate_stores(
    tmp_path: Path, actual: str
):
    from weedz.review_snapshot import reviewed_pilot_samples

    store, photo_id = pinned_store(tmp_path)
    store.finding(
        "run", photo_id, Finding.model_validate(finding(box=[1, 2, 3, 4], reviewer=actual))
    )
    store.review("run", photo_id, "confirmed", "Actual source name", actual)
    actors = set()
    for namespace in ("team", "team-alice_2.0"):
        (sample,) = reviewed_pilot_samples(store, "run", namespace=namespace)
        expected = f"discovery:{namespace}:reviewer:{actual}"
        assert sample.annotations[-1].author == expected
        assert sample.annotations[0].reviewers == (expected,)
        assert {event.actor for event in sample.review_history} == {expected}
        actors.add(expected)
    assert len(actors) == 2


def test_legacy_nested_nonfinite_scores_keep_distinct_snapshot_hashes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    import json

    from weedz.discovery import store as store_module
    from weedz.review_snapshot import write_review_snapshot

    # The snapshots differ only in the nested score, not acquisition/review timestamps.
    monkeypatch.setattr(store_module, "now", lambda: "2026-11-16T00:00:00Z")
    hashes = set()
    for index, margin in enumerate([float("nan"), float("inf"), -float("inf"), None]):
        store, photo_id = pinned_store(tmp_path / f"source-{index}")
        scores = store.photos("run")[0]["scores"] | {
            "margin": 0.25,
            "species": [{"margin": margin}],
        }
        store.score("run", photo_id, scores)
        before = store.database.read_bytes()
        output = tmp_path / f"snapshot-{index}"
        receipt = write_review_snapshot(store.root, "run", output, namespace="legacy")
        assert store.database.read_bytes() == before

        def no_nonfinite(value):
            pytest.fail(f"Published snapshot must remain strict JSON: {value}")

        sample = json.loads((output / "samples.jsonl").read_text(), parse_constant=no_nonfinite)
        assert sample["annotations"][0]["score"] == 0.25
        hashes.add(receipt["source_snapshot_sha256"])
    assert len(hashes) == 4


@pytest.mark.parametrize("margin", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_annotation_scores_still_refuse_snapshot_output(tmp_path: Path, margin: float):
    from weedz.review_snapshot import write_review_snapshot

    store, photo_id = pinned_store(tmp_path / "source")
    store.score("run", photo_id, store.photos("run")[0]["scores"] | {"margin": margin})
    before = store.database.read_bytes()
    output = tmp_path / "snapshot"
    with pytest.raises(ValueError):
        write_review_snapshot(store.root, "run", output, namespace="legacy")
    assert store.database.read_bytes() == before
    assert not output.exists()


def test_snapshot_command_reads_an_existing_database_without_opening_a_writer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    import json

    from weedz.discovery.store import Store
    from weedz.manifest import read_manifest
    from weedz.release_cli import main

    store, photo_id = pinned_store(tmp_path / "source")
    store.review("run", photo_id, "confirmed", "actual fixture review", "Ana")
    before = store.database.read_bytes()

    def no_migrations(*_args):
        pytest.fail("A historical review export must not initialize or migrate its store")

    monkeypatch.setattr(Store, "__init__", no_migrations)
    output = tmp_path / "snapshot"
    main(
        [
            "review-snapshot",
            "--source",
            str(store.root),
            "--run",
            "run",
            "--namespace",
            "fixture",
            "--output-dir",
            str(output),
        ]
    )
    receipt = json.loads((output / "snapshot.json").read_text())
    samples = read_manifest(output / "samples.jsonl", receipt["manifest_sha256"])
    assert len(samples) == receipt["count"] == 1
    assert samples[0].review_history[0].actor == "discovery:fixture:reviewer:Ana"
    assert store.database.read_bytes() == before
