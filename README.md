# Fuel Planner API

A Django REST API that:

- Accepts a U.S. start and finish location.
- Builds the driving route via the public OSRM routing service.
- Overlays cost-optimized refueling stops sourced from `fuel-prices-for-be-assessment.csv`.
- Estimates the total fuel spend assuming a configurable range (default 500 mi) and efficiency (default 10 mpg).
- Returns an embeddable HTML map showing the route and recommended stops.

## Prerequisites

- Python 3.12 (latest release with official Shapely/PyProj wheels; `.python-version` pins 3.12.7 for pyenv/ASDF users)
- A virtual environment (recommended)
- Internet access for Nominatim geocoding + OSRM routing

## Project Setup

```powershell
cd G:\Django_Developer_Remote
py -3.12 -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements-dev.txt
```

> On macOS/Linux, run `python3.12 -m venv .venv` and `source .venv/bin/activate`.

If you need to support Python 3.13+ later, either ensure Shapely/PyProj publish wheels for that version or use a container/pyenv environment that bundles the necessary GEOS libraries.

> **Heads up:** run `python --version` (or `py --version`) before installing requirements. If it doesn’t show 3.12.x, recreate the virtualenv with `py -3.12 -m venv .venv` (Windows) or `python3.12 -m venv .venv` (macOS/Linux) to avoid Shapely/PyProj build errors.

### Deployment Notes

- **Docker (recommended)**:
  ```bash
  docker build -t fuelplanner .
  docker run -p 8000:8000 fuelplanner
  ```
  Render/Fly/GCP can run the same container; just point them at the Dockerfile.
- Target an environment that offers Python 3.12 (Render/Cloud Run/Docker). A simple approach is to base your image on `python:3.12-slim`, copy the repo, install `requirements-dev.txt`, and run `gunicorn fuelplanner.wsgi:application`.
- If you deploy on a platform with only Python 3.13+, you must bring your own GEOS/PROJ binaries or swap back to the pure-Python geometry path—otherwise the build will fail while installing Shapely/PyProj.

### 1. Build (or refresh) the station dataset

The provided CSV does not include coordinates, so I enrich it once with the free `uszipcode` database (downloaded automatically and cached under `C:\Users\<you>\.uszipcode`). A pre-built `data/stations_with_coords.json` is already committed, so check that file first—if it exists, you can skip this step entirely.

```powershell
python scripts\build_station_dataset.py
```

Run it only when you need to regenerate `data/stations_with_coords.json` (for example, after deleting the file or updating the CSV). Otherwise, leave the existing JSON in place; that’s what the API loads at runtime.

### 2. Apply migrations

```powershell
python manage.py migrate
```

### 3. Run the API

```powershell
python manage.py runserver
```

The primary endpoint is `POST /api/route-plan/`.

### 4. Launch the browser demo (optional)

Navigate to `http://127.0.0.1:8000/api/demo/` to open a lightweight UI where you can choose start/finish cities from dropdowns, tweak vehicle settings, and render the returned map/metrics directly in the browser. The page simply proxies the same `/api/route-plan/` endpoint under the hood.

If you want to power another client, you can fetch the full list of supported cities via `GET /api/cities/` (derived from the station dataset).

## Example Request

```http
POST http://127.0.0.1:8000/api/route-plan/
Content-Type: application/json

{
  "start": "Austin, TX",
  "finish": "Chicago, IL",
  "vehicle_range_miles": 500,
  "fuel_efficiency_mpg": 10
}
```

### Example Response (truncated)

```json
{
  "route": {
    "distance_miles": 1152.03,
    "duration_minutes": 1005.3
  },
  "fuel_plan": {
    "stops": [
      {
        "name": "BIG WILLY'S",
        "city": "Austin",
        "state": "TX",
        "mile_marker": 0.0,
        "price_per_gallon": 2.979,
        "type": "start",
        "coordinates": { "latitude": 30.30, "longitude": -97.70 }
      },
      {
        "name": "NORTH PLATTE TRAVEL PLAZA",
        "city": "North Platte",
        "state": "NE",
        "mile_marker": 486.42,
        "price_per_gallon": 2.899,
        "type": "mid_route",
        "coordinates": { "latitude": 41.13, "longitude": -100.76 }
      }
      // ...
    ],
    "total_cost_usd": 333.77,
    "total_gallons": 115.2
  },
  "map_html": "<div>...</div>"
}
```

The `map_html` string can be rendered directly in a browser or embedded inside a documentation site.

## Implementation Notes

- **Routing**: [OSRM](https://project-osrm.org/) public endpoint (`router.project-osrm.org`) — one request per API call.
- **Geocoding**: OpenStreetMap Nominatim via `geopy`. Requests are restricted to U.S. locations.
- **Fuel data**: Cached copy of the provided CSV, deduplicated and enriched with coordinates using `uszipcode`.
- **City catalog**: `/api/cities/` exposes every `City, ST` combination present in the station dataset for UI dropdowns/autocomplete fields.
- **Spatial math**: Shapely + pyproj handle all buffering, projections, and distance/mile-marker calculations (hence the Python 3.12 requirement for wheels).
- **Optimization**: Greedy algorithm that ensures the vehicle never exceeds its maximum range while minimizing price within each reachable window.
- **Mapping**: Folium builds an interactive Leaflet map highlighting start, finish, and each refueling stop.
