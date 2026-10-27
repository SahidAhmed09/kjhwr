"""Breakdowns, every-vintage lead view and persistence baseline. SYNTHETIC data."""
import unittest
from datetime import date

from synth import build, day_data, hours_of, merge, ts
from wind_analysis.analysis import evaluate
from wind_analysis.config import AnalysisConfig
from wind_analysis.timeutil import decision_cutoff, london_hour, market_day_slots

D1, D2 = date(2026, 1, 15), date(2026, 1, 16)
CFG = AnalysisConfig()          # lead bucket 6 h, level bin 5000 MW


def two_day_world():
    """actual = 1000 everywhere. Decision vintage published 07:30Z on D-1.
    D1: forecast 1100 before 12:00 London, 6000 after.  D2: 900 before 12:00, 7000 after."""
    def fc(hi_val, lo_val):
        return lambda h: lo_val if london_hour(h) < 12 else hi_val
    p1, p2 = ts("2026-01-14T07:30:00Z"), ts("2026-01-15T07:30:00Z")
    return build(*merge(day_data(D1, 1000, fc(6000, 1100), p1), day_data(D2, 1000, fc(7000, 900), p2)))


class OverallAndByDay(unittest.TestCase):
    def setUp(self):
        self.r = evaluate(two_day_world(), [D1, D2], CFG)

    def test_overall_hand_computed(self):
        o = self.r["overall"]
        self.assertEqual(o["n"], 96)
        self.assertAlmostEqual(o["mae"], 2800.0)     # 24*(100+5000+100+6000)/96
        self.assertAlmostEqual(o["bias"], 2750.0)    # 24*(100+5000-100+6000)/96
        self.assertAlmostEqual(o["wape"], 2.8)       # 268800 / 96000
        self.assertAlmostEqual(o["share_over"], 0.75)

    def test_by_day(self):
        d = {x["key"]: x for x in self.r["by_day"]}
        self.assertEqual(set(d), {"2026-01-15", "2026-01-16"})
        self.assertAlmostEqual(d["2026-01-15"]["mae"], 2550.0)
        self.assertAlmostEqual(d["2026-01-16"]["mae"], 3050.0)
        self.assertEqual(d["2026-01-15"]["n"], 48)

    def test_by_hour_of_day_uses_london_hours(self):
        h = {x["key"]: x for x in self.r["by_hour"]}
        self.assertEqual(sorted(h), list(range(24)))
        self.assertEqual(h[0]["n"], 4)
        self.assertAlmostEqual(h[0]["mae"], 100.0)
        self.assertAlmostEqual(h[0]["bias"], 0.0)
        self.assertAlmostEqual(h[12]["mae"], 5500.0)

    def test_by_forecast_level(self):
        lv = {x["key"]: x for x in self.r["by_level"]}
        self.assertEqual(set(lv), {0, 5000})
        self.assertEqual(lv[0]["n"], 48)
        self.assertAlmostEqual(lv[0]["mae"], 100.0)
        self.assertAlmostEqual(lv[5000]["mae"], 5500.0)

    def test_by_decision_lead_time(self):
        lead = {x["key"]: x for x in self.r["by_lead"]}
        # lead = slot - 07:30Z on D-1 = 16.5 .. 40.0 h ; 6 h buckets
        self.assertEqual(sorted(lead), [12, 18, 24, 30, 36])
        self.assertEqual(lead[12]["n"], 6)    # 3 slots/day
        self.assertEqual(lead[36]["n"], 18)   # 9 slots/day


class Reconciliation(unittest.TestCase):
    def setUp(self):
        self.r = evaluate(two_day_world(), [D1, D2], CFG)

    def test_every_breakdown_sums_to_overall_n(self):
        n = self.r["overall"]["n"]
        for k in ("by_day", "by_hour", "by_lead", "by_level"):
            self.assertEqual(sum(x["n"] for x in self.r[k]), n, k)

    def test_every_breakdown_recombines_to_overall_abs_error_and_bias(self):
        o = self.r["overall"]
        for k in ("by_day", "by_hour", "by_lead", "by_level"):
            self.assertAlmostEqual(sum(x["n"] * x["mae"] for x in self.r[k]), o["n"] * o["mae"], msg=k)
            self.assertAlmostEqual(sum(x["n"] * x["bias"] for x in self.r[k]), o["n"] * o["bias"], msg=k)

    def test_counts_reconcile(self):
        c = self.r["counts"]
        self.assertEqual(c["n_slots"], c["n_scored"] + c["n_missing_forecast"] + c["n_missing_actual"]
                         - c.get("n_missing_both", 0))
        self.assertEqual(c["n_slots"], 96)

    def test_missing_forecast_and_actual_both_counted_once(self):
        slots = market_day_slots(D1)
        acts, fcs = day_data(D1, 1000, 1100, ts("2026-01-14T07:30:00Z"))
        del acts[slots[0]]                                   # no actual for 00:00
        fcs = [f for f in fcs if f[1] != slots[0] - slots[0] % 3600]  # and no forecast for that hour
        r = evaluate(build(acts, fcs), [D1], CFG)
        c = r["counts"]
        self.assertEqual(c["n_slots"], 48)
        self.assertEqual(c["n_missing_both"], 1)
        self.assertEqual(c["n_scored"] + c["n_missing_forecast"] + c["n_missing_actual"] - c["n_missing_both"], 48)
        self.assertEqual(r["overall"]["n"], c["n_scored"])


