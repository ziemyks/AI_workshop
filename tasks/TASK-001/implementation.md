# Implementation: TASK-001

## What I built

Real implementation of `POST /repositories`, following architecture.md: check order 401 -> 400 -> 409, nothing written before all checks pass, new id from `store.next_id`, analysis created in the same call, 201 with the full repository. Missing or empty `X-User` gives 401 on this endpoint only; other endpoints keep the `alice` default.

## Files changed

- `app/service.py`: `Conflict` (409), `register_repository`, helpers `_text_field`, `_valid_url` (uses `urlsplit`; `ValueError` becomes 400).
- `app/server.py`: `Request.user_header` (raw `X-User`, `None` when absent); handler `POST /repositories`.
- `tests/test_api.py`: 6 tests for AC1-AC6 (create + access, optional description, 12 invalid bodies, inclusive limits 100/500, duplicate URL across users and seed data, missing/unknown user).
- `docs/api.md`: new row in "Endpoints today".

## Tests

`python3 -m unittest`: OK, all tests pass (run in the Developer's terminal; the agent sandbox cannot bind a port for the API tests).

## Known limits

- In memory only; lost on restart (as before).
- Duplicate check and id counter rely on the single-threaded `HTTPServer` (architecture risk).
- URL match is exact text after trimming; no URL length limit (none decided).

## Attempts

- Attempt 1: first implementation.
