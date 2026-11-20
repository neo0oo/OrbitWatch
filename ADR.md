# Architecture Decision Record

## 1. Backend Language & Framework Choice
**Date**: 2026-09-29

**Status**: Decided

**Context**: Needed something that could hit the Celestrak API, refresh that data on a timer without a separate worker process, and serve JSON to a Three.js frontend, and something I could actually explain at the comprehension check.

**Decision**: Python, since it's what I know best, plus FastAPI for the async support (so the TLE refresh doesn't block everything else) and free request validation.

**Alternatives considered**: Thought about JS/Node just to match the Three.js frontend, but that's picking a language I'm worse in for no reason. Flask was the real alternative to FastAPI but I'd just end up adding async and validation myself anyway.

**Consequences**: Less time fighting syntax, more time on the actual orbit math. Do need to be careful not to block the event loop with async, but the dependency list stays small (FastAPI, Uvicorn, Pydantic).


## 2. Scoping two feature domains to be independently modularizable
**Date** 2026/10/01

**Status** Decided

**Context** The assignment needs two feature domains that could later become separate services, so I had to decide where the line between them goes.

**Decision** Catalog handles satellites and TLE storage, and Propagation handles the orbit math as pure functions with no HTTP or database code.

**Alternatives Considered** One big module was faster to write, but the orbit math would be tangled up with database and network code, so I couldn't test or pull it out on its own. 

**Consequences** Propagation only depends on catalog to read a TLE, so splitting it into its own service later just means passing the TLE in instead. The cost is a bit more folder structure and one cross-domain read I have to keep an eye on.

## 3. SQLite Schema: Two Tables Linked by NORAD ID
**Date**: 2026-10-06

**Status**: Decided

**Context**: The catalog needs to store which satellites are tracked and their latest TLE, and propagation needs to read that TLE without owning any data of its own.

**Decision**: Two tables, satellites and tle_cache, both keyed on norad_id, so each satellite has at most one cached TLE that gets overwritten on refresh. tle_cache.norad_id is also a foreign key to satellites with ON DELETE CASCADE.

**Alternatives considered**: A separate auto-increment id plus a TLE history table with one row per fetch, but I only ever need the current TLE to get a position, so the history would be unused.

**Consequences**: Refreshing a TLE is a single upsert and removing a satellite cleans up its TLE automatically. The downside is that I can't look at old TLEs later.

## 4. Testing Approach
**Date**: 2026-10-11

**Status**: Decided

**Context**: The brief needs at least 70% coverage on the core logic of both domains, but my app depends on the network (Celestrak) and a database, which are awkward to test.

**Decision**: I unit-tested the pure logic directly (the orbit maths in engine.py checked against reference values, TLE parsing, the staleness check) and tested the catalog functions against a temporary SQLite file with Celestrak faked. Coverage excludes main.py and the routes files since they're thin glue.

**Alternatives considered**: Testing everything through the HTTP routes was an option, but it's slower and the logic is already covered more directly. Calling the real Celestrak in tests would make them fail whenever the internet or Celestrak is down.

**Consequences**: The tests run fast and offline and coverage is 82%. The routes, the frontend and the real fetch_tle network call have no automated tests, so I only checked those by hand.

## 5. Not Building Pass Prediction
**Date**: 2026-10-12

**Status**: Decided

**Context**: My original idea included telling a user when a satellite will next be overhead from their location, but I only had about two weeks and needed both domains, the tests and the docs finished first.

**Decision**: I didn't build pass prediction, so the propagation domain only covers a satellite's live position and its upcoming orbit path.

**Alternatives considered**: A basic version needs an observer's location, azimuth and elevation maths, and a search over time for when the satellite rises and sets. I rejected it because it would have taken time away from testing and documentation, which are worth more in this assignment.

**Consequences**: OrbitWatch shows where a satellite is but not when to look for it. It can be added later as new functions in engine.py that reuse the existing position code, without touching the catalog domain.

## 6. The split
**Date**: 2026-11-16

**Status**: Decided

**Context**: Assignment 2 needs one service per domain, each with its own container and database, talking over HTTP.

**Decision**: I kept the ADR-2 seam: catalog (satellites and TLEs) and propagation (orbit maths). The only call across it is propagation asking the catalog for a TLE (`GET /api/satellites/{id}/tle`), which replaced the in-process `get_tle()` call.

**Alternatives considered**: Letting the UI fetch the TLE and pass it to propagation. Rejected because the brief needs a server-side cross-seam flow and the browser shouldn't handle TLEs.

**Consequences**: ADR-2 held and nothing moved. Because the UI polls position every 2 s, propagation caches TLEs so it doesn't call the catalog every time (ADR-7).

## 7. Data and migrations
**Date**: 2026-11-17

**Status**: Decided

**Context**: SQLite became SQL Server with one database per service, so the foreign key from a cached TLE to `satellites` can't cross into propagation's database.

