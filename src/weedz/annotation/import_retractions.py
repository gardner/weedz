"""Explicit cancelled revisions revoke standing claims without inventing negatives."""

import json
from datetime import datetime

from weedz.annotation.import_records import HumanRecord
from weedz.contract import ReviewEvent, Sample, revise_sample


def retract(sample: Sample, record: HumanRecord, evidence: dict[str, str]) -> Sample:
    existing = next((event for event in sample.review_history if event.id == record.revision), None)
    if existing:
        if existing.payload.get("revision_sha256") != record.sha256:
            raise ValueError("Conflicting cancellation revision bytes")
        return sample
    prior = [
        event
        for event in sample.review_history
        if event.payload.get("annotation_revision_key") == record.key
    ]
    if not prior:
        return sample
    previous = prior[-1]
    if datetime.fromisoformat(record.recorded_at.replace("Z", "+00:00")) <= datetime.fromisoformat(
        str(previous.recorded_at).replace("Z", "+00:00")
    ):
        raise ValueError("Cancelled revision must advance its recorded timestamp")
    event = ReviewEvent.model_validate(
        dict(
            id=record.revision,
            sample_id=sample.id,
            media_sha256=sample.media.sha256,
            origin="reviewer",
            actor=record.actor,
            recorded_at=record.recorded_at,
            action="retracted_human_annotation",
            dimension="annotation",
            supersedes=previous.id,
            evidence=evidence,
            payload={
                "annotation_revision_key": record.key,
                "revision_sha256": record.sha256,
                "cancelled": True,
                "annotation_author": record.author,
                "actor_field": record.actor_field,
                "attribution": (
                    "Revision account supplied by updated_by"
                    if record.actor_field == "updated_by"
                    else "Annotation author account; cancellation editor not separately identified"
                ),
            },
        )
    )
    event = ReviewEvent.model_validate_json(
        json.dumps(event.model_dump(mode="json"), sort_keys=True)
    )
    return revise_sample(
        sample,
        annotations=[
            note for note in sample.annotations if not note.id.startswith(f"{record.key}:region:")
        ],
        completeness=[
            item for item in sample.completeness if item.id != f"{record.key}:completeness"
        ],
        review_history=[*sample.review_history, event],
    )
