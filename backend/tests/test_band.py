"""Uncertainty band: only delivery days already finished at the cut-off. SYNTHETIC data."""
import unittest
from datetime import date

from synth import build, day_data, merge, ts
from wind_analysis.band import uncertainty_band
from wind_analysis.config import AnalysisConfig
from wind_analysis.timeutil import decision_cutoff

TARGET = date(2026, 1, 20)     # cut-off = 2026-01-19T09:20Z


def history(errors_by_day, absurd_unfinished=True):
    """actual=1000; each day's decision vintage = 1000 + its error. Day 19 (D-1) is unfinished at the cut-off."""
    parts = []
    for d, e in errors_by_day.items():
        parts.append(day_data(d, 1000, 1000 + e, decision_cutoff(d) - 600))
    if absurd_unfinished:
        # D-1 (19 Jan): its first ~9 h of actuals ARE published before the cut-off, but the day is not finished
        parts.append(day_data(date(2026, 1, 19), 1000, 1000 + 1e9, decision_cutoff(date(2026, 1, 19)) - 600))
    # the target day itself: absurd actuals (ex-post) must never feed its own band
    parts.append(day_data(TARGET, 5e8, 1500, decision_cutoff(TARGET) - 600))
    return build(*merge(*parts))


HIST = {date(2026, 1, 18): 100, date(2026, 1, 17): -50, date(2026, 1, 16): 10}
CFG3 = AnalysisConfig(band_min_days=3)


class BandUsesOnlyFinishedDays(unittest.TestCase):
    def test_hand_computed_band(self):
        b = uncertainty_band(history(HIST), TARGET, CFG3)
        self.assertEqual(b.method, "trailing_empirical")
        self.assertEqual((b.n_days, b.n_errors), (3, 144))
        self.assertAlmostEqual(b.p10, -50.0)
        self.assertAlmostEqual(b.p90, 100.0)
        lo, hi = b.interval(1500)       # actual = forecast - error  ->  [f - p90, f - p10]
        self.assertAlmostEqual(lo, 1400.0)
        self.assertAlmostEqual(hi, 1550.0)

    def test_day_before_delivery_is_excluded_even_though_part_of_it_is_published(self):
        with_d1 = uncertainty_band(history(HIST, absurd_unfinished=True), TARGET, CFG3)
        without = uncertainty_band(history(HIST, absurd_unfinished=False), TARGET, CFG3)
        self.assertEqual(with_d1, without)

    def test_target_day_actuals_never_used(self):
        b = uncertainty_band(history(HIST), TARGET, CFG3)
        self.assertLess(abs(b.p90), 1e6)

    def test_window_limits_how_far_back_we_look(self):
        b = uncertainty_band(history(HIST), TARGET, AnalysisConfig(band_min_days=2, band_window_days=2))
        self.assertEqual(b.n_days, 2)                       # 18 Jan and 17 Jan only
        self.assertAlmostEqual(b.p10, -50.0)
        self.assertAlmostEqual(b.p90, 100.0)
        self.assertEqual(b.method, "trailing_empirical")

    def test_days_with_no_data_are_not_counted(self):
        b = uncertainty_band(history(HIST), TARGET, AnalysisConfig(band_min_days=3, band_window_days=14))
        self.assertEqual(b.n_days, 3)


class BandFallbacks(unittest.TestCase):
    def test_reduced_history_is_computed_but_labelled(self):
        h = dict(list(HIST.items())[:2])                   # only 2 finished days, 3 required
        b = uncertainty_band(history(h), TARGET, CFG3)
        self.assertEqual(b.method, "reduced_history")
        self.assertEqual(b.n_days, 2)
        self.assertIsNotNone(b.p10)
        self.assertIn("2", b.label)

    def test_no_history_gives_no_band_and_says_so(self):
        b = uncertainty_band(history({}, absurd_unfinished=True), TARGET, CFG3)
        self.assertEqual(b.method, "insufficient_history")
        self.assertEqual(b.n_days, 0)
        self.assertIsNone(b.p10)
        self.assertIsNone(b.interval(1500))                # never invented

    def test_label_is_human_readable(self):
        b = uncertainty_band(history(HIST), TARGET, CFG3)
        self.assertIn("3", b.label)


class BandIgnoresMissingSlots(unittest.TestCase):
    def test_slots_missing_a_forecast_are_not_zero_filled_into_the_errors(self):
        acts, fcs = merge(*[day_data(d, 1000, 1000 + e, decision_cutoff(d) - 600) for d, e in HIST.items()])
        fcs = [f for f in fcs if not (f[1] // 86400 == ts("2026-01-18T00:00:00Z") // 86400)]  # no forecasts at all on 18 Jan
        b = uncertainty_band(build(acts, fcs), TARGET, CFG3)
        self.assertEqual(b.n_days, 2)
        self.assertEqual(b.n_errors, 96)


if __name__ == "__main__":
    unittest.main()
