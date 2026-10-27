import math
import unittest

from synth import ts  # noqa: F401  (puts backend/ on sys.path)
from wind_analysis.metrics import error_metrics, percentile


class PercentileTests(unittest.TestCase):
    def test_linear_interpolation(self):
        v = [1, 2, 3, 4]
        self.assertAlmostEqual(percentile(v, 50), 2.5)
        self.assertAlmostEqual(percentile(v, 0), 1)
        self.assertAlmostEqual(percentile(v, 100), 4)
        self.assertAlmostEqual(percentile(v, 90), 3.7)  # pos 2.7 -> 3 + .7*(4-3)

    def test_single_value(self):
        self.assertEqual(percentile([7], 90), 7)

    def test_empty_is_none(self):
        self.assertIsNone(percentile([], 50))


class HandComputedMetrics(unittest.TestCase):
    """forecast=[12,16,36,40], actual=[10,20,30,40] -> error=[2,-4,6,0] (forecast - actual)."""

    def setUp(self):
        self.m = error_metrics([2, -4, 6, 0], [10, 20, 30, 40])

    def test_core_metrics(self):
        m = self.m
        self.assertEqual(m["n"], 4)
        self.assertAlmostEqual(m["mae"], 3.0)
        self.assertAlmostEqual(m["rmse"], math.sqrt(14))
        self.assertAlmostEqual(m["bias"], 1.0)
        self.assertAlmostEqual(m["wape"], 12 / 100)

    def test_over_and_under_shares(self):
        self.assertAlmostEqual(self.m["share_over"], 0.5)    # errors > 0: 2, 6
        self.assertAlmostEqual(self.m["share_under"], 0.25)  # errors < 0: -4
        self.assertAlmostEqual(self.m["share_exact"], 0.25)  # error == 0

    def test_signed_percentiles(self):
        p = self.m["signed_pct"]  # sorted [-4,0,2,6]
        self.assertAlmostEqual(p["p10"], -2.8)
        self.assertAlmostEqual(p["p50"], 1.0)
        self.assertAlmostEqual(p["p90"], 4.8)

    def test_absolute_percentiles(self):
        p = self.m["abs_pct"]  # sorted [0,2,4,6]
        self.assertAlmostEqual(p["p50"], 3.0)
        self.assertAlmostEqual(p["p90"], 5.4)

    def test_shortfall_90_is_p90_of_forecast_minus_actual(self):
        self.assertAlmostEqual(self.m["shortfall_90"], 4.8)


class EdgeTests(unittest.TestCase):
    def test_shortfall_is_zero_when_forecast_never_too_high(self):
        m = error_metrics([-5, -3, -1], [10, 10, 10])
        self.assertEqual(m["shortfall_90"], 0.0)
        self.assertEqual(m["share_over"], 0.0)

    def test_empty_input_gives_none_not_zero(self):
        m = error_metrics([], [])
        self.assertEqual(m["n"], 0)
        for k in ("mae", "rmse", "bias", "wape", "share_over", "shortfall_90"):
            self.assertIsNone(m[k], k)

    def test_wape_is_none_when_actuals_sum_to_zero(self):
        self.assertIsNone(error_metrics([1], [0])["wape"])

    def test_length_mismatch_rejected(self):
        with self.assertRaises(ValueError):
            error_metrics([1, 2], [1])


if __name__ == "__main__":
    unittest.main()
