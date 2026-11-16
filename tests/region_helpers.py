"""Constructed contract fixtures, never external benchmark observations."""

from typing import Any

from weedz.contract import Sample


def sample(**fields: Any) -> Sample:
    return Sample.model_validate(
        {
            "id": "cwfid:1",
            "source": "cwfid",
            "source_id": "1",
            "snapshot": "v1",
            "rights": {
                "media_license": "research",
                "metadata_license": "research",
                "attribution": "Publisher",
                "license_source": "https://example.org",
            },
            "media": {"uri": "1.png", "sha256": "a" * 64, "width": 10, "height": 10},
            "tasks": ["inference"],
        }
        | fields
    )
