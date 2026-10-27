# Wind day-ahead

A decision-support app for a GB energy utility's day-ahead buying team. For any day in January 2026 it shows the national wind
forecast that was available at the buying cut-off, a cautious case with the extra volume needed to cover it, and how accurate that
forecast has actually been. Every number is computed from Elexon data (FUELHH wind actuals, WINDFOR wind forecasts); nothing is
estimated or filled in.

> **Status:** built and tested locally and in Docker. The Vercel deployment has been **prepared but not yet deployed or tested live**.
> Numbers quoted in this repository come from the local and Docker builds, which run the same code and the same snapshot. Check a
> live deployment against them with `python backend/scripts/compare_deploy.py <url>` (see [Deploy](#deploy)).

## What it does

- **Tomorrow's wind (the decision tab).** It asks one question, "How much wind should you count on for tomorrow?", and answers it in
  one sentence (the forecast's expected average and a cautious figure). Below sit the half-hourly chart with the likely range (a
  toggle reveals what actually happened; a table sits behind the chart) and three short steps: which forecast was used and how old it
  was, how far it could be off, and what to plan for (expected wind, cautious case, extra to cover). The day is chosen with arrows or
  a collapsed bar strip; the decision time (the "cut-off" below; default 09:20 London) sits in a collapsed setting.
- **Track record (the accuracy tab).** Three steps: how big the misses are (four headline measures, more behind a toggle), how it went
  day by day (forecast against actual for the month, error by day), and whether the likely range held. A collapsed "More detail for
  analysts" holds error by lead time, by time of day, the error distribution and a by-forecast-level table.
- **No hindsight.** For a decision on day D the forecast is the latest vintage published at or before the cut-off, and the likely range
  uses only days that had finished by then. Actuals are shown only as an explicitly labelled replay.
- **Out of scope** (by the brief): other fuels, demand, prices and money. The app does not say what a purchase costs.

## Data

| | |
|---|---|
| Actuals | Elexon BMRS `FUELHH` stream, `fuelType=WIND`, 30-minute, 2 Jan to 1 Feb 2026 (1,488 rows) |
| Forecasts | Elexon BMRS `WINDFOR` stream, hourly, every vintage published 1 to 31 Jan 2026 (248 publishes, 18,104 rows) |
| Snapshot | `backend/data/snapshot.json.gz` (107 KB), fetched 2026-10-25 14:59 UTC, committed; sha256 starts `20580c46a321` |
| Quality | no missing half-hours, no nulls, no negatives, no duplicates; report in `backend/data/REPORT.txt` |

The API reads only the snapshot; it does not call Elexon at request time.

## Modelling assumptions

Read these before trusting a number. "Default" means I chose it and it has not been confirmed by the client.

| # | Assumption | Status |
|---|---|---|
| 1 | Cut-off is **09:20 Europe/London on the day before delivery**; the UI offers 09:20 and 09:50 and any HH:MM | Default. 09:50 GMT is confirmed on a Nord Pool page (last modified 2022). 09:20 comes from secondary sources and was not confirmed from an EPEX primary source. |
| 2 | "Decisions made in January" means decision days 1 to 31 Jan, delivery days 2 Jan to 1 Feb | Default |
| 3 | The forecast for a half-hour is the whole vintage with the greatest `publishTime` at or before the cut-off; `publishTime` is treated as the moment it became available | Default. The real delay between `publishTime` and availability is unknown. |
| 4 | WINDFOR is hourly; each hourly value applies to both half-hours of that hour and is compared with each half-hourly actual separately | Default |
| 5 | Error = forecast minus actual. Positive = over-forecast, the costly side for a buyer (wind that did not arrive) | Default |
| 6 | Values are MW; energy = MW x 0.5 h per half-hour | FUELHH is documented as average MW over 30 minutes. The WINDFOR unit is **not stated** in the API documentation I read and is assumed. |
| 7 | Likely range = P10 and P90 of the signed errors of past decision forecasts, pooled over the most recent finished days (up to 14, "full" at 7 or more with data, "reduced" at 1 to 6, none at 0). A day counts as finished only if it ended before the cut-off and its actuals were published by then. The interval is `[forecast - P90, forecast + (-P10)]`, one constant MW offset for every half-hour of the day | Default |
| 8 | Cautious case = low end of the range (floored at zero); extra to cover = expected energy minus cautious energy | Default |
| 9 | Persistence baseline = the actual 48 hours earlier, usable only if published by the cut-off | Default |
| 10 | WAPE = sum of absolute errors / sum of actuals. 90% shortfall = max(0, P90 of forecast minus actual). Percentiles use linear interpolation | Definitions |
| 11 | Days and cut-offs are Europe/London; stored times are UTC; 46- and 50-slot clock-change days are handled | Tested with constructed data only: January has no clock change |
| 12 | Missing data stays missing and is counted; it is never filled | Rule |

`docs/PLAN.md` is the original plan, written before implementation. Where it differs from the code, the code and
[`docs/DESIGN.md`](docs/DESIGN.md) are right.

## Current results (January 2026 snapshot, 09:20 cut-off)

| Measure | Value |
|---|---|
| Half-hours scored | 1,488 of 1,488 |
| Typical miss (mean absolute error) | 2,042 MW (18.1% of actual output) |
| Average error | **+1,748 MW** (forecast too high), too high in 84.7% of half-hours |
| Against the 48-hour persistence baseline | 2,003 MW vs 4,508 MW on 1,392 comparable half-hours |
| Likely range held | actual inside it 75.3% of the time (aim: 80%) |

The forecast ran high on average and the cause is not known. See [`docs/PITCH.md`](docs/PITCH.md) for the full table and the
unflattering parts.

## Run it

Requirements: Python 3.13, Node 22 (local); Docker Desktop (container).

### Docker

```bash
docker compose up --build                 # http://localhost:8000
docker compose --profile test run --rm test-backend
docker compose --profile test run --rm test-frontend
docker compose --profile tools run --rm snapshot    # OVERWRITES backend/data/snapshot.json.gz from the live Elexon API
```

One image serves the API and the built front end; it runs as a non-root user, read-only, with a healthcheck on `/api/health`.

### Local

```bash
# back end (from backend/)
pip install -r requirements-dev.txt
python -m unittest discover -s tests

# front end (from frontend/)
npm ci
npm run build                              # strict type-check, then bundle

# serve both from one process (from backend/)
STATIC_DIR=../frontend/dist python -m uvicorn wind_api.main:create_app --factory --port 8000
#   PowerShell: $env:STATIC_DIR="../frontend/dist"; python -m uvicorn wind_api.main:create_app --factory --port 8000

# front-end development with hot reload: run the line above without STATIC_DIR, then in frontend/:
npm run dev                                # proxies /api to 127.0.0.1:8000
```

Use plain `python`, not `python -I`, if `tzdata` was installed into your user site-packages.

### API

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | liveness; reports whether the snapshot file exists without loading it |
| `GET /api/meta` | snapshot provenance, accepted decision window, defaults, known caveats |
| `GET /api/decision?decision_date&cutoff` | forecast at the cut-off for each half-hour of the next day, with the range |
| `GET /api/accuracy?cutoff` | metrics, breakdowns, persistence baseline |
| `GET /api/series?cutoff` | every half-hour of the month: forecast, actual, range (feeds the period chart, the error distribution and the range check) |

Errors: `422` for a bad cut-off or date, `404` for a date outside the window, `503` with a message if the snapshot is missing.
Interactive docs at `/docs`.

## Deploy

Prepared for Vercel's FastAPI preset: root `app.py`, `pyproject.toml`, `vercel.json`, the built front end in `public/`, snapshot bundled.
Full notes, limits and sources: [`docs/DEPLOY.md`](docs/DEPLOY.md). The short version:

```powershell
cd frontend; npm ci; npm run build:public; cd ..
cd backend; python -m unittest discover -s tests; cd ..
vercel link
vercel deploy --prod --logs        # --prod: previews are protected and answer 401 to anyone not signed in to Vercel
python backend\scripts\compare_deploy.py https://YOUR-PROJECT.vercel.app
```

## Verification status

| Area | Status | How |
|---|---|---|
| Back-end logic and API | Tested | 155 `unittest` tests pass. Most use constructed data (labelled in the code); some check the real snapshot against values read from the live Elexon API. Key tests were checked by deliberately breaking the code (cut-off leak, unfinished-day band, persistence timing, window edge, cache, path traversal): each break was caught. |
| Front-end logic | Tested | 14 Vitest unit tests; strict TypeScript with no errors |
| Front-end behaviour | Tested, Chrome only | 42 scripted browser checks (`frontend/e2e/ui-check.mjs`, run by hand; see its header) pass locally: tooltips by mouse and keyboard, chart/table switches, day selection, cut-off change, stale data stays visible while refetching, 503 error and retry, theme and patterns toggles, no console errors |
| Visual layout | Inspected, Chrome only | Both views at 1440 px and 390 px, light and dark; no horizontal overflow at 390 px |
| Colour and contrast | Checked by calculation | Text and mark contrast pass in both themes; the red/blue pair passed the dataviz palette validator, including colour-blindness simulation |
| Docker | Tested on Windows Docker Desktop | clean `build --no-cache`, `up`, healthcheck healthy, `/api/health`, `/api/decision`, `/` all answered, tests pass inside containers, runs as uid 10001 and read-only |
| Snapshot rebuild | Partly tested | the `snapshot` service ran on a 14 to 16 Jan window and matched the committed snapshot exactly (1,168 forecast and 96 actual values); the full month was not re-fetched |
| Vercel build | Inspected locally | the CLI's local build output shows the entrypoint, packages and snapshot in the function and the front end as static files; bundle estimated at about 15 MB against the 500 MB Python limit |
| **Vercel live deployment** | **Not tested** | not yet deployed. Cold start, runtime file access and live numbers are unknown. |
| Cross-browser, real phone | Not tested | Chrome (desktop and emulated 390 px) only |
| Screen reader, full accessibility audit | Not tested | keyboard operation and ARIA labels are implemented and exercised by script, not by a person using assistive technology |
| Load, concurrency | Not tested | |
| Linux hosts (bind-mount permissions) | Not tested | |
| Elexon restatement of other January values | Not tested | only 14 to 16 Jan were re-fetched and compared |
| WINDFOR unit; EPEX 09:20 gate closure | Not verified | see assumptions 1 and 6 |
| Independent code review | None | the review steps in the build were run by the same AI that wrote the code |

## Limitations

- **One winter month, 31 decisions.** Nothing here says how the forecast behaves in other months or seasons.
- **The forecast ran high.** Over-forecast on 27 of 31 days; the cause is unexplained and could be a definition difference between
  WINDFOR and FUELHH, a real forecast bias, or both. A plain timing mismatch is **not** the explanation: shifting the alignment by up to
  three hours either way leaves the average error between 1,699 and 1,797 MW (`backend/scripts/alignment_check.py`). The same check
  shows the miss is smallest (1,961 MW against 2,042 MW) when forecasts are compared with the actual from two hours earlier, which
  suggests the forecast trails actual output; why is not known, and the app's alignment has not been changed.
- **The cautious case is expensive and not a guarantee.** It adds about 97 GWh per day on average (about a third of expected volume),
  and on the worst day (28 Jan) none of the 48 half-hours fell inside the range and the day's average actual (5,760 MW) was well below
  the cautious case (7,938 MW).
- **The range under-covers** (75.3% against an 80% aim) and early January has little or no history behind it (6 days "reduced", 2 with none).
- **The range is one constant MW offset per day**, not shaped by hour or forecast level, though errors grow with forecast level.
- **The range can go below zero.** On 12 half-hours (decision days 7 and 17 Jan, lowest -585 MW) the low end is negative, which is
  physically impossible. The cautious-case sums floor it at zero; the chart, table and API show the raw value. Known defect, not yet fixed.
- **No prices or demand**, so no money figure and no purchase recommendation.
- **A weak yardstick:** beating a 48-hour persistence baseline is a low bar. Other baselines were not tested.
- **Snapshot, not live.** Fetched 2026-10-25; later restatements by Elexon would not appear.
- **No authentication, no stored user data, no audit trail.**
- **Clock-change days** are handled and tested with constructed data only.

## AI assistance disclosure

This project was built with AI assistance, as the brief requires me to state.

- **What the owner did:** set the brief and the rules, decided the architecture, the design pattern and how the system should behave,
  set the designs (primary user, cut-off presets, the visual direction) and chose among options. The owner reviews the
  AI-written code and documents, and once reviewed by the owner, the code goes to production.
- **What the AI did:** it wrote the code, tests, configuration and documents in this repository as per instructed by the owner.
- **What was used:** Claude Code (Anthropic's command-line coding agent), running Claude Sonnet 5.5. Within it, the "impeccable" design workflow and a data-visualisation skill guided
  the interface and chart colours. Docker were used to test it.

## Repository map

```
backend/wind_data      snapshot fetch, parsing, in-memory loader (bisect lookup)
backend/wind_analysis  pure analysis: decision forecast, metrics, band, persistence
backend/wind_api       FastAPI app, typed models, lazy loading and caches
backend/scripts        fetch_snapshot.py, compare_deploy.py, doc_numbers.py (regenerates every quoted number), alignment_check.py
backend/tests          155 tests
frontend/src           React + TypeScript app (hand-built SVG charts)
frontend/e2e           ui-check.mjs: 42 browser checks, runnable against any URL
public/                built front end for Vercel
app.py, vercel.json    Vercel entrypoint and config
Dockerfile, docker-compose.yml
docs/                  BRIEF, PLAN (original), DEPLOY, PITCH, DESIGN (technical walkthrough)
PRODUCT.md, DESIGN.md  product context and visual design system (root DESIGN.md is the visual system, not docs/DESIGN.md)
```
