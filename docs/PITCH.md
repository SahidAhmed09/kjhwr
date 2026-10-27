# Pitch: Wind day-ahead, for a day-ahead buying team

**Length:** 10 minutes, about 6 of them in the app. **Audience:** people who buy GB power the day before delivery.

**Where the numbers come from.** Every figure below is from the app's own API running on the committed January 2026 snapshot
(Elexon FUELHH actuals, WINDFOR forecasts; fetched 2026-10-25). They were produced by the local and Docker builds. **The Vercel
deployment has not been tested yet**, so before presenting from a live URL run
`python backend/scripts/compare_deploy.py <url>` and `python backend/scripts/doc_numbers.py --compare <url>`, and `node frontend/e2e/ui-check.mjs` with `BASE_URL=<url>`, and fix any difference.
`python backend/scripts/doc_numbers.py` regenerates every number on this page.

**Wording.** The app has two tabs, **Tomorrow's wind** and **Track record**, and calls the cut-off the **decision time**. This page and the
API say "cut-off"; it is the same thing.

---

## The message in four sentences

1. At 09:20 you decide how much to buy for tomorrow, and wind is the biggest unknown.
2. This tool shows, for any day in January 2026, exactly the wind forecast you would have had at that moment, how old it was, and how far
   past forecasts like it have been wrong, using no information from after the cut-off.
3. **On this month of data the forecast was too high far more often than too low: it overestimated wind in 85% of half-hours, by
   1,748 MW on average.** That is the costly direction for a buyer.
4. The tool puts a number on that error so you can decide how much cushion to buy. It does not yet say what the cushion costs.

## Agenda

| Time | What | Where |
|---|---|---|
| 0:00 to 1:00 | The decision, and what "no hindsight" means | slides or talk |
| 1:00 to 4:30 | Tomorrow's wind tab: one day, then the worst day, then a day with no history | app |
| 4:30 to 7:30 | Track record tab: headline, the day-by-day picture, does the range hold | app |
| 7:30 to 9:00 | What the results say, including what they do not | talk |
| 9:00 to 10:00 | What we need from you; questions | talk |

---

## The headline numbers

All for decisions made 1 to 31 Jan 2026 (delivery 2 Jan to 1 Feb), 09:20 London cut-off, 1,488 half-hours, none missing.

| Measure | Value | Where to see it |
|---|---|---|
| Typical miss (mean absolute error) | **2,042 MW**, 18.1% of actual wind output | Track record headline; the 18.1% is under "More measures" |
| Average error (forecast minus actual) | **+1,748 MW** (positive means too high) | Track record, step 1 |
| Half-hours the forecast was too high / too low | **84.7% / 15.3%** | Track record headline (85%); "More measures" has both shares |
| Days too high / too low on average | **27 of 31 / 4 of 31** | Track record, step 2, "Error by day" |
| Middle and tail of the miss | half the half-hours missed by 1,688 MW or less; 1 in 10 by 4,140 MW or more; 1 in 20 by 5,310 MW or more; 1 in 100 by 6,360 MW or more | Track record, step 1 shows the 90% figure; the rest come from the API (`/api/accuracy`) |
| Worst day | 28 Jan: forecast 11,135 MW average, actual 5,760 MW (**+5,375 MW**) | "Jump to another day", tile 27 |
| Only clearly under-forecast day | 19 Jan: forecast 5,796 MW, actual 6,526 MW (**-730 MW**) | "Jump to another day", tile 18 |
| By forecast level | below 5 GW: miss 1,253 MW, average error +539 MW. At 20 to 25 GW: miss and average error both **+4,562 MW**, too high in every one of the 86 half-hours | Track record, "More detail for analysts", "Error by forecast level" |
| Against a simple baseline (actual from 2 days earlier) | forecast 2,003 MW vs baseline 4,508 MW on 1,392 comparable half-hours (55.6% lower) | Track record, step 1 |
| Does the likely range hold? | actual inside it **75.3%** of 1,392 half-hours (aim 80%); below 12.0%; above 12.7% | Track record, step 3 |
| Days with a full / reduced / no range | 23 / 6 / 2 of 31 | counted from the API; on screen, Tomorrow's wind step 2 says which applies to the day shown |
| Fresher forecasts are better, but not available at 09:20 | every forecast published: miss 1,689 MW when 0 to 6 h ahead, 2,312 MW when 42 to 48 h ahead | Track record, "More detail for analysts", "Error by lead time" |
| Does waiting for the 09:30 publish help? | miss 2,016 MW at a 09:50 cut-off vs 2,042 MW at 09:20 (1.3% better). A 12:00 cut-off (after gate closure, contrast only) gives 1,904 MW | the "Decision time" setting |
| Overnight is worst | miss about 2,400 MW from 03:00 to 06:00; about 1,800 to 2,000 MW from 09:00 to 22:00 | Track record, "More detail for analysts", "Error by time of day" |

### Volume view (not a screen in the app)

Calculated from `/api/series` over the 29 days that have a range (`doc_numbers.py`). **Volumes only, no prices.**
"Short" is wind a plan counted on that did not arrive; "surplus" is wind beyond the plan.