class DstReconciliation(unittest.TestCase):
    def test_spring_day_hours_and_totals(self):
        d = date(2026, 3, 29)
        r = evaluate(build(*day_data(d, 1000, 1100, decision_cutoff(d) - 600)), [d], CFG)
        self.assertEqual(r["overall"]["n"], 46)
        self.assertEqual(sum(x["n"] for x in r["by_hour"]), 46)
        self.assertNotIn(1, [x["key"] for x in r["by_hour"]])   # local 01:00-02:00 does not exist

    def test_autumn_day_has_repeated_hour_merged_into_one_key(self):
        d = date(2026, 10, 25)
        r = evaluate(build(*day_data(d, 1000, 1100, decision_cutoff(d) - 600)), [d], CFG)
        h = {x["key"]: x["n"] for x in r["by_hour"]}
        self.assertEqual(r["overall"]["n"], 50)
        self.assertEqual(h[1], 4)
        self.assertEqual(sum(h.values()), 50)


class EveryVintageLeadView(unittest.TestCase):
    def setUp(self):
        acts, _ = day_data(D1, 1000, 0, 0)
        v1 = ts("2026-01-14T07:30:00Z")   # decision vintage (<= 09:20Z cut-off)
        v2 = ts("2026-01-15T02:30:00Z")   # later vintage, after the cut-off
        hrs = hours_of(market_day_slots(D1))
        fcs = [(v1, h, 1100) for h in hrs] + [(v2, h, 1300) for h in hrs]
        self.r = evaluate(build(acts, fcs), [D1], CFG)

    def test_decision_views_ignore_the_later_vintage(self):
        self.assertAlmostEqual(self.r["overall"]["mae"], 100.0)
        self.assertEqual(self.r["overall"]["n"], 48)

    def test_all_vintage_view_uses_every_vintage_slot_pair(self):
        lead = {x["key"]: x for x in self.r["lead_all_vintages"]}
        self.assertEqual(sum(x["n"] for x in lead.values()), 96)
        # v2 leads: slot - 02:30Z on the 15th. The 5 slots 00:00..02:00 have negative lead -> bucket -6
        self.assertEqual(lead[-6]["n"], 5)
        self.assertAlmostEqual(lead[-6]["mae"], 300.0)
        self.assertAlmostEqual(lead[-6]["bias"], 300.0)


class PersistenceBaseline(unittest.TestCase):
    """Persistence = actual 48 h earlier, usable only if published by the cut-off."""

    def _world(self, tweak=None):
        d13, d14, d15 = date(2026, 1, 13), date(2026, 1, 14), date(2026, 1, 15)
        acts, fcs = merge(day_data(d13, 800, 0, 0), day_data(d14, 900, 0, 0),
                          day_data(d15, 1000, 1100, ts("2026-01-14T07:30:00Z")))
        fcs = [f for f in fcs if f[0] != 0]                  # only the real vintage remains
        if tweak:
            tweak(acts)
        return build(acts, fcs)

    def test_skill_hand_computed(self):
        p = evaluate(self._world(), [D1], CFG)["persistence"]
        self.assertEqual(p["n_paired"], 48)
        self.assertAlmostEqual(p["forecast"]["mae"], 100.0)    # 1100 vs 1000
        self.assertAlmostEqual(p["baseline"]["mae"], 200.0)    # 800  vs 1000 -> error -200
        self.assertAlmostEqual(p["baseline"]["bias"], -200.0)
        self.assertAlmostEqual(p["skill_mae"], 0.5)            # 1 - 100/200
        self.assertAlmostEqual(p["skill_rmse"], 0.5)

    def test_missing_baseline_actual_is_dropped_from_pair_and_counted(self):
        slot0 = market_day_slots(D1)[0]
        p = evaluate(self._world(lambda a: a.pop(slot0 - 172800)), [D1], CFG)["persistence"]
        self.assertEqual((p["n_paired"], p["n_missing_baseline"]), (47, 1))

    def test_baseline_actual_published_after_cutoff_is_not_used(self):
        slot0 = market_day_slots(D1)[0]
        late = ts("2026-01-14T10:00:00Z")
        p = evaluate(self._world(lambda a: a.__setitem__(slot0 - 172800, (800, late))), [D1], CFG)["persistence"]
        self.assertEqual((p["n_paired"], p["n_missing_baseline"]), (47, 1))


if __name__ == "__main__":
    unittest.main()
