"""Markdown rendering of the pilot outcomes report, for people deciding what to do next."""

from typing import Any

from weedz.discovery.outcomes import plural


def _render(value: Any) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, dict) and "site_visits" in value:
        visits = plural(value["site_visits"], "site visit")
        ungrouped = plural(value["ungrouped_photos"], "ungrouped photo")
        return f"{visits} + {ungrouped} ({plural(value['photos'], 'photo')})"
    if isinstance(value, dict) and set(value) == {"photos"}:
        return plural(value["photos"], "photo")
    if isinstance(value, dict):
        return "; ".join(f"{key}: {_render(item)}" for key, item in value.items()) or "none"
    if isinstance(value, list):
        return " / ".join(map(_render, value)) or "none"
    return str(value)


def to_markdown(report: dict[str, Any]) -> str:
    context = report["context"]
    lines = [
        f"# Pilot outcomes: {report['run_id']}",
        "",
        report["meaning"],
        "",
        f"Incidental photos: {_render(context['incidental'])}. Model: {context['model']}, "
        f"ranking revision {context['ranking_revision']}. Reference snapshot: "
        f"{context['reference_as_of'] or 'none'}.",
        "",
        "| Measure | Status | Value | Out of | Why |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in report["measures"]:
        cells = [item["measure"], item["status"], _render(item["value"])]
        cells += [_render(item["denominator"]), item["reason"] or ""]
        lines.append(f"| {' | '.join(cells)} |")
    lines += ["", "## Evidence"]
    for item in report["measures"]:
        lines += [
            "",
            f"### {item['measure']}",
            "",
            f"Success condition: {item['success_condition']}.",
        ]
        lines += [f"- {key}: {_render(value)}" for key, value in item["evidence"].items()]
    return "\n".join(lines) + "\n"
