"""Aggregate assessed positive support, retaining category namespaces and image weights."""

from collections import Counter, defaultdict


def aggregate_sparse(cases: list[dict]) -> dict:
    if not 1 <= len(cases) <= 1000:
        raise ValueError("Use a bounded nonempty collection of evaluated images")
    images: dict[str, list[str]] = defaultdict(list)
    grouped: dict[tuple, list[dict]] = defaultdict(list)
    for case in cases:
        images[case["image_sha256"]].append(case["sample_id"])
        seen = set()
        for label in case["labels"]:
            target = (case["source"], label["category"], label["taxon"])
            for row in label["budgets"]:
                key = (*target, row["budget"])
                if key in seen:
                    raise ValueError(
                        "Multiple sparse masks for one target need explicit union policy"
                    )
                seen.add(key)
                grouped[key].append(row)
    aliases = [identities for identities in images.values() if len(identities) > 1]
    return {
        "record_count": len(cases),
        "unique_image_count": len(images),
        "duplicate_image_groups": aliases,
        "execution_status_counts": dict(Counter(case["proposal_status"] for case in cases)),
        "aggregate": None
        if aliases
        else [_measurement(key, rows) for key, rows in grouped.items()],
        "interpretation": (
            "Assessed labelled-positive support only; no precision, IoU, absence or instance claim"
        ),
    }


def _measurement(key: tuple, rows: list[dict]) -> dict:
    selected = sum(row["assessed_labelled_pixels"] for row in rows)
    covered = sum(row["covered_labelled_pixels"] for row in rows)
    defined = [
        row["covered_labelled_pixels"] / row["assessed_labelled_pixels"]
        for row in rows
        if row["assessed_labelled_pixels"]
    ]
    return {
        "source": key[0],
        "category": key[1],
        "taxon": key[2],
        "budget": key[3],
        "labelled_image_count": len(rows),
        "images_with_assessed_positive_pixels": len(defined),
        "assessed_labelled_pixels": selected,
        "covered_labelled_pixels": covered,
        "excluded_labelled_pixels": sum(row["excluded_labelled_pixels"] for row in rows),
        "micro_positive_pixel_coverage": covered / selected if selected else None,
        "macro_image_positive_pixel_coverage": sum(defined) / len(defined) if defined else None,
    }
