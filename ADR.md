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