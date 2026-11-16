"""Bounded new NZ observations for later review, with no gold labels or predictions."""

import json
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps

from weedz.contract import Geography, Media, Rights, Sample
from weedz.discovery.source import Inaturalist, photo_from_observation
from weedz.labelled.cwfid import png
from weedz.labelled.pixels import pixel_sha256
from weedz.labelled.publication import close_batch, digest, json_bytes, output_namespace, publish

STRATA = (
    ("gorse", {"taxon_name": "Ulex europaeus"}),
    ("broom", {"taxon_name": "Cytisus scoparius"}),
    ("pampas", {"taxon_name": "Cortaderia"}),
    ("clematis", {"taxon_name": "Clematis vitalba"}),
    ("other-plants", {"taxon_id": 47126}),
    ("incidental-animals", {"taxon_id": 1}),
)
LICENCES = frozenset({"cc0", "cc-by"})


def eligible(
    raw: dict,
    old_ids: set[int],
    old_observers: set[str],
    selected_ids: set[int],
    selected_observers: set[str],
) -> bool:
    return (
        raw["id"] not in old_ids | selected_ids
        and str(raw["user"]["id"]) not in old_observers | selected_observers
    )


def prior_exposure(root: Path) -> tuple[set[int], set[str], set[str]]:
    observations: set[int] = set()
    observers: set[str] = set()
    pixels: set[str] = set()
    for path in sorted((root / "runs").rglob("*.json")):
        record = json.loads(path.read_bytes())
        for row in record.get("response", {}).get("results", []):
            observations.add(row["id"])
            observers.add(str(row["user"]["id"]))
    for path in sorted((root / "images").glob("*")):
        if path.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
            continue
        with Image.open(path) as image:
            pixels.add(pixel_sha256(ImageOps.exif_transpose(image)))
    return observations, observers, pixels


def _sample(raw: dict, image_raw: bytes, query_sha: str, stratum: str, output: Path) -> Sample:
    photo = photo_from_observation(
        raw, "New Zealand", "incidental", allowed_licences=frozenset(LICENCES)
    )
    if photo is None:
        raise ValueError("Both image and observation licences must be admitted")
    with Image.open(BytesIO(image_raw)) as image:
        if image.width * image.height > 40_000_000:
            raise ValueError("NZ source pixel budget exceeded")
        upright = ImageOps.exif_transpose(image).convert("RGB")
        clean = Image.frombytes("RGB", upright.size, upright.tobytes())
    encoded = png(clean)
    uri = f"images/{photo.observation_id}-{photo.photo_id}.png"
    publish(output / uri, encoded)
    geography = None
    if photo.latitude is not None and photo.longitude is not None:
        geography = Geography(
            latitude=photo.latitude,
            longitude=photo.longitude,
            uncertainty_m=photo.positional_accuracy_m,
            privacy="obscured" if photo.coordinate_status == "obscured" else "public",
        )
    return Sample(
        id=f"inaturalist:{photo.observation_id}/{photo.photo_id}",
        source="inaturalist",
        source_id=f"{photo.observation_id}/{photo.photo_id}",
        snapshot=query_sha,
        rights=Rights(
            media_license=photo.photo_license,
            metadata_license=photo.observation_license,
            attribution=photo.attribution,
            license_source=photo.source_url,
        ),
        media=Media(
            uri=uri, sha256=digest(encoded), width=clean.width, height=clean.height, format="PNG"
        ),
        geography=geography,
        captured_on=photo.observed_on,
        original_label=photo.original_taxon,
        groups={
            "observation": f"inaturalist:{photo.observation_id}",
            "observer": f"inaturalist:{raw['user']['id']}",
        },
        tasks=frozenset({"inference"}),
        context={
            "source_url": photo.source_url,
            "source_taxon_context_only": photo.original_taxon,
            "review_status": "unreviewed; no expert NZ gold",
            "sampling_stratum": stratum,
            "uploaded_at": photo.uploaded_at or "unknown",
            "coordinate_status": photo.coordinate_status,
            "original_encoded_sha256": digest(image_raw),
            "decoded_pixel_sha256": pixel_sha256(clean),
            "modifications": "EXIF upright, metadata-free RGB PNG; no resize",
            "encounter_group": "unknown; no independent-site claim",
            "source_photo_license_code": photo.photo_license,
            "source_observation_license_code": photo.observation_license,
            "source_observer_credit": raw["user"]["login"],
        },
    )


def prepare(prior_root: Path, output: Path, *, per_stratum: int = 20) -> str:
    if not 1 <= per_stratum <= 20:
        raise ValueError("NZ review budget is 1–20 per stratum (maximum120)")
    output = output_namespace(output, prior_root)
    old_ids, old_observers, old_pixels = prior_exposure(prior_root)
    exclusions = {
        "observations": sorted(old_ids),
        "observers": sorted(old_observers),
        "decoded_pixel_sha256": sorted(old_pixels),
    }
    publish(output / "prior-exposure.json", json_bytes(exclusions))
    client = Inaturalist(output / "source", allowed_photo_licences=frozenset(LICENCES))
    ids: set[int] = set()
    observers: set[str] = set()
    pixels = set(old_pixels)
    samples = []
    try:
        for stratum, query in STRATA:
            params = {
                "place_id": 6803,
                "photos": "true",
                "quality_grade": "research",
                "license": "cc0,cc-by",
                "photo_license": "cc0,cc-by",
                "per_page": 100,
                "order_by": "observed_on",
                "order": "desc",
                **query,
            }
            record = client.query(output / f"source/queries/{stratum}.json", params)
            query_sha = digest(json_bytes(record))
            count = 0
            for raw in record["response"]["results"]:
                if not eligible(raw, old_ids, old_observers, ids, observers):
                    continue
                photo = photo_from_observation(
                    raw, "New Zealand", "incidental", allowed_licences=frozenset(LICENCES)
                )
                if photo is None:
                    continue
                photo = client.image(photo)
                sample = _sample(
                    raw, (client.root / photo.image_path).read_bytes(), query_sha, stratum, output
                )
                pixel_sha = sample.context["decoded_pixel_sha256"]
                if pixel_sha in pixels:
                    continue
                samples.append(sample)
                ids.add(raw["id"])
                observers.add(str(raw["user"]["id"]))
                pixels.add(pixel_sha)
                count += 1
                if count == per_stratum:
                    break
    finally:
        client.close()
    return close_batch(
        output,
        samples,
        {
            "source": "https://api.inaturalist.org/v1/docs/",
            "maximum_images": per_stratum * len(STRATA),
            "count": len(samples),
            "prior_exposure_sha256": digest(json_bytes(exclusions)),
            "scope": "review preparation only; source subject context is not gold",
            "dedup": "observation/observer against pilot queries; decoded RGB against pilot images",
            "prediction_count": 0,
            "human_annotation_count": 0,
        },
    )
