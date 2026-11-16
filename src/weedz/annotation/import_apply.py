"""Standing human annotations and their immutable revision history."""

import hashlib
import json
from datetime import datetime

from weedz.annotation.import_claims import Claims
from weedz.annotation.import_records import HumanRecord
from weedz.contract import Annotation, Completeness, ReviewEvent, Sample


def _annotations(claims: Claims, categories: set[str]) -> tuple[list[Annotation], dict[str, bytes]]:
    annotations, masks = [], {}
    for region in claims.regions:
        mask_sha = hashlib.sha256(region.mask).hexdigest() if region.mask else None
        mask_uri = f"masks/{mask_sha}.png" if mask_sha else None
        if mask_uri and region.mask:
            masks[mask_uri] = region.mask
        annotations.append(
            Annotation.model_validate(
                dict(
                    id=f"{claims.record.key}:region:{region.id}",
                    supervision="box" if region.box else "dense_mask",
                    taxon=None if region.taxon in categories else region.taxon,
                    category=region.taxon if region.taxon in categories else None,
                    label="present",
                    box=region.box,
                    mask_uri=mask_uri,
                    mask_sha256=mask_sha,
                    origin="reviewer",
                    review=claims.decision.review,
                    author=claims.record.author,
                    reviewers=[claims.record.actor],
                    recorded_at=claims.record.recorded_at,
                )
            )
        )
    return annotations, masks


def _previous(sample: Sample, record: HumanRecord) -> ReviewEvent | None:
    prior = [
        event
        for event in sample.review_history
        if event.payload.get("annotation_revision_key") == record.key
    ]
    return prior[-1] if prior else None


def apply_claims(
    sample: Sample, claims: Claims, evidence: dict[str, str], categories: set[str]
) -> tuple[Sample, dict[str, bytes]]:
    record, decision = claims.record, claims.decision
    existing = next((event for event in sample.review_history if event.id == record.revision), None)
    if existing:
        if existing.payload.get("revision_sha256") != record.sha256:
            raise ValueError("Conflicting bytes for an existing human revision")
        return sample, {}
    prior = _previous(sample, record)
    if prior and datetime.fromisoformat(
        record.recorded_at.replace("Z", "+00:00")
    ) <= datetime.fromisoformat(str(prior.recorded_at).replace("Z", "+00:00")):
        raise ValueError("New human revision must advance its recorded timestamp")
    annotations, masks = _annotations(claims, categories)
    coverage = Completeness.model_validate(
        dict(
            id=f"{record.key}:completeness",
            task=decision.task,
            taxa=decision.taxa,
            categories=decision.categories,
            status=decision.status,
            origin="reviewer",
            author=record.actor,
            review=decision.review,
            reviewers=[record.actor],
            recorded_at=record.recorded_at,
            media_sha256=sample.media.sha256,
            evidence=evidence,
        )
    )
    event = ReviewEvent.model_validate(
        dict(
            id=record.revision,
            sample_id=sample.id,
            media_sha256=sample.media.sha256,
            origin="reviewer",
            actor=record.actor,
            recorded_at=record.recorded_at,
            action="completed_human_revision",
            dimension="annotation",
            supersedes=prior.id if prior else None,
            evidence=evidence,
            payload={
                "annotation_revision_key": record.key,
                "revision_sha256": record.sha256,
                "created_at": record.created_at,
                "actor_field": record.actor_field,
                "annotation_author": record.author,
                "review": decision.review,
                "completeness": coverage.model_dump(mode="json"),
                "annotations": [a.model_dump(mode="json") for a in annotations],
            },
        )
    )
    event = ReviewEvent.model_validate_json(
        json.dumps(event.model_dump(mode="json"), sort_keys=True)
    )
    prefix = f"{record.key}:region:"
    updated = sample.model_dump(mode="json")
    updated.update(
        annotations=[a for a in sample.annotations if not a.id.startswith(prefix)] + annotations,
        completeness=[c for c in sample.completeness if c.id != coverage.id] + [coverage],
        review_history=[*sample.review_history, event],
    )
    # Revalidate rather than using model_copy, which deliberately bypasses validation.
    return Sample.model_validate(updated), masks
