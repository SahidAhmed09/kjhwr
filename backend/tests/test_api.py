"""API tests. Data is SYNTHETIC (tests only) except RealSnapshotApiTests, which uses the committed snapshot."""
import gzip
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from starlette.testclient import TestClient

from synth import day_data, merge, ts, write_snapshot
from wind_analysis.analysis import evaluate as real_evaluate
from wind_analysis.decision import decision_day as real_decision_day
from wind_analysis.timeutil import decision_cutoff, market_day_slots
from wind_data.loader import load_snapshot as real_load_snapshot
from wind_api.main import create_app

REAL = Path(__file__).resolve().parents[1] / "data" / "snapshot.json.gz"
DAYS = [date(2026, 1, 14), date(2026, 1, 15), date(2026, 1, 16)]   # delivery days in the synthetic window


def synthetic_parts():
    """Per delivery day D: actual = 1000 + slot index; vintages for every hour at
    07:40Z (2000), exactly 09:20Z (3000) and 09:30Z (9e9, absurd) on D-1."""
    parts = []
    for d in DAYS:
        c = decision_cutoff(d)                                       # 09:20Z in January
        first = market_day_slots(d)[0]
        acts, early = day_data(d, lambda s, first=first: 1000 + (s - first) // 1800, 2000, c - 6000)
        hours = [h for _, h, _ in early]
        parts.append((acts, early + [(c, h, 3000) for h in hours] + [(c + 600, h, 9e9) for h in hours]))
    return merge(*parts)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "snapshot.json.gz"
        acts, fcs = synthetic_parts()
        write_snapshot(self.path, acts, fcs, "2026-01-14", "2026-01-16")
        self._env = mock.patch.dict(os.environ, {}, clear=False)
        self._env.start()
        os.environ.pop("STATIC_DIR", None)
        self.addCleanup(self._env.stop)
        self.client = TestClient(create_app(snapshot_path=self.path))

    def missing_client(self):
        return TestClient(create_app(snapshot_path=Path(self.tmp.name) / "nope.json.gz"))


class HealthTests(Base):
    def test_health_ok_and_does_not_force_a_load(self):
        r = self.client.get("/api/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"status": "ok", "data_file_present": True, "data_loaded": False})

    def test_data_loaded_after_first_data_request(self):
        self.client.get("/api/meta")
        self.assertTrue(self.client.get("/api/health").json()["data_loaded"])

    def test_health_stays_200_when_data_is_missing(self):
        r = self.missing_client().get("/api/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["data_file_present"], False)


class MetaTests(Base):
    def test_meta_fields(self):
        r = self.client.get("/api/meta")
        self.assertEqual(r.status_code, 200)
        j = r.json()
        self.assertEqual(j["data"]["settlement_from"], "2026-01-14")
        self.assertEqual(j["data"]["n_actual_rows"], 3 * 48)
        self.assertEqual(j["data"]["fetched_at"], "2026-01-01T00:00:00Z")
        self.assertEqual(j["decision_window"], {"first": "2026-01-13", "last": "2026-01-15"})
        self.assertEqual(j["defaults"]["cutoff"], "09:20")
        self.assertEqual(j["defaults"]["error_definition"], "forecast - actual")
        self.assertTrue(len(j["notes"]) >= 1)

    def test_meta_503_when_snapshot_missing(self):
        r = self.missing_client().get("/api/meta")
        self.assertEqual(r.status_code, 503)
        self.assertIn("snapshot", r.json()["detail"].lower())
        self.assertIn("fetch_snapshot.py", r.json()["detail"])

    def test_503_when_file_is_corrupt(self):
        self.path.write_bytes(b"not gzip")
        r = self.client.get("/api/meta")
        self.assertEqual(r.status_code, 503)
        self.assertIn("unreadable", r.json()["detail"].lower())

    def test_503_when_schema_unsupported(self):
        acts, fcs = synthetic_parts()
        write_snapshot(self.path, acts, fcs, "2026-01-14", "2026-01-16", schema=99)
        r = self.client.get("/api/meta")
        self.assertEqual(r.status_code, 503)
        self.assertIn("schema", r.json()["detail"].lower())

    def test_failure_is_not_cached_data_appearing_later_works(self):
        c = TestClient(create_app(snapshot_path=Path(self.tmp.name) / "late.json.gz"))
        self.assertEqual(c.get("/api/meta").status_code, 503)
        (Path(self.tmp.name) / "late.json.gz").write_bytes(self.path.read_bytes())
        self.assertEqual(c.get("/api/meta").status_code, 200)


class DecisionTests(Base):
    def get(self, **params):
        return self.client.get("/api/decision", params=params)

    def test_default_cutoff_uses_vintage_exactly_at_cutoff(self):
        r = self.get(decision_date="2026-01-14")
        self.assertEqual(r.status_code, 200)
        j = r.json()
        self.assertEqual(j["delivery_date"], "2026-01-15")
        self.assertEqual(j["cutoff"], {"local": "09:20", "utc": "2026-01-14T09:20:00Z", "timezone": "Europe/London"})
        self.assertEqual(len(j["slots"]), 48)
        self.assertTrue(all(s["forecast_mw"] == 3000 for s in j["slots"]))
        self.assertEqual(j["slots"][0]["vintage_publish_utc"], "2026-01-14T09:20:00Z")
        self.assertEqual(j["slots"][0]["start_utc"], "2026-01-15T00:00:00Z")
        self.assertEqual(j["slots"][0]["actual_mw"], 1000)
        self.assertEqual((j["n_slots"], j["n_scored"], j["n_missing_forecast"]), (48, 48, 0))
        self.assertEqual(j["vintages"], [{"publish_utc": "2026-01-14T09:20:00Z", "n_slots": 48}])

    def test_later_cutoff_picks_the_later_vintage(self):
        j = self.get(decision_date="2026-01-14", cutoff="09:30").json()
        self.assertTrue(all(s["forecast_mw"] == 9e9 for s in j["slots"]))
        self.assertEqual(j["cutoff"]["utc"], "2026-01-14T09:30:00Z")

    def test_earlier_cutoff_picks_the_earlier_vintage(self):
        j = self.get(decision_date="2026-01-14", cutoff="08:00").json()
        self.assertTrue(all(s["forecast_mw"] == 2000 for s in j["slots"]))

    def test_cutoff_before_any_vintage_gives_missing_not_filled(self):
        j = self.get(decision_date="2026-01-14", cutoff="01:00").json()
        self.assertTrue(all(s["forecast_mw"] is None for s in j["slots"]))
        self.assertEqual((j["n_missing_forecast"], j["n_scored"]), (48, 0))
        self.assertEqual(j["vintages"], [])

    def test_band_with_no_history_is_labelled_and_null(self):
        j = self.get(decision_date="2026-01-13").json()      # delivery 14 Jan: nothing earlier in the snapshot
        self.assertEqual(j["band"]["method"], "insufficient_history")
        self.assertIsNone(j["band"]["p10"])
        self.assertTrue(all(s["band_low_mw"] is None and s["band_high_mw"] is None for s in j["slots"]))

    def test_band_with_one_day_history_is_reduced_and_hand_computed(self):
        j = self.get(decision_date="2026-01-15").json()      # delivery 16 Jan; history = 14 Jan only
        self.assertEqual(j["band"]["method"], "reduced_history")
        self.assertEqual(j["band"]["n_days"], 1)
        self.assertAlmostEqual(j["band"]["p10"], 1957.7)
        self.assertAlmostEqual(j["band"]["p90"], 1995.3)
        s = j["slots"][0]
        self.assertAlmostEqual(s["band_low_mw"], 3000 - 1995.3)
        self.assertAlmostEqual(s["band_high_mw"], 3000 - 1957.7)

    def test_window_boundaries_are_inclusive(self):
        self.assertEqual(self.get(decision_date="2026-01-13").status_code, 200)
        self.assertEqual(self.get(decision_date="2026-01-15").status_code, 200)

    def test_404_outside_window(self):
        for d in ("2026-01-12", "2026-01-16", "2025-01-15", "2030-01-01"):
            r = self.get(decision_date=d)
            self.assertEqual(r.status_code, 404, d)
            self.assertIn("2026-01-13", r.json()["detail"])
            self.assertIn("2026-01-15", r.json()["detail"])

    def test_422_for_bad_cutoff(self):
        for c in ("25:00", "9:20", "09:60", "abc", "", "09:20:00", "0920", "24:00", " 09:20"):
            r = self.get(decision_date="2026-01-14", cutoff=c)
            self.assertEqual(r.status_code, 422, repr(c))

    def test_422_for_bad_or_missing_date(self):
        self.assertEqual(self.get(decision_date="2026-13-01").status_code, 422)
        self.assertEqual(self.get(decision_date="yesterday").status_code, 422)
        self.assertEqual(self.get().status_code, 422)

    def test_validation_errors_do_not_need_data_so_bad_cutoff_beats_503(self):
        r = self.missing_client().get("/api/decision", params={"decision_date": "2026-01-14", "cutoff": "99:99"})
        self.assertEqual(r.status_code, 422)

    def test_503_when_data_missing(self):
        r = self.missing_client().get("/api/decision", params={"decision_date": "2026-01-14"})
        self.assertEqual(r.status_code, 503)
        self.assertIn("snapshot", r.json()["detail"].lower())


class AccuracyTests(Base):
    def test_default_cutoff_hand_computed(self):
        r = self.client.get("/api/accuracy")
        self.assertEqual(r.status_code, 200)
        j = r.json()
        self.assertEqual(j["cutoff_local"], "09:20")
        self.assertEqual(j["counts"]["n_days"], 3)
        self.assertEqual(j["overall"]["n"], 144)
        self.assertAlmostEqual(j["overall"]["mae"], 1976.5)      # mean of 2000 - i, i = 0..47
        self.assertAlmostEqual(j["overall"]["bias"], 1976.5)
        self.assertEqual(j["overall"]["share_over"], 1.0)
        self.assertEqual(sorted(d["key"] for d in j["by_day"]), ["2026-01-14", "2026-01-15", "2026-01-16"])
        self.assertEqual(len(j["by_hour"]), 24)
        for k in ("by_lead", "by_level", "lead_all_vintages", "persistence", "config"):
            self.assertIn(k, j)

    def test_cutoff_param_changes_the_result(self):
        j = self.client.get("/api/accuracy", params={"cutoff": "09:30"}).json()
        self.assertAlmostEqual(j["overall"]["mae"], 9e9 - 1023.5, delta=1)
        self.assertEqual(j["cutoff_local"], "09:30")

    def test_422_for_bad_cutoff(self):
        for c in ("25:00", "9:20", "abc", ""):
            self.assertEqual(self.client.get("/api/accuracy", params={"cutoff": c}).status_code, 422, repr(c))

    def test_503_when_data_missing(self):
        r = self.missing_client().get("/api/accuracy")
        self.assertEqual(r.status_code, 503)

    def test_results_cached_per_cutoff_and_data_loaded_once(self):
        with mock.patch("wind_api.service.evaluate", wraps=real_evaluate) as ev, \
                mock.patch("wind_api.service.load_snapshot", wraps=real_load_snapshot) as ld:
            c = TestClient(create_app(snapshot_path=self.path))
            a1 = c.get("/api/accuracy").json()
            a2 = c.get("/api/accuracy").json()
            c.get("/api/accuracy", params={"cutoff": "09:20"})          # same cut-off spelled explicitly
            self.assertEqual(a1, a2)
            self.assertEqual(ev.call_count, 1)
            c.get("/api/accuracy", params={"cutoff": "09:30"})
            self.assertEqual(ev.call_count, 2)
            c.get("/api/decision", params={"decision_date": "2026-01-14"})
            self.assertEqual(ld.call_count, 1)

    def test_decision_results_cached_per_date_and_cutoff(self):
        with mock.patch("wind_api.service.decision_day", wraps=real_decision_day) as dd:
            c = TestClient(create_app(snapshot_path=self.path))
            c.get("/api/decision", params={"decision_date": "2026-01-14"})
            n = dd.call_count
            c.get("/api/decision", params={"decision_date": "2026-01-14"})
            self.assertEqual(dd.call_count, n)


class SeriesTests(Base):
    def test_series_flattens_every_decision_day_hand_computed(self):
        r = self.client.get("/api/series")
        self.assertEqual(r.status_code, 200)
        j = r.json()
        self.assertEqual(j["cutoff_local"], "09:20")
        self.assertAlmostEqual(j["band_nominal_coverage"], 0.8)
        self.assertEqual(len(j["points"]), 3 * 48)
        self.assertEqual([d["decision_date"] for d in j["days"]], ["2026-01-13", "2026-01-14", "2026-01-15"])
        p0 = j["points"][0]
        self.assertEqual(p0["start_utc"], "2026-01-14T00:00:00Z")
        self.assertEqual(p0["decision_date"], "2026-01-13")
        self.assertEqual((p0["forecast_mw"], p0["actual_mw"]), (3000, 1000))
        self.assertIsNone(p0["band_low_mw"])                       # no earlier finished day for the first day
        self.assertEqual(j["days"][0]["band_method"], "insufficient_history")
        self.assertEqual(j["days"][2]["band_method"], "reduced_history")
        self.assertIsNotNone(j["points"][-1]["band_low_mw"])

    def test_series_matches_the_decision_endpoint_slot_for_slot(self):
        s = self.client.get("/api/series", params={"cutoff": "09:30"}).json()
        d = self.client.get("/api/decision", params={"decision_date": "2026-01-14", "cutoff": "09:30"}).json()
        pts = [p for p in s["points"] if p["decision_date"] == "2026-01-14"]
        self.assertEqual([p["forecast_mw"] for p in pts], [x["forecast_mw"] for x in d["slots"]])
        self.assertEqual([p["band_low_mw"] for p in pts], [x["band_low_mw"] for x in d["slots"]])

    def test_series_422_and_503(self):
        self.assertEqual(self.client.get("/api/series", params={"cutoff": "9:20"}).status_code, 422)
        self.assertEqual(self.missing_client().get("/api/series").status_code, 503)

    def test_series_is_cached_per_cutoff(self):
        with mock.patch("wind_api.service.decision_day", wraps=real_decision_day) as dd:
            c = TestClient(create_app(snapshot_path=self.path))
            c.get("/api/series")
            n = dd.call_count
            c.get("/api/series")
            self.assertEqual(dd.call_count, n)

    def test_series_documented(self):
        spec = self.client.get("/openapi.json").json()
        self.assertIn("SeriesResponse", spec["components"]["schemas"])
        self.assertEqual({"200", "422", "503"}, set(spec["paths"]["/api/series"]["get"]["responses"]))


class OpenApiTests(Base):
    def test_docs_and_schema_available_with_typed_models(self):
        self.assertEqual(self.client.get("/docs").status_code, 200)
        spec = self.client.get("/openapi.json").json()
        for p in ("/api/meta", "/api/decision", "/api/accuracy", "/api/health"):
            self.assertIn(p, spec["paths"])
        schemas = spec["components"]["schemas"]
        for m in ("MetaResponse", "DecisionResponse", "AccuracyResponse", "HealthResponse", "ErrorResponse"):
            self.assertIn(m, schemas)

    def test_error_codes_are_documented(self):
        spec = self.client.get("/openapi.json").json()
        self.assertEqual({"200", "404", "422", "503"}, set(spec["paths"]["/api/decision"]["get"]["responses"]))
        self.assertEqual({"200", "422", "503"}, set(spec["paths"]["/api/accuracy"]["get"]["responses"]))
        self.assertEqual({"200", "503"}, set(spec["paths"]["/api/meta"]["get"]["responses"]))

    def test_cutoff_parameter_documented_with_default(self):
        spec = self.client.get("/openapi.json").json()
        params = {p["name"]: p for p in spec["paths"]["/api/decision"]["get"]["parameters"]}
        self.assertEqual(params["cutoff"]["schema"]["default"], "09:20")
        self.assertTrue(params["decision_date"]["required"])


class StaticServingTests(Base):
    def make_static(self):
        d = Path(self.tmp.name) / "dist"
        (d / "assets").mkdir(parents=True)
        (d / "index.html").write_text("<html>SPA-INDEX</html>")
        (d / "assets" / "app.js").write_text("console.log('app')")
        (Path(self.tmp.name) / "secret.txt").write_text("SECRET")
        return d

    def test_no_static_dir_means_root_is_404(self):
        self.assertEqual(self.client.get("/").status_code, 404)

    def test_serves_index_assets_and_spa_fallback(self):
        c = TestClient(create_app(snapshot_path=self.path, static_dir=self.make_static()))
        r = c.get("/")
        self.assertEqual((r.status_code, "SPA-INDEX" in r.text), (200, True))
        self.assertIn("console.log", c.get("/assets/app.js").text)
        self.assertIn("SPA-INDEX", c.get("/accuracy").text)           # client-side route -> index.html

    def test_api_still_works_and_unknown_api_path_is_json_404(self):
        c = TestClient(create_app(snapshot_path=self.path, static_dir=self.make_static()))
        self.assertEqual(c.get("/api/health").status_code, 200)
        r = c.get("/api/nope")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.headers["content-type"], "application/json")
        self.assertEqual(c.get("/docs").status_code, 200)

    def test_path_traversal_cannot_escape_static_dir(self):
        c = TestClient(create_app(snapshot_path=self.path, static_dir=self.make_static()))
        for p in ("/../secret.txt", "/..%2fsecret.txt", "/%2e%2e/secret.txt", "/assets/../../secret.txt"):
            self.assertNotIn("SECRET", c.get(p).text, p)

    def test_static_dir_from_environment(self):
        with mock.patch.dict(os.environ, {"STATIC_DIR": str(self.make_static())}):
            c = TestClient(create_app(snapshot_path=self.path))
            self.assertIn("SPA-INDEX", c.get("/").text)

    def test_bad_static_dir_fails_fast_at_startup(self):
        with self.assertRaises(RuntimeError) as cm:
            create_app(snapshot_path=self.path, static_dir=Path(self.tmp.name) / "missing")
        self.assertIn("STATIC_DIR", str(cm.exception))
        empty = Path(self.tmp.name) / "empty"
        empty.mkdir()
        with self.assertRaises(RuntimeError):
            create_app(snapshot_path=self.path, static_dir=empty)


@unittest.skipUnless(REAL.exists(), "real snapshot not present")
class RealSnapshotApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.pop("STATIC_DIR", None)
        cls.c = TestClient(create_app(snapshot_path=REAL))

    def test_meta_matches_data_report(self):
        j = self.c.get("/api/meta").json()
        self.assertEqual(j["data"]["n_actual_rows"], 1488)
        self.assertEqual(j["data"]["n_forecast_rows"], 18104)
        self.assertEqual(j["data"]["n_publish_times"], 248)
        self.assertEqual(j["decision_window"], {"first": "2026-01-01", "last": "2026-01-31"})
        self.assertEqual(len(j["data"]["sha256"]), 64)

    def test_decision_for_known_day(self):
        j = self.c.get("/api/decision", params={"decision_date": "2026-01-14"}).json()
        self.assertEqual(j["vintages"], [{"publish_utc": "2026-01-14T07:30:00Z", "n_slots": 48}])
        self.assertEqual(j["slots"][0]["actual_mw"], 14602)
        self.assertEqual(j["n_scored"], 48)

    def test_accuracy_matches_module_smoke_numbers(self):
        j = self.c.get("/api/accuracy").json()
        self.assertEqual(j["overall"]["n"], 1488)
        self.assertAlmostEqual(j["overall"]["mae"], 2041.9583, places=3)

    def test_window_edges(self):
        self.assertEqual(self.c.get("/api/decision", params={"decision_date": "2026-01-01"}).status_code, 200)
        self.assertEqual(self.c.get("/api/decision", params={"decision_date": "2026-01-31"}).status_code, 200)
        self.assertEqual(self.c.get("/api/decision", params={"decision_date": "2025-12-31"}).status_code, 404)
        self.assertEqual(self.c.get("/api/decision", params={"decision_date": "2026-02-01"}).status_code, 404)


if __name__ == "__main__":
    unittest.main()
