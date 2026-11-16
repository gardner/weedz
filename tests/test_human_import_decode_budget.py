"""Brush work is bounded before any decoding, including across human records."""

import hashlib
import json
from dataclasses import replace
from io import BytesIO

import pytest
from PIL import Image
from test_human_import_pipeline import inputs


def brush(number):
    return dict(
        id=f"mask-{number}",
        from_name="regions",
        to_name="image",
        type="brushlabels",
        original_width=10,
        original_height=10,
        image_rotation=0,
        value=dict(format="rle", rle=[0, 0, 1, 144], brushlabels=["Ulex europaeus"]),
    )


def request_with_masks(tmp_path, count=1):
    request, task, _ = inputs(tmp_path)
    results = task["annotations"][0]["result"]
    next(row for row in results if row["from_name"] == "completeness_task")["value"]["choices"] = [
        "segmentation"
    ]
    results.extend(brush(number) for number in range(count))
    return request, task


def save(request, task):
    request.export.write_text(json.dumps([task]), encoding="utf-8")
    return replace(request, export_sha256=hashlib.sha256(request.export.read_bytes()).hexdigest())


def decoder(monkeypatch):
    import weedz.annotation.import_geometry as geometry

    output = BytesIO()
    Image.new("L", (10, 10), 255).save(output, format="PNG")
    calls = []

    def decoded(*args):
        calls.append(True)
        return output.getvalue()

    monkeypatch.setattr(geometry, "_mask", decoded)
    return calls


@pytest.mark.parametrize(
    "limit,count", [("MAX_REGIONS_PER_RECORD", 65), ("MAX_RECORD_BRUSH_PIXELS", 2)]
)
def test_record_budget_is_checked_before_first_brush_decode(tmp_path, monkeypatch, limit, count):
    import weedz.annotation.import_claims as claims
    from weedz.annotation.import_pipeline import import_reviews

    request, task = request_with_masks(tmp_path, count)
    monkeypatch.setattr(claims, limit, 64 if "REGIONS" in limit else 150, raising=False)
    calls = decoder(monkeypatch)
    with pytest.raises(ValueError, match="budget"):
        import_reviews(save(request, task), tmp_path / "refused")
    assert calls == []


def test_entire_export_pixel_budget_is_reserved_before_any_record_is_decoded(tmp_path, monkeypatch):
    import weedz.annotation.import_claims as claims
    from weedz.annotation.import_pipeline import import_reviews

    request, task = request_with_masks(tmp_path)
    other = json.loads(json.dumps(task["annotations"][0]))
    other["id"] = 3
    task["annotations"].append(other)
    monkeypatch.setattr(claims, "MAX_IMPORT_BRUSH_PIXELS", 150, raising=False)
    calls = decoder(monkeypatch)
    with pytest.raises(ValueError, match="budget"):
        import_reviews(save(request, task), tmp_path / "refused")
    assert calls == []


def test_later_invalid_geometry_is_found_before_first_brush_decode(tmp_path, monkeypatch):
    from weedz.annotation.import_pipeline import import_reviews

    request, task = request_with_masks(tmp_path, 2)
    task["annotations"][0]["result"][-1]["original_width"] = 11
    calls = decoder(monkeypatch)
    with pytest.raises(ValueError, match="geometry"):
        import_reviews(save(request, task), tmp_path / "refused")
    assert calls == []


def test_exact_replay_and_cancellation_need_no_new_decode_budget(tmp_path, monkeypatch):
    import weedz.annotation.import_claims as claims
    from weedz.annotation.import_pipeline import import_reviews

    request, task = request_with_masks(tmp_path)
    calls = decoder(monkeypatch)
    request = save(request, task)
    original = tmp_path / "first"
    import_reviews(request, original)
    checksum = hashlib.sha256((original / "manifest.json").read_bytes()).hexdigest()
    assert len(calls) == 1
    calls.clear()
    monkeypatch.setattr(claims, "MAX_IMPORT_BRUSH_PIXELS", 0, raising=False)
    repeated = import_reviews(
        request, tmp_path / "repeat", previous=original, previous_sha256=checksum
    )
    assert repeated["imported_revisions"] == 0 and calls == []
    task["annotations"][0].update(was_cancelled=True, updated_at="2026-11-16T02:00:00Z", result=[])
    retracted = import_reviews(
        save(request, task), tmp_path / "cancelled", previous=original, previous_sha256=checksum
    )
    assert retracted["imported_revisions"] == 1 and calls == []


def test_export_budget_is_shared_across_different_tasks(tmp_path, monkeypatch):
    from test_human_import_bindings import two_samples

    import weedz.annotation.import_claims as claims
    from weedz.annotation.import_pipeline import import_reviews

    request, first, second = two_samples(tmp_path)
    results = first["annotations"][0]["result"]
    next(row for row in results if row["from_name"] == "completeness_task")["value"]["choices"] = [
        "segmentation"
    ]
    results.append(brush(1))
    second["annotations"] = json.loads(json.dumps(first["annotations"]))
    second["annotations"][0].update(id=3, task=2)
    request.export.write_text(json.dumps([first, second]), encoding="utf-8")
    request = replace(
        request, export_sha256=hashlib.sha256(request.export.read_bytes()).hexdigest()
    )
    calls = decoder(monkeypatch)
    monkeypatch.setattr(claims, "MAX_IMPORT_BRUSH_PIXELS", 150)
    with pytest.raises(ValueError, match="budget"):
        import_reviews(request, tmp_path / "refused")
    assert calls == []


def test_exact_region_and_pixel_budget_boundary_is_accepted(tmp_path, monkeypatch):
    import weedz.annotation.import_claims as claims
    from weedz.annotation.import_pipeline import import_reviews

    request, task = request_with_masks(tmp_path)
    calls = decoder(monkeypatch)
    monkeypatch.setattr(claims, "MAX_REGIONS_PER_RECORD", 1)
    monkeypatch.setattr(claims, "MAX_RECORD_BRUSH_PIXELS", 100)
    monkeypatch.setattr(claims, "MAX_IMPORT_BRUSH_PIXELS", 100)
    import_reviews(save(request, task), tmp_path / "accepted")
    assert calls == [True]
