"""Rate-limited iNaturalist acquisition, retaining a raw, attributed bronze snapshot."""

import hashlib
import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

import httpx
from PIL import Image

from weedz.discovery.lookalikes import LOOKALIKES
from weedz.discovery.records import REGIONS, SPECIES, Photo, RunSpec
from weedz.discovery.sampling import season_windows, select_across_strata

LICENSES = {"cc0", "cc-by", "cc-by-nc"}
HEADERS = {"User-Agent": "Weedz/0.1 (open-source non-commercial conservation research)"}


def photo_from_observation(
    raw: dict,
    region: str,
    cohort: Literal["incidental", "reference", "lookalike"],
    reference_species: str | None = None,
    lookalike_taxon: str | None = None,
    lookalike_of: str | None = None,
) -> Photo | None:
    if raw.get("license_code") not in LICENSES:
        return None
    eligible = [photo for photo in raw.get("photos", []) if photo.get("license_code") in LICENSES]
    if not eligible:
        return None
    photo = eligible[0]
    latitude, longitude = _coordinates(raw.get("location"))
    status = "missing" if latitude is None else ("obscured" if raw.get("obscured") else "public")
    taxon = raw.get("taxon") or {}
    return Photo(
        id=f"inat-{raw['id']}-{photo['id']}",
        observation_id=raw["id"],
        photo_id=photo["id"],
        region=region,
        cohort=cohort,
        reference_species=reference_species,
        lookalike_taxon=lookalike_taxon,
        lookalike_of=lookalike_of,
        source_url=raw["uri"],
        image_url=photo["url"].replace("/square.", "/large."),
        attribution=photo.get("attribution") or raw["user"]["login"],
        photo_license=photo["license_code"],
        observation_license=raw["license_code"],
        observer=raw["user"]["login"],
        original_taxon=taxon.get("name", "Unknown"),
        original_common_name=taxon.get("preferred_common_name", ""),
        observed_on=raw.get("observed_on"),
        uploaded_at=raw.get("created_at"),
        latitude=latitude,
        longitude=longitude,
        positional_accuracy_m=raw.get("positional_accuracy"),
        coordinate_status=status,
    )


def _coordinates(value: str | None) -> tuple[float | None, float | None]:
    if not value:
        return None, None
    latitude, longitude = (float(part) for part in value.split(","))
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise ValueError("Invalid source coordinates")
    return latitude, longitude


