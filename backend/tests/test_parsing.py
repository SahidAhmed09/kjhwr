"""Parser tests. Expected values are copied by hand from the real fixtures
(see fixtures/SOURCES.md). Cases marked SYNTHETIC are hand-built edge cases;
they exist only in these unit tests."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wind_data.parsing import (DataConflict, ParseError, parse_fuelhh, parse_ts,  # noqa: E402
                               parse_windfor, to_iso)

FIX = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIX / name).read_text())


class TimestampTests(unittest.TestCase):
    def test_roundtrip_and_known_epoch(self):
        self.assertEqual(parse_ts("2026-01-15T00:00:00Z"), 1768435200)
        self.assertEqual(to_iso(1768435200), "2026-01-15T00:00:00Z")

    def test_naive_timestamp_rejected(self):
        with self.assertRaises(ParseError):
            parse_ts("2026-01-15T00:00:00")


class FuelhhRealFixtureTests(unittest.TestCase):
    def setUp(self):
        self.rows = load("fuelhh_wind_2026-01-15_excerpt.json")
        self.actuals, self.dups = parse_fuelhh(self.rows)

    def test_values_match_fixture(self):
        self.assertEqual(self.dups, 0)
        self.assertEqual([a.mw for a in self.actuals], [14602, 14311, 14200, 14516, 14534, 14202])

    def test_times_and_settlement_fields(self):
        a0, a1 = self.actuals[0], self.actuals[1]
        self.assertEqual(to_iso(a0.start), "2026-01-15T00:00:00Z")
        self.assertEqual(to_iso(a0.publish), "2026-01-15T00:30:00Z")
        self.assertEqual((a0.settlement_date, a0.period), ("2026-01-15", 1))
        self.assertEqual(a1.start - a0.start, 1800)  # 30-minute resolution

    def test_sorted_ascending_even_if_input_reversed(self):
        out, _ = parse_fuelhh(list(reversed(self.rows)))
        self.assertEqual(out, self.actuals)


class WindforRealFixtureTests(unittest.TestCase):
    def setUp(self):
        self.fc, self.dups = parse_windfor(load("windfor_2026-01-14_0730_0930_excerpt.json"))

    def test_counts_and_values(self):
        self.assertEqual(self.dups, 0)
        self.assertEqual(len(self.fc), 8)
        first = self.fc[0]
        self.assertEqual(to_iso(first.publish), "2026-01-14T07:30:00Z")
        self.assertEqual(to_iso(first.start), "2026-01-13T21:00:00Z")
        self.assertEqual(first.mw, 12079)
        self.assertEqual([f.mw for f in self.fc[:4]], [12079, 11434, 10988, 10739])

    def test_negative_horizon_is_preserved(self):
        # Real data: the 07:30 publish contains hours that started before it.
        self.assertEqual((self.fc[0].start - self.fc[0].publish) / 3600, -10.5)

    def test_hourly_spacing(self):
        starts = [f.start for f in self.fc[:4]]
        self.assertEqual({b - a for a, b in zip(starts, starts[1:])}, {3600})


class EdgeCaseTests(unittest.TestCase):
    """SYNTHETIC rows."""

    W = {"dataset": "WINDFOR", "publishTime": "2026-01-14T07:30:00Z",
         "startTime": "2026-01-14T00:00:00Z", "generation": 100}

    def test_identical_duplicate_dropped_and_counted(self):
        out, dups = parse_windfor([self.W, dict(self.W)])
        self.assertEqual((len(out), dups), (1, 1))

    def test_conflicting_duplicate_raises(self):
        with self.assertRaises(DataConflict):
            parse_windfor([self.W, {**self.W, "generation": 101}])

    def test_null_generation_kept_as_none(self):
        out, _ = parse_windfor([{**self.W, "generation": None}])
        self.assertIsNone(out[0].mw)

    def test_negative_generation_not_altered(self):
        out, _ = parse_windfor([{**self.W, "generation": -5}])
        self.assertEqual(out[0].mw, -5)

    def test_non_numeric_generation_raises(self):
        with self.assertRaises(ParseError):
            parse_windfor([{**self.W, "generation": "12"}])

    def test_missing_field_raises(self):
        bad = {k: v for k, v in self.W.items() if k != "publishTime"}
        with self.assertRaises(ParseError):
            parse_windfor([bad])

    def test_wrong_fuel_type_rejected(self):
        row = {"dataset": "FUELHH", "publishTime": "2026-01-15T00:30:00Z", "startTime": "2026-01-15T00:00:00Z",
               "settlementDate": "2026-01-15", "settlementPeriod": 1, "fuelType": "CCGT", "generation": 1}
        with self.assertRaises(ParseError):
            parse_fuelhh([row])


if __name__ == "__main__":
    unittest.main()
