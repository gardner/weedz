"""Downloads keep receipts, verify cache hits, resume, and never need a live server."""

import hashlib
import io
import json
from pathlib import Path

import httpx
import pytest
from PIL import Image
from test_validation_plantclef2024 import row, write_labels

from weedz.validation import plantclef2024, plantclef2024_data
from weedz.validation.inat2021_data import Item
from weedz.validation.inat2021_models import Prediction
from weedz.validation.plantclef2024_data import load_photos, prepare_images
from weedz.validation.registry import RunContext


def jpeg() -> bytes:
    stream = io.BytesIO()
    Image.new("RGB", (4, 3), "green").save(stream, format="JPEG")
    return stream.getvalue()


def test_image_receipts_verify_cache_hits_and_repair_corruption(tmp_path: Path):
    photos = load_photos(write_labels(tmp_path / "labels.csv", [row("a"), row("b")]))
    calls: list[str] = []
    content = jpeg()

    def respond(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, content=content)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        digest = prepare_images(tmp_path, photos, client=client, delay=0)
        assert len(calls) == 2
        assert prepare_images(tmp_path, photos, client=client, delay=0) == digest
        assert len(calls) == 2
        (tmp_path / photos[0].item.file_name).write_bytes(b"truncated")
        assert prepare_images(tmp_path, photos, client=client, delay=0) == digest
        assert len(calls) == 3
        assert prepare_images(tmp_path, photos[:1], client=client, delay=0) != digest
    receipt = json.loads((tmp_path / "images/val/a.jpg.json").read_text())
    assert receipt["sha256"] == hashlib.sha256(content).hexdigest()
    assert receipt["url"] == photos[0].url
    assert receipt["licence"] == "cc-by-sa" and receipt["author"] == "A photographer"


def test_partial_image_transfer_resumes(tmp_path: Path):
    photos = load_photos(write_labels(tmp_path / "labels.csv", [row("a")]))
    content = jpeg()
    partial = tmp_path / "images/val/a.jpg.part"
    partial.parent.mkdir(parents=True)
    partial.write_bytes(content[:100])

    def respond(request: httpx.Request) -> httpx.Response:
        assert request.headers["Range"] == "bytes=100-"
        return httpx.Response(
            206,
            content=content[100:],
            headers={
                "Content-Range": f"bytes 100-{len(content) - 1}/{len(content)}",
            },
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        prepare_images(tmp_path, photos, client=client, delay=0)
    assert (tmp_path / photos[0].item.file_name).read_bytes() == content
    assert not partial.exists()


def test_download_cannot_replace_a_previously_recorded_image(tmp_path: Path):
    photos = load_photos(write_labels(tmp_path / "labels.csv", [row("a")]))
    content = jpeg()
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, content=content))
    ) as client:
        prepare_images(tmp_path, photos, client=client, delay=0)
    (tmp_path / photos[0].item.file_name).unlink()
    with (
        httpx.Client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(200, content=content + b"changed")
            )
        ) as client,
        pytest.raises(ValueError, match="SHA-256"),
    ):
        prepare_images(tmp_path, photos, client=client, delay=0)


def test_metadata_is_verified_even_when_already_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    path = tmp_path / plantclef2024_data.LABELS_PATH
    path.parent.mkdir(parents=True)
    path.write_bytes(b"fixture metadata")
    expected = hashlib.sha256(path.read_bytes()).hexdigest()
    monkeypatch.setattr(plantclef2024_data, "LABELS_SHA256", expected)
    assert plantclef2024_data.labels_file(tmp_path) == path
    path.write_bytes(b"edited metadata")
    with pytest.raises(ValueError, match="Checksum"):
        plantclef2024_data.labels_file(tmp_path)


def test_runner_verifies_models_before_reusing_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    labels = write_labels(tmp_path / "labels.csv", [row("a")])
    monkeypatch.setattr(plantclef2024, "labels_file", lambda _: labels)
    calls: list[str] = []

    def fail(_root: Path) -> dict[str, str]:
        calls.append("verify models")
        raise ValueError("modified checkpoint")

    monkeypatch.setattr(plantclef2024, "verify_inputs", fail)
    with pytest.raises(ValueError, match="modified checkpoint"):
        plantclef2024._run(plantclef2024.SPECIES_ID, RunContext(tmp_path, tmp_path))
    assert calls == ["verify models"]


