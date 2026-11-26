# Implementation: TASK-002

<!-- Owner: DEVELOPER. Be honest: QA won't take your word for it anyway. -->

## What I built

Real implementation (no stubs): `DELETE /repositories/{id}` as designed in `architecture.md`.

- `service.remove_repository(store, username, repository_id)`: a missing or empty username gives 401 first; then `_get_owned` gives 401 (unknown user), 404 (missing or already removed) or 403 (not the owner); only after all checks pass does it delete the entry from `store.repositories` and `store.analyses`. `store.next_id` is untouched, so ids are not reused.
- `server.py`: handler `DELETE /repositories/(\d+)` passes the raw `X-User` header (no `alice` default) and returns `204` with no body.
- `docs/api.md`: new row in "Endpoints today".
- No change needed to list/get/analysis/scan (already 404 for a missing id) or to the duplicate-URL check in `register_repository` (only looks at stored repositories), which covers AC2 and AC5.

## Files changed

- `app/service.py`
- `app/server.py`
- `docs/api.md`
- `tests/test_service.py` (7 new tests)
- `tests/test_api.py` (6 new tests)

## Tests

Command: `python -m unittest discover -s tests -t .`
Result: `Ran 61 tests ... OK` (48 existing + 13 new). The new tests cover AC1 to AC6, plus `DELETE /repositories` (collection) still answering 405.

## Known limits

- In-memory only: a restart brings back the seed data, including removed seed repositories.
- Removal is permanent: no undo, recycle bin or audit log (Product Owner decision).
- Two-dict delete is safe only because `HTTPServer` handles one request at a time; a threaded server would need a lock.
- `X-User` is trusted as identity, as elsewhere in the app.
- Not tested by me: a request body on DELETE beyond the existing automatic 400 for invalid JSON (body is otherwise ignored).

## Attempts

- Attempt 1: first implementation of DELETE /repositories/{id} per architecture.md.
