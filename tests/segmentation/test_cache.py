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
