"""Decision-forecast selection. All data here is SYNTHETIC (unit tests only)."""
import copy
import unittest
from datetime import date, time

from synth import build, day_data, hours_of, merge, ts
from wind_analysis.analysis import evaluate
from wind_analysis.band import uncertainty_band
from wind_analysis.config import AnalysisConfig
from wind_analysis.decision import decision_day
from wind_analysis.timeutil import market_day_slots

D = date(2026, 1, 15)
CUT = ts("2026-01-14T09:20:00Z")
CFG = AnalysisConfig()


def world(extra_forecasts=(), drop_forecast_hours=(), drop_actual_slots=()):
    slots = market_day_slots(D)
    acts = {s: 1000 + i for i, s in enumerate(slots)}
    for s in drop_actual_slots:
        del acts[s]
    fcs = []
    for h in hours_of(slots):
        if h in drop_forecast_hours:
            continue
        fcs.append((ts("2026-01-14T07:30:00Z"), h, 2000))
        fcs.append((CUT, h, 3000))                          # exactly at the cut-off
        fcs.append((ts("2026-01-14T09:30:00Z"), h, 9e9))     # after the cut-off
    return build(acts, fcs + list(extra_forecasts))


class SelectionTests(unittest.TestCase):
    def test_vintage_exactly_at_cutoff_is_included(self):
        r = decision_day(world(), D, CFG)
        self.assertTrue(all(s.forecast == 3000 for s in r.slots))
        self.assertTrue(all(s.vintage_publish == CUT for s in r.slots))

    def test_one_second_after_cutoff_is_excluded(self):
        src = world(extra_forecasts=[(CUT + 1, h, -7e9) for h in hours_of(market_day_slots(D))])
        r = decision_day(src, D, CFG)
        self.assertTrue(all(s.forecast == 3000 for s in r.slots))

    def test_one_second_before_cutoff_is_included(self):
        src = build({s: 1 for s in market_day_slots(D)},
                    [(CUT - 1, h, 42) for h in hours_of(market_day_slots(D))])
        self.assertTrue(all(s.forecast == 42 for s in decision_day(src, D, CFG).slots))

    def test_cutoff_time_is_configurable(self):
        r = decision_day(world(), D, AnalysisConfig(cutoff_time=time(9, 30)))
        self.assertTrue(all(s.forecast == 9e9 for s in r.slots))  # 09:30 vintage now qualifies

    def test_hourly_forecast_applies_to_both_half_hours(self):
        slots = market_day_slots(D)
        fc = [(ts("2026-01-14T07:30:00Z"), h, 100 + i) for i, h in enumerate(hours_of(slots))]
        r = decision_day(build({s: 1 for s in slots}, fc), D, CFG)
        self.assertEqual([s.forecast for s in r.slots[:4]], [100, 100, 101, 101])

    def test_lead_time_is_slot_start_minus_vintage_publish(self):
        r = decision_day(world(), D, CFG)
        self.assertAlmostEqual(r.slots[0].lead_h, 14 + 40 / 60)   # 15 Jan 00:00Z minus vintage 14 Jan 09:20Z
        self.assertAlmostEqual(r.slots[1].lead_h - r.slots[0].lead_h, 0.5)


class MissingTests(unittest.TestCase):
    def test_missing_forecast_hour_stays_missing_and_is_counted(self):
        slots = market_day_slots(D)
        gap = ts("2026-01-15T10:00:00Z")
        r = decision_day(world(drop_forecast_hours=[gap]), D, CFG)
        miss = [s for s in r.slots if s.forecast is None]
        self.assertEqual([s.slot for s in miss], [gap, gap + 1800])
        self.assertEqual(r.n_missing_forecast, 2)
        self.assertEqual(r.n_scored, len(slots) - 2)

    def test_missing_actual_is_counted(self):
        r = decision_day(world(drop_actual_slots=[ts("2026-01-15T00:00:00Z")]), D, CFG)
        self.assertEqual((r.n_missing_actual, r.n_missing_forecast, r.n_scored), (1, 0, 47))

    def test_null_in_latest_vintage_is_missing_not_backfilled_from_older(self):
        slots = market_day_slots(D)
        fc = []
        for h in hours_of(slots):
            fc += [(ts("2026-01-14T07:30:00Z"), h, 2000), (CUT, h, None)]
        r = decision_day(build({s: 1 for s in slots}, fc), D, CFG)
        self.assertTrue(all(s.forecast is None for s in r.slots))
        self.assertEqual(r.n_missing_forecast, 48)

    def test_no_vintage_before_cutoff_means_all_missing(self):
        slots = market_day_slots(D)
        src = build({s: 1 for s in slots}, [(CUT + 60, h, 5) for h in hours_of(slots)])
        r = decision_day(src, D, CFG)
        self.assertEqual((r.n_missing_forecast, r.n_scored), (48, 0))

    def test_missing_slots_are_excluded_from_metrics_not_zero_filled(self):
        gap = ts("2026-01-15T10:00:00Z")
        res = evaluate(world(drop_forecast_hours=[gap]), [D], CFG)
        self.assertEqual(res["overall"]["n"], 46)
        self.assertEqual(res["counts"]["n_missing_forecast"], 2)


