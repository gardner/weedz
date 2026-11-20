import unittest

from pipeline.analysis import admit, aggregate, route_area
from shapely.geometry import LineString


def observation(identifier=1, **changes):
    result = {
        "id": identifier,
        "observed_on": "2020-04-30",
        "location": "-41,173",
        "positional_accuracy": 20,
        "obscured": False,
        "geoprivacy": None,
        "taxon_geoprivacy": None,
        "user": {"id": 4},
    }
    return result | changes


class AnalysisTests(unittest.TestCase):
    def test_use_observation_month_and_deduplicate_observer_days(self):
        records = [observation(), observation(2), observation(3, observed_on="2021-05-01")]
        result = aggregate(records)
        self.assertEqual(result["counts"], [0, 0, 0, 2, 1, 0, 0, 0, 0, 0, 0, 0])
        self.assertEqual(result["observer_days"][3:5], [1, 1])
        self.assertEqual(result["years"], [2020, 2021])

    def test_tied_peak_preserved_and_empty_has_no_peak(self):
        result = aggregate([observation(), observation(2, observed_on="2020-05-01")])
        self.assertEqual(result["peak_months"], [4, 5])
        self.assertEqual(aggregate([])["peak_months"], [])

    def test_unknown_or_obscured_coordinates_are_excluded(self):
        for changes in [
            {"obscured": True},
            {"positional_accuracy": None},
            {"positional_accuracy": 1001},
            {"geoprivacy": "obscured"},
            {"taxon_geoprivacy": "obscured"},
            {"observed_on": None},
        ]:
            self.assertIsNotNone(admit(observation(**changes), 2016, 2025))
        self.assertIsNone(admit(observation(), 2016, 2025))

    def test_complete_year_window_and_invalid_dates(self):
        for date in ["2015-12-31", "2026-01-01", "2020", "2020-02-31"]:
            self.assertIsNotNone(admit(observation(observed_on=date), 2016, 2025))

    def test_route_buffer_not_just_bounding_box(self):
        area = route_area(LineString([(173, -41), (173.2, -41.2)]), 10)
        self.assertTrue(area.covers_location("-41,173"))
        self.assertFalse(area.covers_location("-40,173"))
        self.assertFalse(area.covers_location("-41.2,173"))
        with self.assertRaises(ValueError):
            route_area(LineString([(173, -41), (173.2, -41.2)]), 0)


if __name__ == "__main__":
    unittest.main()
