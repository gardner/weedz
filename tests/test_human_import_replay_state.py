"""Receipt-owned captures, not mutable standing snapshots, define prior human state."""

import hashlib
import json

import pytest
from test_human_import_decode_budget import save
from test_human_import_pipeline import inputs

from weedz.annotation.import_pipeline import import_reviews


def repin_prior(prior, receipt, provenance):
    raw = json.dumps(provenance).encode()
    (prior / "private/provenance.json").write_bytes(raw)
    receipt["files"]["private/provenance.json"] = hashlib.sha256(raw).hexdigest()
    manifest = json.dumps(receipt).encode()
    (prior / "manifest.json").write_bytes(manifest)
    return hashlib.sha256(manifest).hexdigest()


@pytest.mark.parametrize("mutation", ["coverage", "event", "omit-event", "omit-claim", "box"])
def test_replay_rederives_human_state_from_owned_capture(tmp_path, mutation):
    request, task, _ = inputs(tmp_path)
    task["annotations"][0]["result"].append(
        dict(
            id="box",
            from_name="review_boxes",
            to_name="image",
            type="rectanglelabels",
            original_width=10,
            original_height=10,
            image_rotation=0,
            value=dict(
                x=10, y=20, width=50, height=40, rotation=0, rectanglelabels=["Ulex europaeus"]
            ),
        )
    )
    request = save(request, task)
    prior = tmp_path / "prior"
    receipt = import_reviews(request, prior)
    provenance = json.loads((prior / "private/provenance.json").read_bytes())
    sample = provenance["samples"][0]["sample"]
    if mutation == "coverage":
        sample["completeness"][0]["status"] = "partial"
    elif mutation == "event":
        sample["review_history"][0]["payload"]["completeness"]["status"] = "partial"
    elif mutation == "omit-event":
        sample["review_history"] = []
    elif mutation == "box":
        sample["annotations"][0]["box"][0] = 0
    else:
        sample["completeness"] = []
    checksum = repin_prior(prior, receipt, provenance)
    output = tmp_path / "refused"
    with pytest.raises(ValueError, match="reconstructed human state"):
        import_reviews(request, output, previous=prior, previous_sha256=checksum)
    assert not output.exists()


def test_capture_journal_retains_zero_human_captures_and_repeated_replays(tmp_path):
    request, task, _ = inputs(tmp_path)
    task["annotations"] = []
    request = save(request, task)
    first = tmp_path / "first"
    receipt = import_reviews(request, first)
    assert receipt["capture_journal"][0]["export_sha256"] == request.export_sha256
    second = tmp_path / "second"
    repeated = import_reviews(
        request,
        second,
        previous=first,
        previous_sha256=hashlib.sha256((first / "manifest.json").read_bytes()).hexdigest(),
    )
    assert len(repeated["capture_journal"]) == 2
    assert (second / "samples.jsonl").read_bytes() == (first / "samples.jsonl").read_bytes()


def test_historical_replay_has_shared_pixel_and_visit_budgets(tmp_path, monkeypatch):
    from test_human_import_decode_budget import decoder, request_with_masks

    import weedz.annotation.import_replay as replay

    request, task = request_with_masks(tmp_path)
    calls = decoder(monkeypatch)
    request = save(request, task)
    prior = tmp_path / "prior"
    import_reviews(request, prior)
    checksum = hashlib.sha256((prior / "manifest.json").read_bytes()).hexdigest()
    calls.clear()
    monkeypatch.setattr(replay, "MAX_REPLAY_BRUSH_PIXELS", 99)
    with pytest.raises(ValueError, match="Historical brush replay"):
        import_reviews(request, tmp_path / "pixels", previous=prior, previous_sha256=checksum)
    assert calls == []
    monkeypatch.setattr(replay, "MAX_REPLAY_BRUSH_PIXELS", 100)
    monkeypatch.setattr(replay, "MAX_REPLAY_VISITS", 2)
    with pytest.raises(ValueError, match="visit budget"):
        import_reviews(request, tmp_path / "visits", previous=prior, previous_sha256=checksum)
    assert calls == []


