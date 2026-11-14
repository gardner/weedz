"""Image-window embeddings are reused only when bytes, weights and preprocessing match."""

from pathlib import Path

import numpy as np
import pytest
import torch
from PIL import Image
from test_discovery_inference import FakeEncoder
from torchvision.transforms import Compose

from weedz.discovery import inference
from weedz.discovery.inference import Screener


class CountingEncoder(FakeEncoder):
    def __init__(self) -> None:
        self.image_calls = 0

    def encode_image(self, image: torch.Tensor, *, normalize: bool) -> torch.Tensor:
        self.image_calls += 1
        return super().encode_image(image, normalize=normalize)


def zeros(_image: Image.Image) -> torch.Tensor:
    return torch.zeros(3)


PREPROCESSING = {"size": [224, 224], "mean": [0.5, 0.5, 0.5], "interpolation": "bicubic"}


def screener(
    cache: Path | None, weights: str = "hash", preprocessing: dict | None = None
) -> tuple[Screener, CountingEncoder]:
    encoder = CountingEncoder()
    recipe = PREPROCESSING if preprocessing is None else preprocessing
    built = Screener(encoder, zeros, lambda prompts: prompts, weights, cache, preprocessing=recipe)
    return built, encoder


def plain_function_transform() -> Compose:
    """A fresh plain function per call, so its repr has a new address, as after a restart."""

    def _convert_to_rgb(image: Image.Image) -> Image.Image:
        return image.convert("RGB")

    return Compose([_convert_to_rgb, zeros])


def photo(tmp_path: Path, colour: tuple[int, int, int] = (200, 200, 220)) -> Path:
    path = tmp_path / f"photo-{colour[0]}.jpg"
    Image.new("RGB", (40, 30), colour).save(path)
    return path


def test_second_screen_of_the_same_photo_reuses_embeddings(tmp_path: Path) -> None:
    path = photo(tmp_path)
    cached, encoder = screener(tmp_path / "cache")
    first = cached.screen(path, "Morus serrator, Australasian gannet")
    second = cached.screen(path, "Morus serrator, Australasian gannet")
    assert encoder.image_calls == 1
    assert (first["embedding_cache"], second["embedding_cache"]) == ("miss", "hit")
    uncached, _ = screener(None)
    plain = uncached.screen(path, "Morus serrator, Australasian gannet")
    assert second["window_similarities"] == plain["window_similarities"]
    assert plain["embedding_cache"] == "off"


def test_changed_bytes_weights_or_windows_miss_the_cache(tmp_path: Path, monkeypatch) -> None:
    cache = tmp_path / "cache"
    first, _ = screener(cache)
    first.screen(photo(tmp_path))
    other_bytes, encoder = screener(cache)
    other_bytes.screen(photo(tmp_path, (10, 120, 40)))
    assert encoder.image_calls == 1
    other_weights, encoder = screener(cache, weights="other")
    other_weights.screen(photo(tmp_path))
    assert encoder.image_calls == 1
    monkeypatch.setattr(inference, "WINDOW_REVISION", inference.WINDOW_REVISION + 1)
    other_windows, encoder = screener(cache)
    other_windows.screen(photo(tmp_path))
    assert encoder.image_calls == 1


@pytest.mark.parametrize("contents", [b"not an array", b""], ids=["garbage", "empty"])
def test_unreadable_cache_entries_are_recomputed(tmp_path: Path, contents: bytes) -> None:
    cache = tmp_path / "cache"
    first, _ = screener(cache)
    first.screen(photo(tmp_path))
    for entry in cache.glob("*.npy"):
        entry.write_bytes(contents)
    again, encoder = screener(cache)
    assert again.screen(photo(tmp_path))["embedding_cache"] == "miss"
    assert encoder.image_calls == 1


def test_metadata_records_the_cache_recipe(tmp_path: Path) -> None:
    cached, _ = screener(tmp_path / "cache")
    assert cached.metadata["embedding_cache"]["window_revision"] == inference.WINDOW_REVISION


def test_preprocessing_fingerprint_ignores_transform_object_identity(tmp_path: Path) -> None:
    first, second = plain_function_transform(), plain_function_transform()
    assert repr(first) != repr(second)
    built = [
        Screener(CountingEncoder(), transform, lambda p: p, "hash", preprocessing=PREPROCESSING)
        for transform in (first, second)
    ]
    assert built[0].preprocessing_sha256 == built[1].preprocessing_sha256
    assert built[0].metadata == built[1].metadata


def test_changed_preprocessing_recipe_misses_the_cache(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    first, _ = screener(cache)
    first.screen(photo(tmp_path))
    resized, encoder = screener(cache, preprocessing={**PREPROCESSING, "size": [336, 336]})
    assert resized.screen(photo(tmp_path))["embedding_cache"] == "miss"
    assert encoder.image_calls == 1


def test_same_count_window_geometry_change_misses_the_cache(tmp_path: Path, monkeypatch) -> None:
    cache = tmp_path / "cache"
    first, _ = screener(cache)
    first.screen(photo(tmp_path))
    original = inference.region_boxes

    def shifted(width: int, height: int) -> list[tuple[int, int, int, int]]:
        return [(x0, y0, max(x0 + 1, x1 - 1), y1) for x0, y0, x1, y1 in original(width, height)]

    monkeypatch.setattr(inference, "region_boxes", shifted)
    moved, encoder = screener(cache)
    assert moved.screen(photo(tmp_path))["embedding_cache"] == "miss"
    assert encoder.image_calls == 1


def test_cached_embeddings_of_the_wrong_width_are_recomputed(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    first, _ = screener(cache)
    first.screen(photo(tmp_path))
    for entry in cache.glob("*.npy"):
        rows = len(np.load(entry))
        np.save(entry, np.zeros((rows, 7), dtype=np.float32))
    again, encoder = screener(cache)
    assert again.screen(photo(tmp_path))["embedding_cache"] == "miss"
    assert encoder.image_calls == 1


def test_recipe_versions_cover_the_libraries_that_decode_and_resize() -> None:
    import open_clip
    import PIL
    import torch
    import torchvision

    from weedz.discovery.inference import library_versions

    assert library_versions() == {
        "open_clip": open_clip.__version__,
        "torch": torch.__version__,
        "torchvision": torchvision.__version__,
        "pillow": PIL.__version__,
    }


def test_a_different_pinned_model_misses_the_cache(tmp_path: Path, monkeypatch) -> None:
    cache = tmp_path / "cache"
    first, _ = screener(cache)
    first.screen(photo(tmp_path))
    monkeypatch.setattr(inference, "REVISION", "0" * 40)
    other, encoder = screener(cache)
    other.screen(photo(tmp_path))
    assert encoder.image_calls == 1


@pytest.mark.parametrize("bad", ["integers", "nan"])
def test_cached_arrays_must_be_finite_floats(tmp_path: Path, bad: str) -> None:
    import numpy as np

    cache = tmp_path / "cache"
    first, _ = screener(cache)
    first.screen(photo(tmp_path))
    for entry in cache.glob("*.npy"):
        stored = np.load(entry)
        if bad == "integers":
            stored = stored.astype(np.int64)
        else:
            stored[0, 0] = np.nan
        np.save(entry, stored)
    again, encoder = screener(cache)
    assert again.screen(photo(tmp_path))["embedding_cache"] == "miss"
    assert encoder.image_calls == 1
