# Design walkthrough (for a technical lead)

How the system works, why it is built this way, and where to look first. This is the technical document; the visual design system is
the separate file `DESIGN.md` at the repository root. Product context is in `PRODUCT.md`; the original, pre-implementation plan is
`docs/PLAN.md` and is partly out of date.

Numbers quoted here come from `python backend/scripts/doc_numbers.py` and `backend/scripts/alignment_check.py`, run on the committed
snapshot. Nothing here has been checked against a live Vercel deployment, because none exists yet.

**Size:** `wind_data` 248 lines, `wind_analysis` 345, `wind_api` 504, scripts 504 (Python); front end 2,352 lines of TypeScript and
1,225 of CSS; 1,432 lines of back-end tests and 108 of front-end tests.

## 1. Shape of the system

```
Elexon BMRS API ──(backend/scripts/fetch_snapshot.py, offline, stdlib only)──► backend/data/snapshot.json.gz  (107 KB, committed)
                                                                                      │ loaded lazily, once
                                      ┌───────────────────────────────────────────────▼───────────────────────┐
                                      │ wind_data.Snapshot  (in-memory; bisect lookup)                        │
                                      │ wind_analysis       (pure functions: decision, metrics, band, ...)    │
                                      │ wind_api            (FastAPI; typed models; per-cut-off caches)       │
                                      └───────────────┬───────────────────────────────────────────────────────┘
                                                      │ JSON
                              frontend (React + TS, built to static files)
                              Docker: served by the same process (STATIC_DIR)   Vercel: public/ on the CDN + one function
```

Layers depend downward only: the analysis package never imports FastAPI or the loader's file code; it needs only an object with
`latest_forecast`, `actual`, `actual_publish` and `vintages` (a duck-typed "source"). That is what lets the tests build constructed
data sources.

## 2. The core operation: the forecast available at the cut-off

For delivery day D and cut-off time T, each half-hour slot s of D gets:

```
cutoff_utc   = (D - 1 day, T) interpreted as Europe/London wall-clock, converted to UTC     timeutil.decision_cutoff
target       = s rounded down to the UTC hour                                             timeutil.hour_floor
(publish, f) = the vintage of `target` with the greatest publishTime <= cutoff_utc        Snapshot.latest_forecast
```

- **One bisect.** `Snapshot` keeps, per target hour, two parallel lists sorted by publish time. `latest_forecast` is
  `bisect_right(publishes, cutoff) - 1`. The bound is **inclusive**: a publish exactly at the cut-off counts, one second later does not.
- **Whole-vintage semantics, no back-fill.** If the latest eligible vintage has a null value, the result is that null; it does not fall
  back to an older vintage. If there is no eligible vintage the slot is missing. Missing slots are counted (`n_missing_forecast`) and
  excluded from metrics, never filled.
- **Hour to half-hour.** WINDFOR is hourly and FUELHH half-hourly, so both half-hours of an hour take the hour's value. Rounding down to
  the UTC hour is equal to rounding down to the London hour because London's offset is always a whole number of hours.
- **Day boundaries.** `timeutil.market_day_slots` generates slots from London midnight to London midnight, so a day has 48 slots, or 46 or
  50 on the two clock-change days. Slots are UTC epoch seconds throughout; London is used only to define days, cut-offs and the hour-of-day
  grouping.
- **Lead time** of a slot is `slot start - vintage publish time`, in hours.

In January the decision vintage is the 07:30 UTC publish for every day (the 08:00 and 09:20 cut-offs give identical results), so the
forecast is always 1 h 50 min old at 09:20. That makes "lead time" and "time of day" confounded in the decision-vintage view: early slots
of the delivery day have a lead of about 16.5 h and late slots about 40 h.

## 3. Data model

### Snapshot file (schema 1, gzip JSON)

```
meta        base_url, fetched_at, window{publish_from, publish_to, settlement_from, settlement_to}, duplicates, requests[]
actuals     cols [start, mw, publish, settlement_date, period]       1,488 rows  (FUELHH WIND)
forecasts   cols [publish, start, mw]                                18,104 rows  (WINDFOR)
```

