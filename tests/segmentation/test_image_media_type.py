from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from test_discovery import observation

from weedz.discovery.api import create_app
from weedz.discovery.records import RunSpec
from weedz.discovery.source import photo_from_observation
from weedz.discovery.store import Store


@pytest.mark.parametrize(
    "format,mime", [("JPEG", "image/jpeg"), ("PNG", "image/png"), ("WEBP", "image/webp")]
)
def test_review_image_uses_encoded_format_not_cache_suffix(tmp_path: Path, format: str, mime: str):
    store = Store(tmp_path)
    store.create_run("run", RunSpec())
    photo = photo_from_observation(observation(), "Nelson", "incidental")
    assert photo
    path = tmp_path / "images" / "public.jpg"  # Existing source cache always uses .jpg.
    path.parent.mkdir()
    Image.new("RGB", (8, 8), (20, 40, 60)).save(path, format=format)
    photo.image_path = "images/public.jpg"
    store.save_photos("run", [photo])
    response = TestClient(create_app(tmp_path)).get(f"/runs/run/photos/{photo.id}/image")
    assert response.status_code == 200
    assert response.headers["content-type"] == mime
    assert response.content == path.read_bytes()
