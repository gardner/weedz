"""Ground truth is decoded only from its checksum-bound source bytes."""

import hashlib
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from weedz.region_evaluation.assets import read_binary_mask


def mask(root: Path) -> tuple[Path, str]:
    path = root / "mask.png"
    Image.fromarray(np.array([[0, 255], [255, 0]], dtype=np.uint8)).save(path)
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def test_binary_ground_truth_mask_has_pinned_pixels(tmp_path: Path) -> None:
    _, sha = mask(tmp_path)
    result = read_binary_mask(tmp_path, "mask.png", sha, size=(2, 2))
    assert result.dtype == np.bool_
    assert result.tolist() == [[False, True], [True, False]]


def test_wrong_mask_hash_and_grid_refused(tmp_path: Path) -> None:
    _, sha = mask(tmp_path)
    with pytest.raises(ValueError, match="checksum"):
        read_binary_mask(tmp_path, "mask.png", "0" * 64, size=(2, 2))
    with pytest.raises(ValueError, match="grid"):
        read_binary_mask(tmp_path, "mask.png", sha, size=(3, 2))


def test_rgb_or_soft_masks_are_not_silently_thresholded(tmp_path: Path) -> None:
    for image in (Image.new("RGB", (2, 2)), Image.new("L", (2, 2), 128)):
        path = tmp_path / "mask.png"
        image.save(path)
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        with pytest.raises(ValueError, match="binary"):
            read_binary_mask(tmp_path, "mask.png", sha, size=(2, 2))


def test_external_symlink_refused_before_decode(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    path, sha = mask(tmp_path)
    (source / "mask.png").symlink_to(path)
    with pytest.raises(ValueError, match="root"):
        read_binary_mask(source, "mask.png", sha, size=(2, 2))