Times are integer epoch seconds (UTC). The window is the delivery days 2 Jan to 1 Feb for actuals and publishes 1 to 31 Jan for
forecasts. The API exposes the file's SHA-256 in `/api/meta`.

### Fetching (`backend/scripts/fetch_snapshot.py`)

Standard library only. WINDFOR is requested one UTC day of publish time at a time, FUELHH one week of settlement dates at a time, with up
to 5 retries and exponential backoff on 408/429/5xx and network errors (other 4xx fail immediately). Rows are parsed by
`wind_data/parsing.py`: identical duplicates are dropped and counted; **conflicting duplicates raise** and abort the build; nulls stay
null; non-numeric generation, wrong dataset or fuel type, and naive timestamps raise. The build ends with a data report
(`backend/data/REPORT.txt`) and a checksum.

### In memory (`wind_data.loader.Snapshot`)

| Structure | Key to value | Used for |
|---|---|---|
| `actuals` | slot start to `(mw, publish, settlement_date, period)` | actual lookup, availability check (`actual_publish`) |
| `_pubs`, `_vals` | hourly target to sorted publish times / matching values | the bisect lookup; `vintages(target)` for the every-vintage view |
| `publish_times` | sorted distinct publishes | meta |

Memory is a few MB. WINDFOR publishes 73 hourly points per vintage, each starting at 21:00 UTC the day before the publish date, so a
target hour appears in a median of 24 vintages (range 8 to 32).

## 4. Accuracy method

**Sign.** `error = forecast - actual`. Positive means over-forecast: wind the buyer counted on did not arrive.

**Metrics** (`wind_analysis/metrics.py::error_metrics`): n, MAE, RMSE, bias (mean error), **WAPE** = sum|error| / sum(actual) (not MAPE),
share of half-hours over / under / exactly right, percentiles of absolute error (50, 90, 95, 99) and signed error (5, 10, 25, 50, 75, 90,
95), and **90% shortfall** = max(0, P90 of signed error). Percentiles use linear interpolation. Empty input returns nulls, not zeros.

**Breakdowns** (`analysis.evaluate`): by delivery day; by London hour of day (the repeated hour on a 50-slot day is one key); by lead time of
the decision vintage (6 h buckets); by forecast level (5,000 MW bins); plus an every-vintage view of error against lead time. The every-vintage
view is deliberately ex-post and uses all forecasts ever published, including ones published after the cut-off, so it shows how accuracy
changes with freshness, not what a buyer could have used. Tests assert every breakdown sums back to the overall count and error.

**Persistence baseline.** For a slot, the actual 48 hours earlier, usable only if that actual was published by the cut-off. Compared on
the slots where both exist (1,392 of 1,488; the first two delivery days lack it). This is a weak baseline; see risks.

**Likely range** (`wind_analysis/band.py::uncertainty_band`), the part most worth a second pair of eyes:

1. Walk back day by day from D-1. A day is **finished** only if its last slot ended at or before the cut-off.
2. Examine the most recent 14 finished days. For each, take its own decision-time forecast errors, keeping only slots where the actual was
   published by the cut-off.
3. Pool all those signed errors. Take P10 and P90.
4. Range for forecast f is `[f - P90, f - P10]`, because actual = forecast - error.
5. Label: 7 or more finished days with data gives `trailing_empirical`; 1 to 6 gives `reduced_history`; 0 gives `insufficient_history` and **no
   range** (nothing is invented).

Consequences to be aware of: the offset is a single pair of numbers for the whole day (not by hour or level); the days used are the days
the range is then judged against, so coverage is not guaranteed (observed: 75.3% inside against the 80% aim, 12.0% below, 12.7% above, over
1,392 half-hours); and the window counts finished calendar days examined, so early January simply has fewer days.

**Hindsight boundary.**

| Hindsight-free (uses only what existed at the cut-off) | Ex-post (uses what happened later) |
|---|---|
| decision forecast, lead time, likely range, cautious case, extra to cover, freshness | actual values in the decision response (labelled replay), the whole accuracy view, the every-vintage lead view, the range-coverage check |

