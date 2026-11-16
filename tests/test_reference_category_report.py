"""The primary Markdown report must retain functional source-category coverage."""

import hashlib

from test_reference import note, sample

from weedz.reference import collection
from weedz.reference_report import to_markdown


def test_category_coverage_is_rendered_separately_from_species():
    report = to_markdown(collection("functional", [sample(note(taxon=None, category="weed"))]))
    assert "## Category coverage" in report
    assert "| Category |" in report
    assert "| weed | 1 | 1 | 1 |" in report


def test_taxon_only_legacy_markdown_is_unchanged():
    report = to_markdown(collection("legacy", [sample()]))
    assert (
        hashlib.sha256(report.encode()).hexdigest()
        == "c42943f3b377aec6a465e0332a1323739e96f2cc9a08ebc8b5f5a759adfe31f9"
    )
