"""Markdown rendering of the pilot outcomes report, for people deciding what to do next."""

from typing import Any

from weedz.discovery.outcomes import plural


def render(value: Any) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, dict) and "site_visits" in value:
        visits = plural(value["site_visits"], "site visit")
        ungrouped = plural(value["ungrouped_photos"], "ungrouped photo")
        return f"{visits} + {ungrouped} ({plural(value['photos'], 'photo')})"
    if isinstance(value, dict) and set(value) == {"photos"}:
        return plural(value["photos"], "photo")
    if isinstance(value, dict):
        return "; ".join(f"{key}: {render(item)}" for key, item in value.items()) or "none"
    if isinstance(value, list):
        return " / ".join(map(render, value)) or "none"
    return str(value)


def _limit(limit: dict[str, Any]) -> str:
    if limit["agreed"] is None:
        return "not agreed"
    return f"{limit['direction']} {limit['agreed']:g} {limit['unit']}"


def _verdict(limit: dict[str, Any]) -> str:
    if limit["agreed"] is None:
        return "no verdict"
    if limit["measured"] is None:
        return limit["verdict"]
    return f"{limit['verdict']} (measured {limit['measured']:g})"


def _budget(name: str, use: dict[str, Any]) -> str:
    if use["budget"] is None:
        return f"{name}: no budget set ({use['used']:g} used)"
    bound = " at least" if use["lower_bound"] else ""
    return f"{name}:{bound} {use['used']:g} of {use['budget']:g} used ({use['state']})"


def _study(study: dict[str, Any] | None) -> list[str]:
    if study is None:
        return [
            "## Study",
            "",
            "No study is linked to this run, so no limit is agreed and no verdict is given.",
            "",
        ]
    use = study["budget_use"]
    lines = [
        "## Study",
        "",
        f"Study {study['id']}, version {study['version']} ({study['status']}), recorded by "
        f"{study['author']} on {study['created_at'][:10]}.",
        "",
        f"- Question: {study['question'] or 'not yet agreed'}",
        f"- Partner: {study['partner'] or 'not yet agreed'}",
        f"- Review budget: {_budget('hours', use['hours'])}; {_budget('photos', use['photos'])}",
        f"- Open decisions: {'; '.join(study['open_decisions']) or 'none'}",
    ]
    lines += [f"- Differs from the screening: {note}" for note in study["differences"]]
    return [*lines, ""]


def to_markdown(report: dict[str, Any]) -> str:
    context = report["context"]
    lines = [
        f"# Pilot outcomes: {report['run_id']}",
        "",
        report["meaning"],
        "",
        f"Incidental photos: {render(context['incidental'])}. Model: {context['model']}, "
        f"ranking revision {context['ranking_revision']}. Reference snapshot: "
        f"{context['reference_as_of'] or 'none'}.",
        "",
        *_study(report.get("study")),
        "| Measure | Status | Value | Out of | Agreed limit | Verdict | Why |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in report["measures"]:
        cells = [item["measure"], item["status"], render(item["value"])]
        limit = item["limit"]
        cells += [render(item["denominator"]), _limit(limit), _verdict(limit)]
        cells.append(item["reason"] or "")
        lines.append(f"| {' | '.join(cells)} |")
    lines += ["", "## Evidence"]
    for item in report["measures"]:
        lines += [
            "",
            f"### {item['measure']}",
            "",
            f"Success condition: {item['success_condition']}.",
            f"Agreed limit: {_limit(item['limit'])}; verdict: {item['limit']['verdict']}. "
            f"{item['limit']['reason']}".rstrip(),
        ]
        if item["limit"]["note"]:
            lines.append(f"Limit note: {item['limit']['note']}")
        lines += [f"- {key}: {render(value)}" for key, value in item["evidence"].items()]
    return "\n".join(lines) + "\n"
