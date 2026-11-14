"""Markdown rendering of a follow-up package, for a specialist or field surveyor."""

from typing import Any

from weedz.discovery.outcome_terms import plural

KIND = {
    "suggestion": "Suggested by screening",
    "correction": "Reviewer's correction of the suggestion",
    "addition": "Plant the screening missed, recorded by a reviewer",
}
NONE_SELECTED = (
    "No leads are selected for follow-up in this run. A reviewer selects a lead, with a "
    "reason, from its photo in the review app."
)


def _name(candidate: dict[str, Any]) -> str:
    species = candidate["species"] or "Unknown"
    common = candidate["common_name"]
    return f"{common} (*{species}*)" if common else f"*{species}* (as typed by the reviewer)"


def _selection(selection: dict[str, Any]) -> list[str]:
    lines = [
        f"**Why follow up:** {selection['reason']}",
        f"Selected by {selection['selector']} on {selection['created_at'][:10]}.",
    ]
    earlier = selection["history"][:-1]
    if earlier:
        lines.append(
            "Earlier: "
            + "; ".join(
                f"{event['action']} by {event['selector']} on {event['created_at'][:10]} "
                f"({event['reason']})"
                for event in earlier
            )
        )
    return lines


def _candidate(lead: dict[str, Any]) -> list[str]:
    candidate, subject = lead["candidate"], lead["original_subject"]
    by = f" ({candidate['recorded_by']})" if candidate["recorded_by"] else ""
    note = f" Note: {candidate['note']}" if candidate["note"] else ""
    subject_name = subject["common_name"] or subject["taxon"]
    return [
        f"**Candidate:** {_name(candidate)}. {KIND[candidate['kind']]}{by}.{note}",
        f"**Photo's original subject:** {subject_name} (*{subject['taxon']}*), which is "
        "context, not evidence about the plant.",
    ]


def _source(lead: dict[str, Any]) -> list[str]:
    source, image = lead["source"], lead["image"]
    lines = [
        f"**Source:** <{source['url']}> by {source['observer']}. {source['attribution']}. "
        f"Photo licence {source['photo_license']}; observation licence "
        f"{source['observation_license']}.",
    ]
    if image["included"]:
        lines.append(f"![Photo {lead['photo_id']}]({image['file']}) {image['terms']}.")
    else:
        lines.append(f"**Photo:** {image['terms']}.")
    lines += [
        f"Detail, box {box['box']} in image pixels (left, top, right, bottom): {box['is']}."
        for box in image["detail"]
    ]
    return lines


def _where(limits: dict[str, Any]) -> list[str]:
    area, dates = limits["search_area"], limits["dates"]
    if area["status"] == "searchable":
        latitude, longitude = area["centre"]
        context = "precise enough" if area["site_context"] else "not precise enough"
        where = (
            f"**Where to search:** within {area['radius_m']:g} m of {latitude}, {longitude}, "
            f"the {area['centre_is']}. Radius = reported accuracy {area['accuracy_m']:g} m + "
            f"{area['allowance_reason']}. The location is {context} for aerial site context."
        )
    else:
        where = f"**Where to search:** not searchable. {area['reason']}."
    when = (
        f"**Dates:** photographed {dates['photographed'] or 'unknown'}; uploaded "
        f"{dates['uploaded'] or 'unknown'}; screened {dates['screened'] or 'unknown'}. "
        f"{dates['current_presence']}."
    )
    return [where, when]


def _review(lead: dict[str, Any]) -> list[str]:
    review = lead["review"]
    decisions = ", ".join(
        f"{name}: {value}" for name, value in review["reviewer_decisions"].items()
    )
    disagree = " Reviewers disagree." if review["reviewers_disagree"] else ""
    return [
        f"**Review of {review['about']}:** latest decision {review['latest_decision']}"
        f" ({decisions or 'no attributed decision'}).{disagree}"
    ]


def _judgements(judged: dict[str, Any]) -> list[str]:
    lines = ["| Judgement | Level | Opinions |", "| --- | --- | --- |"]
    for dimension, entry in judged.items():
        if dimension == "disputed_dimensions":
            continue
        opinions = "; ".join(
            f"{name}: {opinion['value']}" + (f" ({opinion['note']})" if opinion["note"] else "")
            for name, opinion in entry["by_reviewer"].items()
        )
        lines.append(f"| {dimension} | {entry['level']} | {opinions or 'none'} |")
    return lines


def _comparison(comparison: dict[str, Any]) -> list[str]:
    snapshot, near = comparison["snapshot"], comparison["records_near_photo"]
    lines = [f"**Judged novelty:** {comparison['judged_novelty']}."]
    if comparison["judged_against_another_snapshot"]:
        lines.append("A record-relative novelty judgement was made against another snapshot.")
    if snapshot is None or not (near and near.get("comparable")):
        return [*lines, f"**Comparison:** {comparison['note']}."]
    nearest = near["nearest"]
    found = f"nearest {nearest['distance_m']} m away" if nearest else "none on record"
    years = f"{near['earliest_year'] or '?'}–{near['latest_year'] or '?'}"
    return [
        *lines,
        f"**Comparison:** {plural(near['within_radius'], 'reference record')} within "
        f"{near['radius_m']:g} m ({years}); {found}. Against {snapshot['snapshot_file']}, "
        f"retrieved {snapshot['retrieved_at']}, SHA-256 {snapshot['snapshot_sha256']}.",
    ]


def _referrals(referrals: list[dict[str, Any]]) -> list[str]:
    lines = []
    for referral in referrals:
        answers = " ".join(
            f"{event['action'].capitalize()} by {event['actor']}: {event['note']}"
            for event in referral["events"]
        )
        lines.append(
            f"- Referral ({referral['status']}, {referral['reason']}) by "
            f"{referral['referrer']}: {referral['note']} {answers}".rstrip()
        )
    return ["**Specialist referrals:**", *lines] if lines else ["**Specialist referrals:** none."]


def _site_visit(visit: dict[str, Any]) -> list[str]:
    if not visit["could_be_grouped"]:
        return ["**Site visit:** could not be grouped with other photos; not independent."]
    others = visit["photos_in_group"] - 1
    return [
        f"**Site visit:** group {visit['group']}, with {plural(others, 'other photo')} from "
        "the same visit (related evidence, not separate infestations)."
    ]


def _lead(number: int, lead: dict[str, Any]) -> list[str]:
    sections = [
        _selection(lead["selection"]),
        _candidate(lead),
        _source(lead),
        _where(lead["limits"]),
        _review(lead),
        _judgements(lead["judgements"]),
        _comparison(lead["comparison"]),
        _referrals(lead["referrals"]),
        _site_visit(lead["site_visit"]),
    ]
    heading = f"## Lead {number}: {_name(lead['candidate'])}, {lead['region']}"
    return [heading, "", *(line for section in sections for line in [*section, ""])]


def to_markdown(package: dict[str, Any]) -> str:
    leads = package["leads"]
    lines = [
        f"# Follow-up package: {package['run']['id']}",
        "",
        f"Generated {package['generated_at']}. "
        f"{plural(len(leads), 'lead')} selected for follow-up.",
        "",
    ]
    if not leads:
        return "\n".join([*lines, NONE_SELECTED, ""])
    lines += ["## How to read this package", ""]
    lines += [f"- {line}" for line in package["how_to_read"]] + [""]
    for number, lead in enumerate(leads, start=1):
        lines += _lead(number, lead)
    return "\n".join(lines)
