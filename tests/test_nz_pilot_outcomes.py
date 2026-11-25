"""Only matching independent review accounts support blind outcome comparisons."""

import hashlib
import json
from pathlib import Path

import pytest

from weedz.annotation.pilot_cue_outcomes import report_cues
from weedz.annotation.pilot_outcomes import evaluate_blind

GORSE = "Ulex europaeus"
PAMPAS = "Cortaderia selloana"


def task(key: str) -> dict:
    return {"data": {"image": key}, "meta": {"external_id": key, "image_sha256": key * 64}}


def result(name: str, *choices: str) -> dict:
    return {"from_name": name, "to_name": "image", "type": "choices", "value": {"choices": choices}}


def vote(reviewer: int, *taxa: str, status: str = "Watchlist plant visible") -> dict:
    results = [result("watchlist_presence", status)]
    if taxa:
        results.append(result("watchlist_species", *taxa))
    for row in results:
        row["value"]["choices"] = list(row["value"]["choices"])
    return {
        "completed_by": reviewer,
        "was_cancelled": False,
        "result": results,
    }


def exported(key: str, *votes: dict) -> dict:
    return task(key) | {
        "id": 7,
        "annotations": [v | {"id": i, "task": 7} for i, v in enumerate(votes, 1)],
    }


def seal(key: str, target: str | None) -> dict:
    row = task(key)["meta"]
    return row | {"target": target}


def test_agreed_visible_taxa_expose_misses_and_unsupported_suggestions() -> None:
    votes = [vote(1, GORSE), vote(2, GORSE)]
    summary = evaluate_blind([task("a")], [exported("a", *votes)], [seal("a", PAMPAS)])
    assert summary["consensus"] == {"agreed_visible": 1}
    assert summary["agreed_visible_taxa"] == 1
    assert summary["agreed_taxa_missed"] == 1
    assert summary["suggestions_supported"] == 0
    assert summary["suggestions_unsupported"] == 1


def test_single_reviewer_duplicate_rows_cannot_become_independent_consensus() -> None:
    votes = [vote(1, GORSE), vote(1, GORSE)]
    summary = evaluate_blind([task("a")], [exported("a", *votes)], [seal("a", None)])
    assert summary["consensus"] == {"single_reviewer": 1}
    assert summary["agreed_taxa_missed"] == 0


def test_disagreement_and_unsure_stay_out_of_agreed_denominators() -> None:
    votes = [vote(1, GORSE), vote(2, PAMPAS)]
    summary = evaluate_blind([task("a")], [exported("a", *votes)], [seal("a", GORSE)])
    assert summary["consensus"] == {"disagreement": 1}
    assert summary["suggestions_unassessed"] == 1
    votes = [vote(1, GORSE), vote(2, status="Unsure")]
    summary = evaluate_blind([task("a")], [exported("a", *votes)], [seal("a", GORSE)])
    assert summary["consensus"] == {"uncertain": 1}
    assert summary["agreed_visible_taxa"] == 0


def test_empty_export_and_seal_binding() -> None:
    summary = evaluate_blind([task("a")], [], [seal("a", None)])
    assert summary["consensus"] == {"unreviewed": 1}
    with pytest.raises(ValueError, match="sealed decisions"):
        evaluate_blind([task("a")], [], [seal("b", None)])


def test_agreed_absence_counts_only_explicit_answers() -> None:
    votes = [vote(i, status="No watchlist plant visible") for i in (1, 2)]
    summary = evaluate_blind([task("a")], [exported("a", *votes)], [seal("a", PAMPAS)])
    assert summary["consensus"] == {"agreed_no_visible": 1}
    assert summary["suggestions_unsupported"] == 1


def test_visible_answer_without_species_is_uncertain() -> None:
    summary = evaluate_blind(
        [task("a")], [exported("a", vote(1), vote(2, GORSE))], [seal("a", GORSE)]
    )
    assert summary["consensus"] == {"uncertain": 1}
    assert summary["suggestions_unassessed"] == 1


def test_camera_cues_bind_package_and_count_independent_reviews(tmp_path: Path) -> None:
    package = tmp_path / "package"
    package.mkdir()
    planned = task("a")
    planned["data"].update(review_hint="Unreviewed cue", search_preview="crop.png")
    raw_tasks = json.dumps([planned]).encode()
    tasks_sha = hashlib.sha256(raw_tasks).hexdigest()
    (package / "tasks.json").write_bytes(raw_tasks)
    raw_manifest = json.dumps({"task_count": 1, "files": {"tasks.json": tasks_sha}}).encode()
    (package / "manifest.json").write_bytes(raw_manifest)
    cue = tmp_path / "cue.json"
    binding = {
        "package_manifest_sha256": hashlib.sha256(raw_manifest).hexdigest(),
        "task_file_sha256": tasks_sha,
        "decisions": [seal("a", GORSE)],
    }
    cue.write_text(json.dumps(binding))
    export = tmp_path / "export.json"
    export.write_text("[]")
    empty = report_cues(package, export, cue)
    assert empty["cue_outcomes"]["suggestions_unassessed"] == 1
    assert empty["effort"]["submissions"] == 0
    assert "agreed_taxa_missed" not in empty["cue_outcomes"]
    row = exported("a", vote(1, GORSE), vote(2, GORSE)) | {"data": planned["data"]}
    export.write_text(json.dumps([row]))
    result = report_cues(package, export, cue)
    assert result["cue_outcomes"]["suggestions_supported"] == 1
    assert result["effort"]["submissions"] == 2

    row["data"] = dict(row["data"], search_preview="wrong.png")
    export.write_text(json.dumps([row]))
    with pytest.raises(ValueError, match="must match the package"):
        report_cues(package, export, cue)
    cue.write_text(json.dumps(binding | {"task_file_sha256": "invalid"}))
    with pytest.raises(ValueError, match="cue receipt"):
        report_cues(package, export, cue)
