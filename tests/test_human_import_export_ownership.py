"""Only receipt-proven exports confer replay authority; source files stay opaque."""

import hashlib
import json
from dataclasses import replace

import pytest
from test_human_import_bindings import export, two_samples
from test_human_import_final_closure import repack

from weedz.annotation.import_pipeline import import_reviews


def checksum(output):
    return hashlib.sha256((output / "manifest.json").read_bytes()).hexdigest()


def rewrite_receipt(output, mutate):
    path = output / "manifest.json"
    receipt = json.loads(path.read_bytes())
    mutate(receipt)
    path.write_text(json.dumps(receipt), encoding="utf-8")
    return checksum(output)


@pytest.mark.parametrize("shape", ["ordinary", "phantom-tasks"])
def test_source_owned_json_is_preserved_but_not_replay_history(tmp_path, shape):
    request, first, second = two_samples(tmp_path)
    phantom = json.loads(json.dumps(second))
    phantom["id"] = 900
    raw = json.dumps(
        {"source_notes": "not a human export"} if shape == "ordinary" else [phantom]
    ).encode()
    name = f"private/exports/{hashlib.sha256(raw).hexdigest()}.json"
    request = repack(request, {name: raw})
    original = tmp_path / "first"
    first_request = export(request, [first])
    import_reviews(first_request, original)
    output = tmp_path / "second"
    second_request = export(request, [second])
    receipt = import_reviews(
        second_request, output, previous=original, previous_sha256=checksum(original)
    )
    assert receipt["task_bindings"] == {
        first["meta"]["external_id"]: 1,
        second["meta"]["external_id"]: 2,
    }
    assert set(receipt["owned_export_sha256"]) == {
        first_request.export_sha256,
        second_request.export_sha256,
    }
    assert hashlib.sha256(raw).hexdigest() not in receipt["owned_export_sha256"]
    assert (output / name).read_bytes() == raw


def test_source_metadata_does_not_seed_task_or_export_authority(tmp_path):
    request, first, _ = two_samples(tmp_path)
    path = request.package / "manifest.json"
    metadata = json.loads(path.read_bytes())
    metadata.update(
        task_bindings={first["meta"]["external_id"]: 900}, owned_export_sha256=["a" * 64]
    )
    path.write_text(json.dumps(metadata), encoding="utf-8")
    request = replace(request, package_sha256=checksum(request.package))
    receipt = import_reviews(export(request, [first]), tmp_path / "reviewed")
    assert receipt["task_bindings"] == {first["meta"]["external_id"]: 1}
    assert receipt["owned_export_sha256"] != ["a" * 64]


def test_empty_and_zero_human_exports_remain_owned_across_subsets(tmp_path):
    request, first, _ = two_samples(tmp_path)
    output = tmp_path / "empty"
    empty = export(request, [])
    import_reviews(empty, output)
    first["annotations"] = []
    selected = export(request, [first])
    receipt = import_reviews(
        selected, tmp_path / "zero-human", previous=output, previous_sha256=checksum(output)
    )
    assert set(receipt["owned_export_sha256"]) == {empty.export_sha256, selected.export_sha256}
    assert receipt["task_bindings"] == {first["meta"]["external_id"]: 1}


def test_owned_export_bytes_must_match_the_receipt_hash(tmp_path):
    request, first, _ = two_samples(tmp_path)
    request = export(request, [first])
    original = tmp_path / "first"
    import_reviews(request, original)
    name = f"private/exports/{request.export_sha256}.json"
    raw = b"[]"
    (original / name).write_bytes(raw)
    prior_sha = rewrite_receipt(
        original, lambda receipt: receipt["files"].update({name: hashlib.sha256(raw).hexdigest()})
    )
    with pytest.raises(ValueError, match="owned export"):
        import_reviews(request, tmp_path / "replay", previous=original, previous_sha256=prior_sha)


