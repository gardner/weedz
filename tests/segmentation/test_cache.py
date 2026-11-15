import numpy as np
import pytest

from weedz.segmentation.regions import ProposalConfig
from weedz.segmentation.sam2 import Sam2Proposer


def reader():
    instance = object.__new__(Sam2Proposer)
    instance.config = ProposalConfig()
    return instance


def test_empty_cache_is_valid_without_inventing_a_region(tmp_path):
    path = tmp_path / "cache.npz"
    np.savez_compressed(path, masks=np.zeros((0, 64, 64), bool), quality=np.zeros((0, 2)))
    assert reader()._cached(path) == []


@pytest.mark.parametrize("shape", [(1, 0, 64), (25, 64, 64), (1, 1025, 64)])
def test_cache_rejects_degenerate_or_excessive_geometry(tmp_path, shape):
    path = tmp_path / "cache.npz"
    np.savez_compressed(path, masks=np.zeros(shape, bool), quality=np.zeros((shape[0], 2)))
    with pytest.raises(ValueError):
        reader()._cached(path)


def test_truncated_zip_cache_is_recomputed_instead_of_losing_baseline(tmp_path, monkeypatch):
    from contextlib import nullcontext
    from types import SimpleNamespace

    from PIL import Image

    from weedz.segmentation.regions import cache_key

    instance = reader()
    instance.cache, instance.stamp = tmp_path, "fixed"
    image = Image.new("RGB", (8, 8))
    key = cache_key(image.tobytes(), "fixed" + str(image.size), instance.config)
    path = tmp_path / f"{key}.npz"
    np.savez_compressed(path, masks=np.ones((1, 8, 8), bool), quality=np.array([[0.9, 0.95]]))
    path.write_bytes(path.read_bytes()[:-22])  # Missing ZIP end-of-central-directory record.
    monkeypatch.setattr(
        instance, "torch", SimpleNamespace(inference_mode=nullcontext), raising=False
    )
    generated = []

    def generate(_):
        generated.append(True)
        return [
            {"segmentation": np.ones((8, 8), bool), "predicted_iou": 0.9, "stability_score": 0.95}
        ]

    monkeypatch.setattr(instance, "generator", SimpleNamespace(generate=generate), raising=False)
    assert len(instance.generate(image)) == 1
    assert generated == [True]
