"""FastAPI app. Run with:  uvicorn wind_api.main:create_app --factory

Environment:
  SNAPSHOT_PATH  snapshot file (default backend/data/snapshot.json.gz)
  STATIC_DIR     built React app; when set, it is served from the same process
"""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse

from .models import (AccuracyResponse, DecisionResponse, ErrorResponse, HealthResponse, MetaResponse,
                     SeriesResponse)
from .service import DEFAULT_CUTOFF, VERSION, AnalysisService, DataUnavailable, OutsideWindow

DEFAULT_SNAPSHOT = Path(__file__).resolve().parents[1] / "data" / "snapshot.json.gz"
CUTOFF_PATTERN = r"^([01]\d|2[0-3]):[0-5]\d$"

CutoffParam = Query(DEFAULT_CUTOFF, pattern=CUTOFF_PATTERN,
                    description="Decision cut-off as HH:MM Europe/London wall-clock time on the day before delivery.",
                    examples=["09:20"])

R503 = {"model": ErrorResponse, "description": "Data snapshot is missing or unreadable."}


def create_app(snapshot_path: str | Path | None = None, static_dir: str | Path | None = None) -> FastAPI:
    path = Path(snapshot_path or os.environ.get("SNAPSHOT_PATH") or DEFAULT_SNAPSHOT)
    static = static_dir or os.environ.get("STATIC_DIR") or None
    root: Path | None = None
    if static:
        root = Path(static).resolve()
        if not (root / "index.html").is_file():
            raise RuntimeError(f"STATIC_DIR {static!r} must be a directory containing index.html")

    service = AnalysisService(path)
    app = FastAPI(title="UK wind forecast decision support", version=VERSION,
                  description="Wind forecast available at the day-ahead cut-off, and its measured accuracy "
                              "(Elexon FUELHH/WINDFOR, January 2026 snapshot). Error = forecast - actual.")

    def guard(fn, *args):
        try:
            return fn(*args)
        except DataUnavailable as e:
            raise HTTPException(503, str(e)) from None
        except OutsideWindow as e:
            raise HTTPException(404, str(e)) from None

    @app.get("/api/health", response_model=HealthResponse, tags=["system"])
    def health():
        """Liveness. Always 200; reports whether data is present without loading it."""
        return HealthResponse(status="ok", data_file_present=service.data_file_present,
                              data_loaded=service.data_loaded)

    @app.get("/api/meta", response_model=MetaResponse, tags=["system"], responses={503: R503})
    def meta():
        """Snapshot provenance, the accepted decision-date window, defaults and known caveats."""
        return guard(service.meta)

    @app.get("/api/decision", response_model=DecisionResponse, tags=["analysis"],
             responses={404: {"model": ErrorResponse, "description": "decision_date outside the data window."},
                        503: R503})
    def decision(decision_date: date = Query(description="Day the purchase decision is made (YYYY-MM-DD). "
                                                         "Delivery is the following day."),
                 cutoff: str = CutoffParam):
        """Forecast available at the cut-off for each half-hour of the next day, with an uncertainty band
        built only from days that had already finished at the cut-off."""
        return guard(service.decision, decision_date, cutoff)

    @app.get("/api/accuracy", response_model=AccuracyResponse, tags=["analysis"], responses={503: R503})
    def accuracy(cutoff: str = CutoffParam):
        """Accuracy of the decision-time forecast over every delivery day in the window, with breakdowns
        and a persistence baseline. Error = forecast - actual."""
        return guard(service.accuracy, cutoff)

    @app.get("/api/series", response_model=SeriesResponse, tags=["analysis"], responses={503: R503})
    def series(cutoff: str = CutoffParam):
        """Forecast (as known at each day's cut-off), actual and uncertainty band for every half-hour of every
        delivery day in the window. Lets a client draw the whole period, the error distribution and band coverage."""
        return guard(service.series, cutoff)

    if root is not None:
        index = root / "index.html"

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa(full_path: str):
            if full_path == "api" or full_path.startswith("api/"):
                raise HTTPException(404, "Unknown API route")
            target = (root / full_path).resolve()
            if target.is_file() and target.is_relative_to(root):
                return FileResponse(target)
            return FileResponse(index)          # client-side route

    return app
