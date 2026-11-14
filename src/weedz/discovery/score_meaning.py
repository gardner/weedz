"""What a screening score means, declared per model and ranking revision (issue #16).

A score is only meaningful next to the configuration that produced it, so each
declaration is keyed by `(model_key, ranking_revision)`, pinned to the model revision
and given its own `meaning_version`. Nothing here is fitted: there are no expert-labelled
background weeds to calibrate against, so a declaration states what the score ranks,
what it does not mean, and the measured evidence (source-labelled, not expert-reviewed).
A run on any other configuration gets an explicit "no declared meaning".
"""

import copy
from typing import Any

COMPARISON = "benchmarks/model-comparison.json"
LABELS = "Source labels from iNaturalist observations, not expert review"
SCORE = (
    "The margin: the target weed's image/text cosine similarity minus the strongest "
    "comparison label's (native lookalikes, general vegetation, animals, sky, water, "
    "shore, rock and, for animal photos, the photo's own original subject) in the same "
    "window, taking the best window of the whole frame and its overlapping tiles."
)
USE = (
    "Orders this run's review queue, highest first, and picks the top suggestion shown "
    "to the reviewer. Every photo stays reviewable whatever its score, and the blind "
    "audit sample reaches low-ranked photos."
)
NOT_MEANING = [
    "Not a probability or a confidence that a weed is visible: it is a difference of "
    "two uncalibrated similarities.",
    "A positive margin does not mean a weed is present, and a negative one does not "
    "mean it is absent; no detection threshold has been chosen.",
    "Not comparable across models or ranking revisions: each model has its own scale, so "
    "compare scores only within runs that share this declaration.",
    "The top suggestion is a candidate for review, not an identification; native "
    "lookalikes can rank as a weed.",
    "The window is a search area, not a plant boundary.",
]
CHOOSING = (
    "An operating point (a threshold or an abstention rule) may only be chosen on "
    "development runs whose photos have been reviewed and blind-audited, then fixed "
    "and declared as a new meaning version before any final test. None exists yet."
)
RUN_EVIDENCE = (
    "This run's own evidence is its blind audit summary (found weeds' queue ranks) and "
    "its lookalike summary, in the export."
)


def _evidence(
    references: tuple[int, int],
    incidental: tuple[int, int],
    lookalike_top: tuple[int, int],
    lookalike_positive: tuple[int, int],
) -> list[dict[str, Any]]:
    """The model comparison's (#14) counts, each with what it does and does not show."""
    cited = [
        (
            "references_own_target_top",
            references,
            "{0} of {1} reference photos (the weed is the subject) ranked their own weed first.",
        ),
        (
            "incidental_positive_margin",
            incidental,
            "{0} of {1} pilot animal photos had a positive margin; whether any weed is "
            "visible in them is not yet known.",
        ),
        (
            "lookalike_top_suggestion",
            lookalike_top,
            "{0} of {1} native or lookalike photos had the weed they resemble as the top "
            "suggestion.",
        ),
        (
            "lookalike_positive_margin",
            lookalike_positive,
            "{0} of {1} native or lookalike photos gave the weed they resemble a positive margin.",
        ),
    ]
    return [
        {
            "key": key,
            "count": count,
            "of": of,
            "finding": finding.format(count, of),
            "source": COMPARISON,
            "labels": LABELS,
        }
        for key, (count, of), finding in cited
    ]


def _declare(
    key: str, revision: str, ranking: int, evidence: list[dict[str, Any]]
) -> dict[str, Any]:
    """Pinned to the checkpoint measured: a new pinned revision has no meaning until declared."""
    version = 1
    return {
        "declared": True,
        "id": f"{key}/ranking-{ranking}/meaning-{version}",
        "model_key": key,
        "model_revision": revision,
        "ranking_revision": ranking,
        "meaning_version": version,
        "calibrated": False,
        "score": SCORE,
        "use": USE,
        "not_meaning": NOT_MEANING,
        "operating_point": None,
        "abstention": None,
        "choosing_an_operating_point": CHOOSING,
        "evidence": evidence,
        "run_evidence": RUN_EVIDENCE,
    }


_FIRST = [
    _declare(
        "bioclip-2",
        "2957b322090f9cb17ae72c71981c7218a28d81e0",
        4,
        _evidence((6, 6), (1, 24), (30, 39), (3, 39)),
    ),
    _declare(
        "bioclip",
        "ce901ab3c6a913f9e9ef94ce6d27761069f4f01c",
        4,
        _evidence((6, 6), (5, 24), (32, 39), (17, 39)),
    ),
]
# Every declaration ever made, by id. Declarations are never edited or removed: a run
# keeps the one it was screened under, so a change is a new meaning version.
DECLARED: dict[str, dict[str, Any]] = {meaning["id"]: meaning for meaning in _FIRST}
# The declaration a newly screened run is pinned to, per (model_key, ranking_revision).
CURRENT: dict[tuple[str, int], str] = {
    (meaning["model_key"], meaning["ranking_revision"]): meaning["id"] for meaning in _FIRST
}

UNDECLARED: dict[str, Any] = {
    "declared": False,
    "id": None,
    "calibrated": False,
    "score": "A target-minus-comparison similarity margin from a configuration with no "
    "declared meaning.",
    "use": "Orders the review queue; compare scores only within this run.",
    "not_meaning": NOT_MEANING,
    "operating_point": None,
    "abstention": None,
    "choosing_an_operating_point": CHOOSING,
    "evidence": [],
    "run_evidence": RUN_EVIDENCE,
}


def _configuration(model: dict[str, Any]) -> tuple[str, int]:
    # Metadata saved before model choice existed was always the original BioCLIP.
    return model.get("model_key", "bioclip"), model.get("ranking_revision", -1)


def _applies(meaning: dict[str, Any] | None, model: dict[str, Any]) -> bool:
    """Whether a declaration describes the model, checkpoint and ranking that scored a run."""
    return (
        meaning is not None
        and (meaning["model_key"], meaning["ranking_revision"]) == _configuration(model)
        and model.get("revision") == meaning["model_revision"]
        and model.get("calibrated") is False
    )


def pin_meaning(saved: dict[str, Any] | None, metadata: dict[str, Any]) -> dict[str, Any]:
    """The model metadata to record for a run: the screener's, plus its pinned meaning.

    A resumed run keeps the pin it started with (or none, if screened before pinning),
    and a changed scoring configuration is refused, as mixing scores would be.
    """
    if saved:
        previous = {"model_key": "bioclip"} | saved
        pinned = previous.pop("score_meaning", None)
        if previous != metadata:
            raise ValueError(
                "Scoring configuration changed; start a new run to preserve provenance"
            )
    else:
        current = CURRENT.get(_configuration(metadata))
        pinned = current if _applies(DECLARED.get(current or ""), metadata) else None
    return metadata | ({"score_meaning": pinned} if pinned else {})


def score_meaning(model: dict[str, Any] | None) -> dict[str, Any]:
    """The declared meaning of a run's scores, from the model metadata it recorded.

    A run screened before meanings were pinned has the configuration's first declaration,
    which was the only one when it was scored.
    """
    model = model or {}
    key, ranking = _configuration(model)
    declared = DECLARED.get(model.get("score_meaning") or f"{key}/ranking-{ranking}/meaning-1")
    if declared is None or not _applies(declared, model):
        return copy.deepcopy(UNDECLARED | {"model_key": model.get("model_key")})
    return copy.deepcopy(declared)