| Plan assumes | Wind short, per day | Wind surplus, per day |
|---|---|---|
| The expected forecast | **44,301 MWh** | 3,772 MWh |
| The cautious case (low end of the range) | 4,669 MWh | **61,344 MWh** |

The cautious case needs **97,204 MWh more purchased per day on average** (76,714 to 116,755), about 32% of the average expected
304,835 MWh. Daily actual wind was below the expected forecast on 25 of the 29 days and below the cautious case on 3.

---

## Demo click path

Start at the app root, for example `http://localhost:8000`. Use a laptop-width window (1440 px) first; show 390 px at the end if asked.
Two things are collapsed by default: **Decision time** and **Jump to another day** (under the day arrows). Open them when the script says so.

### A. Tomorrow's wind tab (1:00 to 4:30)

1. **Open** `/?view=decision&day=2026-01-14&cutoff=09:20`. Read the page aloud: *"How much wind should you count on for Thursday 15 January?
   The forecast says about 11.6 GW. Forecasts miss, so a cautious plan counts on 7.0 GW."* Point at the top row: you are buying on Wed 14 Jan
   for delivery on Thu 15 Jan.
2. **The chart.** The line is the forecast for each half-hour. Hover over 15:00 for the forecast and the likely range. Say what the grey band
   is: *"where the actual wind has usually landed, taken only from days that had already finished."*
3. **Tick "Show what actually happened".** Wind averaged 10.6 GW, 1.0 GW below the forecast, so the forecast was too high, the costly side;
   all 48 half-hours stayed inside the range. Say: *"A fair day for the range. Not every day is."* Untick it.
4. **Step 1, which forecast.** Published at 07:30 on Wed 14 Jan, 1 h 50 min old at the decision time; it averages 11.6 GW and moves between
   8,864 and 15,834 MW. Say: *"Anything published after 09:20 is ignored on purpose."*
5. **Step 2, how far could it be off.** The band comes from the 12 most recent finished days. Say: *"A guide, not a guarantee."* The link
   under it opens the Track record tab; use the Tomorrow's wind tab to come back.
6. **Step 3, what could you plan for.** Expected wind 11.6 GW (278,630 MWh). Cautious case 7.0 GW. Extra to cover 109,620 MWh, about 4,568 MW
   more in every half-hour.
7. **Click Table** above the chart: 48 half-hours with the forecast publish time on each row. Click Chart to go back.
8. **Open "Decision time" and press 09:50.** The forecast now comes from the 09:30 publish. Say: *"It barely changes the answer: 1.3% on
   average."* Set it back to 09:20.
9. **Show the worst day.** Open "Jump to another day" and click tile **27** (buying on 27 Jan, delivering 28 Jan). The answer reads about
   11.1 GW with a cautious 7.9 GW. Tick the toggle: wind averaged 5.8 GW, **none of the 48 half-hours inside the range.** Say plainly:
   *"This is the day the forecast failed, and the cautious case would not have been enough either."*
10. **Show an under-forecast day.** Click tile **18** (delivering 19 Jan). Forecast 5.8 GW, actual 6.5 GW. The cautious case is 1.6 GW with
    101,117 MWh extra to cover, which is far too cautious on the day. Say: *"It errs on the side of safety, and on a day like this that costs."*
11. **Show a day with no range.** Click tile **1** (buying 1 Jan). The answer says there is not enough finished-day history to say how low it
    could go, step 2 says there is no band, and the cautious case and extra to cover read "Not available". Say: *"There was no finished
    history yet, so the app shows nothing rather than guessing."*

### B. Track record tab (4:30 to 7:30)

1. **Click Track record.** Read: *"Across January, the forecast available at 09:20 was off by about 2,042 MW on average, and too high in
   85% of half-hours."*
