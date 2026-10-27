"""Checks that the repo is shaped the way Vercel's FastAPI preset expects.

These tests read the real files in the repo (no synthetic data). They cannot prove a deployment works;
they catch the mistakes that would break one.
"""
import importlib.util
import json
import os
import re
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

from starlette.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
CONFIG = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
FN = CONFIG["functions"]["app.py"]


def expand_braces(pattern: str) -> list[str]:
    m = re.search(r"\{([^{}]*)\}", pattern)
    if not m:
        return [pattern]
    return [p for alt in m.group(1).split(",") for p in expand_braces(pattern[:m.start()] + alt + pattern[m.end():])]


def glob_to_regex(glob: str) -> re.Pattern:
    out, i = "", 0
    while i < len(glob):
        if glob.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
        elif glob.startswith("**", i):
            out += ".*"
            i += 2
        elif glob[i] == "*":
            out += "[^/]*"
            i += 1
        elif glob[i] == "?":
            out += "[^/]"
            i += 1
        else:
            out += re.escape(glob[i])
            i += 1
    return re.compile(f"^{out}$")


def excluded(relpath: str) -> bool:
    return any(glob_to_regex(g).match(relpath) for g in expand_braces(FN["excludeFiles"]))


class GlobHelperTests(unittest.TestCase):
    def test_helper_semantics(self):
        self.assertTrue(excluded("frontend/src/App.tsx"))
        self.assertTrue(excluded("backend/tests/test_api.py"))
        self.assertTrue(excluded("a/b/__pycache__/x.pyc"))
        self.assertTrue(excluded("README.md"))
        self.assertFalse(excluded("backend/wind_api/main.py"))
        self.assertFalse(excluded("app.py"))


class VercelConfigTests(unittest.TestCase):
    def test_entrypoint_exists_at_root_and_defines_app(self):
        src = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertRegex(src, r"(?m)^app\s*=\s*create_app\(\)")

    def test_function_key_matches_the_entrypoint_file(self):
        self.assertTrue((ROOT / "app.py").is_file())
        self.assertEqual(list(CONFIG["functions"]), ["app.py"])

    def test_no_legacy_builds_or_routes(self):
        self.assertNotIn("builds", CONFIG)
        self.assertNotIn("routes", CONFIG)

    def test_snapshot_is_included_and_not_excluded(self):
        snap = "backend/data/snapshot.json.gz"
        self.assertEqual(FN["includeFiles"], snap)
        self.assertTrue((ROOT / snap).is_file())
        self.assertFalse(excluded(snap))

    def test_runtime_code_is_not_excluded(self):
        for pkg in ("wind_api", "wind_analysis", "wind_data"):
            for f in (ROOT / "backend" / pkg).glob("*.py"):
                rel = f.relative_to(ROOT).as_posix()
                self.assertFalse(excluded(rel), rel)

    def test_dev_only_files_are_excluded(self):
        for rel in ("frontend/src/App.tsx", "frontend/package.json", "backend/tests/test_api.py",
                    "docs/PLAN.md", ".impeccable/design.json", "public/index.html", "Dockerfile",
                    "docker-compose.yml", "backend/requirements.txt", "backend/requirements-dev.txt"):
            self.assertTrue(excluded(rel), rel)

    def test_max_duration_is_within_the_documented_hobby_limit(self):
        self.assertLessEqual(FN["maxDuration"], 300)


class PythonSetupTests(unittest.TestCase):
    def test_python_version_is_one_vercel_supports(self):
        v = (ROOT / ".python-version").read_text().strip()
        self.assertIn(v, {"3.12", "3.13", "3.14"})

    def test_pyproject_pins_match_backend_requirements(self):
        deps = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["dependencies"]
        reqs = [ln.strip() for ln in (ROOT / "backend" / "requirements.txt").read_text().splitlines()
                if ln.strip() and not ln.startswith("#")]
        self.assertEqual(sorted(deps), sorted(reqs))

    def test_fastapi_is_declared_so_the_preset_is_detected(self):
        deps = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["dependencies"]
        self.assertTrue(any(d.startswith("fastapi") for d in deps))


class StaticFrontEndTests(unittest.TestCase):
    def test_public_has_an_index_and_every_referenced_asset(self):
        index = (ROOT / "public" / "index.html").read_text(encoding="utf-8")
        refs = re.findall(r'(?:src|href)="(/assets/[^"]+)"', index)
        self.assertTrue(refs)
        for r in refs:
            self.assertTrue((ROOT / "public" / r.lstrip("/")).is_file(), r)

    def test_public_is_the_current_build(self):
        dist = ROOT / "frontend" / "dist"
        if not dist.is_dir():
            self.skipTest("frontend/dist not built; run npm run build:public to refresh public/")
        self.assertEqual((dist / "index.html").read_bytes(), (ROOT / "public" / "index.html").read_bytes(),
                         "public/ is stale: run `npm run build:public` in frontend/")


class EntrypointLoadsLikeAServerlessRuntimeTests(unittest.TestCase):
    """Import app.py from a different working directory, the way a function host would."""

    @classmethod
    def setUpClass(cls):
        cls._cwd = os.getcwd()
        cls._env = {k: os.environ.pop(k) for k in ("STATIC_DIR", "SNAPSHOT_PATH") if k in os.environ}
        os.chdir(tempfile.gettempdir())
        spec = importlib.util.spec_from_file_location("vercel_entry", ROOT / "app.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        cls.client = TestClient(mod.app)

    @classmethod
    def tearDownClass(cls):
        os.chdir(cls._cwd)
        os.environ.update(cls._env)

    def test_health_sees_the_bundled_snapshot(self):
        j = self.client.get("/api/health").json()
        self.assertEqual((j["status"], j["data_file_present"]), ("ok", True))

    def test_decision_matches_the_known_values(self):
        j = self.client.get("/api/decision", params={"decision_date": "2026-01-14"}).json()
        self.assertEqual(j["slots"][0]["forecast_mw"], 15834.0)
        self.assertEqual(j["slots"][0]["actual_mw"], 14602.0)

    def test_the_function_does_not_serve_the_front_end(self):
        # On Vercel the CDN serves public/; this function must not depend on STATIC_DIR.
        self.assertEqual(self.client.get("/").status_code, 404)

    def test_docs_are_reachable(self):
        self.assertEqual(self.client.get("/openapi.json").status_code, 200)


if __name__ == "__main__":
    unittest.main()