def test_multiple_captures_decode_distinct_revision_once(tmp_path, monkeypatch):
    from test_human_import_decode_budget import decoder, request_with_masks

    request, task = request_with_masks(tmp_path)
    calls = decoder(monkeypatch)
    request = save(request, task)
    prior = tmp_path / "prior"
    import_reviews(request, prior)
    repeated = tmp_path / "repeated"
    import_reviews(
        request,
        repeated,
        previous=prior,
        previous_sha256=hashlib.sha256((prior / "manifest.json").read_bytes()).hexdigest(),
    )
    calls.clear()
    import_reviews(
        request,
        tmp_path / "third",
        previous=repeated,
        previous_sha256=hashlib.sha256((repeated / "manifest.json").read_bytes()).hexdigest(),
    )
    assert len(calls) == 1


def test_journal_replays_recorded_configuration_before_current_scope(tmp_path):
    from dataclasses import replace

    from weedz.annotation.gold_config import gold_config

    request, _, _ = inputs(tmp_path)
    prior = tmp_path / "prior"
    import_reviews(request, prior)
    taxa = ("Ulex europaeus", "Cortaderia selloana")
    request.config.write_text(gold_config(taxa), encoding="utf-8")
    changed = replace(
        request, taxa=taxa, config_sha256=hashlib.sha256(request.config.read_bytes()).hexdigest()
    )
    second = tmp_path / "second"
    receipt = import_reviews(
        changed,
        second,
        previous=prior,
        previous_sha256=hashlib.sha256((prior / "manifest.json").read_bytes()).hexdigest(),
    )
    assert receipt["capture_journal"][0]["taxa"] == ["Ulex europaeus"]
    assert receipt["capture_journal"][1]["taxa"] == list(taxa)
    import_reviews(
        changed,
        tmp_path / "third",
        previous=second,
        previous_sha256=hashlib.sha256((second / "manifest.json").read_bytes()).hexdigest(),
    )


def test_repeated_unknown_cancellation_is_reconsidered_in_capture_order(tmp_path):
    request, task, _ = inputs(tmp_path)
    annotation = task["annotations"][0]
    original = json.loads(json.dumps(annotation))
    annotation.update(was_cancelled=True, updated_at="2026-11-16T02:00:00Z", result=[])
    cancelled = json.loads(json.dumps(task))
    first = tmp_path / "unknown-cancel"
    import_reviews(save(request, task), first)
    task["annotations"] = [original]
    second = tmp_path / "created"
    import_reviews(
        save(request, task),
        second,
        previous=first,
        previous_sha256=hashlib.sha256((first / "manifest.json").read_bytes()).hexdigest(),
    )
    third = tmp_path / "known-cancel"
    import_reviews(
        save(request, cancelled),
        third,
        previous=second,
        previous_sha256=hashlib.sha256((second / "manifest.json").read_bytes()).hexdigest(),
    )
    receipt = import_reviews(
        save(request, cancelled),
        tmp_path / "repeat",
        previous=third,
        previous_sha256=hashlib.sha256((third / "manifest.json").read_bytes()).hexdigest(),
    )
    assert receipt["imported_revisions"] == 0
    row = json.loads((third / "samples.jsonl").read_bytes())
    assert row.get("completeness", []) == []


def test_single_capture_legacy_can_be_reconstructed_without_guessing(tmp_path):
    request, _, _ = inputs(tmp_path)
    prior = tmp_path / "prior"
    receipt = import_reviews(request, prior)
    receipt.pop("capture_journal")
    manifest = json.dumps(receipt).encode()
    (prior / "manifest.json").write_bytes(manifest)
    import_reviews(
        request,
        tmp_path / "replay",
        previous=prior,
        previous_sha256=hashlib.sha256(manifest).hexdigest(),
    )


def test_all_journal_configs_are_validated_before_first_mask_decode(tmp_path, monkeypatch):
    from test_human_import_decode_budget import decoder, request_with_masks

    request, task = request_with_masks(tmp_path)
    calls = decoder(monkeypatch)
    request = save(request, task)
    prior = tmp_path / "prior"
    receipt = import_reviews(request, prior)
    receipt["capture_journal"].append({**receipt["capture_journal"][0], "taxa": ["wrong"]})
    manifest = json.dumps(receipt).encode()
    (prior / "manifest.json").write_bytes(manifest)
    calls.clear()
    with pytest.raises(ValueError, match="configuration"):
        import_reviews(
            request,
            tmp_path / "refused",
            previous=prior,
            previous_sha256=hashlib.sha256(manifest).hexdigest(),
        )
    assert calls == []
