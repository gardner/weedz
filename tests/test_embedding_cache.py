"""Image-window embeddings are reused only when bytes, weights and preprocessing match."""

from pathlib import Path

import torch
from PIL import Image
from test_discovery_inference import FakeEncoder

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


def screener(cache: Path | None, weights: str = "hash") -> tuple[Screener, CountingEncoder]:
    encoder = CountingEncoder()
    return Screener(encoder, zeros, lambda prompts: prompts, weights, cache), encoder


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


def test_unreadable_cache_entries_are_recomputed(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    first, _ = screener(cache)
    first.screen(photo(tmp_path))
    for entry in cache.glob("*.npy"):
        entry.write_bytes(b"not an array")
    again, encoder = screener(cache)
    assert again.screen(photo(tmp_path))["embedding_cache"] == "miss"
    assert encoder.image_calls == 1


def test_metadata_records_the_cache_recipe(tmp_path: Path) -> None:
    cached, _ = screener(tmp_path / "cache")
    assert cached.metadata["embedding_cache"]["window_revision"] == inference.WINDOW_REVISION
