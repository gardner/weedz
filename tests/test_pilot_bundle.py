"""Portable pilot archives include only checksum-bound reviewer material."""

import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from weedz.annotation.pilot_bundle import build


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _fixture(root: Path, *, wrong_image: bool = False, hidden_hint: bool = False) -> None:
    image = b"fixture image"
    image_sha = _sha(image)
    prefix = "blind-v1"
    image_path = f"images/{prefix}/{image_sha}.png"
    data = {
        "image": f"/data/local-files/?d={prefix}/{image_sha}.png",
        "photo_credit": "Source fixture",
        "source_dataset": "fixture",
    }
    if wrong_image:
        data["image"] = "/data/local-files/?d=../private/sealed-decisions.json"
    if hidden_hint:
        data["review_hint"] = "A model prediction"
    task = {"data": data, "meta": {"image_sha256": image_sha, "external_id": "fixture"}}
    files = {
        image_path: image,
        "tasks.json": json.dumps([task]).encode(),
        "label-config.xml": b'<View><Image name="image" value="$image" /></View>',
        "private/sealed-decisions.json": b"private",
    }
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    (root / "manifest.json").write_text(
        json.dumps({"task_count": 1, "files": {name: _sha(blob) for name, blob in files.items()}})
    )


def test_bundle_preserves_exact_tasks_and_excludes_private_material(tmp_path: Path) -> None:
    package = tmp_path / "package"
    _fixture(package)
    output = tmp_path / "blind.zip"
    build(package, output, arm="blind")
    with ZipFile(output) as result:
        assert result.read("tasks.json") == (package / "tasks.json").read_bytes()
        assert not any("private" in name for name in result.namelist())
        assert json.loads(result.read("distribution-manifest.json"))["task_count"] == 1


@pytest.mark.parametrize("wrong_image,hidden_hint", [(True, False), (False, True)])
def test_blind_bundle_rejects_unbound_images_and_hints(
    tmp_path: Path, wrong_image: bool, hidden_hint: bool
) -> None:
    package = tmp_path / "package"
    _fixture(package, wrong_image=wrong_image, hidden_hint=hidden_hint)
    output = tmp_path / "blind.zip"
    with pytest.raises(ValueError):
        build(package, output, arm="blind")
    assert not output.exists()