2. **Step 1, how big are the misses.** Typical miss 2,042 MW; average error +1,748 MW; 90% shortfall 4,140 MW ("on 9 half-hours in 10 the
   forecast was no more than this far too high"); against a simple baseline 2,003 vs 4,508 MW. Open "More measures" for the 18.1% miss share,
   the 84.7% / 15.3% split and the big-miss measure (2,509 MW).
3. **Step 2, day by day.** The whole-period chart: forecast (solid) tracks actual (dashed) in shape and sits above it most of the time. Hover
   to compare a peak. Then "Error by day": red bars above the line on 27 of 31 days; the outlined bar is the day picked at the top. Say
   what red means.
4. **Step 3, does the likely range hold.** 75.3% against an aim of 80%. Say: *"The range is a bit too narrow, and we tell you so."*
5. **Open "More detail for analysts".** Error by lead time and by time of day: fresher is better (1,689 vs 2,312 MW) but a day-ahead buyer
   cannot use fresher, and overnight is worst. The forecast-level table: big-wind forecasts are the least trustworthy, 100% too high above 20 GW.
6. **Click Table on any chart** to show that every picture has its numbers behind it. Optionally switch on **Patterns** and **Dark mode**.

---

## Being plain about the unflattering results

Say these before they are asked.

- **The forecast overestimates wind.** Too high in 85% of half-hours and on 27 of 31 days, by 1,748 MW on average. We do not know why.
  It could be a real bias, or a difference in what the two Elexon datasets measure (the forecast's unit is not stated in the documentation
  we read, and we assumed MW), or both. We tested one cause and ruled it out: a timing mismatch between the hourly forecast and the
  half-hourly actuals does not account for it. We have not tested the others.
- **The error is largest when the forecast is large.** Forecasts above 20 GW were too high every time, by 4,562 MW on average.
- **The cautious case is a blunt tool.** It would have cut wind shortfall from 44,301 to 4,669 MWh a day, but it asks for about 97 GWh
  more purchased per day and leaves 61,344 MWh a day of surplus. Whether that pays depends on prices we do not have. On the worst day it
  was not enough.
- **The likely range is too narrow** (75.3% against 80%) and is one constant offset for the whole day, not shaped by hour or forecast level.
  On two days (7 and 17 Jan) its low end even dips below zero, down to -585 MW, which cannot happen to real wind. The cautious-case sums
  floor it at zero but the chart and table show the raw number. We know about it and have not fixed it.
- **Beating the baseline is a low bar.** Reusing the actual from 2 days earlier is a weak comparison. We did not test a stronger one
  or any other forecaster.
- **It is one winter month.** 31 decisions. Nothing about summer, other months, or clock-change days on real data.
- **It is a replay, not live.** The data is a snapshot fetched on 25 Oct 2026. There is no live feed yet.
- **No money.** No prices, demand or positions went in, so we cannot say what any of this would have saved or cost.
- **Built by an AI under direction, and not yet independently reviewed.** See the README's disclosure.

## What we are asking for

Not a decision today. To make this useful we would need:

1. **Your price and imbalance data** (or a sample), so volumes can become money and the cautious case can be sized.
2. **A check of what WINDFOR measures**, ideally against your own wind metering or Elexon's data team, to explain the +1,748 MW.
3. **Your real gate-closure and decision times** (we confirmed N2EX 09:50 from a Nord Pool page, not EPEX 09:20).
4. **More history** (several months across seasons) to test whether the bias persists and to calibrate the range properly.
5. **Your view on what the screen should recommend**, if anything, beyond showing the range.

We would also test a simple correction for the average error, which we have **not** done. It may help, and we are not promising it.

---

## Likely questions, straight answers

**How much money would this have saved us?** We cannot say. There are no prices or positions in the data. The only thing we can show is
volume, in the table above.

**Why is the forecast too high so often?** We do not know. We ruled out one cause: it is not a simple timing mismatch. Shifting how the
hourly forecast lines up with the half-hourly actuals by up to three hours either way leaves the average error between 1,699 and
1,797 MW. We did notice the miss is smallest (1,961 MW against 2,042 MW) when forecasts are compared with actuals from two hours
earlier, so the forecast seems to trail what the wind actually did; we do not know why. Still open: a genuine forecast bias, or a
difference in what the two datasets count (the forecast's unit is not stated in the documentation we read).

**Can't we just subtract the average error?** Possibly, and the cautious case already leans that way because the range comes from past
errors. A plain bias correction has not been tested here, so we will not claim it works.

**Is the cautious case the right size?** It is a starting point. It trades 97 GWh a day extra bought against shortfall falling from
44,301 to 4,669 MWh a day. The right size depends on the price gap between buying early and settling short, which we need from you.

**How far can we trust the range?** Inside it 75.3% of the time against an aim of 80%, and early January has little or no history
(6 reduced days, 2 with none). Treat it as a rough band.

**Does waiting for the 09:30 forecast help?** A little: 2,016 MW miss at 09:50 against 2,042 MW at 09:20. N2EX's gate closes at 09:50 GMT
per Nord Pool's page; we could not confirm the EPEX 09:20 time from a primary source.

**What about the latest forecasts?** They are better (miss 1,689 MW when 0 to 6 hours ahead) but are not available to a day-ahead decision.

**Is this live? Is the data final?** It is a snapshot, not live. We re-fetched 14 to 16 Jan from Elexon and 1,168 forecast and 96 actual
values matched exactly; we did not re-check the rest of the month.

**Does it work for other months, or around clock changes?** Not tested on real data. Clock-change days (46 and 50 half-hours) are
handled and tested with constructed data only.

**Does it use anyone else's forecast?** No, only Elexon's WINDFOR. It does not compare providers.

**Who has checked it?** Its tests pass (155 back end, 14 front end, 42 scripted browser checks, in Chrome), and the Docker build runs.
No independent human review yet, and it is not yet live on Vercel.

**Is it secure?** It holds only public Elexon data, has no login and stores nothing about users. Hosting is not yet in place.

**What does the bar on each day tile mean?** The tiles sit behind "Jump to another day". Each shows the average error for the next day: red up for too high, blue down for too low.

---

## If the live demo fails

Run it locally (`docker compose up --build`, then `http://localhost:8000`). The same numbers appear; `compare_deploy.py` is the proof
they match a deployment. As a last resort, the tables above carry every figure.
