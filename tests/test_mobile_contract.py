"""The mobile app's report fixture is a valid #57 intake report.

The Dart test checks that the app's report model serialises to this fixture, so
together the two tests keep the app and the server on the same contract.
"""

import json
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parents[1] / "mobile" / "test" / "fixtures" / "report_v1.json"


def test_the_app_fixture_is_a_valid_intake_report() -> None:
    # The intake (#57) may land after the app scaffold; until then there is nothing to check.
    schema = pytest.importorskip("weedz.intake.schema")
    text = FIXTURE.read_text()
    report = schema.Report.model_validate_json(text)
    # Exact coordinates survive validation unchanged.
    assert report.model_dump(mode="json", exclude_none=True) == {
        **json.loads(text),
        "captured_at": "2026-10-02T23:15:42Z",
    }
