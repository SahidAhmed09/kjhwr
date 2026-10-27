You are a product developer building a customized software product for a client: an energy utility in the UK. The team buys power from the UK day-ahead market. To meet consumer demand they need to know how much power must be procured beyond renewable (wind) generation. Wind is weather-dependent and day-ahead purchase decisions are made one day before the delivery day, so they rely on forecasts.

The web app must let them:
1. Clearly understand the latest renewable generation forecasts available when they need to make decisions on buying from the day-ahead market.
2. Evaluate the accuracy of the forecasts quantitatively, so they can make decisions considering the quantified error.

Scope: national-level wind generation from Elexon only, no other data.
- Actuals: https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/FUELHH/stream, fuelType "WIND". Fields: startTime (30-minute resolution), generation.
- Forecasts: https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/WINDFOR/stream. Fields: startTime, publishTime (when the forecast was created), generation.
Consider only data relevant to purchase decisions made in January 2026.

Build with React (front end) and Python (back end). Use Docker. Deploy the sample app on Vercel or Heroku. AI tools may be used but must be mentioned explicitly in the README.
I must also be able to (a) pitch the product to the client and (b) explain the software design and implementation to an internal technical lead.
