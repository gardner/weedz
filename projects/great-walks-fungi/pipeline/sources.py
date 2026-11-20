"""Repeatable acquisition of the extra official DOC routes and public-domain basemap."""

import json
from pathlib import Path
from typing import Any

from pipeline.cache import Acquisition, sha, write_json

NATURAL_EARTH = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/"
    "master/geojson/ne_50m_admin_0_countries.geojson"
)


def _extra_walk(client: Acquisition, source: dict[str, Any]) -> dict[str, Any]:
    field, identifiers = next(iter(source["selector"].items()))
    quoted = ",".join(str(v) if isinstance(v, int) else "'" + v + "'" for v in identifiers)
    data = client.json(
        source["source"] + "/query",
        {
            "f": "geojson",
            "where": f"{field} IN ({quoted})",
            "outFields": "*",
            "outSR": 4326,
            "orderByFields": "OBJECTID ASC",
        },
    )
    if {f["properties"][field] for f in data["features"]} != set(identifiers):
        raise ValueError(f"DOC route source membership changed: {source['name']}")
    lines = []
    for feature in data["features"]:
        geometry = feature["geometry"]
        if geometry["type"] not in ("LineString", "MultiLineString"):
            raise ValueError("DOC source is not a line route")
        lines.extend(
            [geometry["coordinates"]]
            if geometry["type"] == "LineString"
            else geometry["coordinates"]
        )
    return {k: v for k, v in source.items() if k != "selector"} | {
        "source_feature_id": [f["properties"]["OBJECTID"] for f in data["features"]],
        "geometry": {"type": "MultiLineString", "coordinates": lines},
    }


def ensure_sources(root: Path) -> None:
    """Reuse a frozen source bundle, or create it from tracked source selectors."""
    receipt = root / "gis-source-receipt.json"
    if receipt.exists():
        expected = json.loads(receipt.read_text())["files"]
        for filename in ("extra-walks.json", "natural-earth-nz-50m.geojson"):
            if sha(root / filename) != expected[filename]:
                raise ValueError(f"Frozen GIS source checksum changed: {filename}")
        return
    client = Acquisition(root / "requests")
    specifications = json.loads(Path(__file__).with_name("gis-sources.json").read_text())
    extra = [_extra_walk(client, source) for source in specifications]
    write_json(root / "extra-walks.json", extra)
    data = client.json(NATURAL_EARTH, {})
    nz = {
        "type": "FeatureCollection",
        "features": [f for f in data["features"] if f["properties"]["ADM0_A3"] == "NZL"],
    }
    if len(nz["features"]) != 1:
        raise ValueError("Natural Earth NZ selection changed")
    write_json(root / "natural-earth-nz-50m.geojson", nz)
    write_json(root / "source-requests.json", client.receipts)
    write_json(
        receipt,
        {
            "files": {
                name: sha(root / name)
                for name in (
                    "extra-walks.json",
                    "natural-earth-nz-50m.geojson",
                    "source-requests.json",
                )
            },
            "licences": {
                "DOC": "CC BY 4.0, Department of Conservation / © Crown",
                "Natural Earth": "Public domain",
            },
            "note": (
                "Line parts preserved; no inferred straight-line connectors or navigation claim"
            ),
        },
    )
