"""Conditional crop identification and completeness-scoped false-alarm accounting."""

from collections.abc import Mapping, Sequence

from weedz.contract import Sample
from weedz.region_evaluation.matching import Matching
from weedz.region_evaluation.scope import Target, assess_scope
from weedz.region_evaluation.taxonomy import TaxonomyMapping
from weedz.region_evaluation.truth import LabelledBox


def score_identification(
    sample: Sample,
    truth: Sequence[LabelledBox],
    proposed: Sequence[dict],
    names: Mapping[str, dict],
    taxonomy: TaxonomyMapping,
    matching: Matching,
) -> dict:
    if sample.source != taxonomy.source:
        raise ValueError("Taxonomy mapping belongs to a different source namespace")
    if any(row["id"] not in names for row in proposed):
        raise ValueError("Missing crop identification evidence")
    supported = {index for index, label in enumerate(truth) if label.taxon in taxonomy.mapping}
    conditional = [pair for pair in matching.matches if pair.truth in supported]
    correct = set()
    for pair in conditional:
        source_taxon = truth[pair.truth].taxon
        if source_taxon is not None and (
            names[proposed[pair.proposal]["id"]]["taxon"] == taxonomy.mapping[source_taxon]
        ):
            correct.add(pair.proposal)
    false_alarms = _false_alarms(sample, truth, proposed, names, taxonomy, correct)
    return {
        "supported_labelled_regions": len(supported),
        "unsupported_labelled_regions": len(truth) - len(supported),
        "conditional_top1_count": len(conditional),
        "conditional_top1_correct": len(correct),
        "conditional_top1_accuracy": len(correct) / len(conditional) if conditional else None,
        "unlocalised_supported_labels": len(supported) - len(conditional),
        "misidentified_localised_labels": len(conditional) - len(correct),
        "correctly_identified_labelled_recall": len(correct) / len(supported)
        if supported
        else None,
        **false_alarms,
    }


def _false_alarms(sample, truth, proposed, names, taxonomy, correct: set[int]) -> dict:
    scopes = {
        target: assess_scope(sample, task="detection", target=Target("taxon", target))
        for target in taxonomy.mapping
    }
    inverse = {model: source for source, model in taxonomy.mapping.items()}
    assessed, unassessed = [], []
    for index, proposal in enumerate(proposed):
        target = inverse.get(names[proposal["id"]]["taxon"])
        if target is not None and scopes[target].exhaustive:
            assessed.append(index)
        else:
            unassessed.append(index)
    negative = [
        {
            "target": target,
            "completeness_ids": scope.completeness_ids,
            "origins": scope.origins,
            "correct_negative": all(
                names[proposal["id"]]["taxon"] != taxonomy.mapping[target] for proposal in proposed
            ),
        }
        for target, scope in scopes.items()
        if scope.exhaustive and all(label.taxon != target for label in truth)
    ]
    return {
        "assessed_false_alarm_regions": sum(index not in correct for index in assessed),
        "assessed_prediction_regions": len(assessed),
        "unassessed_false_alarm_regions": len(unassessed),
        "verified_negative_targets": negative,
    }
