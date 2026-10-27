import unittest
from datetime import date, time

from synth import ts
from wind_analysis.timeutil import (decision_cutoff, hour_floor, london_date, london_hour,
                                    market_day_slots)


class SlotCountTests(unittest.TestCase):
    def test_normal_winter_day_48_slots(self):
        s = market_day_slots(date(2026, 1, 15))
        self.assertEqual(len(s), 48)
        self.assertEqual(s[0], ts("2026-01-15T00:00:00Z"))
        self.assertEqual(s[-1], ts("2026-01-15T23:30:00Z"))

    def test_normal_summer_day_starts_an_hour_before_midnight_utc(self):
        s = market_day_slots(date(2026, 7, 1))
        self.assertEqual(len(s), 48)
        self.assertEqual(s[0], ts("2026-06-30T23:00:00Z"))

    def test_spring_forward_day_has_46_slots(self):
        s = market_day_slots(date(2026, 3, 29))
        self.assertEqual(len(s), 46)
        self.assertEqual(s[0], ts("2026-03-29T00:00:00Z"))
        self.assertEqual(s[-1], ts("2026-03-29T22:30:00Z"))

    def test_autumn_back_day_has_50_slots(self):
        s = market_day_slots(date(2026, 10, 25))
        self.assertEqual(len(s), 50)
        self.assertEqual(s[0], ts("2026-10-24T23:00:00Z"))
        self.assertEqual(s[-1], ts("2026-10-25T23:30:00Z"))

    def test_slots_are_strictly_30_minutes_apart_and_sorted(self):
        for d in (date(2026, 3, 29), date(2026, 10, 25), date(2026, 1, 15)):
            s = market_day_slots(d)
            self.assertEqual({b - a for a, b in zip(s, s[1:])}, {1800})

    def test_consecutive_days_tile_without_gap_or_overlap(self):
        for d0 in (date(2026, 3, 28), date(2026, 10, 24)):
            a = market_day_slots(d0)
            b = market_day_slots(date.fromordinal(d0.toordinal() + 1))
            c = market_day_slots(date.fromordinal(d0.toordinal() + 2))
            self.assertEqual(b[0] - a[-1], 1800)
            self.assertEqual(c[0] - b[-1], 1800)

    def test_2026_has_exactly_two_clock_change_days(self):
        odd = [d for d in (date.fromordinal(date(2026, 1, 1).toordinal() + i) for i in range(365))
               if len(market_day_slots(d)) != 48]
        self.assertEqual(sorted(odd), [date(2026, 3, 29), date(2026, 10, 25)])


class CutoffTests(unittest.TestCase):
    def test_winter_cutoff_is_0920_utc_on_previous_day(self):
        self.assertEqual(decision_cutoff(date(2026, 1, 15)), ts("2026-01-14T09:20:00Z"))

    def test_summer_cutoff_is_london_time_so_0820_utc(self):
        self.assertEqual(decision_cutoff(date(2026, 7, 1)), ts("2026-06-30T08:20:00Z"))

    def test_cutoff_is_local_time_of_the_day_before(self):
        # delivery 29 Mar (clocks go forward that night): D-1 28 Mar is still GMT
        self.assertEqual(decision_cutoff(date(2026, 3, 29)), ts("2026-03-28T09:20:00Z"))
        # delivery 30 Mar: D-1 29 Mar is already BST
        self.assertEqual(decision_cutoff(date(2026, 3, 30)), ts("2026-03-29T08:20:00Z"))
        # delivery 25 Oct (clocks back): D-1 24 Oct still BST
        self.assertEqual(decision_cutoff(date(2026, 10, 25)), ts("2026-10-24T08:20:00Z"))
        self.assertEqual(decision_cutoff(date(2026, 10, 26)), ts("2026-10-25T09:20:00Z"))

    def test_custom_cutoff_time(self):
        self.assertEqual(decision_cutoff(date(2026, 1, 15), time(9, 50)), ts("2026-01-14T09:50:00Z"))


class LocalHelpers(unittest.TestCase):
    def test_london_hour_and_date(self):
        self.assertEqual(london_hour(ts("2026-07-01T10:30:00Z")), 11)
        self.assertEqual(london_date(ts("2026-06-30T23:00:00Z")), date(2026, 7, 1))
        self.assertEqual(london_hour(ts("2026-01-15T10:30:00Z")), 10)

    def test_hour_floor(self):
        self.assertEqual(hour_floor(ts("2026-01-15T10:30:00Z")), ts("2026-01-15T10:00:00Z"))


if __name__ == "__main__":
    unittest.main()