class DstDayTests(unittest.TestCase):
    def _full(self, d):
        acts, fcs = day_data(d, 1000, 1100, publish=decision_cutoff_minus(d))
        return build(acts, fcs)

    def test_46_slot_day_end_to_end(self):
        d = date(2026, 3, 29)
        r = decision_day(self._full(d), d, CFG)
        self.assertEqual((r.n_slots, r.n_scored), (46, 46))

    def test_50_slot_day_end_to_end(self):
        d = date(2026, 10, 25)
        r = decision_day(self._full(d), d, CFG)
        self.assertEqual((r.n_slots, r.n_scored), (50, 50))

    def test_summer_cutoff_boundary(self):
        d = date(2026, 7, 1)
        slots = market_day_slots(d)
        cut = ts("2026-06-30T08:20:00Z")
        fc = [(cut, h, 1) for h in hours_of(slots)] + [(cut + 1, h, 2) for h in hours_of(slots)]
        r = decision_day(build({s: 0 for s in slots}, fc), d, CFG)
        self.assertTrue(all(s.forecast == 1 for s in r.slots))


def decision_cutoff_minus(d):
    from wind_analysis.timeutil import decision_cutoff
    return decision_cutoff(d) - 3600


class NoHindsightTests(unittest.TestCase):
    """Injecting absurd vintages published after the cut-off must change nothing
    that is derived from the decision forecast."""

    def _scenario(self):
        # history for the band + a target day, all via the normal builders
        parts = []
        days = [date(2026, 1, 12), date(2026, 1, 13), date(2026, 1, 14), D]
        for i, d in enumerate(days):
            from wind_analysis.timeutil import decision_cutoff
            parts.append(day_data(d, 1000 + 10 * i, lambda h, i=i: 1000 + 50 * i, decision_cutoff(d) - 600))
        return merge(*parts), days

    def test_late_vintages_cannot_change_any_decision_output(self):
        (acts, fcs), days = self._scenario()
        base_src = build(acts, fcs)
        base_eval = evaluate(base_src, days, CFG)
        base_band = uncertainty_band(base_src, D, CFG)
        base_day = decision_day(base_src, D, CFG)

        from wind_analysis.timeutil import decision_cutoff
        absurd = []
        for d in days:
            c = decision_cutoff(d)
            for s in market_day_slots(d):
                h = s - s % 3600
                for dt in (1, 600, 3600, 86400):         # strictly after each day's own cut-off
                    absurd.append((c + dt, h, 1e12))
                    absurd.append((c + dt + 7, h, -1e12))
        hacked_src = build(acts, fcs + absurd)

        hacked_eval = evaluate(hacked_src, days, CFG)
        hacked_band = uncertainty_band(hacked_src, D, CFG)
        hacked_day = decision_day(hacked_src, D, CFG)

        self.assertEqual(hacked_day, base_day)
        self.assertEqual(hacked_band, base_band)
        for key in ("overall", "counts", "by_day", "by_hour", "by_lead", "by_level", "persistence"):
            self.assertEqual(hacked_eval[key], base_eval[key], key)
        # sanity: the injection is real - the every-vintage view legitimately does see it
        self.assertNotEqual(hacked_eval["lead_all_vintages"], base_eval["lead_all_vintages"])

    def test_evaluate_does_not_mutate_its_input(self):
        (acts, fcs), days = self._scenario()
        src = build(acts, fcs)
        before = copy.deepcopy(src.actuals)
        evaluate(src, days, CFG)
        self.assertEqual(src.actuals, before)


if __name__ == "__main__":
    unittest.main()