A test injects absurd vintages published after each cut-off and asserts nothing in the first column changes (while the every-vintage view
does, as a control).

**Cautious case and extra to cover** are computed in the browser from the decision response (`frontend/src/lib/summary.ts`): cautious wind
is the range's low end floored at zero; extra to cover is expected energy minus cautious energy; energy is MW x 0.5 h per slot. Because the
range is a constant MW offset, extra to cover is the same MW in every half-hour of a day (for example 4,568 MW on 14 Jan).

## 5. API layer

- `wind_api/main.py::create_app(snapshot_path, static_dir)` is a factory (run with `uvicorn ... --factory`); `STATIC_DIR` and
  `SNAPSHOT_PATH` environment variables are read here. A bad `STATIC_DIR` fails at startup.
- `wind_api/service.py::AnalysisService` loads the snapshot **lazily** on first use under a lock. A failed load (missing, corrupt, wrong
  schema) is **not cached**, so data appearing later is picked up. Results are cached in bounded LRU caches (64 entries): accuracy and
  series per cut-off, decisions per (date, cut-off). Cut-offs are validated by regex (`HH:MM`) so the cache key space is at most 1,440.
- Errors: 422 (bad cut-off or date, from validation, which runs before data is touched), 404 (decision date outside the window, message gives
  the valid range), 503 (snapshot missing or unreadable, message names the fix). Responses use typed pydantic models, so `/openapi.json`
  is the contract; `frontend/src/api/types.ts` mirrors it by hand.
- `/api/series` exists so the browser can draw the whole period, the error histogram and the range-coverage check without 31 requests;
  it flattens the 31 decision results and is the largest response (234 KB).
- Measured first-call times in-process on a developer laptop (not Vercel): meta 0.04 s, accuracy 0.07 s, series 0.12 s.

## 6. Front end

React 19 and strict TypeScript, built by Vite. No chart or state libraries: charts are small hand-built SVG components so that every chart
has a keyboard-readable tooltip, a legend and a table without fighting a library.

- `api/useApi.ts` keeps the previous response on screen while the next loads or fails, and exposes `stale` and `retry`. The UI dims stale data
  and shows "Updating…" rather than a spinner.
- **Page structure.** Two tabs named for the question each answers: *Tomorrow's wind* (`view=decision`) and *Track record* (`view=accuracy`).
  Each opens with the answer, then numbered steps. Tomorrow's wind: the question and a one-sentence answer, the chart, then "which forecast",
  "how far could it be off", "what could you plan for". Track record: the headline finding, then "how big are the misses" (four measures, more
  behind a toggle), "day by day", "does the likely range hold", and a collapsed "More detail for analysts" (lead time, time of day, error
  distribution, forecast level). The decision time and the day strip sit behind collapsed controls. The UI says "decision time" for what the
  API and this document call the cut-off. Nothing in the API changed for this; the same figures are shown, in a different order.
- State lives in the URL query (`view`, `day`, `cutoff`), so a view can be shared; an out-of-window day falls back to the last day.
- `lib/summary.ts` holds the computations the browser does (energy, cautious case, outcome of a day, range coverage, histogram), with
  unit tests (14 in total, with the formatting helpers). These partly duplicate ideas that exist in Python (coverage, percentile-style counts); see risks.
- Accessibility: keyboard focus ring, arrow-key reading of every chart, a live region mirroring the tooltip, a table behind every chart,
  patterns mode for the colour-blind case, a roving tab stop on the day strip.

## 7. Deployment shapes

- **Docker** (`Dockerfile`): multi-stage; Node builds the front end, a Python slim image runs one uvicorn process that serves API and static
  files; non-root uid 10001, read-only root filesystem, capabilities dropped, healthcheck that requires the snapshot file.
- **Vercel** (`app.py`, `pyproject.toml`, `vercel.json`, `public/`): the FastAPI preset runs `app.py` as one function; `public/` is served from
  the CDN. The function bundle includes the snapshot and excludes dev files. Built output was inspected locally; a live deployment has not
  been tested (see `docs/DEPLOY.md`).

