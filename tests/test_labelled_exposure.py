"""Old source aliases and pixels remain explicit exclusion evidence."""

import json
from io import BytesIO

import pytest
from PIL import Image

from weedz.contract import Media, Rights, Sample
from weedz.labelled.exposure import additional, observer_tokens
from weedz.labelled.publication import digest


def test_old_id_alias_pixels_and_observer_evidence_are_joined(tmp_path):
    out = BytesIO()
    Image.new("RGB", (2, 3), "green").save(out, format="PNG")
    raw = out.getvalue()
    (tmp_path / "image.png").write_bytes(raw)
    sample = Sample(
        id="inaturalist:inat-12-34",
        source="inaturalist",
        source_id="inat-12-34",
        snapshot="old",
        rights=Rights(
            media_license="cc0",
            metadata_license="cc-by",
            attribution="Source photographer",
            license_source="https://www.inaturalist.org/observations/12",
        ),
        media=Media(uri="image.png", sha256=digest(raw), width=2, height=3),
        groups={"observer": "inaturalist:Source-Observer"},
        tasks=frozenset({"inference"}),
    )
    manifest = tmp_path / "samples.jsonl"
    manifest.write_text(sample.model_dump_json() + "\n")
    provenance = tmp_path / "provenance.json"
    provenance.write_text(
        json.dumps(
            {
                "photos": [
                    {
                        "photo": {"observation_id": 12, "observer": "Source-Observer"},
                        "scores": {"not": "imported"},
                    }
                ]
            }
        )
    )
    assert additional((manifest,))[1] == {"login:source-observer"}
    observations, observers, pixels, pins = additional((manifest, provenance))
    assert observations == {12} and observers == {"login:source-observer"} and len(pixels) == 1
    assert len(pins) == 2 and all(len(pin["sha256"]) == 64 for pin in pins)
    (tmp_path / "image.png").write_bytes(b"replaced")
    with pytest.raises(ValueError, match="checksum"):
        additional((manifest,))


def test_stable_observer_id_and_casefolded_login_are_separate_aliases():
    assert observer_tokens({"user": {"id": 91, "login": "Observer"}}) == {"id:91", "login:observer"}
