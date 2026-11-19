# OrbitWatch

OrbitWatch tracks satellites in real time. It pulls real orbital data (TLEs) from [Celestrak](https://celestrak.org), calculates where each satellite is with SGP4, and shows it on a 3D globe with its upcoming orbit path.

Assignment 1 built it as one FastAPI + SQLite process. Assignment 2 splits it into two services with their own SQL Server databases, a static UI, and CI/CD to Azure.

**Live URL:** https://nmedicieu2024ui.z43.web.core.windows.net (live once the first deploy from `main` has run)

## What it does

- Add a satellite by its NORAD ID (for example, the ISS is `25544`) and OrbitWatch fetches its latest TLE from Celestrak.
- Shows the satellite's live latitude, longitude and altitude, updated every 2 seconds.
- Draws the satellite's orbit for the next ~95 minutes on a 3D Earth (Three.js).
- Caches TLEs and refreshes them when they get old. If Celestrak is down, it keeps using the last TLE it saved.

## Architecture

| Part | Folder | What it owns | Database |
|---|---|---|---|
| **catalog** service | `services/catalog` | Which satellites are tracked, and fetching their TLEs from Celestrak | `catalog` (`satellites`, `tle_cache`) |
| **propagation** service | `services/propagation` | The orbit maths: TLE → position and track | `propagation` (`tle_cache`) |
| UI | `ui/` | Static HTML/JS globe that calls both services from the browser | none |

The cross-seam call is server side: propagation asks the catalog for a TLE with `GET /api/satellites/{norad_id}/tle`, using `CATALOG_URL` and a timeout. If the catalog is down, propagation uses its cached TLE and marks the response `stale_tle: true`; with no cached copy it returns `503 "Catalog service is unavailable"`. See `ADR.md` (6-10) for the decisions and `system.yaml` for the machine-readable description.

Each service:
- applies its numbered SQL migrations (`migrations/NNN_*.sql`) on startup, recording them in `schema_migrations`
- serves `GET /health` (`200` with `{"status","db","version"}` when it can read and write its database, `503` otherwise)
- logs one line per request (method, path, status, duration)

## Run locally (Docker Compose)

Requirements: Docker. On Apple Silicon, turn on Rosetta emulation in Docker Desktop for the SQL Server image.

```bash
git clone https://github.com/neo0oo/OrbitWatch
cd OrbitWatch
docker compose up --build
```

| URL | What |
|---|---|
| http://localhost:3000 | UI (nginx serving `ui/`) |
| http://localhost:8001/docs | catalog API |
| http://localhost:8002/docs | propagation API |

Compose starts SQL Server, runs `db/init.sql` once (the `db-init` service creates both databases and the `catalog_user` and `propagation_user` logins, idempotently), then starts both services. The local passwords default to throwaway values. Override them with `MSSQL_SA_PASSWORD`, `CATALOG_DB_PASSWORD` and `PROPAGATION_DB_PASSWORD` in a `.env` file (git-ignored, see `.env.example`).

To see partial failure: `docker compose stop catalog`. Propagation keeps serving positions from its cached TLEs.

## Run a single service

Start only the database, then run one service from its folder:

```bash
docker compose up -d sqlserver db-init
cd services/catalog
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
DATABASE_URL="mssql://catalog_user:LocalOnly_Catalog_Pass1@localhost:1433/catalog" PORT=8001 python -m app.main
```

For propagation, use `services/propagation`, `propagation_user`/`LocalOnly_Prop_Pass1`, the `propagation` database and `PORT=8002`. It finds the catalog through `CATALOG_URL` (default `http://localhost:8001`).

## Configuration

Every variable each service reads is listed, with defaults, in `system.yaml`. The main ones:

| Variable | Service | Default | What it does |
|---|---|---|---|
| `PORT` | both | `8000` | Port the service listens on |
| `DATABASE_URL` | both | none (secret) | `mssql://user:password@host:1433/database` |
| `ALLOWED_ORIGINS` | both | `http://localhost:3000` | Origins allowed by CORS, comma separated |
| `GIT_SHA` | both | `dev` | Version reported by `/health` |
| `CATALOG_URL` | propagation | `http://localhost:8001` | Base URL of the catalog |
| `CATALOG_TIMEOUT_S` | propagation | `5` | Timeout for calls to the catalog |

The UI reads the two service URLs from `ui/config.js`. The committed file points at localhost; the CD job overwrites it with the deployed URLs.

## Tests and coverage

The tests need the SQL Server from compose, as in CI:

```bash
docker compose run --rm db-init
cd services/catalog          # or services/propagation
pip install -r requirements.txt
DATABASE_URL="mssql://catalog_user:LocalOnly_Catalog_Pass1@localhost:1433/catalog" \
  python -m pytest --cov=app --cov-report=term-missing --cov-fail-under=70
```

Propagation's `tests/test_seam.py` is the cross-seam integration test. `main.py` and `routes.py` are excluded from coverage in `.coveragerc`.

## CI/CD

One workflow, `.github/workflows/ci.yml`:

- **Every push and pull request:** lint (ruff), check each `openapi.json` matches the code, run tests with a 70% coverage gate against a SQL Server container (never Azure SQL), validate `system.yaml` and the OpenAPI files, and build both images.
- **Push to `main` only, after all of the above pass on the same commit:**
  - push the images to GHCR, tagged with the commit SHA
  - `infra/deploy.sh` creates or updates each container app with 0–1 replicas, the database connection string as a Container Apps secret, and CORS limited to the UI's origin
  - write `ui/config.js` with the deployed URLs and upload `ui/` to the `$web` container of the UI storage account
  - fail the run if either `/health` does not return `200` within 6 minutes; this allows for a cold start and the database resuming from pause

## Azure deployment

Everything is in resource group `rg-nmedic` (subscription "Azure for Students"), named with the prefix `nmedic-ieu2024`:

| Resource | Type | Region | Created by |
|---|---|---|---|
| `nmedic-ieu2024-sql` | SQL logical server (firewall: allow Azure services) | spaincentral | `infra/setup.sh` |
| `nmedic-ieu2024-catalog-db` | Azure SQL Database, serverless GP Gen5, 0.5–1 vCore, auto-pause 15 min, 2 GB, local backups | spaincentral | `infra/setup.sh` |
| `nmedic-ieu2024-propagation-db` | same | spaincentral | `infra/setup.sh` |
| `nmedic-ieu2024-env` | Container Apps environment, Consumption only | spaincentral | `infra/setup.sh` |
| `workspace-rgnmedicZfnA` | Log Analytics workspace that Azure creates with the environment; stores the containers' logs (free up to 5 GB/month) | spaincentral | Azure, with the environment |
| `nmedic-ieu2024-catalog` | Container App, 0–1 replicas | spaincentral | the pipeline |
| `nmedic-ieu2024-propagation` | Container App, 0–1 replicas | spaincentral | the pipeline |
| `nmedicieu2024ui` | Storage account (StorageV2, Standard LRS) serving the UI as a static website | spaincentral | `infra/setup.sh` |

The subscription only allows polandcentral, denmarkeast, switzerlandnorth, belgiumcentral and spaincentral, which is why everything is in spaincentral. The storage account name is the prefix without hyphens plus `ui`, because storage names cannot contain hyphens.

### Reproducing the initial setup

Run once from a machine with the Azure CLI (logged in) and Docker:

```bash
az account set --subscription "<subscription id>"
export SQL_ADMIN_PASSWORD="Ow_$(openssl rand -hex 16)_A1"
export CATALOG_DB_PASSWORD="Ow_$(openssl rand -hex 16)_A1"
export PROPAGATION_DB_PASSWORD="Ow_$(openssl rand -hex 16)_A1"
infra/setup.sh all
```

`infra/setup.sh` takes one step at a time too (`extension`, `sql-server`, `databases`, `db-users`, `verify-isolation`, `env`, `ui-storage`). The `db-users` step creates `catalog_user` and `propagation_user` as contained users, each `db_owner` of its own database only. `verify-isolation` proves each one cannot log in to the other database. Both steps open the firewall to your IP only while they run.

Save the passwords in a password manager; they are never written to the repo.

### GitHub Actions secrets

| Secret | Value |
|---|---|
| `AZURE_CREDENTIALS` | Service principal JSON with Contributor on `rg-nmedic` |
| `CATALOG_DB_PASSWORD` | Password of `catalog_user` |
| `PROPAGATION_DB_PASSWORD` | Password of `propagation_user` |
| `GHCR_PULL_TOKEN` | Only if the GHCR packages stay private: a token with `read:packages`, so Container Apps can pull images on a cold start |

## Limitations

- OrbitWatch shows where a satellite is, not when it will pass over a given place (pass prediction was deliberately left out, see ADR-5).
- Positions are only as accurate as the TLE, which is why TLEs are refreshed regularly.
- After 15 idle minutes a database pauses and the containers scale to zero, so the first request afterwards can take up to about a minute.