## 8. Trade-offs

| Decision | Alternative | Why this | Cost |
|---|---|---|---|
| Committed snapshot, no live Elexon calls | Fetch per request | Reproducible numbers; no serverless time-limit risk; the history is fixed | It is a replay; later restatements are invisible |
| Pure analysis package over a duck-typed source | Analysis inside the API | Testable with constructed data; reusable | One more layer |
| Whole-vintage selection, nulls not back-filled | Fall back to the next-older vintage | Honest about what was known | A null in the latest vintage hides a usable older value |
| Pooled P10/P90 of past errors for the range | Per-hour or per-level quantiles, or a model | Simple, explainable, no hindsight | One offset per day; observed under-coverage |
| Hand-built SVG charts | A chart library | Per-chart keyboard reading, legends and tables; small bundle (84 KB gzipped JS in total) | More code to maintain (543 lines of chart code) |
| `public/` committed build output on Vercel | Build on Vercel | No dependency on Node being present in a Python build | Can go stale (a test guards it) |
| Browser computes cautious case and summaries | Server returns them | Keeps the API generic | Logic in two languages |
| Series endpoint returns everything flat | Paginate | One request, 234 KB | Grows with the window |

## 9. Edge cases

| Case | Handling | Tested | Seen in real data |
|---|---|---|---|
| Clock-change days (46 and 50 slots) | London midnight-to-midnight slots; hour-of-day key merges the repeated hour | constructed data | no (January) |
| Publish exactly at the cut-off | included | yes | n/a |
| Vintage published after the cut-off | never used for the decision; test injects absurd values | yes | n/a |
| Missing forecast or actual | stays missing, counted, excluded from metrics | yes | none missing |
| Null values | kept as null, never filled | yes | none |
| Duplicate rows | identical dropped and counted; conflicting aborts the build | yes | none |
| Off-schedule publish | accepted as published | n/a | 15 Jan 12:25 instead of 11:30 |
| Negative horizon (forecast for hours already begun) | kept; the every-vintage view buckets them as negative lead | yes | 3,721 of the 18,104 forecast rows in the snapshot |
| No finished day for the range | range omitted and labelled, not guessed | yes | 2 of 31 days |
| Short history | computed but labelled `reduced_history` | yes | 6 of 31 days |
| Low end of the range below zero | the cautious-case arithmetic floors wind at 0 (tested); **the API, the chart and the table show the raw negative value** (known defect, risk 4) | summary floor yes; display no | **yes**: 12 half-hours on two decision days (7 and 17 Jan), lowest -585 MW |
| Actual for a baseline day not yet published at the cut-off | baseline missing for that slot, counted | yes | 96 slots lack a baseline |
| Snapshot missing, corrupt or wrong schema | 503 with a clear message; not cached | yes | n/a |
| Bad cut-off or date | 422 before touching data | yes | n/a |
| Path traversal under `STATIC_DIR` | resolved path must stay inside the directory | yes | n/a |

## 10. Testing

155 back-end tests: API 44, tests for the Vercel setup 17, decision 16, breakdowns 16, parsing 15, loader 13, time 13, metrics 12, band 9;
plus 14 front-end unit tests and 42 scripted browser checks (`frontend/e2e/ui-check.mjs`, Chrome, run by hand). Most back-end logic tests use constructed
data and say so; a few check the real snapshot against values read directly from the Elexon API. Key tests were mutation-checked by hand:
cut-off leaking by an hour, the band including an unfinished day, persistence ignoring publish time, an off-by-one window edge, a disabled
cache and a removed traversal guard each caused a failure.

Not covered: property-based tests, load tests, cross-browser, assistive technology, a live deployment, and real clock-change data.

## 11. Risks to review first

Ordered by how much a wrong answer would change the numbers a buyer sees.

