"""Review preparation does not turn source subjects into human-labelled gold."""

from weedz.labelled.nz_review import eligible


def row(observation, observer):
    return {"id": observation, "user": {"login": observer, "id": observer}}


def test_previous_observation_and_observer_groups_are_excluded():
    assert not eligible(row(1, "new"), {1}, {"id:old"}, set(), set())
    assert not eligible(row(2, "old"), {1}, {"id:old"}, set(), set())
    assert eligible(row(2, "new"), {1}, {"id:old"}, set(), set())


def test_same_observation_and_observer_cannot_be_counted_independent():
    assert not eligible(row(2, "new"), set(), set(), {2}, set())
    assert not eligible(row(2, "new"), set(), set(), set(), {"id:new"})


def test_upright_review_image_has_context_not_gold_and_keeps_actual_licence_codes(tmp_path):
    from io import BytesIO

    from PIL import Image

    from weedz.labelled.nz_review import _sample

    raw = {
        "id": 5,
        "uri": "https://www.inaturalist.org/observations/5",
        "license_code": "cc-by",
        "user": {"id": 9, "login": "source-observer"},
        "taxon": {"name": "Ulex europaeus"},
        "photos": [
            {
                "id": 6,
                "url": "https://static.inaturalist.org/photos/6/square.jpg",
                "license_code": "cc0",
                "attribution": "Actual photographer credit",
            }
        ],
        "location": "-41,173",
        "obscured": True,
        "positional_accuracy": 1000,
        "observed_on": "2024-01-01",
        "created_at": "2024-01-02T01:00:00Z",
    }
    image = Image.new("RGB", (3, 2), "green")
    exif = Image.Exif()
    exif[274] = 6
    encoded = BytesIO()
    image.save(encoded, format="JPEG", exif=exif)
    sample = _sample(raw, encoded.getvalue(), "a" * 64, "gorse", tmp_path)
    assert (sample.media.width, sample.media.height) == (2, 3)
    assert not sample.annotations and not sample.completeness
    assert sample.tasks == frozenset({"inference"})
    assert sample.original_label == "Ulex europaeus"
    assert sample.rights.media_license == "cc0" and sample.rights.metadata_license == "cc-by"
    assert sample.geography is not None
    assert sample.geography.privacy == "obscured"
    assert sample.geography.uncertainty_m is None
    assert sample.groups["observer"] == "inaturalist:9"
    with Image.open(tmp_path / sample.media.uri) as upright:
        assert upright.size == (2, 3) and not upright.getexif()


def test_download_to_conversion_bytes_are_joined_before_source_attribution(tmp_path, monkeypatch):
    import pytest

    from weedz.discovery.records import Photo
    from weedz.discovery.source import Inaturalist
    from weedz.labelled.nz_review import downloaded_bytes
    from weedz.labelled.publication import digest

    (tmp_path / "source.jpg").write_bytes(b"changed after verified acquisition")
    photo = Photo.model_construct(image_path="source.jpg", sha256=digest(b"acquired bytes"))
    client = Inaturalist(tmp_path, allowed_photo_licences=frozenset({"cc0"}))
    monkeypatch.setattr(client, "image", lambda _: photo)
    try:
        with pytest.raises(ValueError, match="source bytes changed"):
            downloaded_bytes(client, photo)
    finally:
        client.close()
