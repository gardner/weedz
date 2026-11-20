"""Build a single-file offline map from closed source-bound aggregate results."""

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import shapely
from shapely.geometry import MultiPolygon, mapping, shape

from pipeline.analysis import TO_DEGREES, aggregate, route_area
from pipeline.cache import sha, write_json
from pipeline.catalog import NAMES

PROJECT = Path(__file__).resolve().parent.parent


def basemap(path: Path) -> dict[str, Any]:
    source = json.loads(path.read_text())
    if source["type"] == "FeatureCollection":
        source = source["features"][0]
    geometry = shape(source["geometry"] if source["type"] == "Feature" else source)
    polygons = [p for p in geometry.geoms if 165 < p.centroid.x < 180 and -49 < p.centroid.y < -33]
    if not polygons:
        raise ValueError("No mainland New Zealand polygons in sourced basemap")
    # d3-geo expects clockwise exterior spherical rings, unlike the GeoJSON convention.
    geometry = shapely.orient_polygons(MultiPolygon(polygons), exterior_cw=True)
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"name": "New Zealand"},
                "geometry": mapping(geometry),
            }
        ],
    }


def prepare(snapshot: Path, extra: Path) -> dict[str, Any]:
    catalog = json.loads((snapshot / "catalog.json").read_text())
    if {w["name"] for w in catalog} != set(NAMES) or len(catalog) != 11:
        raise ValueError("Final map requires all eleven sourced Great Walks")
    config = json.loads((snapshot / "config.json").read_text())
    walks: list[dict[str, Any]] = []
    all_ids: set[int] = set()
    for item in catalog:
        source_path = snapshot / "walks" / (item["id"] + ".json")
        raw = json.loads(source_path.read_text())
        if raw["walk"] != item:
            raise ValueError("Geometry changed after observation acquisition")
        area = route_area(shape(item["geometry"]), config["radius_km"])
        # Simplification is viewing-only; geographic admission used original geometry.
        route = shapely.transform(area.route.simplify(60), TO_DEGREES.transform, interleaved=False)
        center = shapely.transform(area.route.centroid, TO_DEGREES.transform, interleaved=False)
        all_ids.update(r["id"] for r in raw["records"])
        query = {
            k: v for k, v in raw["query"].items() if k not in ("per_page", "order_by", "order")
        }
        walks.append(
            {
                **{k: v for k, v in item.items() if k != "geometry"},
                **aggregate(raw["records"]),
                "geometry": mapping(route),
                "center": list(center.coords)[0],
                "exclusions": raw["exclusions"],
                "source_records_sha256": sha(source_path),
                "query_url": "https://www.inaturalist.org/observations?" + urlencode(query),
            }
        )
    return {
        "schema": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        **config,
        "unique_observations": len(all_ids),
        "walks": walks,
        "basemap": basemap(extra / "natural-earth-nz-50m.geojson"),
        "sources": {
            "route_source_receipt_sha256": sha(extra / "gis-source-receipt.json"),
            "request_manifest_sha256": sha(snapshot / "request-manifest.json"),
        },
    }


def build(snapshot: Path, extra: Path, output: Path) -> dict[str, Any]:
    data = prepare(snapshot, extra)
    subprocess.run(["pnpm", "--dir", str(PROJECT / "web"), "run", "build"], check=True)
    template = (PROJECT / "web/template.html").read_text()
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    html = template.replace("__STYLES__", (PROJECT / "web/styles.css").read_text())
    html = html.replace("__DATA__", payload.replace("<", "\\u003c"))
    html = html.replace("__SCRIPT__", (PROJECT / "web/bundle.js").read_text())
    if any(marker in html for marker in ("__STYLES__", "__DATA__", "__SCRIPT__")):
        raise ValueError("Unreplaced template marker")
    output.mkdir(parents=True, exist_ok=True)
    temporary = output / "index.tmp.html"
    temporary.write_text(html)
    temporary.replace(output / "index.html")
    write_json(output / "summary.json", data)
    provenance = {
        "snapshot": str(snapshot),
        "index_sha256": sha(output / "index.html"),
        "summary_sha256": sha(output / "summary.json"),
        "source_files": {
            str(p.relative_to(PROJECT)): sha(p) for p in sorted((PROJECT / "pipeline").glob("*.py"))
        },
        "privacy": "No individual observation locations or observer IDs in public output",
        "offline": "All map geometry, aggregate data, styles and JavaScript embedded",
    }
    write_json(output / "build-receipt.json", provenance)
    return data
