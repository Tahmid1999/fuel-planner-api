# Haulfill

Cheapest diesel stops between two US cities, for one truck and its tank.

Live: https://haulfill.vercel.app

The API runs on Render's free plan and sleeps after 15 idle minutes. If nobody has used it for a while, the first plan takes about a minute while it wakes up; the page tells you when that's happening.

https://github.com/user-attachments/assets/eb0acda3-c80f-4746-9f19-c46cb1fe8ff4

The explainer (2:36, captioned, also at [docs/haulfill-explainer.mp4](docs/haulfill-explainer.mp4)) plans one trip, Austin to Chicago, then goes through each part behind it. It is drawn, not a screen recording: the phone screens in it are screenshots of the app at phone size, and the numbers come from the code and the measured table below. The voice is a stock ElevenLabs voice.

## What it does

You pick From and To, enter your truck's mpg, tank size and how full it is now. You get the route on a map, the stops in order with the price, how many gallons to buy at each and what that costs, and the same trip priced under the "fill up at a quarter tank" habit, so you can see what the plan saves. Every plan gets a link you can reopen or send to your phone.

Prices come from an OPIS truck-stop file (6,622 stations, as of 28 Nov 2025). They are not live, and the page says so.

## How the stops are picked

Only stations within 3 miles of the route count (you can change that). Then, going along the route: at each station, if a cheaper one or the finish is within reach, buy just enough to get there; otherwise fill the tank. The reserve (15% of the tank unless you change it) is never touched.

That's the known greedy for refuelling on a fixed route. I don't just claim it's the cheapest: `api/tests/test_fuel_cheapest.py` checks it against a brute-force solver (`api/tests/oracle.py`) on 500 random routes.

Two definitions matter for the savings number:

- **The habit.** Drive on, and fill to full at the first station where the next leg would leave you under a quarter tank. Same stations, same prices.
- **Trip cost.** Money spent at the pump, minus the value of whatever is left in the tank at the finish (valued at what it cost, first in, first out). Without that credit the habit, which always fills to full, would look worse by fuel it never burned.

## Measured

Output of `api/scripts/compare_plans.py` on six saved routes. OPIS sample as of 2025-11-28, 6.5 mpg, 150 gal tank, half full at the start, 15% reserve, stations within 3 miles.

| Route | Miles | Stops (plan / habit) | Plan | Habit | Saves | Old take-home rule |
|---|---|---|---|---|---|---|
| Atlanta, GA to Denver, CO | 1399 | 5 / 2 | $396.17 | $465.64 | $69.46 | $407.26 |
| Austin, TX to Chicago, IL | 1161 | 3 / 2 | $289.99 | $328.27 | $38.28 | $295.72 |
| Los Angeles, CA to Dallas, TX | 1444 | 5 / 2 | $425.52 | $544.53 | $119.00 | $445.30 |
| Miami, FL to New York, NY | 1291 | 5 / 2 | $363.92 | $449.85 | $85.93 | $374.84 |
| Phoenix, AZ to Kansas City, MO | 1250 | 3 / 2 | $339.38 | $379.93 | $40.55 | $339.38 |
| Seattle, WA to Salt Lake City, UT | 832 | 1 / 1 | $171.85 | $171.85 | $0.00 | $171.85 |

So against the quarter-tank habit it saves $0 to $119 a trip. Against the rule I wrote for the take-home the gap is much smaller, $0 to $20, and I'd rather say that than hide it. The plan buys at more stops than the habit does; whether five stops is worth $69 is the driver's call.

A plan on a route that's already cached comes back in 0.6 to 0.9 s from my machine in Bangladesh, about 0.3 s of which is the round trip.

## Where this came from

This started as a take-home test in Dec 2025: a Django endpoint that took two cities and returned fuel stops and a Folium map. Coming back to it, I found my stop-picking rule wasn't the cheapest, and it priced the first tank at whichever station was nearest the start, even one 250 miles away, which isn't fuel a driver can actually buy. I replaced the rule with one I could prove, moved stations, cities and saved plans into Postgres, and built a mobile-first front end for the person who would actually use it: an owner-operator paying for their own diesel. The old code is still in the history.

## Similar tools

Truckers already have fuel tools: [TruckMaster Fuel Finder](https://truckmaster.com/fuel-finder), [ProMiles Fuel Finder](https://promiles.com/fuel-finder), Trucker Tools' route and fuel optimizer, and Mudflap and Trucker Path for discounted prices. They have live prices and real station locations, which this doesn't. This is a portfolio project; the parts I care about are the planning rule, checked against a brute-force solver, and a savings number you can check.

## Run it

With Docker:

```bash
docker compose up --build
```

Then open http://localhost:3300. On its first start the API loads the cities and the price sample into an empty database.

Without Docker you need Python 3.12, Node 20 and a Postgres (or leave `DATABASE_URL` out and it uses SQLite):

```bash
cd api
python -m venv .venv
.venv/Scripts/activate          # source .venv/bin/activate on macOS/Linux
pip install -r requirements-dev.txt
export DJANGO_DEBUG=1           # plus DATABASE_URL for Postgres; .env.example lists the rest
python manage.py prepare_db     # migrate, and seed if the database is empty
python manage.py runserver
```

```bash
cd web
npm ci
cp .env.example .env.local
npm run dev                     # http://localhost:3300
```

A new price file goes in with `python manage.py import_prices file.csv --source "OPIS" --as-of 2026-01-15`. It becomes the active list; saved plans keep the prices they were made with.

## API

| | |
|---|---|
| `GET /api/cities/?q=aus` | city search for the From/To boxes |
| `GET /api/prices/active/` | which price file is in use, and its date |
| `POST /api/plans/` | plan a trip: `from_city`, `to_city`, optional truck and limits |
| `GET /api/plans/<id>/` | a saved plan |
| `GET /api/health/` | API and database up |

Swagger is at `/api/docs/`.

## Tests

104 pytest tests for the API and 58 jest tests for the web app. CI runs both on every pull request and push to main, the API ones against Postgres 16, and also builds and starts the whole compose stack.

## Hosting

Web on Vercel, API on Render (free, Virginia), Postgres on Neon (free, AWS us-east-1, next to the API). A free Render instance gets about a tenth of a CPU, where Django took 38 s to boot with two workers and a separate migrate step. `api/gunicorn.conf.py` boots it once and forks one worker, which brought it to about 14 s on a 0.1-core cap on my PC.

## Limits

- Station positions are the city from the price file, not the truck stop itself, so they're off by up to about a kilometre and detour miles are estimates.
- Prices are whatever file was loaded last. The date is on every result.
- Routes are car routes from the public OSRM server. No height, weight or hazmat restrictions.
- The plan is the cheapest among stations within the detour limit. It shows each stop's detour but doesn't trade detour against price.
- Free hosting: the first request after 15 idle minutes takes about a minute.

## Data

- Diesel prices: an OPIS truck-stop sample (as of 28 Nov 2025), the file that came with the take-home.
- Cities: built from the [uszipcode](https://github.com/MacHu-GWU/uszipcode-project) database, shipped as `api/planner/fixtures/us_cities.csv.gz`.
- Routes: [OSRM](https://project-osrm.org/) public server, cached per city pair.
- Map: [OpenFreeMap](https://openfreemap.org/) tiles, © OpenMapTiles, data © OpenStreetMap contributors.
