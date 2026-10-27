"""Vercel entrypoint: the FastAPI preset looks for a top-level `app` in a root app.py.

The application code lives in backend/, so put it on the import path first. The front end is not served
from here on Vercel: the built files in public/ are served from the CDN, and every other path
(/api/*, /docs, /openapi.json) reaches this function. Locally and in Docker, wind_api.main:create_app
serves the front end itself when STATIC_DIR is set.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

from fastapi import FastAPI  # noqa: E402
from wind_api.main import create_app  # noqa: E402

app = create_app()
assert isinstance(app, FastAPI)  # also tells Vercel's entrypoint detection that `app` is a FastAPI instance
