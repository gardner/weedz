"""Review preparation does not turn source subjects into human-labelled gold."""

import pytest

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
    sample, normalized = _sample(raw, encoded.getvalue(), "a" * 64, "gorse")
    assert (sample.media.width, sample.media.height) == (2, 3)
    assert not sample.annotations and not sample.completeness
    assert sample.tasks == frozenset({"inference"})
    assert sample.original_label == "Ulex europaeus"
    assert sample.rights.media_license == "cc0" and sample.rights.metadata_license == "cc-by"
    assert sample.geography is not None
    assert sample.geography.privacy == "obscured"
    assert sample.geography.uncertainty_m is None
    assert sample.groups["observer"] == "inaturalist:id:9"
    with Image.open(BytesIO(normalized)) as upright:
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


def test_decoded_duplicate_never_publishes_an_unmanifested_canonical_png(tmp_path, monkeypatch):
    from io import BytesIO

    from PIL import Image

    import weedz.labelled.nz_review as module
    from weedz.discovery.source import Inaturalist

    encoded = BytesIO()
    Image.new("RGB", (3, 2), "green").save(encoded, format="PNG")
    data = encoded.getvalue()
    rows = []
    for number in [1, 2]:
        rows.append(
            {
                "id": number,
                "uri": f"https://www.inaturalist.org/observations/{number}",
                "license_code": "cc0",
                "user": {"id": number, "login": f"user{number}"},
                "taxon": {"name": "Unknown source subject"},
                "photos": [
                    {
                        "id": number + 10,
                        "url": f"https://static.inaturalist.org/photos/{number + 10}/square.jpg",
                        "license_code": "cc0",
                        "attribution": "Source photographer",
                    }
                ],
            }
        )
    client = Inaturalist(tmp_path / "raw", allowed_photo_licences=frozenset({"cc0"}))
    monkeypatch.setattr(client, "query", lambda *args: {"response": {"results": rows}})

    def image(photo):
        path = client.root / f"images/{photo.photo_id}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        photo.image_path = str(path.relative_to(client.root))
        photo.sha256 = module.digest(data)
        return photo

    monkeypatch.setattr(client, "image", image)
    monkeypatch.setattr(module, "STRATA", (("plants", {"taxon_id": 47126}),))
    output = tmp_path / "canonical"
    try:
        accepted = module._collect(client, output, 20, (set(), set(), set()))
    finally:
        client.close()
    assert len(accepted) == 1
    assert {str(p.relative_to(output)) for p in (output / "images").glob("*.png")} == {
        accepted[0].media.uri
    }


@pytest.mark.parametrize("layout", ["missing", "wrong", "empty"])
def test_invalid_prior_root_refuses_before_output_or_network(tmp_path, monkeypatch, layout):
    import weedz.labelled.nz_review as module

    root = tmp_path / "prior"
    if layout != "missing":
        root.mkdir()
    if layout == "empty":
        (root / "runs").mkdir()
        (root / "images").mkdir()

    def no_network(*args, **kwargs):
        raise AssertionError("must not create a network client for invalid prior evidence")

    monkeypatch.setattr(module, "Inaturalist", no_network)
    output = tmp_path / "new-cohort"
    with pytest.raises(ValueError, match="Prior"):
        module.prepare(root, output, per_stratum=1)
    assert not output.exists()
