"""Source-defined walk catalogue; no invented routes or manually drawn coastlines."""

from pathlib import Path
from typing import Any

from pipeline.cache import Acquisition

DOC_LAYER = (
    "https://services1.arcgis.com/3JjYDyG3oajxU6HO/arcgis/rest/services/"
    "DOC_Walking_Experiences/FeatureServer/1/query"
)
NAMES = [
    "Lake Waikaremoana Track",
    "Tongariro Northern Circuit",
    "Whanganui Journey",
    "Abel Tasman Coast Track",
    "Heaphy Track",
    "Paparoa Track",
    "Routeburn Track",
    "Milford Track",
    "Kepler Track",
    "Hump Ridge Track",
    "Rakiura Track",
]


def walk_id(name: str) -> str:
    return name.lower().replace(" ", "-")


def source_walks(client: Acquisition, extra: Path) -> list[dict[str, Any]]:
    names = ",".join("'" + n + "'" for n in NAMES)
    data = client.json(
        DOC_LAYER, {"f": "geojson", "where": f"name IN ({names})", "outFields": "*", "outSR": 4326}
    )
    found = {
        f["properties"]["name"]: {
            "id": walk_id(f["properties"]["name"]),
            "name": f["properties"]["name"],
            "source": DOC_LAYER,
            "source_feature_id": f["properties"]["OBJECTID"],
            "source_license": "CC BY 4.0, Department of Conservation",
            "url": f["properties"]["walkingAndTrampingWebPage"],
            "geometry": f["geometry"],
            "mode": "Walking",
        }
        for f in data["features"]
    }
    if extra.exists():
        import json

        for record in json.loads(extra.read_text()):
            found[record["name"]] = record | {"id": walk_id(record["name"])}
    return [found[name] for name in NAMES if name in found]