1. **The average error (+1,748 MW) is unexplained.** Over-forecast in 84.7% of half-hours and on 27 of 31 days. Review whether WINDFOR and
   FUELHH measure the same thing (the WINDFOR unit is not stated in the documentation read; MW is assumed). `backend/scripts/alignment_check.py`
   rules out a simple alignment error: shifting the alignment by up to three hours either way leaves the bias between 1,699 and 1,797 MW,
   and the hour-mean alignment gives the same +1,748 MW. It also shows the miss is smallest (1,961 MW against 2,042 MW) when forecasts are
   compared with actuals two hours earlier, so the forecast appears to trail output. Cause unknown; the app's alignment is unchanged.
2. **`publishTime` is treated as the moment a forecast became available.** The true delay is unknown. Every "no hindsight" claim rests on it.
   Check against Elexon's publication behaviour or the team's own receipt times.
3. **The default cut-off, 09:20 London.** N2EX 09:50 GMT is confirmed on a Nord Pool page (last modified 2022); EPEX 09:20 is from
   secondary sources. Confirm both from current rulebooks. The cut-off is a parameter, so this is a configuration question, not a code one.
4. **The likely range.** Pooled P10/P90 over up to 14 finished days: one offset per day, observed coverage 75.3% against an 80% aim, and the
   same days that set the offset are used to judge it. **Known defect:** the low end goes below zero in 12 half-hours (decision days 7
   and 17 Jan, lowest -585 MW; for example 8 Jan 12:00 shows a forecast of 3,487 MW with a range of -259 to 3,835 MW). `summary.ts`
   floors wind at zero for the cautious case, but `/api/decision` returns the raw value and the chart and table display it. The likely
   fix is a floor of zero in `Band.interval`; coverage figures would not change, since an actual cannot be below a negative low end. A quick improvement to evaluate is a range that depends on forecast level, since
   mean error grows from +539 MW (forecasts under 5 GW) to +4,562 MW (20 to 25 GW).
5. **The cautious case is derived from that range**, so it inherits the problem, and it is large: about 97 GWh per day on average
   (about 32% of expected volume), and on 28 Jan none of the 48 half-hours fell inside the range. Whether it is "right-sized" needs prices.
6. **The baseline is weak.** Reusing the actual from 48 hours earlier is easy to beat (2,003 MW against 4,508 MW). No stronger baseline or
   alternative forecaster was tested.
7. **Logic in two languages.** The browser re-implements the cautious-case arithmetic, range coverage and the histogram
   (`frontend/src/lib/summary.ts`), separately from the Python metrics. They are unit-tested, but nothing checks that the two agree beyond
   spot values.
8. **Snapshot provenance.** Fetched 2026-10-25. Only 14 to 16 Jan were re-fetched and compared (1,168 forecast and 96 actual values
   identical); the rest of the month was not. Elexon restatements would change numbers silently.
9. **One winter month.** Everything is 31 decisions; clock-change handling has never seen real data.
10. **Operational:** per-instance in-memory caches on Vercel (bounded, harmless but not shared); `public/` can go stale; the Vercel
    deployment has not been exercised; no authentication or rate limiting; the pinned FastAPI (0.115.6) and dev-only npm advisories (3
    reported in vitest's dependencies) are untriaged.

## 12. Where to start changing things

| To change | Edit |
|---|---|
| Cut-off default or presets | `wind_api/service.py::DEFAULT_CUTOFF`, `frontend/src/components/Controls.tsx` (`PRESETS`), `frontend/src/App.tsx` |
| Range window, minimum days, percentiles | `wind_analysis/config.py::AnalysisConfig` |
| Lead and level bucket widths | `AnalysisConfig` (`lead_bucket_h`, `level_bin_mw`) |
| Alignment of hourly forecast to slots | `wind_analysis/decision.py::decision_day` (uses `hour_floor`) |
| Snapshot window | `backend/scripts/fetch_snapshot.py` arguments, then re-run and review `REPORT.txt` |
| Add an endpoint | `wind_api/models.py`, `service.py`, `main.py`, mirror in `frontend/src/api/types.ts`, add API tests |
| Regenerate every quoted number | `python backend/scripts/doc_numbers.py` |
