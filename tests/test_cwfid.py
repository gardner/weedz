"""Functional publisher masks retain uncertainty and overlapping native splits."""

from io import BytesIO

import numpy as np
import pytest
from PIL import Image

from weedz.labelled.cwfid import masks, memberships


def png(array):
    out = BytesIO()
    Image.fromarray(np.asarray(array, dtype=np.uint8)).save(out, format="PNG")
    return out.getvalue()


def test_unassigned_vegetation_is_not_assessed_background():
    classes = png([[[255, 0, 0], [0, 255, 0], [0, 0, 0], [0, 0, 0]]])
    vegetation = png([[0, 0, 0, 255]])
    result = masks(classes, vegetation, (4, 1))
    assert list(result["weed"].get_flattened_data()) == [255, 0, 0, 0]
    assert list(result["crop"].get_flattened_data()) == [0, 255, 0, 0]
    assert list(result["vegetation"].get_flattened_data()) == [255, 255, 255, 0]
    assert list(result["assessed"].get_flattened_data()) == [255, 255, 0, 0]


def test_class_pixels_must_be_vegetation():
    with pytest.raises(ValueError, match="vegetation"):
        masks(png([[[255, 0, 0]]]), png([[255]]), (1, 1))


def test_source_split_overlap_preserved():
    assert memberships(28, {"train": [2, 28], "test": [1, 28]}) == ("train", "test")
    assert memberships(2, {"train": [2, 28], "test": [1, 28]}) == ("train",)


def test_interrupted_conversion_resumes_closed_source_identity(tmp_path, monkeypatch):
    import hashlib
    import io
    import json
    import tarfile

    import weedz.labelled.cwfid as module

    archive = tmp_path / "source" / "fixture.tar.gz"
    archive.parent.mkdir()
    root = f"dataset-{module.REVISION}"
    files = {
        f"{root}/images/001_image.png": png([[[10, 20, 30], [30, 20, 10]]]),
        f"{root}/annotations/001_annotation.png": png([[[255, 0, 0], [0, 255, 0]]]),
        f"{root}/masks/001_mask.png": png([[0, 0]]),
        f"{root}/annotations/001_annotation.yaml": b"annotation: []\n",
        f"{root}/train_test_split.yaml": b"train: [1]\ntest: []\n",
    }
    with tarfile.open(archive, "w:gz") as output:
        for name, raw in files.items():
            entry = tarfile.TarInfo(name)
            entry.size = len(raw)
            output.addfile(entry, io.BytesIO(raw))
    monkeypatch.setattr(module, "ARCHIVE_SHA256", hashlib.sha256(archive.read_bytes()).hexdigest())
    output = tmp_path / "converted"
    publish = module.publish

    def interrupted(path, raw):
        if path.name == "001-crop.png":
            raise InterruptedError("cancelled during mask conversion")
        publish(path, raw)

    monkeypatch.setattr(module, "publish", interrupted)
    with pytest.raises(InterruptedError):
        module.prepare(archive, output, limit=1)
    assert not (output / "ready.json").exists()
    image = (output / "images/001.png").read_bytes()
    monkeypatch.setattr(module, "publish", publish)
    sha = module.prepare(archive, output, limit=1)
    assert (output / "images/001.png").read_bytes() == image
    assert json.loads((output / "ready.json").read_text())["manifest_sha256"] == sha
    sample = json.loads((output / "samples.jsonl").read_text())
    assert sample["rights"]["media_license"] == module.TERMS
    assert all(a["origin"] == "source" and a["taxon"] is None for a in sample["annotations"])
    assert all(a["supervision"] == "sparse_mask" for a in sample["annotations"])


def test_conversion_budget_refused_before_source_or_output_access(tmp_path):
    from weedz.labelled.cwfid import prepare

    with pytest.raises(ValueError, match="between 1 and 60"):
        prepare(tmp_path / "missing", tmp_path / "output", limit=61)
    assert not (tmp_path / "output").exists()