class Inaturalist:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.client = httpx.Client(headers=HEADERS, timeout=60, follow_redirects=True)
        self.last_request = 0.0

    def close(self) -> None:
        self.client.close()

    def _response(self, url: str, params: dict | None = None) -> httpx.Response:
        time.sleep(max(0, 1.1 - (time.monotonic() - self.last_request)))
        self.last_request = time.monotonic()
        response = self.client.get(url, params=params)
        response.raise_for_status()
        return response

    def query(self, snapshot: Path, params: dict) -> dict:
        if snapshot.exists():
            return json.loads(snapshot.read_text())
        data = self._response("https://api.inaturalist.org/v1/observations", params).json()
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        temporary = snapshot.with_suffix(".tmp")
        temporary.write_text(json.dumps({"params": params, "response": data}, indent=2))
        temporary.replace(snapshot)
        return {"params": params, "response": data}

    def image(self, photo: Photo) -> Photo:
        parsed = urlparse(photo.image_url)
        if parsed.scheme != "https" or parsed.hostname not in {
            "inaturalist-open-data.s3.amazonaws.com",
            "static.inaturalist.org",
            "inaturalist-media.s3.amazonaws.com",
        }:
            raise ValueError("Unexpected iNaturalist media host")
        path = self.root / "images" / f"{photo.photo_id}.jpg"
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            response = self._response(photo.image_url)
            if len(response.content) > 15_000_000:
                raise ValueError("Photo exceeds bounded pilot download size")
            temporary = path.with_suffix(".tmp")
            temporary.write_bytes(response.content)
            with Image.open(temporary) as image:
                image.verify()
            temporary.replace(path)
        photo.image_path = str(path.relative_to(self.root))
        photo.sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        return photo

    def collect(
        self, run_id: str, spec: RunSpec, progress: Callable[..., None] = lambda *_: None
    ) -> list[Photo]:
        photos: dict[int, Photo] = {}
        for region, place in REGIONS.items():
            base = {
                "place_id": place,
                "photos": "true",
                "quality_grade": "research",
                "license": ",".join(sorted(LICENSES)),
                "photo_license": ",".join(sorted(LICENSES)),
                "d2": spec.before.isoformat(),
                "order_by": "observed_on",
                "order": "desc",
                "per_page": 100,
            }
            queries = []
            if spec.sampling == "stratified":
                self._stratified(run_id, region, base, spec, photos, progress)
            else:
                queries.append(("incidental", None, spec.limit_per_region, {"taxon_id": 1}))
            queries += [
                ("reference", species, spec.controls_per_species, {"taxon_name": species})
                for species in SPECIES
            ]
            self._lookalikes(run_id, region, base, spec.lookalikes_per_taxon, photos, progress)
            for cohort, species, limit, extra in queries:
                if limit == 0:
                    continue
                snapshot = self.root / "runs" / run_id / f"{region}-{species or 'animals'}.json"
                result = self.query(snapshot, base | extra)
                self._select(
                    result["response"]["results"], photos, region, cohort, species, limit, progress
                )
        return list(photos.values())

    def _lookalikes(
        self,
        run_id: str,
        region: str,
        base: dict,
        limit: int,
        photos: dict[int, Photo],
        progress: Callable[..., None],
    ) -> None:
        """Newest eligible photos of each declared lookalike taxon, kept as their own cohort."""
        if limit == 0:
            return
        for taxon_id, entry in LOOKALIKES.items():
            progress(f"Querying {region}: lookalike {entry['name']}")
            snapshot = self.root / "runs" / run_id / f"{region}-lookalike-{taxon_id}.json"
            result = self.query(snapshot, base | {"taxon_id": taxon_id})
            count = 0
            for raw in result["response"]["results"]:
                photo = photo_from_observation(
                    raw,
                    region,
                    "lookalike",
                    lookalike_taxon=entry["name"],
                    lookalike_of=entry["confusable_with"],
                )
                if photo is None or photo.photo_id in photos:
                    continue
                photos[photo.photo_id] = self.image(photo)
                count += 1
                if count >= limit:
                    break

    def _stratified(
        self,
        run_id: str,
        region: str,
        base: dict,
        spec: RunSpec,
        photos: dict[int, Photo],
        progress: Callable[..., None],
    ) -> None:
        """Query each season window, then download only the round-robin sample."""
        strata: dict[str, list[Photo]] = {}
        for label, first, last in season_windows(spec.after, spec.before):
            progress(f"Querying {region}: {label}")
            snapshot = self.root / "runs" / run_id / f"{region}-animals-{label}.json"
            window = {"taxon_id": 1, "d1": first.isoformat(), "d2": last.isoformat()}
            result = self.query(snapshot, base | window)
            strata[label] = [
                photo
                for raw in result["response"]["results"]
                if (photo := photo_from_observation(raw, region, "incidental")) is not None
                and photo.photo_id not in photos
            ]
        # An outing that crosses the council boundary still counts as one observer-day.
        incidental = [photo for photo in photos.values() if photo.cohort == "incidental"]
        for photo in select_across_strata(strata, spec.limit_per_region, incidental):
            progress(f"Fetching {region}: {photo.id}")
            photos[photo.photo_id] = self.image(photo)

    def _select(
        self,
        observations: list[dict],
        photos: dict[int, Photo],
        region: str,
        cohort: str,
        species: str | None,
        limit: int,
        progress: Callable[..., None],
    ) -> None:
        count = 0
        for raw in observations:
            photo = photo_from_observation(raw, region, cohort, species)  # type: ignore[arg-type]
            if photo is None or photo.photo_id in photos:
                continue
            progress(f"Fetching {region}: {photo.id}")
            photos[photo.photo_id] = self.image(photo)
            count += 1
            if count >= limit:
                break
