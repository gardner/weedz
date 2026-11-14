"""Read-only adapters from existing collections into the common sample contract."""

from pathlib import Path, PurePath
from typing import Any

from PIL import Image

from weedz.contract import Annotation, Geography, Ground, Media, Review, Rights, Sample
from weedz.dataset import ATTRIBUTION, LICENSE, REPOSITORY, REVISION, read_observations
from weedz.discovery.records import Photo
from weedz.discovery.store import Store
from weedz.provenance import verify_dataset

HUGGING_FACE = f"https://huggingface.co/datasets/{REPOSITORY}"
# Crops come from a 1.3 cm orthoimage (the dataset README); labels are surveyed points.
LEAFY_SPURGE_GSD_M = 0.013
LEAFY_SPURGE_RIGHTS = Rights(
    media_license=LICENSE,
    metadata_license=LICENSE,
    creator="Doherty et al.",
    attribution=ATTRIBUTION,
    license_source=f"{HUGGING_FACE}/blob/{REVISION}/README.md",
)


def source_uri(relative: PurePath) -> str:
    """The pinned upstream URL; URLs always use '/', whatever the local path separator."""
    return f"{HUGGING_FACE}/resolve/{REVISION}/{relative.as_posix()}"


def leafy_spurge_samples(root: Path) -> list[Sample]:
    """Each surveyed point as a sample, after verifying the pinned source checksums.

    The label is the upstream survey's, attached to the point at the crop centre; it has
    not been independently adjudicated and says nothing about the rest of the crop.
    """
    files = verify_dataset(root)["files"]
    samples = []
    for row in read_observations(root):
        relative_path = row.image_path.relative_to(root.resolve())
        relative = str(relative_path)  # the checksum record's native-path key
        with Image.open(row.image_path) as image:
            width, height = image.size
            image_format = image.format
        point = Annotation(
            id="survey",
            supervision="surveyed_point",
            taxon="Euphorbia esula",
            label="present" if row.label else "absent",
            point=(width / 2, height / 2),
            origin="source",
        )
        samples.append(
            Sample(
                id=f"leafy-spurge:{row.sample_id}",
                source="leafy-spurge",
                source_id=str(row.sample_id),
                snapshot=REVISION,
                rights=LEAFY_SPURGE_RIGHTS,
                media=Media(
                    uri=source_uri(relative_path),
                    sha256=files[relative],
                    width=width,
                    height=height,
                    format=image_format,
                ),
                view="nadir",
                scale="detail",
                geography=Geography(latitude=row.latitude, longitude=row.longitude),
                ground=Ground(gsd_m=LEAFY_SPURGE_GSD_M),
                groups={"survey_cluster": str(row.cluster), "source_split": row.source_split},
                tasks=frozenset({"point_classification"}),
                annotations=(point,),
            )
        )
    return samples


IDENTITY_REVIEW: dict[str, Review] = {
    "confirmed": "accepted",
    "disputed": "rejected",
    "unresolved": "uncertain",
}
SUGGESTION_REVIEW: dict[str, Review] = {
    "confirmed": "accepted",
    "rejected": "rejected",
    "uncertain": "uncertain",
}


def _identity_review(judgements: dict[str, dict[str, dict]]) -> tuple[Review, tuple[str, ...]]:
    """Agreeing standing identity judgements decide a plant; disagreement is uncertain.
    The reviewers are whoever holds those judgements, not the plant's author."""
    standing = judgements["identity"]
    values = {judgement["value"] for judgement in standing.values()}
    names = tuple(sorted(standing))
    if len(values) > 1:
        return "uncertain", names
    return (IDENTITY_REVIEW[values.pop()] if values else "unreviewed"), names


def _finding(plant: dict[str, Any]) -> Annotation:
    review, reviewers = _identity_review(plant["judgements"])
    return Annotation(
        id=f"{plant['kind']}-{plant['id']}",
        supervision="box" if plant["box"] else "image_class",
        taxon=plant["species"] or plant["other_taxon"],
        label="present",
        box=tuple(plant["box"]) if plant["box"] else None,
        origin="reviewer",
        review=review,
        author=plant["reviewer"],
        reviewers=reviewers,
        recorded_at=plant["created_at"],
        note=plant["note"],
    )


