# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

React + TypeScript (Vite) front end, served by the FastAPI back end from the same process (STATIC_DIR). Fixed by the brief; deploy target Vercel or Heroku.

## Users

Power procurement analysts at a UK energy utility who buy on the GB day-ahead market. Primary scene (confirmed): at a desk on a large monitor, minutes before the day-ahead gate closure (about 09:20 London), deciding how much power to buy beyond expected wind generation. Secondary: a manager or technical lead reviewing accuracy later, on a laptop or phone.

## Product Purpose

Show the latest wind generation forecast that was available at the decision cut-off for the next delivery day, and measure quantitatively how accurate that forecast has been, so buyers can size their purchase with the measured error in mind. Scope is national GB wind only, from Elexon only (FUELHH actuals, WINDFOR forecasts), January 2026 decisions.

## Positioning

Honest, no-hindsight replay: every number for a decision day uses only what had been published by the cut-off, and the uncertainty band uses only days already finished at that moment. A generic wind-forecast chart does not make that guarantee.

## Operating Context

Decision at a fixed daily deadline. Times are Europe/London; data is stored in UTC. Delivery days can have 46, 48 or 50 half-hour slots on clock-change days. Data is a committed January 2026 snapshot (replay), not live. Error convention: forecast minus actual, so a positive error means the forecast was too high and the buyer under-procures (the costly side).

## Capabilities and Constraints

- API: GET /api/meta, /api/decision?decision_date&cutoff, /api/accuracy?cutoff, /api/health (OpenAPI at /docs).
- Cut-off presets (confirmed): 09:20 and 09:50, labelled by time only; free HH:MM entry also allowed. N2EX 09:50 GMT is confirmed from a primary page; the EPEX 09:20 time is not confirmed from a primary source, so exchange names are not shown.
- Units are treated as MW but the WINDFOR unit is unverified; the UI must say so where numbers are shown (api notes).
- Observed in the data: the forecast over-forecasts on average (+1,748 MW bias, 85% of slots over). Cause unknown; the UI reports it as measured and does not explain it.
- No demand data is in scope; the app does not compute a purchase volume against demand.
- Requirements from the brief: plain sentence-case wording, red means over-forecast, colour-blind-safe validated palette with its own dark mode, tooltips on every chart, a legend whenever there are two or more series, a table behind every chart, mobile-friendly, visible keyboard focus, previous data stays on screen while refetching, strict TypeScript, no unused code.
- No synthetic data anywhere in the UI.

## Evidence on Hand

Real Elexon snapshot for January 2026 behind the API (1,488 half-hourly actuals, 18,104 forecast rows from 248 publishes). No customer names, testimonials or commercial claims exist and none may be invented.

## Product Principles

1. Never show a number the buyer could not have had at the cut-off, unless it is plainly labelled as what happened afterwards.
2. Say how sure we are: every forecast comes with its measured error and its freshness.
3. Missing stays missing: gaps and short history are labelled, never filled.
4. The costly side is named and coloured consistently: over-forecast is red.
5. Plain language first; metric names (MAE, WAPE) only with a plain-English gloss.

## Accessibility & Inclusion

Colour-blind-safe validated palette with a separate dark mode; colour is never the only carrier of meaning (over/under also encoded by direction and label); keyboard focus visible; every chart has a table behind it; works at 390px width.
