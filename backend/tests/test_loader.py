"""Loader tests.

Part 1 uses a SYNTHETIC in-memory snapshot to pin exact bisect boundaries.
Part 2 checks the committed real snapshot against facts observed from the live API."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wind_data.loader import Snapshot, load_snapshot  # noqa: E402
from wind_data.parsing import parse_ts  # noqa: E402

SNAP = Path(__file__).resolve().parents[1] / "data" / "snapshot.json.gz"
T = parse_ts("2026-01-15T00:00:00Z")


class BisectBoundaryTests(unittest.TestCase):
    """SYNTHETIC data."""

    def setUp(self):
        self.s = Snapshot({}, [], [[100, T, 1.0], [200, T, 2.0], [300, T, None], [250, T + 3600, 9.0]])

    def test_exactly_at_cutoff_is_included(self):
        self.assertEqual(self.s.latest_forecast(T, 200), (200, 2.0))

    def test_between_vintages(self):
        self.assertEqual(self.s.latest_forecast(T, 299), (200, 2.0))

    def test_before_first_vintage_is_none(self):
        self.assertIsNone(self.s.latest_forecast(T, 99))

    def test_after_last_vintage(self):
        self.assertEqual(self.s.latest_forecast(T, 10**9), (300, None))

    def test_null_latest_does_not_fall_back(self):
        self.assertIsNone(self.s.latest_forecast(T, 300)[1])

    def test_unknown_target_is_none(self):
        self.assertIsNone(self.s.latest_forecast(T + 7200, 10**9))

    def test_vintages_ascending_even_if_input_unsorted(self):
        self.assertEqual([p for p, _ in self.s.vintages(T)], [100, 200, 300])

    def test_targets_are_independent(self):
        self.assertEqual(self.s.latest_forecast(T + 3600, 260), (250, 9.0))
        self.assertIsNone(self.s.latest_forecast(T + 3600, 249))


class RealSnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = load_snapshot(SNAP)

    def test_counts_match_data_report(self):
        self.assertEqual(len(self.s.actuals), 1488)
        self.assertEqual(len(self.s.publish_times), 248)
        self.assertEqual(sum(len(v) for v in self.s._pubs.values()), 18104)

    def test_every_published_hour_has_73_points(self):
        from collections import Counter
        c = Counter(p for v in self.s._pubs.values() for p in v)
        self.assertEqual(set(c.values()), {73})

    def test_latest_forecast_for_known_case(self):
        # Target 2026-01-15 00:00Z, cut-off 2026-01-14 09:20Z: 07:30 is the latest publish <= cut-off
        # (09:30 is after it). Both vintages exist in the snapshot.
        target = parse_ts("2026-01-15T00:00:00Z")
        pub, mw = self.s.latest_forecast(target, parse_ts("2026-01-14T09:20:00Z"))
        self.assertEqual(pub, parse_ts("2026-01-14T07:30:00Z"))
        pub2, _ = self.s.latest_forecast(target, parse_ts("2026-01-14T09:30:00Z"))
        self.assertEqual(pub2, parse_ts("2026-01-14T09:30:00Z"))  # at-cutoff inclusive

    def test_known_actual_from_live_api(self):
        self.assertEqual(self.s.actual(parse_ts("2026-01-15T00:00:00Z")), 14602)

    def test_every_decision_day_has_a_vintage_for_every_delivery_hour(self):
        # Cut-off 09:20Z on D-1, delivery days 2 Jan..1 Feb, 24 hours each.
        from datetime import date, timedelta
        missing = 0
        d = date(2026, 1, 2)
        while d <= date(2026, 2, 1):
            cutoff = parse_ts(f"{(d - timedelta(1)).isoformat()}T09:20:00Z")
            base = parse_ts(f"{d.isoformat()}T00:00:00Z")
            for h in range(24):
                if self.s.latest_forecast(base + 3600 * h, cutoff) is None:
                    missing += 1
            d += timedelta(1)
        self.assertEqual(missing, 0)


if __name__ == "__main__":
    unittest.main()