def _suggestion_review(row: dict[str, Any]) -> tuple[Review, tuple[str, ...]]:
    """From each reviewer's standing decision, so a later reopen or another reviewer's
    event cannot hide a decision that still stands."""
    standing = row.get("reviewer_decisions") or {}
    if not standing:  # unattributed decisions from before reviewer names existed
        return SUGGESTION_REVIEW.get(row["review_status"], "unreviewed"), ()
    names = tuple(sorted(standing))
    statuses = set(standing.values())
    if len(statuses) > 1:
        return "uncertain", names
    return SUGGESTION_REVIEW.get(statuses.pop(), "unreviewed"), names


def _suggestion(row: dict[str, Any], model: dict[str, Any]) -> Annotation | None:
    """The screening model's best species: a prediction, never supervision."""
    scores = row["scores"]
    if not scores.get("best_species"):
        return None
    review, reviewers = _suggestion_review(row)
    return Annotation(
        id="suggestion",
        supervision="image_class",
        taxon=scores["best_species"],
        label="present",
        origin="model",
        review=review,
        reviewers=reviewers,
        note=scores.get("method", ""),
        model="@".join(filter(None, [model.get("model"), model.get("revision")])) or "unknown",
        score=scores.get("margin"),
    )


def _geography(photo: Photo) -> Geography | None:
    if photo.coordinate_status == "missing" or photo.latitude is None or photo.longitude is None:
        return None
    return Geography(
        latitude=photo.latitude,
        longitude=photo.longitude,
        # An obscured point is deliberately displaced; the observer's GPS accuracy would
        # make it look precise, so its uncertainty stays unknown.
        uncertainty_m=None
        if photo.coordinate_status == "obscured"
        else photo.positional_accuracy_m,
        privacy=photo.coordinate_status,
    )


def _context(photo: Photo) -> dict[str, str]:
    fields = {
        "cohort": photo.cohort,
        "region": photo.region,
        "original_common_name": photo.original_common_name,
        "reference_species": photo.reference_species,
        "lookalike_taxon": photo.lookalike_taxon,
        "lookalike_of": photo.lookalike_of,
    }
    return {name: value for name, value in fields.items() if value}


def _pilot_sample(run_id: str, row: dict[str, Any], model: dict[str, Any]) -> Sample:
    photo = Photo.model_validate(row)
    suggestion = _suggestion(row, model)
    findings = [_finding(plant) for plant in row["findings"]]
    return Sample(
        id=f"inaturalist:{photo.id}",
        source="inaturalist",
        source_id=photo.id,
        snapshot=run_id,
        rights=Rights(
            media_license=photo.photo_license,
            metadata_license=photo.observation_license,
            creator=photo.observer,
            attribution=photo.attribution,
            license_source=photo.source_url,
        ),
        media=Media(
            uri=photo.image_url,
            sha256=photo.sha256 or None,
            width=row["scores"].get("width"),
            height=row["scores"].get("height"),
        ),
        geography=_geography(photo),
        captured_on=photo.observed_on,
        groups={"observation": str(photo.observation_id)},
        original_label=photo.original_taxon,
        context=_context(photo),
        tasks=frozenset({"inference"}),
        annotations=tuple(filter(None, [suggestion, *findings])),
    )


def pilot_samples(store: Store, run_id: str) -> list[Sample]:
    """A pilot run's photos as image-level samples with no plant supervision.

    The original subject and cohort are context only. Reviewer findings are annotations
    whose review state comes from standing identity judgements; the model suggestion is a
    prediction whose review state is the suggestion review.
    """
    run = next((run for run in store.runs() if run["id"] == run_id), None)
    if run is None:
        raise KeyError(run_id)
    return [_pilot_sample(run_id, row, run["model"]) for row in store.photos(run_id)]
