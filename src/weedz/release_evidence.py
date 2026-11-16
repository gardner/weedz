"""Count explicitly checked absences without inventing empty boxes or global negatives."""

from weedz.contract import Sample, Task


def checked_negatives(sample: Sample, task: Task) -> set[str]:
    absent: set[tuple[str, str]] = set()
    present: set[tuple[str, str]] = set()
    for coverage in sample.completeness:
        if coverage.task != task or not coverage.supervises():
            continue
        absent.update(("taxon", value) for value in coverage.taxa)
        absent.update(("category", value) for value in coverage.categories)
        for note in sample.annotations:
            if note.label == "present" and note.supervises():
                present.update(coverage.targets(note))
    return {f"{kind}:{value}" for kind, value in absent - present}
