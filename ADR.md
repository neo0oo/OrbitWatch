# Architecture Decision Record

## 1. Backend Language & Framework Choice
**Date**: 2026-09-29

**Status**: Decided

**Context**: Needed something that could hit the Celestrak API, refresh that data on a timer without a separate worker process, and serve JSON to a Three.js frontend, and something I could actually explain at the comprehension check.

**Decision**: Python, since it's what I know best, plus FastAPI for the async support (so the TLE refresh doesn't block everything else) and free request validation.

**Alternatives considered**: Thought about JS/Node just to match the Three.js frontend, but that's picking a language I'm worse in for no reason. Flask was the real alternative to FastAPI but I'd just end up adding async and validation myself anyway.

**Consequences**: Less time fighting syntax, more time on the actual orbit math. Do need to be careful not to block the event loop with async, but the dependency list stays small (FastAPI, Uvicorn, Pydantic).