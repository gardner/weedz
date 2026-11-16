"""Blind tasks carry credited images, not source subjects or model hints."""

from io import BytesIO

from PIL import Image

from weedz.contract import Media, Rights, Sample
from weedz.labelled.publication import digest
from weedz.labelled.review_package import prepare
from weedz.manifest import write_manifest


def test_blind_package_strips_source_hints_and_keeps_source_identity_private(tmp_path):
    import json

    root = tmp_path / "source"
    root.mkdir()
    out = BytesIO()
    Image.new("RGB", (3, 2), "green").save(out, format="PNG")
    raw = out.getvalue()
    (root / "one.png").write_bytes(raw)
    sample = Sample(
        id="inaturalist:12/34",
        source="inaturalist",
        source_id="12/34",
        snapshot="query",
        rights=Rights(
            media_license="cc0",
            metadata_license="cc-by",
            attribution="Actual credit",
            license_source="https://www.inaturalist.org/observations/12",
        ),
        media=Media(uri="one.png", sha256=digest(raw), width=3, height=2, format="PNG"),
        original_label="Ulex europaeus",
        context={"sampling_stratum": "gorse", "source_observer_login": "Actual observer"},
        groups={"observer": "inaturalist:id:9"},
        tasks=frozenset({"inference"}),
    )
    manifest = root / "samples.jsonl"
    write_manifest(manifest, [sample])
    output = tmp_path / "new-blind-package"
    receipt = prepare(manifest, output, image_prefix="new-blind-package")
    tasks = json.loads((output / "tasks.json").read_text())
    assert receipt["task_count"] == 1
    from weedz.batches.package import validate_package

    package = validate_package(output, digest((output / "manifest.json").read_bytes()))
    assert len(package.tasks) == 1
    assert "Ulex" not in json.dumps(tasks) and "gorse" not in json.dumps(tasks)
    assert all("annotations" not in task and "predictions" not in task for task in tasks)
    assert "Actual credit" in tasks[0]["data"]["photo_credit"]
    assert "d=new-blind-package/" in tasks[0]["data"]["image"]
    assert (output / "private/source-samples.jsonl").read_text() == manifest.read_text()


def test_blind_profile_refuses_model_hints_and_nondefault_rights_before_output(tmp_path):
    import pytest

    from weedz.contract import Annotation
    from weedz.labelled.review_package import _unreviewed

    sample = Sample(
        id="inaturalist:12/34",
        source="inaturalist",
        source_id="12/34",
        snapshot="query",
        rights=Rights(
            media_license="cc0",
            metadata_license="cc0",
            attribution="Source",
            license_source="https://example.org",
        ),
        media=Media(uri="one.png", sha256="a" * 64, width=3, height=2),
        tasks=frozenset({"inference"}),
        annotations=(
            Annotation(
                id="model",
                supervision="image_class",
                taxon="Ulex europaeus",
                label="present",
                origin="model",
                model="test",
            ),
        ),
    )
    with pytest.raises(ValueError, match="without annotations"):
        _unreviewed(sample)


def test_public_source_blind_profile_refuses_consent_backed_contributor_media():
    import pytest

    from weedz.contract import ContributorConsent
    from weedz.labelled.review_package import _unreviewed

    sample = Sample(
        id="inaturalist:12/34",
        source="inaturalist",
        source_id="12/34",
        snapshot="query",
        rights=Rights(
            media_license="cc0",
            metadata_license="cc0",
            attribution="Contributor",
            license_source="https://example.org",
            consent=ContributorConsent(version="2026-11-15", uses=frozenset({"public"})),
        ),
        media=Media(uri="one.png", sha256="a" * 64, width=3, height=2),
        tasks=frozenset({"inference"}),
    )
    with pytest.raises(ValueError, match="consent"):
        _unreviewed(sample)
