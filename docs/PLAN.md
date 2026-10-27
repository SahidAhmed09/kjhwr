# PLAN (DRAFT, pending confirmation of the open decisions in section 8)

Nothing below is implemented. Section 1 records facts observed from the live Elexon API on 2026-10-25. Everything else is a proposal.

## 1. Verified facts about the data (observed 2026-10-25)

Base URL `https://data.elexon.co.uk/bmrs/api/v1`. OpenAPI spec: `https://data.elexon.co.uk/swagger/v1/swagger.json` (the `/bmrs/api/v1/swagger/...` path returns 404).

| | FUELHH `/datasets/FUELHH/stream` | WINDFOR `/datasets/WINDFOR/stream` |
|---|---|---|
| Query params | `publishDateTimeFrom/To`, `settlementDateFrom/To` (yyyy-MM-dd), `settlementPeriod[]`, `fuelType[]` | `publishDateTimeFrom/To` only. **No filter on startTime.** With no params it returns only the latest publish. |
| Fields | dataset, publishTime, startTime, settlementDate, settlementPeriod, fuelType, generation | dataset, publishTime, startTime, generation |
| Resolution | 30 min (1920 rows = 40 days x 48, gaps all exactly 30 min) | 60 min (all startTime at minute 00) |
| Time zone | ISO-8601 UTC ("Z"). `settlementDate` is the GB-local date. | UTC |
| Unit | Spec: "average MW values over 30 minutes". | Not stated in the spec text I read. Values (1,981 to 21,353) are consistent with MW. **Unit not verified.** |
| Row order | newest first | oldest first (not guaranteed) |

WINDFOR publishing, from 320 publishes between 2025-12-25 and 2026-02-02:
- 8 per day at 02:30, 04:30, 07:30, 09:30, 11:30, 15:30, 18:30, 22:30 UTC.
- One deviation: on 2026-01-15 the 11:30 publish was stamped 12:25 instead.
- Every publish holds exactly 73 hourly points. The window always starts at 21:00 UTC on the day before the publish date.
- Horizon (startTime minus publishTime) over all publishes: -25.5 h to +66.5 h. About 4,800 of about 23,000 rows have a negative horizon (startTime earlier than publishTime). These are not actuals: they differ from FUELHH by about 1.6 GW mean absolute error, and they are revised between publishes.
- For a delivery day D, the D-1 07:30 UTC publish covers all 24 hours of D, at horizons of 16.5 h to 39.5 h.
- 1,002 of 1,009 startTimes seen in more than 3 publishes have different values across publishes, so forecasts are revised.

Not verifiable from the API: how long after `publishTime` a forecast actually became available to a user. We use `publishTime` as the availability time.

## 2. Architecture

```
Elexon BMRS API --(scripts/fetch_snapshot.py, offline)--> data/raw/*.json (committed, with provenance)
                                                              |
                                              backend (FastAPI, Python) loads + validates
                                                              |
                                        /api/* JSON  <--  React (Vite, TypeScript) SPA
```
- **Backend**: FastAPI. Pure functions in `core/` (selection, alignment, metrics) with no I/O, so they are unit-testable. An `ElexonClient` and a `SnapshotStore` sit behind one `DataSource` interface.
- **Frontend**: React + Vite + TypeScript, charts via Recharts or similar. It never computes metrics; it renders what the API returns.
- **Docker**: multi-stage `Dockerfile` (build SPA, serve from the FastAPI container) and `docker-compose.yml` for local dev.
- **Deploy**: Vercel (static SPA + Python serverless function) or Heroku (container). See decision D8.

## 3. Data flow

1. `fetch_snapshot.py` pulls FUELHH (WIND) and WINDFOR for the required windows, in chunks, and writes raw JSON unchanged plus a `manifest.json` (URL, params, fetch time, row counts, sha256).
2. Backend loads the snapshot and checks: no duplicates, 30 min / 60 min grid, expected coverage. It fails loudly on gaps. It never fills them.
3. Per decision day, "latest forecast at cut-off" is selected by rule D3. Hourly forecast is aligned to actuals by D5.
4. Metrics and uncertainty bands are computed per D4 and D6 and served as JSON. Missing data is returned as `null` with a reason, never imputed.

## 4. API endpoints (proposed)

- `GET /api/health`
- `GET /api/meta`: snapshot provenance, decision cut-off, covered days.
- `GET /api/days`: list of decision days with data-completeness flags.
- `GET /api/decision/{decision_date}`: selected publish (publishTime, age at cut-off), 24 hourly forecasts for delivery day, uncertainty band (D6), horizon.
- `GET /api/accuracy/summary?horizon=...`: bias, MAE, RMSE, MAPE-style %, per-day and overall.
- `GET /api/accuracy/by-horizon`: the same metrics by forecast horizon bucket.
- `GET /api/accuracy/day/{delivery_date}`: forecast vs actual by hour and the error series.
- `GET /api/forecast-evolution/{delivery_date}`: all publishes for that delivery day (how the forecast was revised).

## 5. Screens

1. **Decision view** (the pitch screen): pick a decision day, see the forecast available at the cut-off for the next day, its band, and "wind to assume vs. residual to buy" given a demand input (user-entered, not fetched, since demand data is out of scope).
2. **Accuracy view**: January summary metrics, error distribution, error by hour of day and by horizon.
3. **Forecast vs actual** for a chosen delivery day, with the forecast revisions.
4. **About / Method**: definitions, sign convention, data provenance and limitations (also the technical lead's reference).

## 6. Test strategy

- **Unit** (pytest): selection rule (boundaries: publish exactly at cut-off, none before cut-off, the 12:25 irregularity), aligning hourly to half-hourly, error signs, metrics against hand-computed values, uncertainty band using no future data (a test that mutates data after the cut-off and asserts the output is unchanged).
- Synthetic data is allowed only in these unit tests, and it is labelled as such.
- **Snapshot integrity**: counts, grid, no duplicates, hashes match the manifest.
- **Contract**: API responses validated against pydantic schemas; a frontend type check against the same OpenAPI.
- **Live smoke test** (opt-in, not in CI): one small request to Elexon to detect schema drift.
- **Frontend**: component tests (Vitest) and one Playwright e2e per screen against the real snapshot.
- Tests are never weakened to pass (project rule 4).

## 7. Deliverables for the two audiences

- Pitch: a short walkthrough of the Decision view and Accuracy view, plus a one-page value case stating only what the data shows.
- Technical lead: this PLAN, a design README (including the explicit AI-tools statement the brief requires), and the Method screen.

## 8. Open decisions (recommended default; awaiting confirmation)

See the chat message for the full table. Summary: D1 cut-off time, D2 January window, D3 latest-forecast rule, D4 error sign, D5 hourly vs half-hourly alignment, D6 uncertainty method (and whether warm-up data from December is allowed), D7 live vs snapshot, D8 hosting.
