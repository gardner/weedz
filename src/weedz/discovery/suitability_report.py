"""Markdown rendering of a run's source suitability, for deciding whether to review it."""

from typing import Any

from weedz.discovery.outcome_report import render


def _counts(counts: dict[str, Any]) -> str:
    return ", ".join(f"{name} {count}" for name, count in counts.items()) or "none"


def _scope(scope: dict[str, Any]) -> list[str]:
    regions = "; ".join(
        f"{name} {item['photos']} of {item['requested']} requested"
        for name, item in scope["regions"].items()
    )
    lines = [
        "## Scope",
        "",
        f"- Run status: {scope['run_status']}",
        f"- Incidental photos: {render(scope['incidental'])}",
        f"- By region: {regions}",
        f"- Other photos (not incidental): {_counts(scope['other_photos'])}",
    ]
    return lines + [f"- Affected coverage: {gap}" for gap in scope["gaps"]]


def _study(study: dict[str, Any] | None) -> list[str]:
    if study is None:
        return ["- Study: none linked, so no study period or regions to check against"]
    lines = [
        f"- Study: {study['id']}, version {study['version']}; regions "
        f"{', '.join(study['regions']) or 'not recorded'}"
    ]
    return lines + [f"- Differs from the screening: {note}" for note in study["differences"]]


def _period(period: dict[str, Any] | None) -> str:
    if period is None:
        return "not recorded"
    return f"{period['start'] or 'open start'} to {period['end'] or 'open end'}"


def _dates(dates: dict[str, Any]) -> list[str]:
    corpus = dates["corpus"]
    years = dates["years_without_photos"]
    lines = [
        "## Dates",
        "",
        f"- Photographed: {dates['earliest'] or 'unknown'} to {dates['latest'] or 'unknown'}",
        f"- Query period: {_period(dates['query_period'])}; sampling "
        f"{corpus.get('sampling', 'unknown')}",
        f"- Study period: {_period(dates['study_period'])}",
        f"- Outside the study period: {render(dates['outside_study_period'])}",
        f"- Undated: {render(dates['undated'])}; dated only to a month or year: "
        f"{render(dates['imprecise'])}",
        f"- By year: {_counts(corpus.get('by_year', {}))}",
        f"- By season: {_counts(corpus.get('by_season', {}))}",
        "- Years in the period with no photos: "
        + ("unknown (open start)" if years is None else ", ".join(map(str, years)) or "none"),
        f"- Seasons with no photos: {', '.join(dates['seasons_without_photos']) or 'none'}",
    ]
    return lines + [f"- {note}" for note in dates["notes"]]


def _locations(locations: dict[str, Any]) -> list[str]:
    areas, accuracy = locations["search_areas"], locations["accuracy_m"]
    lines = [
        "## Location quality",
        "",
        f"- With a search area: {areas['searchable']} photos; precise enough for aerial site "
        f"context: {areas['site_context_precision']}",
    ]
    lines += [
        f"- Not searchable, {name.replace('_', ' ')}: {render(item)} ({item['reason']})"
        for name, item in locations["not_searchable"].items()
    ]
    return lines + [
        f"- Reported accuracy (public points): {accuracy['reported']} reported, "
        f"{accuracy['not_reported']} not reported; min {render(accuracy['min'])} m, median "
        f"{render(accuracy['median'])} m, max {render(accuracy['max'])} m",
        f"- Accuracy bands: {_counts(accuracy['bands'])}",
    ]


def _uses(uses: dict[str, Any]) -> list[str]:
    places = uses["locations"]
    lines = [
        "## Permitted uses",
        "",
        f"- Photo licences: {_counts(uses['photo_licences'])}",
        f"- Observation licences: {_counts(uses['observation_licences'])}",
        f"- Non-commercial use only: {uses['non_commercial_only']} photos",
        f"- Images that may be shared: {uses['images']['include']}; link only: "
        f"{uses['images']['link']}",
    ]
    lines += [f"  - {reason}: {count}" for reason, count in uses["image_link_reasons"].items()]
    lines.append(
        f"- Locations that may be shared: {places['shared']}; none supplied: "
        f"{places['none_supplied']}"
    )
    return lines + [f"  - {reason}: {count}" for reason, count in places["withheld"].items()]


def _screening(screening: dict[str, Any], independence: dict[str, Any]) -> list[str]:
    pixels, featureless = screening["pixel_coverage"], screening["featureless_windows"]
    return [
        "## Independence",
        "",
        f"- Independent site visits: {independence['independent_site_visits']}; ungrouped "
        f"photos: {independence['ungrouped_photos']}; observers: "
        f"{render(independence.get('observers'))}; observer-days: "
        f"{render(independence.get('observer_days'))}",
        f"- Grouping rule: {independence['rule']}",
        "",
        "## Screening and visibility",
        "",
        f"- Screened: {render(screening['screened'])}; not screened: "
        f"{render(screening['not_screened'])}",
        f"- Every pixel covered by tiles: yes {pixels['complete']}, thinned "
        f"{pixels['thinned']}, not recorded {pixels['not_recorded']}",
        f"- With featureless windows: {featureless['photos_with']}; not recorded "
        f"{featureless['not_recorded']}",
        f"- Visible vegetation: {screening['visible_vegetation']}",
        f"- Original subjects: {_counts(screening['original_subjects'])}",
        f"- Reviewed: {render(screening['reviewed'])}; unassessed: "
        f"{render(screening['unassessed'])}",
    ]


def _comparison(comparison: dict[str, Any]) -> list[str]:
    snapshot = comparison["snapshot"]
    basis = (
        f"{snapshot['title']}, retrieved {snapshot['retrieved_at']}"
        if snapshot
        else "No reference snapshot"
    )
    lines = [
        "## Comparison with known records",
        "",
        f"- Basis: {basis}",
        f"- Compared: {render(comparison['compared'])}",
    ]
    return lines + [
        f"- Not compared, {reason}: {render(count)}"
        for reason, count in comparison["not_compared"].items()
    ]


def _cannot(items: list[dict[str, Any]]) -> list[str]:
    lines = [
        "## What these photos cannot support",
        "",
        "| Conclusion | Photos that cannot support it | Because |",
        "| --- | --- | --- |",
    ]
    return lines + [
        f"| {item['conclusion']} | "
        f"{'not assessed' if item['photos'] is None else render(item['photos'])} | "
        f"{item['because']} |"
        for item in items
    ]


def to_markdown(report: dict[str, Any]) -> str:
    missing = report["missing"]
    lines = [
        f"# Source suitability: {report['run_id']}",
        "",
        report["meaning"],
        "",
        *_scope(report["scope"]),
        *_study(report["study"]),
        "",
        *_dates(report["dates"]),
        "",
        *_locations(report["locations"]),
        "",
        *_uses(report["permitted_uses"]),
        "",
        "## Missing information",
        "",
        f"- Photos missing each field: {_counts(missing)}",
        "",
        *_screening(report["screening"], report["independence"]),
        "",
        *_comparison(report["reference_comparison"]),
        "",
        *_cannot(report["cannot_support"]),
    ]
    return "\n".join(lines) + "\n"