**Decision**: The catalog keeps `satellites` and `tle_cache` with the FK and cascade. Propagation has its own `tle_cache` with a plain `norad_id` and no FK: if the catalog returns 404, propagation deletes its copy, and cached TLEs expire after `TLE_CACHE_HOURS`. Schemas come from numbered SQL files run by my own runner, which records each file in `schema_migrations`.

**Alternatives considered**: Alembic. Rejected because it adds SQLAlchemy and a tool I'd have to learn, while my runner is about 30 lines I can explain.

**Consequences**: Propagation can serve a removed satellite's TLE for up to an hour. Recovery plan for a bad migration: it's forward-only, a failed migration rolls back because it commits together with its record, and the fix goes in a new migration, with Azure SQL's point-in-time restore if data was damaged.

## 8. Serverless hosting on Azure
**Date**: 2026-11-18

**Status**: Decided

**Context**: Both services, their two databases and the UI had to run on Azure in my own resource group (`rg-nmedic`, Spain Central because of the subscription's region policy), costing close to nothing while nobody is using it.

**Decision**: Each service is a Container App in one Consumption environment with 0.25 vCPU, 0.5 GiB, and between 0 and 1 replicas. Each service has its own serverless Azure SQL database (Gen5, 0.5–1 vCore, auto-pause after 15 minutes, 2 GB, locally redundant backups), both on one SQL server. The UI is static files on a Storage static website. Idle, I only pay for database storage and a few cents of blob storage, because the apps scale to zero, the databases pause, and compute is billed per second only while it runs. The catch is that the first request after a quiet period hits a cold start: the container has to start and the database has to resume, which can take up to a minute. `get_connection()` covers this by retrying 5 times with growing delays, the pipeline's health check waits up to 6 minutes, and the UI shows "Service unavailable, try again shortly" and keeps polling. Migrations run at startup, which is safe because there is only ever one replica, and each migration is additive (like `003` adding a column with a default) so the old revision keeps working during the switch.

**Alternatives considered**: An always-on App Service plan and a provisioned database. Rejected because they cost money every hour even with zero users, and a student project is idle most of the time.

**Consequences**: Almost free, but slow on the first request. At 100x traffic I would set the minimum replicas to 1 or more to remove cold starts and raise the maximum, give the database a higher vCore limit or a provisioned tier with auto-pause off, and move migrations out of startup into a separate pipeline step. With several replicas, two of them could try to apply the same migration at the same time.

## 9. Pipeline and testing
**Date**: 2026-11-19

**Status**: Decided

**Context**: Assignment 2 deploys only through the pipeline, so CI is the only thing standing between a bad commit and the live site.

**Decision**: Every push and PR runs, per service: ruff lint, a check that `openapi.json` still matches the code, and the tests against a real SQL Server started with `docker compose run db-init` (throwaway passwords, masked in the logs), with a 70% coverage gate. A second job validates `system.yaml` against `system.schema.json` and both OpenAPI files, and a third builds both images. Deploy runs only on a push to `main` and only if all of those passed on the same commit, and it ends with a health check on both services. `test_seam.py` tests the cross-seam flow inside propagation: it calls the real routes with FastAPI's `TestClient` and replaces `requests.get` in `catalog_client` with a fake, so I can make the catalog answer with a TLE, a 404, a 500, a timeout or a connection error, and check that propagation returns 200, 404 or 503, and serves its cached TLE marked `stale_tle` when the catalog is down.

**Alternatives considered**: Testing against SQLite in CI would be faster, but the SQL is SQL Server-specific (`MERGE`, `IF NOT EXISTS`), so it wouldn't test the real queries. Calling a real catalog container from the seam test was rejected because faking it lets me produce failures, like timeouts, on purpose.

**Consequences**: I deliberately don't test the UI, the real Celestrak call (`fetch_tle`), the catalog's routes (thin glue, excluded from coverage), `deploy.sh` or Azure itself. The real HTTP call between the two containers is only checked by hand with compose and by the health check after deploy.

## 10. Not building event-based cache invalidation
**Date**: 2026-11-20   

**Status**: Decided

**Context**: Since the split, propagation keeps its own copy of each TLE (ADR-7). When a satellite is removed from the catalog, propagation doesn't hear about it straight away.

**Decision**: I didn't build a way for the catalog to tell propagation about changes, such as a "satellite removed" event on Azure Service Bus. Propagation finds out on its own: its cached TLE expires after `TLE_CACHE_HOURS`, and if the catalog then answers 404, it deletes its copy.

**Alternatives considered**: A message queue or a webhook from the catalog to propagation. Rejected because it adds another Azure resource, retry and ordering logic, and a second way for the services to depend on each other, all to fix a delay of at most an hour on a hobby tracker.

**Consequences**: A removed satellite can still be tracked for up to an hour, or longer while the catalog is down. It would be worth building if more services needed to react to catalog changes, if TLE updates had to reach users within seconds, or if traffic grew enough that polling the catalog became the bottleneck.
