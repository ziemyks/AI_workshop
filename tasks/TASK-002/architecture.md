# Architecture: TASK-002

<!-- Owner: ARCHITECT. Security notes: SECURITY. A few bullets, not a design document. -->

## Approach

- New endpoint `DELETE /repositories/{id}` with a thin handler in `app/server.py` and the logic in a new `service.remove_repository(store, username, repository_id)`.
- Like `POST /repositories`, the handler passes the raw `req.user_header` (no `alice` default), as the Product Owner decided. The service refuses a missing or empty header with 401 before anything else (AC4).
- Reuse `_get_owned` for every other check, in the existing order: unknown user 401, missing repository 404, not the owner 403 (AC2, AC3, AC4). Nothing is removed until every check has passed.
- On success, delete the entry from `store.repositories` and from `store.analyses` (AC1, AC2, AC6). Don't touch `store.next_id`, so ids are never reused within a run (assumption in `requirements.md`).
- No other code changes are needed: `list_repositories`, `get_repository`, `get_analysis` and `scan_repository` already answer 404 for a missing id, and the duplicate-URL check in `register_repository` only looks at repositories still in the store, so the URL is free again (AC2, AC5).

## Parts that change

- `app/service.py`: new function `remove_repository(store, username, repository_id)`. No new error class.
- `app/server.py`: new handler `@route("DELETE", r"/repositories/(\d+)")` that calls the service with `req.user_header` and `int(repository_id)` and returns `204, None`. `do_DELETE` and the 405 handling already exist.
- `tests/test_service.py`, `tests/test_api.py`: tests for every rule below.
- `docs/api.md`: add the new row to "Endpoints today".

## Interface

- `DELETE /repositories/{id}`, caller from `X-User` (required here, no `alice` default)
  - Who may call: only the repository's owner, checked with `require_user` and `_get_owned`. Error messages name only the requested id, never the owner.
  - Input: `id` (path, digits only, from the route regex). Any request body is ignored. A body that is not valid JSON still gets the existing automatic 400.
  - **204:** no body. The repository and its analysis are gone (AC1).
  - **401** `Unauthorized`: no `X-User` header or an empty one (`"The X-User header is required"`, the same message as registering), or an unknown user. Checked first, so nothing is removed (AC4).
  - **404** `NotFound`: no repository with that id, including one already removed. Same message as for an id that never existed: `"Repository {id} not found"` (AC2).
  - **403** `Forbidden`: the repository belongs to another user. Same message as opening it today. The repository and its analysis stay unchanged (AC3).
- `DELETE /repositories` (the collection) keeps answering 405, as `tests/test_qa_task001.py` expects. Removing several at once is out of scope.

| AC | Covered by |
|---|---|
| AC1 | 204; entry deleted from `store.repositories`, so `GET /repositories` no longer lists it |
| AC2 | Entry deleted from `store.repositories` and `store.analyses`; existing `_get_owned` gives 404 on GET, analysis, scan and a second DELETE |
| AC3 | `_get_owned` raises 403 before any write |
| AC4 | Missing or empty `X-User` gives 401 before `_get_owned`; unknown user gives 401 inside `_get_owned` |
| AC5 | Duplicate check only sees repositories still in the store; new id from `store.next_id`; fresh analysis from `register_repository` |
| AC6 | Only the one id is deleted from each dict; nothing else is touched |

## Risks and limits

- Data is in memory only. A restart brings back the seed data, including any removed seed repositories (assumption in `requirements.md`).
- Removal is permanent, with no undo, recycle bin or audit log (Product Owner decision, out of scope).
- Ids are not reused within one run. After a restart the counter starts again from the seed data, but all earlier data is gone by then too.
- Deleting from two dicts is safe only because `HTTPServer` handles one request at a time. A threaded server would need a lock, as noted in TASK-001.
- `X-User` is trusted as the caller's identity, as everywhere else in the app. Real authentication is out of scope.

## Security notes

<!-- Filled in by SECURITY when a risk is reported: what was found, where, and what must change. -->