def test_legacy_table_without_order_cannot_reconstruct_multiple_captures(tmp_path):
    request, first, second = two_samples(tmp_path)
    first["annotations"] = []
    original = tmp_path / "first"
    import_reviews(export(request, [first]), original)
    prior = tmp_path / "second"
    import_reviews(
        export(request, [second]), prior, previous=original, previous_sha256=checksum(original)
    )
    prior_sha = rewrite_receipt(
        prior,
        lambda receipt: (
            receipt.pop("owned_export_sha256", None),
            receipt.pop("capture_journal", None),
        ),
    )
    with pytest.raises(ValueError, match="capture order|task bindings"):
        import_reviews(
            export(request, [first]), tmp_path / "replay", previous=prior, previous_sha256=prior_sha
        )


def test_legacy_without_table_refuses_unprovable_earlier_zero_human_exports(tmp_path):
    request, first, second = two_samples(tmp_path)
    first["annotations"] = []
    original = tmp_path / "first"
    import_reviews(export(request, [first]), original)
    prior = tmp_path / "second"
    import_reviews(
        export(request, [second]), prior, previous=original, previous_sha256=checksum(original)
    )

    def legacy(receipt):
        receipt.pop("owned_export_sha256", None)
        receipt.pop("task_bindings", None)
        receipt.pop("capture_journal", None)

    prior_sha = rewrite_receipt(prior, legacy)
    with pytest.raises(ValueError, match="ownership"):
        import_reviews(
            export(request, [second]),
            tmp_path / "replay",
            previous=prior,
            previous_sha256=prior_sha,
        )


def test_declared_owned_history_cannot_contradict_its_complete_task_table(tmp_path):
    request, first, second = two_samples(tmp_path)
    phantom = json.loads(json.dumps(second))
    phantom["id"] = 900
    raw = json.dumps([phantom]).encode()
    phantom_sha = hashlib.sha256(raw).hexdigest()
    request = repack(request, {f"private/exports/{phantom_sha}.json": raw})
    original = tmp_path / "first"
    selected = export(request, [first])
    import_reviews(selected, original)
    prior_sha = rewrite_receipt(
        original, lambda receipt: receipt["owned_export_sha256"].append(phantom_sha)
    )
    with pytest.raises(ValueError, match="binding|journal"):
        import_reviews(selected, tmp_path / "replay", previous=original, previous_sha256=prior_sha)


def test_legacy_event_anchors_without_order_cannot_reconstruct_multiple_captures(tmp_path):
    request, first, second = two_samples(tmp_path)
    original = tmp_path / "first"
    first_request = export(request, [first])
    import_reviews(first_request, original)  # This produces an actual imported event anchor.
    prior = tmp_path / "second"
    second_request = export(request, [second])
    import_reviews(second_request, prior, previous=original, previous_sha256=checksum(original))

    def legacy(receipt):
        receipt.pop("owned_export_sha256")
        receipt.pop("task_bindings")
        receipt.pop("capture_journal", None)

    prior_sha = rewrite_receipt(prior, legacy)
    with pytest.raises(ValueError, match="capture order|task bindings"):
        import_reviews(
            second_request, tmp_path / "replay", previous=prior, previous_sha256=prior_sha
        )


def test_before_table_legacy_refuses_source_bytes_that_were_also_an_actual_capture(tmp_path):
    request, first, second = two_samples(tmp_path)
    first["annotations"] = []
    first_request = export(request, [first])
    raw = first_request.export.read_bytes()
    # Source bytes alone cannot prove that this snapshot was never actually imported.
    request = repack(request, {f"private/exports/{first_request.export_sha256}.json": raw})
    original = tmp_path / "first"
    import_reviews(export(request, [first]), original)
    prior = tmp_path / "second"
    import_reviews(
        export(request, [second]), prior, previous=original, previous_sha256=checksum(original)
    )

    def legacy(receipt):
        receipt.pop("owned_export_sha256")
        receipt.pop("task_bindings")
        receipt.pop("capture_journal", None)

    prior_sha = rewrite_receipt(prior, legacy)
    first["id"] = 3
    with pytest.raises(ValueError, match="ownership"):
        import_reviews(
            export(request, [first]),
            tmp_path / "renumbered",
            previous=prior,
            previous_sha256=prior_sha,
        )
