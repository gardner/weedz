"""The reference collection as Markdown: standings, uses, coverage, gaps and unknowns."""

from typing import Any

STANDINGS = {
    "original": "The source's own label",
    "accepted": "A reviewer finding or suggestion that reviewers accepted",
    "unresolved": "Reviewers disagree or left it unresolved",
    "unsuitable": "Rejected on review",
    "unreviewed": "A finding or suggestion nobody has judged yet",
}


def _table(header: list[str], rows: list[list[Any]]) -> list[str]:
    lines = ["| " + " | ".join(header) + " |", "|" + " --- |" * len(header)]
    # Reviewers type free-text taxa, so a "|" in one must not split its cell.
    cells = [[str(cell).replace("|", "\\|") for cell in row] for row in rows]
    return lines + ["| " + " | ".join(row) + " |" for row in cells]


def _standings(result: dict[str, Any]) -> list[str]:
    counts = result["standings"]
    rows = [[name.capitalize(), counts.get(name, 0), STANDINGS[name]] for name in STANDINGS]
    return ["## Standing", "", *_table(["Standing", "Examples", "Meaning"], rows), ""]


def _uses(result: dict[str, Any]) -> list[str]:
    rows = [
        [use.capitalize(), summary["eligible"], sum(summary["not_eligible"].values())]
        for use, summary in result["uses"].items()
    ]
    reasons = [
        f"- {use.capitalize()}, not eligible ({count}): {reason}"
        for use, summary in result["uses"].items()
        for reason, count in summary["not_eligible"].items()
    ]
    table = _table(["Use", "Eligible", "Not eligible"], rows)
    return ["## Eligible uses", "", *table, "", *reasons, *([""] if reasons else [])]


def _coverage(result: dict[str, Any]) -> list[str]:
    uses = list(result["uses"])
    rows = [
        [taxon, *(cells[use]["photos"] for use in uses)]
        for taxon, cells in result["coverage"].items()
    ]
    header = ["Species", *(f"Photos for {use}" for use in uses)]
    return ["## Coverage", "", *_table(header, rows), ""]


def _category_coverage(result: dict[str, Any]) -> list[str]:
    if "category_coverage" not in result:
        return []
    uses = list(result["uses"])
    rows = [
        [category, *(cells[use]["photos"] for use in uses)]
        for category, cells in result["category_coverage"].items()
    ]
    return [
        "## Category coverage",
        "",
        *_table(["Category", *(f"Photos for {use}" for use in uses)], rows),
        "",
    ]


def _bullets(title: str, items: list[str]) -> list[str]:
    return [f"## {title}", "", *(f"- {item}" for item in items or ["None"]), ""]


def to_markdown(result: dict[str, Any]) -> str:
    lines = [
        f"# Reference collection: {result['name']}",
        "",
        result["meaning"],
        "",
        *_standings(result),
        *_uses(result),
        *_coverage(result),
        *_category_coverage(result),
        *_bullets("Gaps", result["gaps"]),
        *_bullets("Unknown", result["unknowns"]),
        *_bullets("Not recorded", list(result["not_recorded"].values())),
    ]
    return "\n".join(lines)
