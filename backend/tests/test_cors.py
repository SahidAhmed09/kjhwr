"""The API may be called from a front end hosted on another domain (read-only, no credentials). Uses the committed real snapshot."""
import os
import sys
import unittest
from pathlib import Path

from starlette.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wind_api.main import create_app  # noqa: E402

REAL = Path(__file__).resolve().parents[1] / "data" / "snapshot.json.gz"


class CorsTests(unittest.TestCase):
    def test_a_get_from_another_origin_is_allowed(self):
        r = TestClient(create_app(snapshot_path=REAL)).get("/api/health", headers={"Origin": "https://frontend.example"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers.get("access-control-allow-origin"), "*")

    def test_credentials_are_not_allowed(self):
        r = TestClient(create_app(snapshot_path=REAL)).get("/api/health", headers={"Origin": "https://frontend.example"})
        self.assertNotIn("access-control-allow-credentials", r.headers)

    def test_origins_can_be_restricted_by_environment(self):
        os.environ["CORS_ALLOW_ORIGINS"] = "https://only.example"
        try:
            client = TestClient(create_app(snapshot_path=REAL))
        finally:
            del os.environ["CORS_ALLOW_ORIGINS"]
        ok = client.get("/api/health", headers={"Origin": "https://only.example"})
        other = client.get("/api/health", headers={"Origin": "https://other.example"})
        self.assertEqual(ok.headers.get("access-control-allow-origin"), "https://only.example")
        self.assertNotIn("access-control-allow-origin", other.headers)


if __name__ == "__main__":
    unittest.main()
