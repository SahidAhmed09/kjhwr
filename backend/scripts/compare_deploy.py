#!/usr/bin/env python
"""Compare a running deployment with the local build, endpoint by endpoint.

    python backend/scripts/compare_deploy.py https://YOUR-PROJECT.vercel.app

The local side is the same app.py that Vercel runs, called in-process, so the comparison needs the dev
requirements (httpx) but no server. Live responses are fetched with the standard library only.
Exit status is 1 if anything differs. Floats are compared to 1e-9.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOL = 1e-9
# Fields that legitimately differ between two healthy instances (lazy loading), or are about the host.
VOLATILE = {"data_loaded"}

API_CASES = [
    ("health", "/api/health"),
    ("meta", "/api/meta"),
    ("decision, first day", "/api/decision?decision_date=2026-01-01"),
    ("decision, 14 Jan", "/api/decision?decision_date=2026-01-14"),
    ("decision, 14 Jan, 09:50", "/api/decision?decision_date=2026-01-14&cutoff=09:50"),
    ("decision, last day", "/api/decision?decision_date=2026-01-31"),
    ("accuracy", "/api/accuracy"),
    ("accuracy, 09:50", "/api/accuracy?cutoff=09:50"),
    ("series", "/api/series"),
    ("error: bad cutoff (422)", "/api/decision?decision_date=2026-01-14&cutoff=9:20"),
    ("error: outside window (404)", "/api/decision?decision_date=2026-02-05"),
]


def local_client():
    sys.path.insert(0, str(ROOT))
    os.environ.pop("STATIC_DIR", None)
    os.environ.pop("SNAPSHOT_PATH", None)
    from starlette.testclient import TestClient

    import app as entry  # the same module Vercel imports

    return TestClient(entry.app)


def fetch(base: str, path: str) -> tuple[int, str, bytes]:
    req = urllib.request.Request(base.rstrip("/") + path, headers={"User-Agent": "compare-deploy/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.headers.get("content-type", ""), r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("content-type", ""), e.read()


def diff(a, b, path="$") -> list[str]:
    """Paths where two JSON values differ."""
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b)):
            if k in VOLATILE:
                continue
            if k not in a or k not in b:
                out.append(f"{path}.{k}: present on one side only")
            else:
                out += diff(a[k], b[k], f"{path}.{k}")
        return out
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [f"{path}: length {len(a)} vs {len(b)}"]
        out = []
        for i, (x, y) in enumerate(zip(a, b)):
            out += diff(x, y, f"{path}[{i}]")
        return out
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        return [] if abs(a - b) <= TOL else [f"{path}: {a!r} vs {b!r}"]
    return [] if a == b else [f"{path}: {a!r} vs {b!r}"]


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    base = sys.argv[1]
    local = local_client()
    results: list[tuple[bool, str, str]] = []

    for name, path in API_CASES:
        status, ctype, body = fetch(base, path)
        lr = local.get(path)
        if status in (401, 403) and lr.status_code not in (401, 403):
            results.append((False, name, f"live answered {status}: the deployment is protected. "
                                         "Use the production domain (vercel deploy --prod) or turn protection off."))
            continue
        problems = []
        if status != lr.status_code:
            problems.append(f"status live {status} vs local {lr.status_code}")
        if "json" not in ctype:
            problems.append(f"live content-type {ctype!r}")
        else:
            try:
                problems += diff(json.loads(body), lr.json())[:5]
            except json.JSONDecodeError:
                problems.append("live body is not JSON")
        results.append((not problems, name, "; ".join(problems) or f"identical ({status}, {len(body)} bytes)"))

    # The static front end: the CDN must serve the same files as public/.
    status, ctype, body = fetch(base, "/")
    index = (ROOT / "public" / "index.html").read_bytes()
    results.append((status == 200 and "html" in ctype and body == index, "front end: / matches public/index.html",
                    f"{status} {ctype}, {len(body)} bytes vs {len(index)}"))
    for ref in sorted(set(re.findall(r'(?:src|href)="(/assets/[^"]+)"', index.decode()))):
        s, ct, b = fetch(base, ref)
        want = (ROOT / "public" / ref.lstrip("/")).read_bytes()
        ok = s == 200 and hashlib.sha256(b).digest() == hashlib.sha256(want).digest()
        results.append((ok, f"asset {ref.rsplit('/', 1)[-1]}", f"{s} {ct}, {len(b)} bytes" + ("" if ok else " (differs from local)")))
    s, ct, b = fetch(base, "/docs")
    results.append((s == 200 and b"swagger" in b.lower(), "/docs serves the Swagger UI", f"{s} {ct}, {len(b)} bytes"))
    s, ct, b = fetch(base, "/openapi.json")
    ok = s == 200
    try:
        ok = ok and "/api/decision" in json.loads(b).get("paths", {})
    except (json.JSONDecodeError, AttributeError):
        ok = False
    results.append((ok, "/openapi.json lists /api/decision", f"{s} {ct}, {len(b)} bytes"))

    width = max(len(n) for _, n, _ in results)
    for ok, name, detail in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name.ljust(width)}  {detail}")
    failed = sum(1 for ok, _, _ in results if not ok)
    print(f"\n{len(results) - failed}/{len(results)} checks match the local build")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
