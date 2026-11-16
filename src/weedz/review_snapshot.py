"""One read-only SQLite snapshot of pilot labels, full review history and known groups.

This export does not establish whole-image completeness or promote model suggestions.
The caller assigns a stable database namespace; reviewer display names remain actual
source identities, rather than being represented as verified botanical expertise.
"""

import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from weedz.adapters import _pilot_sample
from weedz.annotation.export import _output
from weedz.contract import Annotation, ReviewEvent, Sample, revise_sample
from weedz.discovery.encounters import with_encounters
from weedz.discovery.store import Store
from weedz.manifest import write_manifest
from weedz.release_storage import staged_release

TABLES = ("reviews", "audits", "findings", "judgements", "referrals", "lead_selections")
ACTOR_FIELDS = {"referrals": "referrer", "lead_selections": "selector", "referral_events": "actor"}
DIMENSIONS = {
    "reviews": "model_suggestion",
    "audits": "watchlist_audit",
    "findings": "annotation",
    "referrals": "referral",
    "referral_events": "referral",
    "lead_selections": "lead_selection",
}
ACTION_FIELDS = {
    "reviews": "status",
    "audits": "finding",
    "judgements": "value",
    "referral_events": "action",
    "lead_selections": "action",
}


def _capture(store: Store | Path, run_id: str) -> tuple[dict[str, Any], list[dict], list[dict]]:
    # Opening a URI in mode=ro avoids Store.connect's write-oriented journal pragmas.
    database = store.database if isinstance(store, Store) else store.resolve() / "discovery.sqlite3"
    read_photos = store._photos if isinstance(store, Store) else Store._photos
    db = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=30)
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        run = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        if run is None:
            raise KeyError(run_id)
        photos = read_photos(db, run_id)
        events = [
            dict(row, source_table=table)
            for table in TABLES
            for row in db.execute(f"SELECT * FROM {table} WHERE run_id=? ORDER BY id", (run_id,))
        ]
        closed = db.execute(
            "SELECT e.*, r.photo_id, r.finding_id FROM referral_events e JOIN referrals r "
            "ON r.id=e.referral_id WHERE r.run_id=? ORDER BY e.id",
            (run_id,),
        )
        events.extend(dict(row, source_table="referral_events") for row in closed)
        return dict(run), photos, events
    finally:
        db.close()


def _actor(namespace: str, actual: str) -> str:
    return f"discovery:{namespace}:reviewer:{actual}"


def _target(row: dict, findings: dict[int, str]) -> str | None:
    if row["source_table"] == "findings":
        return findings[row["id"]]
    found = row.get("finding_id")
    if found is not None:
        return findings.get(found)
    return (
        "suggestion"
        if row["source_table"] in {"reviews", "judgements", "lead_selections"}
        else None
    )


def _history(
    sample: Sample, rows: list[dict], namespace: str, digest: str
) -> tuple[ReviewEvent, ...]:
    findings = {
        row["id"]: f"{row['kind']}-{row['id']}" for row in rows if row["source_table"] == "findings"
    }
    result: list[ReviewEvent] = []
    previous: dict[tuple[str, str, str | None, str], str] = {}
    for row in sorted(rows, key=lambda r: (r["created_at"], r["source_table"], r["id"])):
        table = row["source_table"]
        actual = row.get(ACTOR_FIELDS.get(table, "reviewer"), "")
        actor = _actor(namespace, actual) if actual else f"discovery:{namespace}:unattributed"
        dimension = row["dimension"] if table == "judgements" else DIMENSIONS[table]
        target = _target(row, findings)
        key = (table, actor, target, dimension)
        identifier = f"discovery:{namespace}:{table}:{row['id']}"
        supersedes = previous.get(key) if table in {"reviews", "judgements", "audits"} else None
        result.append(
            ReviewEvent.model_validate(
                {
                    "id": identifier,
                    "sample_id": sample.id,
                    "media_sha256": sample.media.sha256,
                    "origin": "reviewer" if actual else "source",
                    "actor": actor,
                    "recorded_at": row["created_at"],
                    "dimension": dimension,
                    "action": row.get(ACTION_FIELDS.get(table, ""), "recorded"),
                    "annotation_id": target,
                    "supersedes": supersedes,
                    "payload": row,
                    "evidence": {
                        "snapshot_sha256": digest,
                        "source_table": table,
                        "source_row_id": str(row["id"]),
                    },
                }
            )
        )
        previous[key] = identifier
    return tuple(result)


def _annotated(sample: Sample, namespace: str) -> tuple[Annotation, ...]:
    return tuple(
        note.model_copy(
            update={
                "author": _actor(namespace, note.author) if note.author else None,
                "reviewers": tuple(_actor(namespace, actor) for actor in note.reviewers),
            }
        )
        for note in sample.annotations
    )


def reviewed_pilot_samples(store: Store | Path, run_id: str, *, namespace: str) -> list[Sample]:
    """Preserve actual history and typed observer/encounter evidence; keep inference only."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}", namespace):
        raise ValueError("Use a stable ASCII review-store namespace without identity delimiters")
    run, rows, events = _capture(store, run_id)
    raw = json.dumps(
        {"run": run, "photos": rows, "events": events},
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    digest = hashlib.sha256(raw).hexdigest()
    model = json.loads(run["model"])
    samples = []
    for row in with_encounters(rows):
        sample = _pilot_sample(run_id, row, model)
        if sample.media.sha256 is None:
            raise ValueError(f"Review snapshot requires a pinned media SHA for {sample.id}")
        groups, context = dict(sample.groups), dict(sample.context)
        if row["observer"]:
            groups["observer"] = f"inaturalist:login:{row['observer']}"
            context["source_observer_login"] = row["observer"]
        if row["encounter_linkable"]:
            groups["encounter"] = (
                f"discovery:{namespace}:{run_id}:encounter:{row['encounter_group']}"
            )
        context.update(review_snapshot_sha256=digest, review_namespace=namespace)
        history = _history(
            sample, [r for r in events if r["photo_id"] == row["id"]], namespace, digest
        )
        samples.append(
            revise_sample(
                sample,
                groups=groups,
                context=context,
                annotations=_annotated(sample, namespace),
                review_history=history,
            )
        )
    return samples


def write_review_snapshot(source: Path, run_id: str, output: Path, *, namespace: str) -> dict:
    """Export history and groups without opening a writer or copying private source exports."""
    source = source.resolve()
    output = _output(source, output)
    samples = reviewed_pilot_samples(source, run_id, namespace=namespace)
    if not samples:
        raise ValueError("A review snapshot requires at least one source sample")
    with staged_release(output) as staging:
        sha = write_manifest(staging / "samples.jsonl", samples)
        receipt = {
            "schema_version": 1,
            "contract_schema_version": max(s.schema_version for s in samples),
            "source_run_id": run_id,
            "namespace": namespace,
            "count": len(samples),
            "manifest_sha256": sha,
            "source_snapshot_sha256": samples[0].context["review_snapshot_sha256"],
            "interpretation": (
                "Historical inference-only records; no completeness or gold status asserted"
            ),
        }
        (staging / "snapshot.json").write_text(
            json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
        )
    return receipt
