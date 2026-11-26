"""iNat2021 images are scored only when their bytes match the verified archive."""

import hashlib
import io
import tarfile
from pathlib import Path

import pytest

from weedz.validation import inat2021_data
from weedz.validation.inat2021_data import Item, prepare_images


def _item(name: str) -> Item:
    return Item(name, name, "Ulex europaeus", "Ulex", "Fabaceae", "held-out")


@pytest.fixture
def archive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    cache = tmp_path / "cache"
    cache.mkdir()
    path = cache / "val.tar.gz"
    with tarfile.open(path, "w:gz") as tar:
        for name, data in [("val/a.jpg", b"first"), ("val/b.jpg", b"second")]:
            member = tarfile.TarInfo(f"./{name}")
            member.size = len(data)
            tar.addfile(member, io.BytesIO(data))
    md5 = hashlib.md5(path.read_bytes(), usedforsecurity=False).hexdigest()
    monkeypatch.setattr(inat2021_data, "IMAGES_ARCHIVE_MD5", md5)
    return cache


def test_a_modified_image_on_disk_is_replaced_from_the_archive(tmp_path: Path, archive: Path):
    items = [_item("val/a.jpg"), _item("val/b.jpg")]
    first = prepare_images(tmp_path, archive, items)
    image = tmp_path / "inat2021" / "val" / "a.jpg"
    image.write_bytes(b"truncated")
    assert prepare_images(tmp_path, archive, items) == first
    assert image.read_bytes() == b"first"


def test_an_image_placed_by_hand_is_not_trusted(tmp_path: Path, archive: Path):
    image = tmp_path / "inat2021" / "val" / "b.jpg"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"from somewhere else")
    prepare_images(tmp_path, archive, [_item("val/b.jpg")])
    assert image.read_bytes() == b"second"


def test_the_image_digest_covers_the_requested_bytes(tmp_path: Path, archive: Path):
    one = prepare_images(tmp_path, archive, [_item("val/a.jpg")])
    both = prepare_images(tmp_path, archive, [_item("val/a.jpg"), _item("val/b.jpg")])
    assert len(one) == 64 and one != both
