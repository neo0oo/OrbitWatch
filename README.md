# OrbitWatch

OrbitWatch tracks satellites in real time. It pulls real orbital data (TLEs) from [Celestrak](https://celestrak.org), calculates where each satellite is with SGP4, and shows it on a 3D globe with its upcoming orbit path.

Built as a single-process Python app (FastAPI + SQLite) for the Individual Assignment 1 DevOps course project.

## What it does

- Add a satellite by its NORAD ID (for example, the ISS is `25544`) and OrbitWatch fetches its latest TLE from Celestrak.
- Shows the satellite's live latitude, longitude and altitude, updated every 2 seconds.
- Draws the satellite's orbit for the next ~95 minutes on a 3D Earth (Three.js).
- Caches TLEs in SQLite and refreshes them when they get old. If Celestrak is down, it keeps using the last TLE it saved.

## Architecture

One FastAPI process serves both the API and the frontend. The backend is split into two domains:

- **Catalog** (`app/catalog/`): which satellites are tracked, plus fetching and caching their TLEs.
- **Propagation** (`app/propagation/`): the orbit maths. `engine.py` is pure functions with no HTTP or database code.

`app/database.py` creates the SQLite connection and tables. See `ADR.md` for the design decisions.

## Requirements

- Python 3.10 or newer
- Internet access (Celestrak for TLE data; the browser loads Three.js and the Earth texture from a CDN)

## Setup and run

```bash
git clone https://github.com/neo0oo/OrbitWatch
cd OrbitWatch
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 -m app.main
```

Then open http://localhost:8000, type `25544` into "Add by NORAD ID" and click Add.

The tables are created automatically on startup, so there is no manual setup or migration step.

## Configuration

Everything is configured with environment variables. All of them have defaults, so none are required.

| Variable | Default | What it does |
|---|---|---|
| `PORT` | `8000` | Port the server listens on (it binds to `0.0.0.0`) |
| `DATA_DIR` | `./data` | Folder for the SQLite file, which is `DATA_DIR/orbitwatch.db` |
| `CELESTRAK_URL` | `https://celestrak.org/NORAD/elements/gp.php` | Where TLEs are fetched from |
| `TLE_REFRESH_HOURS` | `6` | How old a cached TLE can be before it is refetched |

Example: `PORT=9000 DATA_DIR=/tmp/orbitwatch python3 -m app.main`

## API

Interactive docs are at http://localhost:8000/docs.

| Method | Path | What it does |
|---|---|---|
| GET | `/api/satellites` | List tracked satellites |
| POST | `/api/satellites` | Add a satellite. Body: `{"norad_id": 25544}` |
| DELETE | `/api/satellites/{norad_id}` | Remove a satellite and its cached TLE |
| GET | `/api/satellites/{norad_id}/position` | Current latitude, longitude and altitude |
| GET | `/api/satellites/{norad_id}/track` | Upcoming orbit points (`minutes`, `step_seconds` query params) |

## Tests and coverage

```bash
python3 -m pytest -v
python3 -m pytest --cov=app --cov-report=term-missing
```

**Coverage result: 82% total.**

Coverage is measured on the core logic of both domains. `app/main.py` and the `routes.py` files are excluded in `.coveragerc` because they are thin glue code. The tests run offline: Celestrak is faked and the database tests use a temporary SQLite file. The real network call in `fetch_tle`, the routes and the frontend were checked by hand.

## Project structure

```
OrbitWatch/
├── app/
│   ├── main.py            # app entry point
│   ├── config.py          # environment variables
│   ├── database.py        # SQLite connection and schema
│   ├── catalog/           # domain 1: satellites and TLE caching
│   └── propagation/       # domain 2: orbit maths
├── frontend/              # Three.js globe (index.html, main.js, style.css)
├── tests/
├── ADR.md                 # architecture decision records
├── AI_USAGE.md            # AI usage log
└── requirements.txt
```

## Limitations

- OrbitWatch shows where a satellite is, not when it will pass over a given place (pass prediction was deliberately left out, see ADR-5).
- Positions are only as accurate as the TLE, which is why TLEs are refreshed regularly.

## Container contract check

Result of running the provided `run.sh` against this repo:

```
=== SDD Assignment 1 contract check ===
Repository: /Users/neomedic/OrbitWatch

==> Repository shape
  PASS  one Dockerfile, one manifest (requirements.txt)

==> Build from a clean context, no build args
  PASS  image built
  PASS  image size 58 MB

==> Start on PORT=8000 and reach it from the host
  PASS  HTTP 200 from http://localhost:8000/

==> SQLite file under DATA_DIR
  PASS  found in /data: orbitwatch.db

==> Data persists, and a second boot does not re-seed
  PASS  volume at /data persists
  PASS  row counts unchanged across restart: satellites=0 tle_cache=0

==> PORT override is honoured (not hardcoded)
  PASS  HTTP 200 from http://localhost:9123/

=== ALL CHECKS PASSED ===
```