@pytest.mark.parametrize("linked", [False, True])
def test_runner_adapts_cache_paths_to_shared_predictor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, linked: bool
):
    labels = write_labels(tmp_path / "labels.csv", [row("a"), row("b", tag="test")])
    data_root = tmp_path / "data"
    if linked:
        # An external data directory linked into place: `..` climbs from the link's target.
        (tmp_path / "disk/data/inat2021").mkdir(parents=True)
        data_root.symlink_to(tmp_path / "disk/data")
    context = RunContext(data_root, tmp_path / "external-cache")
    monkeypatch.setattr(plantclef2024, "labels_file", lambda _: labels)
    monkeypatch.setattr(
        plantclef2024, "verify_inputs", lambda _: {"inat2021/models/fixture": "a" * 64}
    )
    monkeypatch.setattr(plantclef2024, "prepare_images", lambda *_: "b" * 64)

    def predict(ctx: RunContext, cache: Path, items: list[Item]) -> list[Prediction]:
        assert cache.name == plantclef2024.evidence_identity(ctx.device)
        for item in items:
            actual = (ctx.data_root / "inat2021" / item.file_name).resolve()
            assert actual.is_relative_to(ctx.cache_dir / "plantclef2024/images")
        return [Prediction(("Ulex europaeus",), (), None, None) for _ in items]

    monkeypatch.setattr(plantclef2024, "predict_all", predict)
    result = plantclef2024._run(plantclef2024.SPECIES_ID, context)
    assert result.configuration["scored_subjects"] == 2
    assert result.configuration["publisher_val_test_binomial_taxa"] == 1
    assert result.inputs["plantclef2024/scored images (SHA-256 of per-file digests)"] == "b" * 64
    assert not any(Path(path).is_absolute() for path in result.inputs)


def test_bounded_prefetch_preserves_prediction_order_and_reuses_shared_predictor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    photos = load_photos(write_labels(tmp_path / "labels.csv", [row(str(i)) for i in range(5)]))
    context = RunContext(tmp_path / "data", tmp_path / "cache")
    cache = context.cache_dir / "plantclef2024"
    cache.mkdir(parents=True)
    downloaded: set[str] = set()
    calls: list[list[str]] = []
    monkeypatch.setattr(plantclef2024, "PREFETCH_SUBJECTS", 2)

    def download(_cache: Path, batch: list[plantclef2024_data.Photo]) -> str:
        assert len(batch) <= 2
        downloaded.update(p.item.source_id for p in batch)
        return "c" * 64

    def predict(_ctx: RunContext, _cache: Path, items: list[Item]) -> list[Prediction]:
        assert all(item.source_id in downloaded for item in items)
        calls.append([item.source_id for item in items])
        return [Prediction((item.source_id,), (), None, None) for item in items]

    monkeypatch.setattr(plantclef2024, "prepare_images", download)
    monkeypatch.setattr(plantclef2024, "predict_all", predict)
    predictions = plantclef2024.predict_photos(context, cache, photos)
    assert calls == [["0.jpg", "1.jpg"], ["2.jpg", "3.jpg"], ["4.jpg"]]
    assert [p.plantclef[0] for p in predictions] == [p.item.source_id for p in photos]


def test_a_corrupt_image_response_is_retried_from_scratch(tmp_path: Path):
    import io

    import httpx
    from PIL import Image

    from weedz.validation import plantclef2024_data

    good = io.BytesIO()
    Image.new("RGB", (4, 4)).save(good, format="JPEG")
    responses = iter([b"<html>busy</html>", good.getvalue()])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=next(responses))

    partial = tmp_path / "photo.jpg.part"
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        plantclef2024_data._download(client, "https://example.invalid/photo", partial, 0.0)
    assert partial.read_bytes() == good.getvalue()


def test_a_mismatched_resume_range_restarts_the_download(tmp_path: Path):
    import io

    import httpx
    from PIL import Image

    from weedz.validation import plantclef2024_data

    good = io.BytesIO()
    Image.new("RGB", (4, 4)).save(good, format="JPEG")
    partial = tmp_path / "photo.jpg.part"
    partial.write_bytes(good.getvalue()[:10])
    ranges: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        ranges.append(request.headers.get("Range"))
        if request.headers.get("Range"):
            return httpx.Response(206, headers={"Content-Range": "bytes 0-9/99"}, content=b"x")
        return httpx.Response(200, content=good.getvalue())

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        plantclef2024_data._download(client, "https://example.invalid/photo", partial, 0.0)
    assert partial.read_bytes() == good.getvalue()
    assert ranges == ["bytes=10-", None]
